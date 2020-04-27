import copy
import logging
import os
import re
import time
from collections import OrderedDict
from typing import List

from lastfmcache import LastfmCache
from ordered_set import OrderedSet

from metafix.Release import Release
from metafix.Violation import Violation
from metafix.constants import ViolationType
from metafix.functions import normalize_str, flatten_artists, normalize_track_title, split_release_title, \
    tag_filter_all, extract_track_disc, unique


class ReleaseValidator:

    def __init__(self, lastfm: LastfmCache = None):
        self.lastfm = lastfm

    def validate(self, release: Release) -> List[Violation]:
        violations = OrderedSet()

        # leading/trailing whitespace
        for filename, track in release.tracks.items():
            if track.artists != track.strip_whitespace_artists():
                violations.add(
                    Violation(ViolationType.ARTIST_WHITESPACE,
                              "File '{0}' has leading/trailing whitespace in its Artist(s)".format(filename)))

        for filename, track in release.tracks.items():
            if track.release_artists != track.strip_whitespace_release_artists():
                violations.add(
                    Violation(ViolationType.RELEASE_ARTIST_WHITESPACE,
                              "File '{0}' has leading/trailing whitespace in its Album/Release Artist(s)"
                              .format(filename)))

        for filename, track in release.tracks.items():
            if track.date != track.strip_whitespace_date():
                violations.add(
                    Violation(ViolationType.DATE_WHITESPACE,
                              "File '{0}' has leading/trailing whitespace in its Year/Date".format(filename)))

        for filename, track in release.tracks.items():
            if track.release_title != track.strip_whitespace_release_title():
                violations.add(
                    Violation(ViolationType.RELEASE_TITLE_WHITESPACE,
                              "File '{0}' has leading/trailing whitespace in its Album/Release Title"
                              .format(filename)))

        for filename, track in release.tracks.items():
            if track.track_title != track.strip_whitespace_track_title():
                violations.add(
                    Violation(ViolationType.TRACK_TITLE_WHITESPACE,
                              "File '{0}' has leading/trailing whitespace in its Track Title"
                              .format(filename)))

        for filename, track in release.tracks.items():
            if track.genres != track.strip_whitespace_genres():
                violations.add(
                    Violation(ViolationType.GENRE_WHITESPACE,
                              "File '{0}' has leading/trailing whitespace in its Genre(s)"
                              .format(filename)))

        # release date
        if not release.validate_release_date():
            violations.add(
                Violation(ViolationType.DATE_INCONSISTENT, "Release contains blank or inconsistent 'Date' tags"))

        # artists
        if release.blank_artists():
            violations.add(
                Violation(ViolationType.ARTIST_BLANK,
                          "Release contains {0} tracks with missing 'Artist' tags".format(release.blank_artists())))

        # track titles
        if release.blank_track_titles():
            violations.add(
                Violation(ViolationType.TRACK_TITLE_BLANK, "Release contains {0} tracks with missing 'Track Title' tags"
                          .format(release.blank_track_titles())))

        # release artist
        release_artists = release.validate_release_artists()
        if not release_artists:
            violations.add(
                Violation(ViolationType.RELEASE_ARTIST_INCONSISTENT,
                          "Release contains blank or inconsistent 'Album/Release Artist' tags"))

        # if the lastfmcache is present, validate the release artist
        validated_release_artists = release_artists
        if self.lastfm and len(release_artists) == 1:
            validated_release_artists = []
            for artist in release_artists:
                try:
                    validated_release_artist = self.lastfm.get_artist(artist.strip()).artist_name

                    if validated_release_artist != artist:
                        violations.add(
                            Violation(ViolationType.RELEASE_ARTIST_SPELLING,
                                      "Incorrectly spelled Album/Release Artist '{0}' (should be '{1}')".format(
                                          artist, validated_release_artist)))

                    validated_release_artists.append(validated_release_artist)
                except LastfmCache.ArtistNotFoundError:
                    violations.add(
                        Violation(ViolationType.ARTIST_LOOKUP, "Lookup failed of release artist '{release_artist}'"
                                  .format(release_artist=artist.strip())))

        # release title
        release_title = release.validate_release_title()
        if not release_title:
            violations.add(Violation(ViolationType.RELEASE_TITLE_INCONSISTENT,
                                     "Release contains blank or inconsistent 'Album/Release Title' tags"))

        # lastfm artist validations
        if self.lastfm and release_title and len(validated_release_artists):
            # extract (edition info) from release titles
            release_title, _ = split_release_title(normalize_str(release_title))

            flattened_artist = flatten_artists(validated_release_artists)
            lastfm_release = None

            try:
                lastfm_release = self.lastfm.get_release(flattened_artist, release_title)
            except LastfmCache.ReleaseNotFoundError as e:
                logging.getLogger(__name__).error(e)

            if lastfm_release:
                # release title
                if lastfm_release.release_name != release_title \
                     and lastfm_release.release_name.lower() != release_title.lower() \
                     and not any(x.isupper() for x in release_title):
                    violations.add(
                        Violation(ViolationType.RELEASE_TITLE_SPELLING,
                                  "Incorrectly spelled Album/Release name '{0}' (should be '{1}')"
                                  .format(release_title, lastfm_release.release_name)))

                # dates
                if lastfm_release.release_date:
                    date = next(iter(release.tracks.values())).date
                    if lastfm_release.release_date != date and \
                            (not date or len(lastfm_release.release_date) >= len(date)):
                        violations.add(
                            Violation(ViolationType.DATE_INCORRECT, "Incorrect Release Date '{0}' (should be '{1}')"
                                      .format(date, lastfm_release.release_date)))

                # tags/genres (only fail if 0-1 genres - i.e. lastfm tags have never been applied)
                release_genres = release.validate_genres()
                lastfm_tags = self.__get_lastfm_tags(release_title, validated_release_artists)
                if len(release_genres) < 2 <= len(lastfm_tags):
                    violations.add(
                        Violation(ViolationType.BAD_GENRES, "Bad release genres: [{0}] (should be [{1}])"
                                  .format(", ".join(release_genres), ", ".join(lastfm_tags))))

                # match and validate track titles (intersection only)
                for track in release.tracks.values():
                    if track.track_number in lastfm_release.tracks:
                        lastfm_title = normalize_track_title(track.track_title)
                        if not track.track_title or track.track_title.lower() != lastfm_title.lower():
                            violations.add(
                                Violation(ViolationType.INCORRECT_TRACK_TITLE,
                                          "Incorrect track title '{0}' should be: '{1}'".format(track.track_title,
                                                                                                lastfm_title)))

            # track artists
            for track in release.tracks.values():
                for artist in track.artists:
                    try:
                        validated_artist = self.lastfm.get_artist(normalize_str(artist)).artist_name
                        if validated_artist != artist:
                            violations.add(
                                Violation(ViolationType.TRACK_ARTIST_SPELLING,
                                          "Incorrectly spelled Track Artist '{0}' (should be '{1}')"
                                          .format(artist, validated_artist)))
                    except LastfmCache.ArtistNotFoundError:  # as e:
                        pass
                        # violations.add(str(e))

            # release artists
            for track in release.tracks.values():
                for artist in track.release_artists:
                    try:
                        validated_artist = self.lastfm.get_artist(normalize_str(artist)).artist_name
                        if validated_artist != artist:
                            violations.add(
                                Violation(ViolationType.RELEASE_ARTIST_SPELLING,
                                          "Incorrectly spelled Release Artist '{0}' (should be '{1}')"
                                          .format(artist, validated_artist)))
                    except LastfmCache.ArtistNotFoundError:  # as e:
                        pass
                        # violations.add(str(e))

        validated_track_numbers = release.validate_track_numbers()
        if validated_track_numbers:
            flattened_track_nums = []
            for disc in validated_track_numbers:
                flattened_track_nums.append(
                    "\nDisc " + str(disc) + ": " + ",".join(str(i) for i in validated_track_numbers[disc]))
            violations.add(
                Violation(ViolationType.MISSING_TRACKS,
                          "Release does not have a full set of tracks:{0}".format("".join(flattened_track_nums))))

        validated_total_tracks = release.validate_total_tracks()
        for disc in validated_total_tracks:
            violations.add(
                Violation(ViolationType.TOTAL_TRACKS_INCONSISTENT,
                          "Release disc {0} has blank, inconsistent or incorrect 'Total Tracks' tags".format(disc)))

        # disc number
        validated_disc_numbers = release.validate_disc_numbers()
        if validated_disc_numbers:
            violations.add(
                Violation(ViolationType.MISSING_DISCS, "Release does not have a full set of discs: {0}"
                          .format(", ".join(str(i) for i in validated_disc_numbers))))

        # total discs
        if not release.validate_total_discs():
            violations.add(
                Violation(ViolationType.TOTAL_DISCS_INCONSISTENT, "Release has incorrect 'Total Discs' tags"))

        # file type
        if len(release.get_tag_types()) != 1:
            violations.add(
                Violation(ViolationType.TAG_TYPES_INCONSISTENT, "Release has inconsistent tag types: {0}"
                          .format(", ".join([str(x) for x in release.get_tag_types()]))))

        # bitrate - CBR/VBR/Vx/APS/APE
        if len(release.get_codecs()) != 1:
            violations.add(
                Violation(ViolationType.CODECS_INCONSISTENT,
                          "Release has inconsistent codecs: [{0}]".format(", ".join(release.get_codecs()))))

        if len(unique([int(x / 1000) for x in release.get_cbr_bitrates()])) > 1:
            violations.add(
                Violation(ViolationType.CBR_INCONSISTENT, "Release has inconsistent CBR bitrates: {0}"
                          .format(", ".join([str(x) for x in release.get_cbr_bitrates()]))))

        # track titles
        for filename in release.tracks:
            correct_filename = release.tracks[filename].get_filename(release.is_va())
            if correct_filename and filename != correct_filename:
                violations.add(
                    Violation(ViolationType.FILENAME,
                              "Invalid filename: {0} - should be '{1}'".format(filename, correct_filename)))

        release.num_violations = len(violations)

        return list(violations)

    def fix(self, release_in: Release) -> Release:
        release = copy.deepcopy(release_in)

        # fix leading/trailing whitespace
        for track in release.tracks.values():
            track.artists = track.strip_whitespace_artists()
            track.release_artists = track.strip_whitespace_release_artists()
            track.date = track.strip_whitespace_date()
            track.release_title = track.strip_whitespace_release_title()
            track.track_title = track.strip_whitespace_track_title()
            track.genres = track.strip_whitespace_genres()

        # extract missing track and disc numbers from filenames
        validated_track_numbers = release.validate_track_numbers()
        validated_disc_numbers = release.validate_disc_numbers()
        for filename in release.tracks:
            track_num, disc_num = extract_track_disc(filename)
            if (not release.tracks[filename].track_number and track_num) or validated_track_numbers:
                release.tracks[filename].track_number = track_num
                if validated_track_numbers and disc_num:
                    release.tracks[filename].disc_number = disc_num
            if (not release.tracks[filename].disc_number and disc_num) or validated_disc_numbers:
                release.tracks[filename].disc_number = disc_num

        # extract missing disc numbers from folder name
        for filename in release.tracks:
            if not release.tracks[filename].disc_number:
                match = re.findall(r'(?i)(disc|disk|cd) ?(\d{1,2})', os.path.split(filename)[0])
                if match:
                    release.tracks[filename].disc_number = int(match[0][1])

        # normalize track titles
        for track in release.tracks.values():
            if track.track_title:
                normalized_title = normalize_track_title(track.track_title)
                if track.track_title.lower() != normalized_title.lower():
                        track.track_title = normalized_title

        # release artists
        release_artists = release.validate_release_artists()
        if not release_artists:
            release_artists = release.extract_release_artist()

        validated_release_artists = []
        if self.lastfm and release_artists:
            for artist in release_artists:
                while True:
                    try:
                        validated_release_artists.append(self.lastfm.get_artist(artist).artist_name)
                        break
                    except LastfmCache.ArtistNotFoundError:
                        break
                    except LastfmCache.ConnectionError:
                        logging.getLogger(__name__).error("Connection error while retrieving artist, retrying...")
                        time.sleep(1)

            # update release artists for all tracks, if all were validated
            if len(validated_release_artists) == len(release_artists):
                for track in release.tracks.values():
                    track.release_artists = validated_release_artists

        # release title
        release_title = release.validate_release_title()
        for track in release.tracks.values():
            if track.release_title != release_title:
                track.release_title = release_title

        # lastfm validations
        if self.lastfm and len(validated_release_artists) and release_title:
            # extract (edition info) from release titles
            release_title, release_edition = split_release_title(normalize_str(release_title))

            flattened_artist = flatten_artists(validated_release_artists)

            lastfm_release = None

            while True:
                try:
                    lastfm_release = self.lastfm.get_release(flattened_artist, release_title)
                    break
                except LastfmCache.ConnectionError:
                    logging.getLogger(__name__).error("Connection error while retrieving release, retrying...")
                    time.sleep(1)
                except LastfmCache.ReleaseNotFoundError as e:
                    logging.getLogger(__name__).error(e)
                    break
                except LastfmCache.LastfmCacheError as e:
                    logging.getLogger(__name__).error(e)

            if lastfm_release:
                # release title
                if lastfm_release.release_name != release_title \
                        and lastfm_release.release_name.lower() == release_title.lower() \
                        and not any(x.isupper() for x in release_title):
                    release_title_full = lastfm_release.release_name
                    if release_edition:
                        release_title_full = "{0} {1}".format(lastfm_release.release_name, release_edition)

                    for track in release.tracks.values():
                        track.release_title = release_title_full

                # dates
                if lastfm_release.release_date:
                    for track in release.tracks.values():
                        if lastfm_release.release_date != track.date \
                                and (not track.date or len(lastfm_release.release_date) >= len(track.date)):
                            track.date = lastfm_release.release_date

                # tags/genres (only fail if 0-1 genres - i.e. lastfm tags have never been applied)
                release_genres = release.validate_genres()
                lastfm_tags = self.__get_lastfm_tags(release_title, validated_release_artists)
                if len(release_genres) < 2 <= len(lastfm_tags):
                    for track in release.tracks.values():
                        track.genres = lastfm_tags

                # fill missing track numbers from lastfm
                for track in release.tracks.values():
                    if track.track_number:
                        continue

                    track_num_matches = [x for x in lastfm_release.tracks
                                         if normalize_track_title(lastfm_release.tracks[x].track_name).lower() ==
                                         normalize_track_title(track.track_title).lower()]
                    if track_num_matches and len(track_num_matches) == 1:
                        track.track_number = track_num_matches[0]

                # match and validate track titles (intersection only)
                track_numbers_validated =  not release.validate_track_numbers()
                for track in release.tracks.values():
                    if track.track_number in lastfm_release.tracks:
                        lastfm_title = normalize_track_title(lastfm_release.tracks[track.track_number].track_name)

                        # if the track title is missing, or if it is lowercase and there is a case insensitive match
                        if (not track.track_title and track_numbers_validated) or \
                                (track.track_title.islower() and track.track_title.lower() == lastfm_title.lower()):
                            track.track_title = lastfm_title

                        # case insensitive match, tag version has no capital letters
                        elif track.track_title.lower() == lastfm_title.lower() \
                            and track.track_title.lower() == track.track_title:
                            track.track_title = lastfm_title

            # track artists
            for track in release.tracks.values():
                validated_artists = []
                for artist in track.artists:
                    while True:
                        try:
                            validated_artists.append(self.lastfm.get_artist(normalize_str(artist)).artist_name)
                            break
                        except LastfmCache.ConnectionError:
                            logging.getLogger(__name__).error(
                                "Connection error while retrieving artist, retrying...")
                            time.sleep(1)
                        except LastfmCache.ArtistNotFoundError:
                            break
                        except AttributeError:  # TODO remove when pylast is fixed
                            break

                if len(validated_artists) == len(track.artists):
                    track.artists = validated_artists

            # release artists
            for track in release.tracks.values():
                validated_artists = []
                for artist in track.release_artists:
                    while True:
                        try:
                            validated_artists.append(self.lastfm.get_artist(normalize_str(artist)).artist_name)
                            break
                        except LastfmCache.ConnectionError:
                            logging.getLogger(__name__).error(
                                "Connection error while retrieving artist, retrying...")
                            time.sleep(1)
                        except LastfmCache.ArtistNotFoundError:
                            break
                        except AttributeError:  # TODO remove when pylast is fixed
                            break

                if len(validated_artists) == len(track.artists):
                    track.release_artists = validated_artists

        # reorder track numbers if they are sequential across discs
        release.resequence_track_numbers()

        # fill in missing total track numbers
        validated_disc_numbers = release.get_total_tracks()
        for track in release.tracks.values():
            disc_number = track.disc_number if track.disc_number else 1
            if validated_disc_numbers.get(disc_number):
                track.total_tracks = validated_disc_numbers[disc_number]

        # if disc number is missing and there appears to only be one disc, set to 1
        if not release.validate_total_discs() and len(validated_disc_numbers) == 1:
            for track in release.tracks.values():
                track.disc_number = 1

        # fill in missing total disc numbers
        if not release.validate_total_discs():
            total_discs = release.get_total_discs()
            if total_discs:
                for track in release.tracks.values():
                    track.total_discs = total_discs

        return release

    # tags/genres
    def __get_lastfm_tags(self, release_title: str, release_artists: List[str]):
        flattened_artist = flatten_artists(release_artists)
        lastfm_release = self.lastfm.get_release(flattened_artist, release_title)

        lastfm_tags = [x for x in tag_filter_all(lastfm_release.tags, release_artists + [release_title], True)]
        if not lastfm_tags:
            filtered_artists = [x for x in release_artists
                                if x.lower() not in ["various artist", "various artists", "va"]]
            artists_tags = [self.lastfm.get_artist(artist).tags for artist in filtered_artists]
            weighted_tags = OrderedDict()
            for artist_tags in artists_tags:
                for tag in artist_tags:
                    if tag not in weighted_tags or (tag in weighted_tags and weighted_tags[tag] < artist_tags[tag]):
                        weighted_tags[tag] = artist_tags[tag]
            lastfm_tags = [x for x in tag_filter_all(weighted_tags, filtered_artists + [release_title], True)]

        return [x for x in lastfm_tags]

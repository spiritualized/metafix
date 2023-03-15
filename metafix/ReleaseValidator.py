import copy
import logging
import os
import re
import time
from collections import OrderedDict
from typing import List

from lastfmcache import LastfmCache
from ordered_set import OrderedSet

from lastfmcache.lastfmcache import LastfmRelease
from metafix.Release import Release
from metafix.Violation import Violation
from metafix.constants import ViolationType, upgrade_message, ReleaseSource, ReleaseCategory
from metafix.functions import flatten_artists, normalize_track_title, split_release_title, tag_filter_all, \
    extract_track_disc, unique, extract_release_year, normalize_artist_name, normalize_release_title


class ReleaseValidator:

    def __init__(self, lastfm: LastfmCache = None):
        self.lastfm = lastfm
        self.forbidden_comment_substrings = set()
        self.lastfm_track_title_validation = True

    def disable_lastfm_track_title_validation(self) -> None:
        self.lastfm_track_title_validation = False

    def add_forbidden_comment_substring(self, forbidden_comment_substring: str) -> None:
        self.forbidden_comment_substrings.add(forbidden_comment_substring.lower())

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

        bracket_pairs = [["[", "]"], ["(", ")"], ["{", "}"]]

        if release_title:
            # check if "[Source]" is contained in the release title
            for source in ReleaseSource:
                for brackets in bracket_pairs:
                    curr_source = "{0}{1}{2}".format(brackets[0], source.value, brackets[1])
                    if curr_source.lower() in release_title.lower():
                        violations.add(Violation(ViolationType.RELEASE_TITLE_SOURCE,
                                                 "Release title contains source {0}".format(curr_source)))

            # check if the release title ends with a space and a source name, without brackets
            for source in [x for x in ReleaseSource]:
                if release_title.lower().endswith(" {0}".format(source.value.lower())):
                    violations.add(Violation(ViolationType.RELEASE_TITLE_SOURCE,
                                             "Release title ends with source {0}".format(source.value)))

            # check if "[Category]" is contained in the release title
            for category in ReleaseCategory:
                for brackets in bracket_pairs:
                    curr_category = "{0}{1}{2}".format(brackets[0], category.value, brackets[1])
                    if curr_category.lower() in release_title.lower():
                        violations.add(Violation(ViolationType.RELEASE_TITLE_CATEGORY,
                                                 "Release title contains category {0}".format(curr_category)))

            # check if the release title ends with a space and a category name, without brackets (except Album)
            for category in [x for x in ReleaseCategory if x is not ReleaseCategory.ALBUM]:
                if release_title.lower().endswith(" {0}".format(category.value.lower())):
                    violations.add(Violation(ViolationType.RELEASE_TITLE_CATEGORY,
                                             "Release title ends with category {0}".format(category.value)))

        # lastfm artist validations
        if self.lastfm and release_title and len(validated_release_artists):
            # extract (edition info) from release titles
            release_title, _ = split_release_title(normalize_release_title(release_title))

            flattened_artist = flatten_artists(validated_release_artists)
            lastfm_release = None

            try:
                lastfm_release = self.lastfm.get_release(flattened_artist, release_title)
            except LastfmCache.ReleaseNotFoundError as e:
                logging.getLogger(__name__).error(e)

            if lastfm_release:
                # release title
                if lastfm_release.release_name != release_title and \
                        ReleaseValidator.__lastfm_can_fix_release_title(release_title, lastfm_release.release_name):
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
                    min_tags = min(2, len(lastfm_tags))
                    violations.add(
                        Violation(ViolationType.BAD_GENRES,
                                  "Bad release genres: [{0}] (should be [{1}]). Add at least {2}"
                                  .format(", ".join(release_genres), ", ".join(lastfm_tags), min_tags)))

                # match and validate track titles (intersection only)
                if self.lastfm_track_title_validation:
                    for track in release.tracks.values():
                        if track.track_number in lastfm_release.tracks:
                            lastfm_title = normalize_track_title(lastfm_release.tracks[track.track_number].track_name)
                            if not track.track_title or track.track_title.lower() != lastfm_title.lower():
                                violations.add(
                                    Violation(ViolationType.INCORRECT_TRACK_TITLE,
                                              "Incorrect track title '{0}' should be: '{1}'".format(track.track_title,
                                                                                                    lastfm_title)))

            # track artists
            for track in release.tracks.values():
                for artist in track.artists:
                    while True:
                        try:
                            validated_artist = self.lastfm.get_artist(normalize_artist_name(artist)).artist_name
                            if validated_artist != artist:
                                violations.add(
                                    Violation(ViolationType.TRACK_ARTIST_SPELLING,
                                              "Incorrectly spelled Track Artist '{0}' (should be '{1}')"
                                              .format(artist, validated_artist)))
                            break
                        except LastfmCache.ArtistNotFoundError:  # as e:
                            # violations.add(str(e))
                            break
                        except LastfmCache.LastfmCacheError:
                            time.sleep(1)

            # release artists
            for track in release.tracks.values():
                for artist in track.release_artists:
                    while True:
                        try:
                            validated_artist = self.lastfm.get_artist(normalize_artist_name(artist)).artist_name
                            if validated_artist != artist:
                                violations.add(
                                    Violation(ViolationType.RELEASE_ARTIST_SPELLING,
                                              "Incorrectly spelled Release Artist '{0}' (should be '{1}')"
                                              .format(artist, validated_artist)))
                            break
                        except LastfmCache.ArtistNotFoundError:  # as e:
                            # violations.add(str(e))
                            break
                        except LastfmCache.LastfmCacheError:
                            time.sleep(1)

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

        # forbidden comment substrings
        for track in release.tracks.values():
            if not track.comment:
                continue
            for substr in self.forbidden_comment_substrings:
                if substr in track.comment.lower():
                    violations.add(
                        Violation(ViolationType.COMMENT_SUBSTRING,
                                  "Invalid comment: contains forbidden substring '{0}'".format(substr)))

        release.num_violations = len(violations)

        return list(violations)

    def fix(self, release_in: Release, folder_name: str) -> Release:
        release = copy.deepcopy(release_in)

        # fix leading/trailing whitespace
        self.__fix_whitespace(release)

        # extract missing track and disc numbers from filenames
        self.__extract_track_disc_numbers_from_filenames(release)

        # extract missing year from folder name
        self.__extract_year_from_folder_name(release, folder_name)

        # extract missing disc numbers from folder name
        self.__extract_disc_numbers_from_folder_name(release)

        # normalize track titles
        self.__normalize_track_titles(release)

        # normalize release artists
        release_artists = self.__normalize_release_artists(release)

        # fix release artists using last.fm
        validated_release_artists = self.__lastfm_release_artists(release, release_artists)

        # fix release title
        self.__fix_release_title(release)

        # lastfm fixes
        self.__lastfm_fixes(release, validated_release_artists)

        # reorder track numbers if they are sequential across discs
        release.resequence_track_numbers()

        # fix missing total track numbers
        self.__fix_missing_total_tracks(release)

        # if disc number is missing and there appears to only be one disc, set to 1
        self.__disc_number_best_guess(release)

        # fix missing total disc numbers
        self.__fix_missing_total_discs(release)
        
        # fix forbidden comment substrings
        self.__fix_forbidden_comment_substrings(release)

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

    @staticmethod
    def __fix_whitespace(release: Release) -> None:
        """fix leading/trailing whitespace"""
        for track in release.tracks.values():
            track.artists = track.strip_whitespace_artists()
            track.release_artists = track.strip_whitespace_release_artists()
            track.date = track.strip_whitespace_date()
            track.release_title = track.strip_whitespace_release_title()
            track.track_title = track.strip_whitespace_track_title()
            track.genres = track.strip_whitespace_genres()

    @staticmethod
    def __extract_track_disc_numbers_from_filenames(release: Release) -> None:
        """extract missing track and disc numbers from filenames"""
        validated_track_numbers = release.validate_track_numbers()
        validated_disc_numbers = release.validate_disc_numbers()
        for path in release.tracks:
            track_num, disc_num = extract_track_disc(os.path.split(path)[-1])
            if (not release.tracks[path].track_number and track_num) or validated_track_numbers:
                release.tracks[path].track_number = track_num
                if validated_track_numbers and disc_num:
                    release.tracks[path].disc_number = disc_num
            if (not release.tracks[path].disc_number and disc_num) or validated_disc_numbers:
                release.tracks[path].disc_number = disc_num

    @staticmethod
    def __extract_year_from_folder_name(release: Release, folder_name: str) -> None:
        """extract missing year from folder name"""
        extracted_year = extract_release_year(folder_name)
        if not release.validate_release_date() and extracted_year:
            for track in release.tracks.values():
                track.date = str(extracted_year)

    @staticmethod
    def __extract_disc_numbers_from_folder_name(release: Release) -> None:
        """extract missing disc numbers from folder name"""
        for filename in release.tracks:
            if not release.tracks[filename].disc_number:
                match = re.findall(r'(?i)(disc|disk|cd|part) ?(\d{1,2})', os.path.split(filename)[0])
                if match:
                    release.tracks[filename].disc_number = int(match[0][1])

    @staticmethod
    def __normalize_track_titles(release: Release) -> None:
        """normalize track titles"""
        for track in release.tracks.values():
            if track.track_title:
                normalized_title = normalize_track_title(track.track_title)
                if track.track_title.lower() != normalized_title.lower():
                    track.track_title = normalized_title

    @staticmethod
    def __normalize_release_title(release: Release) -> None:
        """normalize release title"""
        release_title = release.validate_release_title()
        for track in release.tracks.values():
            if track.release_title != release_title:
                track.release_title = release_title

    @staticmethod
    def __normalize_release_artists(release: Release) -> List[str]:
        """normalize release artists"""
        release_artists = release.validate_release_artists()
        if not release_artists:
            release_artists = release.extract_release_artist()

        return release_artists

    def __lastfm_release_artists(self, release: Release, release_artists: List[str]) -> List[str]:
        """fix release artists using last.fm"""
        if not self.lastfm or not release_artists:
            return []

        validated_release_artists = []
        for artist in release_artists:
            while True:
                try:
                    validated_release_artists.append(self.lastfm.get_artist(artist).artist_name)
                    break
                except LastfmCache.ArtistNotFoundError:
                    break
                except LastfmCache.UpgradeRequiredError:
                    logging.getLogger(__name__).error(upgrade_message)
                    exit(1)
                except LastfmCache.ConnectionError:
                    logging.getLogger(__name__).error("Connection error while retrieving artist, retrying...")
                    time.sleep(1)
                except LastfmCache.LastfmCacheError:
                    logging.getLogger(__name__).error("Server error while retrieving artist, retrying...")
                    time.sleep(1)

        # update release artists for all tracks, if all were validated
        if len(validated_release_artists) == len(release_artists):
            for track in release.tracks.values():
                track.release_artists = validated_release_artists

        return validated_release_artists

    @staticmethod
    def __fix_release_title(release: Release) -> None:
        """fix release title"""
        release_title = release.validate_release_title()
        if not release_title:
            return

        for category_stub in ["CD", "CDS", "CDM"]:
            if release_title.endswith(" {0}".format(category_stub)):
                release_title = release_title[:-(len(category_stub)+1)]


        bracket_pairs = [["[", "]"], ["(", ")"], ["{", "}"]]

        # Remove "[Source]" from release title
        for source in ReleaseSource:
            for brackets in bracket_pairs:
                curr_source = "{0}{1}{2}".format(brackets[0], source.value, brackets[1])
                pattern = "(?i)( )?" + re.escape(curr_source)
                if re.search(pattern, release_title):
                    release_title = re.sub(pattern, "", release_title)

        # Remove trailing ' Source' from release title
        for source in [x for x in ReleaseSource]:
            pattern = "(?i)( \-)? " + source.value + "$"
            if re.search(pattern, release_title):
                release_title = re.sub(pattern, "", release_title)

        # Remove "[Category]" from release title
        for category in ReleaseCategory:
            for brackets in bracket_pairs:
                curr_category = "{0}{1}{2}".format(brackets[0], category.value, brackets[1])
                pattern = "(?i)( )?" + re.escape(curr_category)
                if re.search(pattern, release_title):
                    release_title = re.sub(pattern, "", release_title)

        # Remove trailing ' category' from release title
        for category in [x for x in ReleaseCategory if x is not ReleaseCategory.ALBUM]:
            pattern = "(?i)( \-)? " + category.value + "$"
            if re.search(pattern, release_title):
                release_title = re.sub(pattern, "", release_title)

        # Overwrite the release's 'release title' tags
        for track in release.tracks.values():
            if track.release_title != release_title:
                track.release_title = release_title

    @staticmethod
    def __fix_missing_total_tracks(release: Release) -> None:
        # fix missing total track numbers
        validated_disc_numbers = release.get_total_tracks()
        for track in release.tracks.values():
            disc_number = track.disc_number if track.disc_number else 1
            if validated_disc_numbers.get(disc_number):
                track.total_tracks = validated_disc_numbers[disc_number]

    @staticmethod
    def __disc_number_best_guess(release: Release) -> None:
        """if disc number is missing and there appears to only be one disc, set to """
        validated_disc_numbers = release.get_total_tracks()
        if not release.validate_total_discs() and len(validated_disc_numbers) == 1:
            for track in release.tracks.values():
                track.disc_number = 1

    @staticmethod
    def __fix_missing_total_discs(release: Release) -> None:
        # fix missing total disc numbers
        if not release.validate_total_discs():
            total_discs = release.get_total_discs()
            if total_discs:
                for track in release.tracks.values():
                    track.total_discs = total_discs

    def __fix_forbidden_comment_substrings(self, release: Release) -> None:
        # forbidden comment substrings
        for track in release.tracks.values():
            if track.comment:
                for substr in self.forbidden_comment_substrings:
                    if substr in track.comment.lower():
                        track.comment = None

    def __lastfm_fixes(self, release: Release, release_artists: List[str]) -> None:
        # lastfm fixes

        release_title = release.validate_release_title()

        if not self.lastfm or not len(release_artists) or not release_title:
            return

        # extract (edition info) from release titles
        release_title, release_edition = split_release_title(normalize_release_title(release_title))

        flattened_artist = flatten_artists(release_artists)

        lastfm_release = None

        while True:
            try:
                lastfm_release = self.lastfm.get_release(flattened_artist, release_title)
                break
            except LastfmCache.ReleaseNotFoundError as e:
                logging.getLogger(__name__).error(e)
                break
            except LastfmCache.UpgradeRequiredError:
                logging.getLogger(__name__).error(upgrade_message)
                exit(1)
            except LastfmCache.ConnectionError:
                logging.getLogger(__name__).error("Connection error while retrieving release, retrying...")
                time.sleep(1)
            except LastfmCache.LastfmCacheError:
                logging.getLogger(__name__).error("Server error while retrieving release, retrying...")
                time.sleep(1)

        self.__lastfm_release_fixes(release, lastfm_release, release_artists, release_title, release_edition)

        # fix track artists using lastfm
        self.__lastfm_fix_track_artists(release)

        # fix release artists using lastfm
        self.__lastfm_fix_release_artists(release)

    def __lastfm_release_fixes(self, release: Release, lastfm_release: LastfmRelease, release_artists: List[str],
                               release_title: str, release_edition: str) -> None:
        """lastfm release fixes"""

        if release_artists:
            for track in release.tracks.values():
                track.release_artists = release_artists

        if not lastfm_release:
            return

        # release title
        if lastfm_release.release_name != release_title and \
                ReleaseValidator.__lastfm_can_fix_release_title(release_title, lastfm_release.release_name):
            release_title_full = lastfm_release.release_name
            if release_edition:
                release_title_full = "{0} {1}".format(lastfm_release.release_name, release_edition)

            for track in release.tracks.values():
                track.release_title = release_title_full

        # dates
        if lastfm_release.release_date:
            for track in release.tracks.values():
                if lastfm_release.release_date and lastfm_release.release_date != track.date:
                    track.date = lastfm_release.release_date

        # tags/genres (only fail if 0-1 genres - i.e. lastfm tags have never been applied)
        release_genres = release.validate_genres()
        lastfm_tags = self.__get_lastfm_tags(release_title, release_artists)
        if len(release_genres) < 2 <= len(lastfm_tags):
            for track in release.tracks.values():
                track.genres = lastfm_tags

        # fill missing track numbers from lastfm
        for track in release.tracks.values():
            if track.track_number:
                continue

            track_num_matches = [int(x) for x in lastfm_release.tracks
                                 if normalize_track_title(lastfm_release.tracks[x].track_name).lower() ==
                                 normalize_track_title(track.track_title).lower()]
            if track_num_matches and len(track_num_matches) == 1 and not \
                    [x.track_number for x in release.tracks.values() if x.track_number == track_num_matches[0]]:
                track.track_number = track_num_matches[0]

        # match and validate track titles (intersection only)
        track_numbers_validated = not release.validate_track_numbers()
        for track in release.tracks.values():
            if track.track_number in lastfm_release.tracks:
                lastfm_title = normalize_track_title(lastfm_release.tracks[track.track_number].track_name)

                if track.track_title != lastfm_title:
                    # if the track title is missing, or if it is lowercase and there is a case insensitive match
                    if (not track.track_title and track_numbers_validated) or \
                            (track.track_title.islower() and track.track_title.lower() == lastfm_title.lower()):
                        track.track_title = lastfm_title

                    # case insensitive match, tag version has no capital letters
                    elif track.track_title.lower() == lastfm_title.lower() \
                            and track.track_title.lower() == track.track_title:
                        track.track_title = lastfm_title


    def __lastfm_fix_track_artists(self, release: Release) -> None:
        """fix track artists using lastfm"""
        for track in release.tracks.values():
            validated_artists = []
            for artist in track.artists:
                while True:
                    try:
                        validated_artists.append(self.lastfm.get_artist(normalize_artist_name(artist)).artist_name)
                        break
                    except LastfmCache.ArtistNotFoundError:
                        validated_artists.append(artist)
                        break
                    except LastfmCache.UpgradeRequiredError:
                        logging.getLogger(__name__).error(upgrade_message)
                        exit(1)
                    except LastfmCache.ConnectionError:
                        logging.getLogger(__name__).error("Connection error while retrieving artist, retrying...")
                        time.sleep(1)
                    except LastfmCache.LastfmCacheError:
                        logging.getLogger(__name__).error("Server error while retrieving artist, retrying...")
                        time.sleep(1)
                    except AttributeError:  # TODO remove when pylast is fixed
                        break

            track.artists = validated_artists

    def __lastfm_fix_release_artists(self, release: Release) -> None:
        """fix release artists using lastfm"""
        for track in release.tracks.values():
            validated_artists = []
            for artist in track.release_artists:
                while True:
                    try:
                        validated_artists.append(self.lastfm.get_artist(normalize_artist_name(artist)).artist_name)
                        break
                    except LastfmCache.ArtistNotFoundError:
                        break
                    except LastfmCache.UpgradeRequiredError:
                        logging.getLogger(__name__).error(upgrade_message)
                        exit(1)
                    except LastfmCache.ConnectionError:
                        logging.getLogger(__name__).error("Connection error while retrieving artist, retrying...")
                        time.sleep(1)
                    except LastfmCache.LastfmCacheError:
                        logging.getLogger(__name__).error("Server error while retrieving artist, retrying...")
                        time.sleep(1)
                    except AttributeError:  # TODO remove when pylast is fixed
                        break

            if len(validated_artists) == len(track.artists):
                track.release_artists = validated_artists

    @staticmethod
    def __lastfm_can_fix_release_title(release_title: str, fixed_title: str) -> bool:
        if fixed_title.islower() and not release_title.islower():
            return False

        exception_substrings = {'fabric'}
        for substr in exception_substrings:
            if substr.lower() in release_title.lower():
                return False

        return True

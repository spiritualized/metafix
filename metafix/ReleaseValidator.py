import copy
from collections import OrderedDict
from typing import List

from lastfmcache import LastfmCache
from ordered_set import OrderedSet

from metafix.Release import Release
from metafix.Track import Track
from metafix.functions import normalize_str, lastfm_flatten_artists, normalize_track_title, split_release_title, \
    tag_filter_all, extract_track_disc


class ReleaseValidator:

    def __init__(self, lastfm: LastfmCache = None):
        self.lastfm = lastfm

    def validate(self, release: Release) -> List[str]:
        violations = OrderedSet()

        # leading/trailing whitespace
        for filename, track in release.tracks.items():
            if track.artists != track.strip_whitespace_artists():
                violations.add("File '{0}' has leading/trailing whitespace in its Artist(s)".format(filename))
                isinstance(track, Track)

        for filename, track in release.tracks.items():
            if track.release_artists != track.strip_whitespace_release_artists():
                violations.add("File '{0}' has leading/trailing whitespace in its Album/Release Artist(s)"
                               .format(filename))

        for filename, track in release.tracks.items():
            if track.date != track.strip_whitespace_date():
                violations.add("File '{0}' has leading/trailing whitespace in its Year/Date".format(filename))

        for filename, track in release.tracks.items():
            if track.release_title != track.strip_whitespace_release_title():
                violations.add("File '{0}' has leading/trailing whitespace in its Album/Release Title"
                               .format(filename))

        for filename, track in release.tracks.items():
            if track.track_title != track.strip_whitespace_track_title():
                violations.add("File '{0}' has leading/trailing whitespace in its Track Title"
                               .format(filename))

        for filename, track in release.tracks.items():
            if track.genres != track.strip_whitespace_genres():
                violations.add("File '{0}' has leading/trailing whitespace in its Genre(s)"
                               .format(filename))

        # release date
        if not release.validate_release_date():
            violations.add("Release contains blank or inconsistent 'Date' tags")

        # artists
        if release.blank_artists():
            violations.add("Release contains {0} tracks with missing 'Artist' tags".format(release.blank_artists()))

        # track titles
        if release.blank_track_titles():
            violations.add("Release contains {0} tracks with missing 'Track Title' tags"
                           .format(release.blank_track_titles()))

        # release artist
        release_artists = release.validate_release_artists()
        if not release_artists:
            violations.add("Release contains blank or inconsistent 'Album/Release Artist' tags")

        # if the lastfmcache is present, validate the release artist
        validated_release_artists = release_artists
        if self.lastfm and len(release_artists) == 1:
            validated_release_artists = []
            for artist in release_artists:
                validated_release_artist = self.lastfm.get_artist(artist.strip()).artist_name

                if validated_release_artist != artist:
                    violations.add(
                        "Incorrectly spelled Album/Release Artist '{0}' (should be '{1}')".format(
                            artist, validated_release_artist))
                validated_release_artists.append(validated_release_artist)

        # release title
        release_title = release.validate_release_title()
        if not release_title:
            violations.add("Release contains blank or inconsistent 'Album/Release Title' tags")

        # lastfm artist validations
        if self.lastfm and release_title and len(validated_release_artists):
            # extract (edition info) from release titles
            release_title, _ = split_release_title(normalize_str(release_title))

            flattened_artist = lastfm_flatten_artists(validated_release_artists)
            lastfm_release = self.lastfm.get_release(flattened_artist, release_title)

            if lastfm_release.release_name != release_title:
                # and lastfm_release.release_name.lower() != release_title.lower() \
                # and not any(x.isupper() for x in release_title):
                violations.add("Incorrectly spelled Album/Release name '{0}' (should be '{1}')"
                               .format(release_title, lastfm_release.release_name))

            # dates
            if lastfm_release.release_date:
                date = next(iter(release.tracks.values())).date
                if lastfm_release.release_date != date and len(lastfm_release.release_date) >= len(date):
                    violations.add("Incorrect Release Date '{0}' (should be '{1}')"
                                   .format(date, lastfm_release.release_date))

            # tags/genres (only fail if 0-1 genres - i.e. lastfm tags have never been applied)
            release_genres = release.validate_genres()
            lastfm_tags = self.__get_lastfm_tags(release_title, validated_release_artists)
            if len(release_genres) < 2 <= len(lastfm_tags):
                violations.add("Bad release genres: [{0}] (should be [{1}])"
                               .format(", ".join(release_genres), ", ".join(lastfm_tags)))

            # match and validate track titles (intersection only)
            for track in release.tracks.values():
                if track.track_number in lastfm_release.tracks:
                    lastfm_title = normalize_track_title(track.track_title)
                    if track.track_title.lower() != lastfm_title.lower():
                        violations.add(
                            "Incorrect track title '{0}' should be: '{1}'".format(track.track_title,
                                                                                  lastfm_title))

            # track artists
            for track in release.tracks.values():
                for artist in track.artists:
                    try:
                        validated_artist = self.lastfm.get_artist(normalize_str(artist)).artist_name
                        if validated_artist != artist:
                            violations.add("Incorrectly spelled Track Artist '{0}' (should be '{1}')"
                                           .format(artist, validated_artist))
                    except LastfmCache.LastfmCacheError as e:
                        pass
                        #violations.add(str(e))

        validated_track_numbers = release.validate_track_numbers()
        if validated_track_numbers:
            flattened_track_nums = []
            for disc in validated_track_numbers:
                flattened_track_nums.append(
                    "\nDisc " + str(disc) + ": " + ",".join(str(i) for i in validated_track_numbers[disc]))
            violations.add("Release does not have a full set of tracks:{0}".format("".join(flattened_track_nums)))

        validated_total_tracks = release.validate_total_tracks()
        for disc in validated_total_tracks:
            violations.add("Release disc {0} has blank, inconsistent or incorrect 'Total Tracks' tags".format(disc))

        # disc number
        validated_disc_numbers = release.validate_disc_numbers()
        if validated_disc_numbers:
            violations.add(
                "Release does not have a full set of discs: {0}"
                .format(", ".join(str(i) for i in validated_disc_numbers)))

        # total discs
        if not release.validate_total_discs():
            violations.add("Release has incorrect 'Total Discs' tags")

        # file type
        if len(release.get_tag_types()) != 1:
            violations.add("Release has a mixture of tag types: {0}"
                           .format(", ".join([str(x) for x in release.get_tag_types()])))

        # bitrate - CBR/VBR/Vx/APS/APE
        if len(release.get_codecs()) != 1:
            violations.add("Release has mismatched codecs: [{0}]".format(", ".join(release.get_codecs())))

        if len(release.get_cbr_bitrates()) > 1:
            violations.add("Release has a mixture of CBR bitrates: {0}"
                           .format(", ".join([str(x) for x in release.get_cbr_bitrates()])))

        # track titles
        for filename in release.tracks:
            correct_filename = release.tracks[filename].get_filename(release.is_va())
            if filename != correct_filename:
                violations.add("Invalid filename: {0} (should be {1})".format(filename, correct_filename))

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
        for filename in release.tracks:
            track_num, disc_num = extract_track_disc(filename)
            if not release.tracks[filename].track_number and track_num:
                release.tracks[filename].track_number = track_num
            if not release.tracks[filename].disc_number and disc_num:
                release.tracks[filename].disc_number = disc_num

        # fill in missing total track numbers
        validated_track_numbers = release.get_total_tracks()
        for track in release.tracks.values():
            disc_number = track.disc_number if track.disc_number else 1
            if not track.total_tracks and validated_track_numbers.get(disc_number):
                track.total_tracks = validated_track_numbers[disc_number]

        # fill in missing disc number
        if not release.validate_total_discs() and len(validated_track_numbers) == 1:
            for track in release.tracks.values():
                track.disc_number = 1

        # fill in missing total disc numbers
        if not release.validate_total_discs():
            total_discs = release.get_total_discs()
            if total_discs:
                for track in release.tracks.values():
                    track.total_discs = total_discs

        # release artists
        release_artists = release.validate_release_artists()
        validated_release_artists = []
        if self.lastfm and release_artists:
            for artist in release_artists:
                validated_release_artists.append(self.lastfm.get_artist(artist).artist_name)

            # update release artists for all tracks, if all were validated
            if len(validated_release_artists) == len(release_artists):
                for track in release.tracks.values():
                    track.release_artists = validated_release_artists

        # release title
        release_title = release.validate_release_title()

        # lastfm artist validations
        if self.lastfm and len(validated_release_artists) and release_title:
            # extract (edition info) from release titles
            release_title, release_edition = split_release_title(normalize_str(release_title))

            flattened_artist = lastfm_flatten_artists(validated_release_artists)
            lastfm_release = self.lastfm.get_release(flattened_artist, release_title)

            if lastfm_release.release_name != release_title:
                # and lastfm_release.release_name.lower() != release_title.lower() \
                # and not any(x.isupper() for x in release_title):
                release_title_full = lastfm_release.release_name
                if release_edition:
                    release_title_full = "{0} {1}".format(lastfm_release.release_name, release_edition)

                for track in release.tracks.values():
                    track.release_title = release_title_full

            # dates
            if lastfm_release.release_date:
                for track in release.tracks.values():
                    if lastfm_release.release_date != track.date \
                            and len(lastfm_release.release_date) >= len(track.date):
                        track.date = lastfm_release.release_date

            # tags/genres (only fail if 0-1 genres - i.e. lastfm tags have never been applied)
            release_genres = release.validate_genres()
            lastfm_tags = self.__get_lastfm_tags(release_title, validated_release_artists)
            if len(release_genres) < 2 <= len(lastfm_tags):
                for track in release.tracks.values():
                    track.genres = lastfm_tags

            # match and validate track titles (intersection only)
            for track in release.tracks.values():
                if track.track_number in lastfm_release.tracks:
                    lastfm_title = normalize_track_title(lastfm_release.tracks[track.track_number].track_name)
                    # if there is a case insensitive mismatch
                    if track.track_title.lower() != lastfm_title.lower():
                        track.track_title = lastfm_title

                    # case insensitive match, tag version has no capital letters
                    elif track.track_title.lower() == lastfm_title.lower() \
                        and track.track_title.lower() == track.track_title:
                        track.track_title = lastfm_title

            # track artists
            for track in release.tracks.values():
                validated_artists = []
                for artist in track.artists:
                    try:
                        validated_artists.append(self.lastfm.get_artist(artist).artist_name)
                    except LastfmCache.LastfmCacheError:
                        pass
                if len(validated_artists) == len(track.artists):
                    track.artists = validated_artists

        return release

    # tags/genres
    def __get_lastfm_tags(self, release_title: str, release_artists: List[str]):
        flattened_artist = lastfm_flatten_artists(release_artists)
        lastfm_release = self.lastfm.get_release(flattened_artist, release_title)

        lastfm_tags = [x for x in tag_filter_all(lastfm_release.tags, release_artists + [release_title], True)]
        if not lastfm_tags:
            artists_tags = [self.lastfm.get_artist(artist).tags for artist in release_artists]
            weighted_tags = OrderedDict()
            for artist_tags in artists_tags:
                for tag in artist_tags:
                    if tag not in weighted_tags or (tag in weighted_tags and weighted_tags[tag] < artist_tags[tag]):
                        weighted_tags[tag] = artist_tags[tag]
            lastfm_tags = [x for x in tag_filter_all(weighted_tags, release_artists + [release_title], True)]

        return [x for x in lastfm_tags]
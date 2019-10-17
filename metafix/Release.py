import os
from collections import OrderedDict
from typing import Dict, List

from cleartag.enums.TagType import TagType
from metafix.Track import Track
from metafix.constants import valid_release_categories
from metafix.functions import unique, lastfm_flatten_artists, get_category_fix_name, normalise_path_chars


class Release:

    def __init__(self, tracks: Dict[str, Track], is_VA_manual:bool = None):
        self.tracks = tracks
        self.is_VA_manual = is_VA_manual

    def __eq__(self, other):
        return self.tracks == other.tracks

    def get_release_codec_setting(self, short=True) -> str:

        # check for mismatched tag types
        tag_types = unique([track.stream_info.tag_type for track in self.tracks.values()])
        if len(tag_types) != 1:
            return ""

        # check for mismatched codec settings
        codec_settings = unique([track.get_codec_setting(short=True) for track in self.tracks.values()])
        if len(codec_settings) != 1:
            return ""

        prefix_str = ""
        if not short:
            if tag_types[0] == TagType.ID3:
                prefix_str = "MP3 "
            elif tag_types[0] == TagType.MP4:
                prefix_str = "MP4 "

        # check for mismatched CBR bitrates
        if codec_settings[0] == "CBR":
            cbr_bitrates = unique([track.stream_info.bitrate for track in self.tracks.values()])
            if len(cbr_bitrates) != 1:
                return ""

            return "{0}CBR{1}".format(prefix_str, int(round(cbr_bitrates[0] / 1000)))

        elif codec_settings[0] == "VBR":
            average_bitrate = round(
                sum([track.stream_info.bitrate * track.stream_info.length for track in self.tracks.values()]) /
                sum([track.stream_info.length for track in self.tracks.values()]) / 1000)

            return "{0}VBR{1}".format(prefix_str, average_bitrate)

        else:
            return "{0}{1}".format(prefix_str, codec_settings[0])

    def is_VA(self) -> bool:
        if self.is_VA_manual != None:
            return self.is_VA_manual

        # extract additional artists
        additional_artists = []
        for track in self.tracks.values():
            for artist in track.artists:
                if artist not in self.tracks[next(iter(self.tracks))].release_artists:
                    additional_artists.append(artist)

        # is this a VA album?
        return len(unique(additional_artists)) > len(self.tracks) / 2


    def get_folder_name(self, is_VA:bool = None, codec_short:bool = True, group_by_category: bool = False,
                        group_by_artist:bool = False, manual_release_category: str = None,
                        manual_release_source:str = ""):

        if is_VA is None:
            is_VA = self.is_VA()

        track1 = self.tracks[next(iter(self.tracks))]

        # clean release name, and category
        release_name, release_category = get_category_fix_name(track1.release_title,
                                                                 len(self.tracks), is_VA)

        valid_release_categories_lower = [x.lower() for x in valid_release_categories]
        if manual_release_category and manual_release_category.lower() in valid_release_categories_lower:
            release_category = valid_release_categories[
                valid_release_categories_lower.index(manual_release_category.lower())]

        release_source = "CD"
        valid_release_sources = ['CD', 'WEB', 'Vinyl']
        valid_release_sources_lower = [x.lower() for x in valid_release_sources]
        if manual_release_source and manual_release_source.lower() in valid_release_sources_lower:
            release_source = valid_release_sources[valid_release_sources_lower.index(manual_release_source.lower())]

        release_artist = lastfm_flatten_artists(track1.release_artists)
        year = track1.date.split("-")[0]
        release_codec = track1.get_codec_setting(short=codec_short)

        release_category_str = "[{0}] ".format(release_category) \
            if manual_release_category and release_category != "Album" else ""
        release_source_str = "" if release_source == "CD" else "[{0}] ".format(release_source)
        artist_folder_str = "" if not group_by_artist else "{0}{1}".format(release_artist, os.path.sep)
        category_folder_str = "" if not group_by_category else "{0}{1}".format(release_category, os.path.sep)

        assert self.validate_release_date(), "Release date validation failed"
        assert self.validate_release_title(), "Release title validation failed"
        assert self.validate_release_artists(), "Release artists validation failed"


        # folder name
        if not is_VA:
            return normalise_path_chars(
            "{category_folder_str}{artist_folder_str}{release_artist} - {year} - {release_name} "
            "{release_category_str}{release_source_str}[{release_codec}]"
                .format(category_folder_str=category_folder_str,
                        artist_folder_str=artist_folder_str,
                        release_artist=release_artist,
                        year=year,
                        release_name=release_name,
                        release_category_str=release_category_str,
                        release_source_str=release_source_str,
                        release_codec=release_codec))

        else:
            return normalise_path_chars(
                "{category_folder_str}{artist_folder_str}VA - {release_name} - {year} - {release_artist} "
                "{release_category_str}{release_source_str}[{release_codec}]"
                    .format(category_folder_str=category_folder_str,
                            artist_folder_str=artist_folder_str,
                            release_name=release_name,
                            year=year,
                            release_artist=release_artist,
                            release_category_str=release_category_str,
                            release_codec=release_codec,
                            release_source_str=release_source_str))


    # return release date if consistent
    def validate_release_date(self) -> str:
        dates = unique([track.date for track in self.tracks.values()])
        if len(dates) == 1 and dates[0]:
            return dates[0]

    # return number of tracks with empty artist tags
    def blank_artists(self) -> int:
        return sum([1 for track in self.tracks.values() if not len(track.artists)])

    # return number of tracks with empty track title tags
    def blank_track_titles(self) -> int:
        return sum([1 for track in self.tracks.values() if not track.track_title])

    # return release artists if consistent
    def validate_release_artists(self) -> List[str]:
        release_artists = unique([track.release_artists for track in self.tracks.values()])
        if len(release_artists) == 1:
            return release_artists[0]
        return []

    # return release title if consistent
    def validate_release_title(self) -> str:
        release_titles = unique([track.release_title for track in self.tracks.values()])
        if len(release_titles) == 1:
            return release_titles[0]

    def __get_disc_numbers_by_track(self) -> Dict[int, List[int]]:
        # extract into track_numbers[disc]
        track_numbers = OrderedDict()
        for track in self.tracks.values():
            disc_num = track.disc_number or 1
            if disc_num not in track_numbers:
                track_numbers[disc_num] = []
            track_numbers[disc_num].append(track.track_number)

        for disc_num in track_numbers:
            track_numbers[disc_num] = sorted(track_numbers[disc_num])

        return OrderedDict(sorted(track_numbers.items(), key=lambda disc: disc[0]))

    # return empty list if consistent
    def validate_track_numbers(self) -> Dict[int, list]:

        # extract into track_numbers[disc]
        track_numbers = self.__get_disc_numbers_by_track()

        # validate a full set of strictly incrementing tracks, starting at 1
        all_tracks_present = True

        for disc in track_numbers:

            if track_numbers[disc][0] != 1:
                all_tracks_present = False

            for i in range(0, len(track_numbers[disc]) - 1):
                if track_numbers[disc][i] != track_numbers[disc][i + 1] - 1:
                    all_tracks_present = False

        if all_tracks_present:
            return OrderedDict()
        else:
            return track_numbers

    def get_total_tracks(self) -> Dict[int, int]:

        result = OrderedDict()

        track_numbers = self.__get_disc_numbers_by_track()

        for disc in track_numbers:
            all_tracks_present = True
            for i in range(0, len(track_numbers[disc]) - 1):
                if track_numbers[disc][i] != track_numbers[disc][i + 1] - 1:
                    all_tracks_present = False

            result[disc] = len(track_numbers[disc]) if all_tracks_present else None

        return result


    # return an invalid sequence of total tracks tags
    def validate_total_tracks(self) -> List[int]:
        violating_discs = []
        total_tracks = OrderedDict()
        for track in self.tracks.values():
            if track.disc_number not in total_tracks:
                total_tracks[track.disc_number] = []
            total_tracks[track.disc_number].append(track.total_tracks)

        for disc in total_tracks:
            curr_disc = unique(total_tracks[disc])
            if len(curr_disc) != 1 or len(total_tracks[disc]) != curr_disc[0]:
                violating_discs.append(disc)

        return violating_discs

    # return an invalid sequence of disc numbers
    def validate_disc_numbers(self) -> List[int]:
        track_numbers = self.__get_disc_numbers_by_track()
        # disc number
        disc_numbers = sorted(list(track_numbers))
        all_discs_present = disc_numbers[0] == 1

        for i in range(0, len(disc_numbers) - 1):
            if disc_numbers[i] != disc_numbers[i + 1] - 1:
                all_discs_present = False

        if all_discs_present:
            return []
        else:
            return disc_numbers

    def validate_total_discs(self) -> bool:
        total_discs = unique([track.total_discs for track in self.tracks.values()])
        return len(total_discs) == 1 and total_discs[0] == sorted(list(self.__get_disc_numbers_by_track()))[-1]

    # return a list of genres, or [] if inconsistent/empty
    def validate_genres(self):
        genres = unique([track.genres for track in self.tracks.values()])
        return genres[0] if len(genres) == 1 else []

    # return multiple tag types or empty list
    def get_tag_types(self) -> List[str]:
        return unique([track.stream_info.tag_type for track in self.tracks.values()])

    def get_codecs(self) -> List[str]:
        return unique([track.get_codec_setting(short=True) for track in self.tracks.values()])

    def get_cbr_bitrates(self) -> List[str]:
        if (self.get_codecs()[0] if len(self.get_codecs()) else "") == "CBR":
            return unique([track.stream_info.bitrate for track in self.tracks.values()])
        else:
            return []

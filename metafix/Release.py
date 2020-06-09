from __future__ import annotations

import os
from collections import OrderedDict
from typing import Dict, List, Optional

from cleartag.enums.TagType import TagType
from cleartag.functions import normalize_path_chars
from metafix.Track import Track
from metafix.constants import ReleaseCategory, ReleaseSource
from metafix.functions import unique, flatten_artists, get_category_fix_name, normalize_release_title


class Release:

    def __init__(self, tracks: Dict[str, Track], manual_category: ReleaseCategory = ReleaseCategory.UNKNOWN,
                 manual_source = ReleaseSource.UNKNOWN):
        self.tracks = tracks
        self.category = manual_category
        self.source = manual_source
        self.num_violations = None
        self.guess_category()
        self.sort()

    def __eq__(self, other):
        return self.tracks == other.tracks

    def __repr__(self):
        track0 = self.tracks[next(iter(self.tracks))]
        date = "<date not found>" if not track0.date else track0.date.split("-")[0]
        return "{0} - {1} - {2}"\
            .format(flatten_artists(track0.release_artists), date, track0.release_title)

    def sort(self):
        reordered = OrderedDict()

        while len(self.tracks):
            smallest_filename = next(iter(self.tracks))
            smallest_track = self.tracks[smallest_filename]
            for filename in self.tracks:
                if self.tracks[filename] < smallest_track:
                    smallest_filename = filename
                    smallest_track = self.tracks[filename]
            del self.tracks[smallest_filename]
            reordered[smallest_filename] = smallest_track

        self.tracks = reordered


    def guess_category(self) -> None:
        if self.category:
            return

        # clean release name, and category
        _, self.category = get_category_fix_name(self)

        # extract additional artists
        additional_artists = []
        for track in self.tracks.values():
            for artist in track.artists:
                if artist not in self.tracks[next(iter(self.tracks))].release_artists:
                    additional_artists.append(artist)

        if len(self.tracks) < 4 and len(unique(additional_artists)) == 1:
            self.category = ReleaseCategory.SINGLE
        elif len(self.tracks) < 6 and len(unique(additional_artists)) == 1:
            self.category = ReleaseCategory.EP
        elif len(unique(additional_artists)) > len(self.tracks) / 2:
            self.category = ReleaseCategory.COMPILATION
        else:
            self.category = ReleaseCategory.ALBUM

    def is_va(self):
        return self.category in {ReleaseCategory.COMPILATION, ReleaseCategory.VIDEO_GAME_MUSIC, ReleaseCategory.MIX,
                                 ReleaseCategory.MIXTAPE, ReleaseCategory.SOUNDTRACK}

    def get_release_codec_setting(self, short=True) -> str:

        # check for mismatched tag types
        tag_types = unique([track.stream_info.tag_type for track in self.tracks.values()])
        if len(tag_types) != 1:
            return ""

        # check for mismatched codec settings
        codec_settings = unique([track.get_codec_setting_str(short=True) for track in self.tracks.values()])
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
            cbr_bitrates = unique([round(track.stream_info.bitrate, -3) for track in self.tracks.values()])
            if len(cbr_bitrates) != 1:
                return ""

            cbr_bitrate = int(round(cbr_bitrates[0] / 1000))
            cbr_bitrate += cbr_bitrate % 2

            return "{0}CBR{1}".format(prefix_str, cbr_bitrate)

        elif codec_settings[0] == "VBR":
            average_bitrate = round(
                sum([track.stream_info.bitrate * track.stream_info.length for track in self.tracks.values()]) /
                sum([track.stream_info.length for track in self.tracks.values()]) / 1000)

            return "{0}VBR{1}".format(prefix_str, average_bitrate)

        else:
            return "{0}{1}".format(prefix_str, codec_settings[0])

    def get_codec_rank(self) -> int:
        """Return a codec indicating the release's codec ranking. Higher is better."""
        codec = self.get_release_codec_setting()
        if not codec:
            return 0

        rank = 1000

        if codec in ["FLAC", "24bit FLAC", "V0"]: return rank
        rank -= 1
        if codec == "APE": return rank
        rank -= 1
        if codec == "CBR320": return rank
        rank -= 1
        if codec == "V1": return rank
        rank -= 1
        if codec == "vbr-old V1": return rank
        rank -= 1
        if codec == "V2": return rank
        rank -= 1
        if codec == "APS": return rank
        rank -= 1
        if codec == "V3": return rank
        rank -= 1
        if codec == "vbr-old V3": return rank
        rank -= 1
        if codec == "V4": return rank
        rank -= 1
        if codec == "APM": return rank
        rank -= 1

        # VBR/CBR/ABR: 320k > bitrate >= 256k
        if len(codec) >= 5 and codec[:3] in ["VBR", "CBR", "ABR"] and codec[3:].isdigit():
            curr_bitrate = 320
            bitrate = int(codec[3:])

            while curr_bitrate >= 256:
                for curr_setting in ["VBR", "CBR", "ABR"]:
                    if curr_setting == codec[:3] and bitrate <= curr_bitrate and bitrate >= curr_bitrate - 64:
                        return rank
                    rank -= 1

                curr_bitrate -= 64

        # V5 -> V9
        for lame in ["V", "vbr-old V"]:
            for num in range(5, 10):
                if codec == "{0}{1}".format(lame, num):
                    return rank
                rank -= 1

        # VBR/CBR/ABR: 255k > bitrate >= 0
        if len(codec) >= 5 and codec[:3] in ["VBR", "CBR", "ABR"] and codec[3:].isdigit():
            curr_bitrate = 192
            bitrate = int(codec[3:])

            while curr_bitrate > 0:
                for curr_setting in ["VBR", "CBR", "ABR"]:
                    if curr_setting == codec[:3] and bitrate <= curr_bitrate and bitrate >= curr_bitrate - 64:
                        return rank
                    rank -= 1

                curr_bitrate -= 64

        if "lame vbr method" in codec: return rank
        rank -= 1

        return -1


    def get_folder_name(self, codec_short: bool = True, group_by_category: bool = False):

        assert self.validate_release_date(), "Release date validation failed"
        assert self.validate_release_title(), "Release title validation failed"
        assert self.validate_release_artists(), "Release artists validation failed"
        assert self.validate_codec(), "Codec validation failed"

        track1 = self.tracks[next(iter(self.tracks))]

        # clean release name, and category
        release_name, _ = get_category_fix_name(self)

        release_artist = flatten_artists(track1.release_artists)
        year = track1.date.split("-")[0]

        release_category_str = "[{0}] ".format(self.category.value) if self.category != ReleaseCategory.ALBUM else ""
        release_source_str = "[{0}] ".format(self.source.value) if self.source != ReleaseSource.CD else ""

        title_first_categories = {ReleaseCategory.COMPILATION, ReleaseCategory.MIX, ReleaseCategory.MIXTAPE,
                                  ReleaseCategory.VIDEO_GAME_MUSIC, ReleaseCategory.SOUNDTRACK}

        # folder name
        if group_by_category is False and self.category in title_first_categories:
            return normalize_path_chars(
                "VA - {release_name} - {year} - {release_artist} "
                "{release_category_str}{release_source_str}[{release_codec}]"
                .format(release_name=release_name,
                        year=year,
                        release_artist=release_artist,
                        release_category_str=release_category_str,
                        release_codec=self.get_release_codec_setting(codec_short),
                        release_source_str=release_source_str))

        elif self.category in title_first_categories:
            return normalize_path_chars(
                "{release_name} - {year} - {release_artist} "
                "{release_category_str}{release_source_str}[{release_codec}]"
                .format(release_name=release_name,
                        year=year,
                        release_artist=release_artist,
                        release_category_str=release_category_str,
                        release_codec=self.get_release_codec_setting(codec_short),
                        release_source_str=release_source_str))

        else:
            """self.category in {ReleaseCategory.ALBUM, ReleaseCategory.ANTHOLOGY, ReleaseCategory.BOOTLEG,
                     ReleaseCategory.CONCERT_RECORDING, ReleaseCategory.DEMO, ReleaseCategory.EP,
                     ReleaseCategory.INTERVIEW, ReleaseCategory.LIVE_ALBUM, ReleaseCategory.REMIX,
                     ReleaseCategory.SINGLE, ReleaseCategory.UNKNOWN}:"""
            return normalize_path_chars(
                "{release_artist} - {year} - {release_name} "
                "{release_category_str}{release_source_str}[{release_codec}]"
                .format(release_artist=release_artist,
                        year=year,
                        release_name=release_name,
                        release_category_str=release_category_str,
                        release_source_str=release_source_str,
                        release_codec=self.get_release_codec_setting(codec_short)))

    def validate_codec(self) -> Optional[str]:
        codec_settings = unique([track.get_codec() for track in self.tracks.values()])
        if len(codec_settings) != 1:
            return None
        return codec_settings[0]

    # return true if the folder name can be validated
    def can_validate_folder_name(self) -> bool:
        return self.validate_release_date() is not None and self.validate_release_title() is not None \
               and self.validate_release_artists() != [] and self.validate_codec()

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
            return unique(release_artists[0])
        return []

    def extract_release_artist(self) -> List[str]:
        artists = unique([x.artists for x in self.tracks.values()])
        return artists[0] if len(artists) == 1 else []

    # return release title if consistent
    def validate_release_title(self) -> Optional[str]:
        release_titles = unique([track.release_title for track in self.tracks.values()])
        if len(release_titles) == 1 and release_titles[0] != "":
            return release_titles[0]

        # if the release title couldn't be validated, try normalizing it
        release_titles = unique([normalize_release_title(track.release_title) for track in self.tracks.values()])
        if len(release_titles) == 1 and release_titles[0] != "":
            return release_titles[0]

    def __get_disc_numbers_by_track(self) -> Dict[int, List[int]]:
        # extract into track_numbers[disc]
        track_numbers = OrderedDict()
        for track in self.tracks.values():
            disc_num = track.disc_number or 1
            if disc_num not in track_numbers:
                track_numbers[disc_num] = []
            if track.track_number:
                track_numbers[disc_num].append(int(track.track_number))

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

            if not track_numbers[disc] or track_numbers[disc][0] != 1:
                all_tracks_present = False

            for i in range(0, len(track_numbers[disc]) - 1):
                if track_numbers[disc][i] != track_numbers[disc][i + 1] - 1:
                    all_tracks_present = False

        if all_tracks_present:
            return OrderedDict()
        else:
            return track_numbers

    def resequence_track_numbers(self):
        """If multiple discs, disc numbers are complete, and track numbers are sequenced as if there is only one disc"""
        track_numbers = self.validate_track_numbers()

        if not track_numbers:
            return

        disc_nums = [x for x in track_numbers]
        if disc_nums[0] != 1:
            return
        for i in range(len(disc_nums) - 1):
            if disc_nums[i] != disc_nums[i+1] - 1:
                return

        flat_track_numbers = []
        for disc in track_numbers:
            flat_track_numbers += track_numbers[disc]

        if not flat_track_numbers or flat_track_numbers[0] != 1:
            return

        for i in range(len(flat_track_numbers) - 1):
            if flat_track_numbers[i] != flat_track_numbers[i+1] - 1:
                return

        curr_track = 1
        curr_disc = 1
        for filename in self.tracks:
            if curr_disc != self.tracks[filename].disc_number:
                curr_track = 1
                curr_disc = self.tracks[filename].disc_number

            self.tracks[filename].track_number = curr_track
            curr_track += 1





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
        if not track_numbers:
            return []

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
        disc_numbers = sorted(list(self.__get_disc_numbers_by_track()))
        total_discs = unique([track.total_discs for track in self.tracks.values()])
        return len(total_discs) == 1 and len(disc_numbers) and total_discs[0] == disc_numbers[-1]

    def get_total_discs(self) -> Optional[int]:
        disc_numbers = sorted(unique([track.disc_number
                                      for track in self.tracks.values() if track.disc_number is not None]))
        if not len(disc_numbers) or disc_numbers[0] != 1:
            return None
        for x in range(len(disc_numbers) - 1):
            if disc_numbers[x] != disc_numbers[x+1] - 1:
                return None
        return disc_numbers[-1]

    # return a list of genres, or [] if inconsistent/empty
    def validate_genres(self):
        genres = unique([track.genres for track in self.tracks.values()])
        return genres[0] if len(genres) == 1 else []

    # return multiple tag types or empty list
    def get_tag_types(self) -> List[str]:
        return unique([track.stream_info.tag_type for track in self.tracks.values()])

    def get_codecs(self) -> List[str]:
        return unique([track.get_codec_setting_str(short=True) for track in self.tracks.values()])

    def get_cbr_bitrates(self) -> List[int]:
        if (self.get_codecs()[0] if len(self.get_codecs()) == 1 else "") == "CBR":
            return unique([track.stream_info.bitrate for track in self.tracks.values()])
        else:
            return []

    def get_vbr_bitrate(self) -> Optional[float]:
        codecs = self.get_codecs()
        if not len(unique(codecs)) == 1 or codecs[0] != "VBR":
            return None

        return sum([track.stream_info.bitrate * track.stream_info.length for track in self.tracks.values()]) / \
               sum([track.stream_info.length for track in self.tracks.values()])

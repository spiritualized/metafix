import copy
import os
import unittest
from collections import OrderedDict

from cleartag.StreamInfo import StreamInfo
from cleartag.Xing import Xing
from cleartag.enums.Mp3Method import Mp3Method
from cleartag.enums.TagType import TagType
from metafix.Release import Release
from metafix.Track import Track

def create_test_release(artists=None, release_artists=None, release_title="Mezzanine", date="1998-04-17",
                        track_titles=None, genres=None) -> Release:

    if not artists:
        artists = ["Massive Attack"]
    if not release_artists:
        release_artists = ["Massive Attack"]
    if not track_titles:
        track_titles = ["Angel", "Risingson", "Teardrop", "Inertia Creeps", "Exchange", "Dissolved Girl",
                        "Man Next Door",
                        "Black Milk", "Mezzanine", "Group Four", "(Exchange)"]
    if not genres:
        genres = ['Trip-hop', 'Electronic', 'Chillout', 'Electronica', 'Downtempo', '90s', 'Alternative', 'Ambient',
                  'British', 'Dark', 'Bristol Sound', 'Atmospheric', 'Hypnotic', 'UK', 'Alternative Dance', 'Bristol',
                  'Chill', 'Dub', 'Experimental', 'Indie', 'Leftfield', 'Lounge', 'Nocturnal', '1990s', 'Bass',
                  'Electro', 'Intense', 'Relax', 'Sophisticated']

    tracks = OrderedDict()

    base_track = Track(artists=artists, release_artists=release_artists, date=date,
                  release_title=release_title, track_number=1, total_tracks=len(track_titles), disc_number=1,
                  total_discs=1, genres=genres,
                  stream_info=StreamInfo(tag_type=TagType.ID3, mp3_method=Mp3Method.CBR, length=100.123,
                                         bitrate=128000, xing=Xing()))

    for i in range(1, len(track_titles)+1):
        curr_track = copy.deepcopy(base_track)
        curr_track.track_title = track_titles[i-1]
        curr_track.track_number = i
        tracks["{0} - {1}.mp3".format(str(i).zfill(2), curr_track.track_title)] = curr_track

    return Release(tracks)


class TestRelease(unittest.TestCase):

    def test_eq(self):
        assert create_test_release() == create_test_release()

    def test_get_release_codec_setting(self):
        release = create_test_release()
        assert release.get_release_codec_setting() == "CBR128"

        next(iter(release.tracks.values())).stream_info = StreamInfo(tag_type=TagType.FLAC, mp3_method=Mp3Method.CBR,
                                                            bitrate=128000, length=100.123)
        assert not release.get_release_codec_setting()

        release = create_test_release()
        next(iter(release.tracks.values())).stream_info.xing.lame_version = 1
        next(iter(release.tracks.values())).stream_info.xing.lame_vbr_method = 3
        assert not release.get_release_codec_setting()

        release = create_test_release()
        assert release.get_release_codec_setting(short=False) == "MP3 CBR128"

        for track in release.tracks.values():
            track.stream_info.tag_type = TagType.MP4
        assert release.get_release_codec_setting(short=False) == "MP4 UNKNOWN"

        release = create_test_release()
        next(iter(release.tracks.values())).stream_info.bitrate = 160000
        assert not release.get_release_codec_setting()

        release = create_test_release()
        for track in release.tracks.values():
            track.stream_info.xing.lame_version = 1
            track.stream_info.xing.lame_vbr_method = 4
            track.stream_info.xing.xing_vbr_v = 0
        assert release.get_release_codec_setting() == "V0"

        release = create_test_release()
        for track in release.tracks.values():
            track.stream_info.mp3_method = Mp3Method.VBR
        assert release.get_release_codec_setting() == "VBR128"

    def test_is_VA(self):
        release = create_test_release()
        assert not release.is_VA()

        for track in release.tracks.values():
            track.artists = ["artist {0}".format(track.track_number)]

        assert release.is_VA()


    def test_get_folder_name(self):
        release = create_test_release()
        assert release.get_folder_name() == "Massive Attack - 1998 - Mezzanine [CBR]"
        assert release.get_folder_name(group_by_artist=True) == \
               "Massive Attack" + os.path.sep + "Massive Attack - 1998 - Mezzanine [CBR]"
        assert release.get_folder_name(is_VA=True) == "VA - Mezzanine - 1998 - Massive Attack [CBR]"
        assert release.get_folder_name(codec_short=False) == "Massive Attack - 1998 - Mezzanine [MP3 CBR]"
        assert release.get_folder_name(group_by_category=True) == \
               "Album" + os.path.sep + "Massive Attack - 1998 - Mezzanine [CBR]"
        assert release.get_folder_name(manual_release_category="Soundtrack") == \
               "Massive Attack - 1998 - Mezzanine [Soundtrack] [CBR]"

        for track in release.tracks.values():
            track.artists = ["artist {0}".format(track.track_number)]

        assert release.get_folder_name() == "VA - Mezzanine - 1998 - Massive Attack [CBR]"

        release = create_test_release()
        assert release.get_folder_name(manual_release_source="Vinyl") == \
               "Massive Attack - 1998 - Mezzanine [Vinyl] [CBR]"

    def test_validate_release_date(self):
        release = create_test_release()
        assert release.validate_release_date() == next(iter(release.tracks.values())).date

        next(iter(release.tracks.values())).date = ""
        assert release.validate_release_date() is None

    def test_blank_artists(self):
        release = create_test_release()
        assert release.blank_artists() == 0

        next(iter(release.tracks.values())).artists = []
        assert release.blank_artists() == 1

    def test_blank_track_titles(self):
        release = create_test_release()
        assert release.blank_track_titles() == 0

        next(iter(release.tracks.values())).track_title = ""
        assert release.blank_track_titles() == 1

    def test_validate_release_artists(self):
        release = create_test_release()
        assert release.validate_release_artists() == next(iter(release.tracks.values())).release_artists

        next(iter(release.tracks.values())).release_artists = []
        assert release.validate_release_artists() == []

    def test_validate_release_title(self):
        release = create_test_release()
        assert release.validate_release_title() == next(iter(release.tracks.values())).release_title

        next(iter(release.tracks.values())).release_title = "Something Else"
        assert release.validate_release_title() is None

    def test_validate_track_numbers(self):
        release = create_test_release()
        assert release.validate_track_numbers() == {}

        next(iter(release.tracks.values())).track_number = 66
        assert release.validate_track_numbers() != {}

    def test_validate_total_tracks(self):
        release = create_test_release()
        assert release.validate_total_tracks() == []

        next(iter(release.tracks.values())).total_tracks = 3
        assert release.validate_total_tracks() == [1]

    def test_validate_disc_numbers(self):
        release = create_test_release()
        assert release.validate_disc_numbers() == []

        next(iter(release.tracks.values())).disc_number = 3
        assert release.validate_disc_numbers() == [1, 3]

    def test_validate_total_discs(self):
        release = create_test_release()
        assert release.validate_total_discs()

        next(iter(release.tracks.values())).total_discs = 3
        assert not release.validate_total_discs()

    def test_get_tag_types(self):
        release = create_test_release()
        assert release.get_tag_types() == [TagType.ID3]

    def test_get_codecs(self):
        release = create_test_release()
        assert release.get_codecs() == ["CBR"]

    def test_get_cbr_bitrates(self):
        release = create_test_release()
        assert release.get_cbr_bitrates() == [128000]

    def test_validate_genres(self):
        release = create_test_release()
        assert release.validate_genres() == next(iter(release.tracks.values())).genres

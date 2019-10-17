import unittest
from collections import OrderedDict

from metafix.functions import normalize_str, tag_filter_all, capitalize_tag, extract_track_disc


class TestRelease(unittest.TestCase):

    def test_normalize_str(self):

        assert normalize_str("Artist 1 Feat. Artist 2") == "Artist 1 feat. Artist 2"

    def test_tag_filter_all(self):
        tags_in = {"seen live": 100, "electronic": 100, "a band":100, "crossover":99, "artist i think is cool": 1}
        tags_out = tag_filter_all(tags_in, ["a band", "their album"])

        assert tags_out == OrderedDict({"electronic": 100, "fusion": 99})

    def test_capitalize_tag(self):
        assert capitalize_tag("by and genre") == "By and Genre"

    def test_extract_track_disc(self):
        track, disc = extract_track_disc("102 - track title.mp3")
        assert disc == 1
        assert track == 2

        track, disc = extract_track_disc("212 - track title.mp3")
        assert disc == 2
        assert track == 12

        track, disc = extract_track_disc("1223 - track title.mp3")
        assert disc == 12
        assert track == 23



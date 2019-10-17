import unittest
from collections import OrderedDict
from unittest.mock import MagicMock

import mockito
from lastfmcache import lastfmcache
from lastfmcache.lastfmcache import lastfm_artist, lastfm_release, lastfm_track

from cleartag.enums.TagType import TagType
from metafix.ReleaseValidator import ReleaseValidator
from metafix.tests.test_Release import create_test_release


def get_lastfmcache(genres_artist:OrderedDict = None, genres_release:OrderedDict = None):
    source_release = create_test_release()
    source_track = next(iter(source_release.tracks.values()))

    _genres_release = genres_release if genres_release is not None else source_track.genres
    _genres_artist = genres_artist if genres_artist is not None else source_track.genres

    lastfm_release_obj = lastfm_release()
    lastfm_release_obj.artist_name = source_track.artists[0]
    lastfm_release_obj.release_date = source_track.date
    lastfm_release_obj.release_name = source_track.release_title
    for track in source_release.tracks.values():
        lastfm_release_obj.tracks[track.track_number] = \
            lastfm_track(track.track_number, track.track_title, track.release_artists[0], 0)
    lastfm_release_obj.tags = OrderedDict()

    i = 100
    for genre in _genres_release:
        lastfm_release_obj.tags[genre] = i
        i -= 1


    mock_lastfm = MagicMock(lastfmcache)
    mock_artist = lastfm_artist()
    mock_artist.artist_name = source_track.artists[0]
    mock_artist.tags = OrderedDict()
    i = 100
    for genre in _genres_artist:
        mock_artist.tags[genre] = i
        i -= 1

    mockito.when(mock_lastfm).get_artist(mockito.ANY).thenReturn(mock_artist)

    mockito.when(mock_lastfm).get_release(mockito.ANY, mockito.ANY).thenReturn(lastfm_release_obj)

    return mock_lastfm

class TestReleaseValidator(unittest.TestCase):

    def test_validate_artist_whitespace(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).artists[0] = " Massive Attack"

        violations = validator.validate(release)
        assert len(violations) == 2

        mockito.unstub()

    def test_validate_release_artist_whitespace(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release(release_artists=[" Massive Attack"])

        violations = validator.validate(release)
        assert len(violations) == len(release.tracks) + 1

        mockito.unstub()

    def test_validate_date_whitespace(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release(date="1998-04-17 ")

        violations = validator.validate(release)
        assert len(violations) == len(release.tracks)

        mockito.unstub()

    def test_validate_release_title_whitespace(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release(release_title=" Mezzanine")

        violations = validator.validate(release)
        assert len(violations) == len(release.tracks)

        mockito.unstub()

    def test_validate_track_title_whitespace(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).track_title = " A Bad Track Title"

        violations = validator.validate(release)
        assert len(violations) == 2

        mockito.unstub()

    def test_validate_genre_whitespace(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release(genres=[" Bass"])

        violations = validator.validate(release)
        assert len(violations) == len(release.tracks) + 1

        mockito.unstub()

    def test_validate_release_date(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release(date="")

        violations = validator.validate(release)
        assert len(violations) == 2

        mockito.unstub()

    def test_validate_blank_artists(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).artists = []

        violations = validator.validate(release)
        assert len(violations) == 1

        mockito.unstub()

    def test_validate_blank_track_title(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).track_title = ""

        violations = validator.validate(release)
        assert len(violations) == 1

        mockito.unstub()

    def test_validate_release_artists(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).release_artists = []

        violations = validator.validate(release)
        assert len(violations) == 1

        mockito.unstub()

    def test_validate_release_title(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release(release_title="")

        violations = validator.validate(release)
        assert len(violations) == 1

        mockito.unstub()

    def test_validate_lastfm_release_title(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release(release_title="mezzanine")

        violations = validator.validate(release)
        assert len(violations) == 1

        mockito.unstub()

    def test_validate_lastfm_release_tags(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release(genres=["genre 1"])

        violations = validator.validate(release)
        assert len(violations) == 1

    def test_validate_lastfm_artist_tags_fallback(self):
        validator = ReleaseValidator(get_lastfmcache(genres_release=OrderedDict()))

        release = create_test_release(genres=["genre 1"])

        violations = validator.validate(release)
        assert len(violations) == 1


    def test_validate_invalid_track_numbers(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).track_number = 2

        violations = validator.validate(release)
        assert len(violations) == 1

        mockito.unstub()

    def test_validate_missing_total_tracks(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).total_tracks = None

        violations = validator.validate(release)
        assert len(violations) == 1

        mockito.unstub()

    def test_validate_invalid_disc_numbers(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).disc_number = 3

        violations = validator.validate(release)
        assert len(violations) > 0

        mockito.unstub()

    def test_validate_tag_types(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).stream_info.tag_type = TagType.FLAC

        violations = validator.validate(release)
        assert len(violations) > 0

        mockito.unstub()

    def test_validate_cbr_bitrates(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).stream_info.bitrate = 160000

        violations = validator.validate(release)
        assert len(violations) == 1

        mockito.unstub()

    def test_fix(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release(release_title="mezzanine", date="")
        fixed = validator.fix(release)
        assert fixed != release

        mockito.unstub()

    def test_lastfm_fix_track_title(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).track_title = "An incorrect track title"
        fixed = validator.fix(release)
        assert fixed != release

        mockito.unstub()

    def test_lastfm_fix_track_title_lowercase(self):
        validator = ReleaseValidator(get_lastfmcache())

        release = create_test_release()
        next(iter(release.tracks.values())).track_title = "angel"
        fixed = validator.fix(release)
        assert fixed != release

        mockito.unstub()

from enum import Enum


class ReleaseCategory(Enum):
    ALBUM = 'Album'
    ANTHOLOGY = 'Anthology'
    BOOTLEG = 'Bootleg'
    COMPILATION = 'Compilation'
    CONCERT_RECORDING = 'Concert Recording'
    DEMO = 'Demo'
    EP = 'EP'
    GAME_SOUNDTRACK = 'Game Soundtrack'
    INTERVIEW = 'Interview'
    LIVE_ALBUM = 'Live Album'
    MIX = 'Mix'
    MIXTAPE = 'Mixtape'
    REMIX = 'Remix'
    SINGLE = 'Single'
    SOUNDTRACK = 'Soundtrack'
    UNKNOWN = 'Unknown'

audio_extensions = {'.mp3', '.flac', '.aac', '.mp4', '.m4a', '.m4b', '.m4p', '.mmf', '.mpc' '.wav', '.ape', '.wv',
                    '.aiff', '.au', '.pcm', '.wma', '.aa', '.aax', '.alac', '.amr', '.au', '.awb', '.dct', '.dss',
                    '.dvf', '.gsm', '.iklax', '.ivs', '.ogg', '.oga', '.mogg', '.ra', '.sln', '.tta', '.8svx'}


class ViolationType(Enum):
    ARTIST_WHITESPACE = 'artist-whitespace'
    RELEASE_ARTIST_WHITESPACE = 'release-artist-whitespace'
    DATE_WHITESPACE = 'date-whitespace'
    RELEASE_TITLE_WHITESPACE = 'release-title-whitespace'
    TRACK_TITLE_WHITESPACE = 'track-title-whitespace'
    GENRE_WHITESPACE = 'genre-whitespace'
    DATE_INCONSISTENT = 'date-inconsistent'
    ARTIST_BLANK = 'artist'
    TRACK_TITLE_BLANK = 'track-title'
    RELEASE_ARTIST_INCONSISTENT = 'release-artist'
    RELEASE_ARTIST_SPELLING = 'release-artist-spelling'
    RELEASE_ARTIST_NOT_FOUND = 'release-artist-not-found'
    RELEASE_TITLE_INCONSISTENT = 'release-title-inconsistent'
    RELEASE_TITLE_SPELLING = 'release-title-spelling'
    DATE_INCORRECT = 'date-incorrect'
    BAD_GENRES = 'bad-genres'
    INCORRECT_TRACK_TITLE = 'incorrect-track-title'
    TRACK_ARTIST_SPELLING = 'track-artist-spelling'
    MISSING_TRACKS = 'missing-tracks'
    TOTAL_TRACKS_INCONSISTENT = 'total-tracks'
    MISSING_DISCS = 'missing-discs'
    TOTAL_DISCS_INCONSISTENT = 'total-discs'
    TAG_TYPES_INCONSISTENT = 'tag-types'
    CODECS_INCONSISTENT = 'codecs'
    CBR_INCONSISTENT = 'cbr'
    FILENAME = 'filename'

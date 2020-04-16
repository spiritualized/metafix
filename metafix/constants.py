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
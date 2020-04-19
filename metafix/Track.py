from typing import List

from cleartag import Track as cleartagTrack
from metafix.functions import unique


class Track(cleartagTrack):

    def strip_whitespace_artists(self) -> List[str]:
        return unique([x.strip() for x in self.artists])

    def strip_whitespace_release_artists(self) -> List[str]:
        return unique([x.strip() for x in self.release_artists])

    def strip_whitespace_date(self) -> str:
        return None if not self.date else self.date.strip()

    def strip_whitespace_release_title(self) -> str:
        return None if not self.release_title else self.release_title.strip()

    def strip_whitespace_track_title(self) -> str:
        return None if not self.track_title else self.track_title.strip()

    def strip_whitespace_genres(self) -> List[str]:
        return unique([x.strip() for x in self.genres])

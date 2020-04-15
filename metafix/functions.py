import os
import re
from collections import OrderedDict
from typing import List, Dict, Tuple, Optional

from metafix.constants import audio_extensions, ReleaseCategory


def unique(seq: List):
    sorted_items = []
    out_items = []

    for item in seq:
        if not hasattr(item, "__iter__") or isinstance(item, str):
            if item not in out_items:
                out_items.append(item)
        else:
            s_item = sorted(item)
            if s_item not in sorted_items:
                sorted_items.append(s_item)
                out_items.append(item)
    return out_items

def normalize_track_title(str):
    return normalize_str(str)


def normalize_artist_name(str):
    return normalize_str(str)


def normalize_str(music_str):
    if not music_str:
        return ""
    music_str = re.sub("(?i) feat(.)?( )?", " feat. ", music_str)
    music_str = re.sub("(?i)\(feat(.)?( )?", "(feat. ", music_str)
    music_str = re.sub("(?i)( )?vs(.)?( )?", " vs. ", music_str)
    music_str = ' '.join(music_str.replace("/", " / ").split())
    music_str = music_str.strip()

    return music_str

def normalise_path_chars(str_in):
    tmp = str_in

    replacements = {
        ':': '：',
        '/': '∕'
    }

    for x in replacements:
        tmp = tmp.replace(x, replacements[x])

    return tmp

def lastfm_flatten_artists(artists: List[str]) -> str:

    if len(artists) == 1:
        return artists[0]
    elif len(artists) == 2:
        return "{0} & {1}".format(artists[0], artists[1])
    else:
        return "{0} & {1}".format(", ".join(artists[0:-2]), artists[-1])


def split_release_title(release_title_full):
    release_title = release_title_full
    release_edition = ""

    edition_match = re.search(r"([({[]{1}[\w\-_ ]+[)}\]]{1})$", release_title_full)
    if edition_match:
        release_edition = edition_match.groups()[0]
        release_title = release_title_full.replace(release_edition, "").strip()

    return release_title, release_edition


def get_category_fix_name(release: "Release") -> Tuple[str, Optional[ReleaseCategory]]:
    clean_name = re.sub(r"[\[{( ]{1}web[\]})]?", "",
                        release.tracks[next(iter(release.tracks))].release_title, flags=re.I)

    lower_name = clean_name.lower()

    if lower_name.endswith(" ep"):
        return clean_name[0:-3].strip(), ReleaseCategory.EP
    elif lower_name.endswith("(ep)") or lower_name.endswith("[ep]") or lower_name.endswith("{ep}"):
        return clean_name[0:-4].strip(), ReleaseCategory.EP
    elif lower_name.endswith(" single"):
        return clean_name[0:-7].strip(), ReleaseCategory.SINGLE
    elif lower_name.endswith(" cds"):
        return clean_name[0:-4].strip(), ReleaseCategory.SINGLE
    elif lower_name.endswith(" (cds)") or lower_name.endswith("(cds)") or lower_name.endswith("{cds}"):
        return clean_name[0:-6].strip(), ReleaseCategory.SINGLE

    return clean_name, None


def tag_filter(tag: str, ignore_substrings: List[str], capitalize:bool):

    for curr_ignore in ignore_substrings:
        if tag.lower() in curr_ignore.lower() or curr_ignore.lower() in tag.lower():
            return None

    if tag.isdigit() and len(tag) == 4:
        return None

    if tag.lower() in ['seen live', 'favourites', 'all', 'awesome', 'love', 'spotify', 'favorite', 'favourite', 'fun',
                       'check out', 'sexy', 'amazing',
                       'genius', 'dj', 'want to see live', 'shit', 'officially shit',
                       'lesser known yet streamable artists', '<3', 'crap',
                       'bands i\'ve seen live', 'seen in concert', 'listen', 'good music', 'saw live', 'local',
                       'fuck off', 'hipster garbage', 'mp3',

                       'masterpiece', 'laptop', 'wishlist', 'cds i own', 'beautiful', 'epic', 'classic',
                       'records i own', 'playlist', 'cd', 'cool', 'great',
                       'good', 'own', 'emusic', 'i own this cd', 'own it', 'love at first listen', 'underrated',
                       'fucking awesome', 'in my collection', 'check',
                       'my private work station', 'top cd', 'fav', 'love it', 'happy', 'owned', 'mandatory', 'the best',
                       'streamable', 'collected', 'reviewed in the guardian',
                       'to check out', 'overrated', 'to buy', 'i own', '1', 'favs', 'essential', '5', 'music',
                       'my music', 'music to download', ]:
        return None

    for substring in ['artist', 'bpm', 'best of', 'album', 'favorite', 'favourite', 'vinyl', 'seen ', 'albun', 'need']:
        if substring in tag:
            return None

    tag_remap = {
        'crossover': 'fusion',
        'drum \'n bass': 'drum and bass',
        'drum \'n\' bass': 'drum and bass',
        'drum & bass': 'drum and bass',
        'drum n bass': 'drum and bass',
        'drum n\' bass': 'drum and bass',
        'drum\'n bass': 'drum and bass',
        'drum\'n\'bass': 'drum and bass',
        'drum&bass': 'drum and bass',
        'drumandbass': 'drum and bass',
        'drumm and bass': 'drum and bass',
        'drumm n bass': 'drum and bass',
        'drumn and bass': 'drum and bass',
        'drumnbass': 'drum and bass',
        'drums and base': 'drum and bass',
        'drums and bass': 'drum and bass',
        'dnb': 'drum and bass',
        'd&b': 'drum and bass',
        'd\'n\'b': 'drum and bass',
        'hip-hop': 'hip hop',
        'hiphop': 'hip hop',
        'triphop': 'trip-hop',
        'trip hop': 'trip-hop',
    }

    if tag in tag_remap:
        tag = tag_remap[tag]

    if capitalize:
        tag = capitalize_tag(tag)

        tag_allcaps = ["av", "uk"]

        if tag.lower() in tag_allcaps:
            tag = tag.upper()

    return tag


def tag_filter_all(tags: Dict[str, int], ignore_substrings: List[str], capitalize=False):
    accepted_tags = OrderedDict()
    for tag in tags:
        curr_tag = tag_filter(tag, ignore_substrings, capitalize)

        # If the tag was filtered, mark as ignore
        if not curr_tag:
            continue

        # If a remapped tag clashes with another, and its score is lower, mark as ignore
        if curr_tag in accepted_tags and accepted_tags[curr_tag] > tags[tag]:
            continue
        accepted_tags[curr_tag] = tags[tag]

    return accepted_tags

non_capitalized = ["a", "an", "the", "and", "but", "or", "for", "nor", "in", "to", "at" "on", "by", "from", "nor",
                   "yet", "so"]

def capitalize_tag(tag_str):
    words = [x.capitalize() if x not in non_capitalized else x for x in tag_str.split(" ")]
    if len(words):
        words[0] = words[0].capitalize()

    return " ".join(words)

def extract_track_disc(filename):
    track = None
    disc = None

    match = re.match(r"^(\d{2,4})", filename)
    if match:
        track = int(match[0][-2:])
    if match and len(match[0]) > 2:
        disc = int(match[0][:-2])

    return track, disc

def has_audio_extension(path):
    return os.path.splitext(path)[1].lower() in audio_extensions
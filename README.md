# metafix

Provides validation and safe, automated repair of audio metadata. Supports MP3, FLAC, and other popular formats.

```python
path = "/path/to/my/album"
files = {}

for file in list_files(path):
    audio[file] = cleartag.read_tags(os.path.join(path_param, file))
    audio[file].__class__ = Track
    
    # Create the release
    release = Release(audio)

    # Initialize LastFM and create a validator
    lastfm = LastfmCache("lastfm_api_key", "lastfm_shared_secret")
    lastfm.enable_file_cache()
    validator = ReleaseValidator(lastfm)

    # Get a list of metadata validation failures
    failures = validator.validate(release)

    # Fix as many validation problems as possible
    fixed_release = validator.fix(release)
    
    # Get the correct folder name
    print(fixed_release.get_folder_name())


# helper functions
def list_files(parent_dir: str) -> List[str]:
    file_list = []
    list_files_inner(parent_dir, None, file_list)

    return file_list


def list_files_inner(parent, path, file_list) -> None:
    joined_path = os.path.join(parent, path) if path else parent
    for curr in os.scandir(joined_path):
        if curr.is_file():
            file_list.append(os.path.relpath(curr.path, parent))
        elif curr.is_dir():
            list_files_inner(parent, curr.path, file_list)

```
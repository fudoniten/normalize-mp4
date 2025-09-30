# normalize-mp4

`normalize-mp4` scans a directory tree for video files and copies/moves them
into a media-server-friendly structure based on duration and basic metadata.
The project now ships as an installable Python package with a reusable library
API, a command-line entrypoint, and tooling to build standalone archives.

## Installation

```bash
pip install .
```

This installs the `normalize-mp4` command as well as the library module.  The
runtime requires Python 3.10+ and the `ffmpeg` command-line tools.

### Editable/development install

```bash
pip install -e .[dev]
```

## Command-line usage

```bash
normalize-mp4 \
  /path/to/incoming \
  /path/to/content \
  /path/to/filler \
  --filler-threshold 600 \
  --ffmpeg-bindir /opt/ffmpeg/bin \
  --show-name "Default Show"
```

Arguments:

- `directory`: directory to scan for media files.
- `content_dir`: destination for "long" videos (duration greater than the
  threshold).
- `filler_dir`: destination for short videos.
- `--filler-threshold`: seconds separating long vs. short content (default 600).
- `--ffmpeg-bindir`: directory that contains `ffprobe` and `ffmpeg`.
- `--show-name`: fallback show name when metadata is missing.
- `--move`: move files instead of copying.
- `--overwrite`: allow overwriting existing files.
- `--dry-run`: print planned actions without touching the filesystem.

## Library API

The package exposes reusable helpers in `normalize_mp4.core`.  For example:

```python
from pathlib import Path
from normalize_mp4 import Context, process_videos

ctx = Context(ffprobe_path=Path("/usr/bin/ffprobe"))
process_videos(
    basedir=Path("incoming"),
    content_dir=Path("library/content"),
    filler_dir=Path("library/filler"),
    filler_threshold=600,
    default_show_name="Variety Hour",
    ctx=ctx,
    move=False,
    overwrite=False,
    dry_run=False,
)
```

## Building a single-file archive

You can create a [zipapp](https://docs.python.org/3/library/zipapp.html)
directly from the source tree.  The resulting `.pyz` file can be copied to any
host that has Python 3.10+ available:

```bash
python -m zipapp src -m normalize_mp4.__main__:main -o normalize-mp4.pyz
```

Then run the archive with `python normalize-mp4.pyz ...`.

## Nix flake

For NixOS development hosts, the repository includes a `flake.nix` that
provides both a development shell and a buildable package:

```bash
nix develop
# or
nix build
```

The development shell bundles Python, Hatch, pytest, ffmpeg, and the
dependencies necessary to work on the project.

## Running tests

```bash
pytest
```

Pytest-based unit tests cover the core helper functions.

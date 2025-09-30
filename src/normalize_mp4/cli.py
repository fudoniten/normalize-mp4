"""Command line interface for normalize-mp4."""
from __future__ import annotations

import argparse
from pathlib import Path

from .core import Context, process_videos


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Categorize and move/copy video files by duration.",
    )
    parser.add_argument("directory", type=Path, help="Directory to search for video files.")
    parser.add_argument("content_dir", type=Path, help="Directory for long videos (scheduled content).")
    parser.add_argument("filler_dir", type=Path, help="Directory for short videos (filler).")
    parser.add_argument("--filler_threshold", type=int, default=600, help="Seconds separating long vs short.")
    parser.add_argument("--ffmpeg-bindir", dest="ffmpeg_bindir", type=Path, required=True, help="Path to the ffmpeg bin directory.")
    parser.add_argument("--show-name", dest="show_name", type=str, default="Show", help="Default show name when missing in metadata.")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    ffprobe_path = args.ffmpeg_bindir / "ffprobe"
    if not ffprobe_path.exists():
        parser.error(f"ffprobe not found at {ffprobe_path}")

    ctx = Context(ffprobe_path=ffprobe_path)
    process_videos(
        basedir=args.directory,
        content_dir=args.content_dir,
        filler_dir=args.filler_dir,
        filler_threshold=args.filler_threshold,
        default_show_name=args.show_name,
        ctx=ctx,
        move=args.move,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

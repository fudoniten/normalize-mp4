import os
import shutil
import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import ffmpeg

SAFE_CHARS = "-_.() "
REPLACE_WITH = "—"  # em dash for banned chars

@dataclass
class Context:
    ffprobe_path: Path

def _sanitize(name: str) -> str:
    # Replace problematic filesystem characters
    return "".join(
        c if c.isalnum() or c in SAFE_CHARS else REPLACE_WITH
        for c in name.strip()
    ).strip()

def _parse_creation_time(s: str | None) -> datetime | None:
    if not s:
        return None
    # Try a few common ffprobe formats
    candidates = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",  # some muxers
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    # Fallback: strip trailing Z and try fromisoformat
    try:
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        return None

def get_video_metadata(ctx: Context, file_path: Path) -> dict | None:
    try:
        probe = ffmpeg.probe(str(file_path), cmd=str(ctx.ffprobe_path))
        fmt = probe.get("format", {})
        streams = probe.get("streams", [])

        # Duration: prefer format duration, then video stream duration
        dur = None
        if "duration" in fmt:
            try:
                dur = float(fmt["duration"])
            except (TypeError, ValueError):
                pass
        if dur is None:
            vstreams = [s for s in streams if s.get("codec_type") == "video"]
            if vstreams and "duration" in vstreams[0]:
                try:
                    dur = float(vstreams[0]["duration"])
                except (TypeError, ValueError):
                    pass

        if dur is None:
            raise ValueError("Unable to determine duration from ffprobe output")

        tags = fmt.get("tags", {}) or {}
        show_name = tags.get("show") or tags.get("album") or "Unknown Show"
        episode_name = tags.get("title") or file_path.stem
        creation_time = _parse_creation_time(tags.get("creation_time"))
        year = (creation_time or datetime.fromtimestamp(file_path.stat().st_mtime)).year
        date_str = (creation_time or datetime.fromtimestamp(file_path.stat().st_mtime)).strftime("%Y-%m-%d")

        return {
            "video_length": float(dur),
            "show_name": show_name,
            "episode_name": episode_name,
            "creation_time": creation_time.isoformat() if creation_time else None,
            "year": year,
            "date_str": date_str,
            "ext": file_path.suffix.lower(),
        }
    except ffmpeg.Error as e:
        print(f"[ffprobe] {file_path}: {e.stderr.decode('utf-8', errors='ignore') if getattr(e, 'stderr', None) else e}", flush=True)
    except Exception as e:
        print(f"[error] {file_path}: {e}", flush=True)
    return None

def generate_new_path(target_dir: Path, show_name: str, episode_name: str, year: int, date_str: str, ext: str) -> Path:
    safe_show = _sanitize(show_name) or "Unknown Show"
    safe_episode = _sanitize(episode_name) or "Episode"
    season = f"{year}"
    filename = f"{date_str} {safe_episode} ({year}){ext}"
    return target_dir / safe_show / season / filename

def copy_or_move(src: Path, dst: Path, move: bool = False, overwrite: bool = False) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    final = dst
    if not overwrite:
        i = 1
        while final.exists():
            final = dst.with_stem(f"{dst.stem} [{i}]")
            i += 1
    try:
        if move:
            shutil.move(str(src), str(final))
        else:
            shutil.copy2(str(src), str(final))
        print(f"{'moved' if move else 'copied'}: {src} -> {final}")
        return True
    except Exception as e:
        print(f"[copy/move error] {src} -> {final}: {e}", flush=True)
        return False

def process_videos(basedir: Path, content_dir: Path, filler_dir: Path, filler_threshold: int,
                   default_show_name: str, ctx: Context, *, move: bool, overwrite: bool, dry_run: bool):
    for root, _, files in os.walk(basedir):
        for fname in files:
            file_path = Path(root) / fname
            if file_path.suffix.lower() not in {".mp4", ".mkv", ".s"}:
                print(f"skipping nonvideo file {file_path}")
                continue
            meta = get_video_metadata(ctx, file_path)
            if not meta:
                print(f"metadata not found for file {file_path}")
                continue
            # Decide long vs short
            target_dir = content_dir if meta["video_length"] > float(filler_threshold) else filler_dir
            # Prefer metadata show name but fall back to user-provided default
            show_name = meta["show_name"] if meta["show_name"] and meta["show_name"] != "Unknown Show" else default_show_name
            # Preserve original extension unless you explicitly remux
            ext = meta["ext"] if meta["ext"] in {".mp4", ".mkv"} else ".mp4"
            new_path = generate_new_path(target_dir, show_name, meta["episode_name"], meta["year"], meta["date_str"], ext)
            print(f"plan: {file_path} -> {new_path}  ({int(meta['video_length'])}s)")
            if not dry_run:
                copy_or_move(file_path, new_path, move=move, overwrite=overwrite)

def main():
    parser = argparse.ArgumentParser(description="Categorize and move/copy video files by duration.")
    parser.add_argument("directory", type=Path, help="Directory to search for video files.")

    parser.add_argument("content_dir", type=Path, help="Directory for long videos (scheduled content).")
    parser.add_argument("filler_dir", type=Path, help="Directory for short videos (filler).")
    parser.add_argument("--filler_threshold", type=int, default=600, help="Seconds separating long vs short.")
    parser.add_argument("--ffmpeg_bindir", type=Path, required=True, help="Path to the ffmpeg bin directory.")
    parser.add_argument("--show_name", type=str, default="Show", help="Default show name when missing in metadata.")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing files.")
    args = parser.parse_args()

    ffprobe_path = args.ffmpeg_bindir / "ffprobe"
    if not ffprobe_path.exists():
        raise FileNotFoundError(f"ffprobe not found at {ffprobe_path}")

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

if __name__ == "__main__":
    main()

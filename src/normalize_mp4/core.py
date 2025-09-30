"""Core functionality for normalize-mp4.

This module exposes pure-Python helpers that can be reused by both the
command-line interface as well as by external callers.  The functions are
largely a refactor of the original single-file script and are intentionally
kept free of CLI side-effects so that they are straightforward to unit test.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import ffmpeg

SAFE_CHARS = "-_.() "
REPLACE_WITH = "—"  # em dash for banned chars
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".s"}


@dataclass(slots=True)
class Context:
    """Container for configuration shared across helper functions."""

    ffprobe_path: Path


def _sanitize(name: str) -> str:
    """Return a filesystem-safe variant of *name*."""

    return "".join(
        c if c.isalnum() or c in SAFE_CHARS else REPLACE_WITH
        for c in name.strip()
    ).strip()


def _parse_creation_time(value: str | None) -> datetime | None:
    if not value:
        return None

    formats = (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return None


def get_video_metadata(ctx: Context, file_path: Path) -> dict | None:
    """Query *file_path* via ``ffprobe`` and normalize the returned metadata."""

    try:
        probe = ffmpeg.probe(str(file_path), cmd=str(ctx.ffprobe_path))
    except ffmpeg.Error as exc:  # pragma: no cover - exercised in integration use
        message = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else str(exc)
        print(f"[ffprobe] {file_path}: {message}", flush=True)
        return None
    except Exception as exc:  # pragma: no cover - exercised in integration use
        print(f"[error] {file_path}: {exc}", flush=True)
        return None

    fmt = probe.get("format", {})
    streams = probe.get("streams", [])

    duration = _coerce_duration(fmt)
    if duration is None:
        duration = _duration_from_streams(streams)

    if duration is None:
        print(f"[error] {file_path}: Unable to determine duration from ffprobe output", flush=True)
        return None

    tags = fmt.get("tags", {}) or {}
    show_name = tags.get("show") or tags.get("album") or "Unknown Show"
    episode_name = tags.get("title") or file_path.stem

    creation_time = _parse_creation_time(tags.get("creation_time"))
    fallback_dt = datetime.fromtimestamp(file_path.stat().st_mtime)
    timestamp = creation_time or fallback_dt

    return {
        "video_length": float(duration),
        "show_name": show_name,
        "episode_name": episode_name,
        "creation_time": creation_time.isoformat() if creation_time else None,
        "year": timestamp.year,
        "date_str": timestamp.strftime("%Y-%m-%d"),
        "ext": file_path.suffix.lower(),
    }


def _coerce_duration(fmt: dict) -> float | None:
    duration = fmt.get("duration")
    if duration is None:
        return None
    try:
        return float(duration)
    except (TypeError, ValueError):
        return None


def _duration_from_streams(streams: Iterable[dict]) -> float | None:
    for stream in streams:
        if stream.get("codec_type") != "video":
            continue
        candidate = stream.get("duration")
        if candidate is None:
            continue
        try:
            return float(candidate)
        except (TypeError, ValueError):
            continue
    return None


def generate_new_path(
    target_dir: Path,
    show_name: str,
    episode_name: str,
    year: int,
    date_str: str,
    ext: str,
) -> Path:
    safe_show = _sanitize(show_name) or "Unknown Show"
    safe_episode = _sanitize(episode_name) or "Episode"
    season = f"{year}"
    filename = f"{date_str} {safe_episode} ({year}){ext}"
    return target_dir / safe_show / season / filename


def copy_or_move(src: Path, dst: Path, *, move: bool = False, overwrite: bool = False) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    final_path = dst
    if not overwrite:
        index = 1
        while final_path.exists():
            final_path = dst.with_stem(f"{dst.stem} [{index}]")
            index += 1
    try:
        if move:
            from shutil import move as _move

            _move(str(src), str(final_path))
        else:
            from shutil import copy2 as _copy2

            _copy2(str(src), str(final_path))
        print(f"{'moved' if move else 'copied'}: {src} -> {final_path}")
        return True
    except Exception as exc:  # pragma: no cover - exercised in integration use
        print(f"[copy/move error] {src} -> {final_path}: {exc}", flush=True)
        return False


def process_videos(
    basedir: Path,
    content_dir: Path,
    filler_dir: Path,
    filler_threshold: int,
    default_show_name: str,
    ctx: Context,
    *,
    move: bool,
    overwrite: bool,
    dry_run: bool,
) -> None:
    for root, files in _walk_videos(basedir):
        for fname in files:
            file_path = Path(root) / fname
            metadata = get_video_metadata(ctx, file_path)
            if not metadata:
                print(f"metadata not found for file {file_path}")
                continue

            target_dir = content_dir if metadata["video_length"] > float(filler_threshold) else filler_dir
            show_name = (
                metadata["show_name"]
                if metadata["show_name"] and metadata["show_name"] != "Unknown Show"
                else default_show_name
            )

            ext = metadata["ext"] if metadata["ext"] in {".mp4", ".mkv"} else ".mp4"
            new_path = generate_new_path(
                target_dir,
                show_name,
                metadata["episode_name"],
                metadata["year"],
                metadata["date_str"],
                ext,
            )
            print(f"plan: {file_path} -> {new_path}  ({int(metadata['video_length'])}s)")
            if not dry_run:
                copy_or_move(file_path, new_path, move=move, overwrite=overwrite)


def _walk_videos(basedir: Path):
    for root, _, files in os.walk(basedir):
        filtered = [f for f in files if Path(f).suffix.lower() in VIDEO_EXTENSIONS]
        yield root, filtered
__all__ = [
    "Context",
    "VIDEO_EXTENSIONS",
    "copy_or_move",
    "generate_new_path",
    "get_video_metadata",
    "process_videos",
]

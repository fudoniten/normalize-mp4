"""normalize-mp4 package."""

from .core import (
    Context,
    VIDEO_EXTENSIONS,
    copy_or_move,
    generate_new_path,
    get_video_metadata,
    process_videos,
)

__all__ = [
    "Context",
    "VIDEO_EXTENSIONS",
    "copy_or_move",
    "generate_new_path",
    "get_video_metadata",
    "process_videos",
]

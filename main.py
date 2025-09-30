import os
from dataclasses import dataclass
import sys
import shutil
import ffmpeg
from datetime import datetime
from pathlib import Path
import argparse

@dataclass
class Context:
    ffmpeg_path: str
    ffprobe_path: str

def get_video_metadata(ctx, file_path):
    try:
        probe = ffmpeg.probe(file_path, cmd=ctx.ffprobe_path)
        video_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'video']
        if not video_streams:
            raise ValueError("No video stream found")
        video_length = float(video_streams[0]['duration'])
        # Attempt to extract show and episode names from metadata
        show_name = probe['format'].get('tags', {}).get('show', 'Unknown Show')
        episode_name = probe['format'].get('tags', {}).get('title', file_path.stem)
        creation_time = probe['format'].get('tags', {}).get('creation_time', None)
        year = datetime.strptime(creation_time, "%Y-%m-%dT%H:%M:%S.%fZ").year if creation_time else datetime.now().year
        return {
            'video_length': video_length,
            'show_name': show_name,
            'episode_name': episode_name,
            'creation_time': creation_time,
            'year': year,
            'video_length': video_length,
        }
    except ffmpeg.Error as e:
        print(f"Error getting video length: {e}")
        return None

def generate_new_path(target_dir, show_name, episode_name, year):
    new_name = f"{show_name}/{date_str} {episode_name} ({year}).mp4"
    target_path = target_dir / new_name
    return target_path

def rename_file(file_path, target_path):
    print(f"renaming {file_path} -> {target_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy(file_path, target_path)
        return True
    except Error as e:
        print(f"Error copying file {file_path}: {e}")
        return False

def process_videos(basedir, content_dir, filler_dir, filler_threshold, show_name, ffmpeg_bindir, args):
    for root, _, files in os.walk(basedir):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() in ['.mp4', '.mkv', '.s']:
                metadata = get_video_metadata(file_path, ffmpeg_path)
                target_dir = long_dir if metadata['video_length'] > filler_threshold else short_dir
                show_name = metadata['show_name'] or show_name
                new_path = generate_new_path(target_dir, show_name, metadata['episode_name'], metadata['year'])
                rename_file(file_path, new_path)

def main():
    parser = argparse.ArgumentParser(description="Categorize and move video files.")
    parser.add_argument("directory", type=str, help="Directory to search for video files.")
    parser.add_argument("content_dir", type=str, help="Directory to move scheduled content (long videos).")
    parser.add_argument("filler_dir", type=str, help="Directory to move filler content (short videos).")
    parser.add_argument("--filler_threshold", type=int, default=600, help="Duration in seconds to distinguish scheduled and filler content.")
    parser.add_argument("--ffmpeg_bindir", type=str, required=True, help="Path to the ffmpeg bin directory.")
    parser.add_argument("--show_name", type=str, default="Show", help="Name of the show for renaming files.")
    
    args = parser.parse_args()

    ctx = Context(f"{ffmpeg_bindir}/ffmpeg", f"{ffmpeg_bindir}/ffprobe")
    if not (Path(ctx.ffmpeg_path).exists() and Path(ctx.ffprobe_path).exists()):
        raise Exception("ffmpeg binaries not found")
    
    process_videos(Path(args.directory), Path(args.content_dir), Path(args.filler_dir), args.filler_threshold, args.show_name, args.ffmpeg_bindir, args)

if __name__ == "__main__":
    main()

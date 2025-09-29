import os
import sys
import shutil
import ffmpeg
from datetime import datetime
from pathlib import Path
import argparse

def get_video_metadata(file_path, ffmpeg_path):
    try:
        probe = ffmpeg.probe(file_path, cmd=ffmpeg_path)
        video_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'video']
        if not video_streams:
            raise ValueError("No video stream found")
        video_length = float(video_streams[0]['duration'])
        # Attempt to extract show and episode names from metadata
        show_name = probe['format'].get('tags', {}).get('show', 'Unknown Show')
        episode_name = probe['format'].get('tags', {}).get('title', file_path.stem)
        return video_length, show_name, episode_name
    except ffmpeg.Error as e:
        print(f"Error getting video length: {e}")
        return 0

def move_and_rename_file(file_path, target_dir, show_name, episode_name, year):
    date_str = datetime.now().strftime("%Y-%m-%d")
    new_name = f"{show_name}/{date_str} {show_name} - {episode_name} {year}/{episode_name}.mp4"
    target_path = target_dir / new_name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(file_path, target_path)

def process_videos(directory, long_dir, short_dir, break_duration, show_name, ffmpeg_path, args):
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() in ['.mp4', '.mkv', '.avi']:  # Add more extensions if needed
                video_length, show_name, episode_name = get_video_length(file_path, ffmpeg_path)
                target_dir = long_dir if video_length > break_duration else short_dir
                year = datetime.now().year
                move_and_rename_file(file_path, target_dir, args.show_name or show_name, episode_name, year)

def main():
    parser = argparse.ArgumentParser(description="Categorize and move video files.")
    parser.add_argument("directory", type=str, help="Directory to search for video files.")
    parser.add_argument("long_dir", type=str, help="Directory to move scheduled content (long videos).")
    parser.add_argument("short_dir", type=str, help="Directory to move filler content (short videos).")
    parser.add_argument("--break_duration", type=int, default=600, help="Duration in seconds to distinguish scheduled and filler content.")
    parser.add_argument("--ffmpeg_path", type=str, required=True, help="Path to the ffmpeg executable.")
    parser.add_argument("--show_name", type=str, default="Show", help="Name of the show for renaming files.")
    
    args = parser.parse_args()
    
    process_videos(Path(args.directory), Path(args.long_dir), Path(args.short_dir), args.break_duration, args.show_name, args.ffmpeg_path, args)

if __name__ == "__main__":
    main()

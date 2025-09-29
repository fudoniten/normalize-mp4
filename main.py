import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
import argparse

def get_video_length(file_path):
    # Placeholder function to get video length in seconds
    # You can use a library like moviepy or ffmpeg to implement this
    return 600  # Example: 10 minutes

def move_and_rename_file(file_path, target_dir, show_name, episode_name, year):
    date_str = datetime.now().strftime("%Y-%m-%d")
    new_name = f"{show_name}/{date_str} {show_name} - {episode_name} {year}/{episode_name}.mp4"
    target_path = target_dir / new_name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(file_path, target_path)

def process_videos(directory, long_dir, short_dir, break_duration, show_name):
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() in ['.mp4', '.mkv', '.avi']:  # Add more extensions if needed
                video_length = get_video_length(file_path)
                target_dir = long_dir if video_length > break_duration else short_dir
                episode_name = file_path.stem
                year = datetime.now().year
                move_and_rename_file(file_path, target_dir, show_name, episode_name, year)

def main():
    parser = argparse.ArgumentParser(description="Categorize and move video files.")
    parser.add_argument("directory", type=str, help="Directory to search for video files.")
    parser.add_argument("long_dir", type=str, help="Directory to move long videos.")
    parser.add_argument("short_dir", type=str, help="Directory to move short videos.")
    parser.add_argument("--break_duration", type=int, default=600, help="Duration in seconds to distinguish long and short videos.")
    parser.add_argument("--show_name", type=str, default="Show", help="Name of the show for renaming files.")
    
    args = parser.parse_args()
    
    process_videos(Path(args.directory), Path(args.long_dir), Path(args.short_dir), args.break_duration, args.show_name)

if __name__ == "__main__":
    main()

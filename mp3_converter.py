#!/usr/bin/env python3
"""
Convert all MP4/M4A files in a folder to MP3, preserving tags and filenames.
Requires: ffmpeg installed on your system.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def get_ffmpeg():
    """Check that ffmpeg is available."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return "ffmpeg"
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Error: ffmpeg not found. Install it with:")
        print("  macOS:   brew install ffmpeg")
        print("  Ubuntu:  sudo apt install ffmpeg")
        print("  Windows: https://ffmpeg.org/download.html")
        sys.exit(1)


def convert_file(src: Path, dest_dir: Path, bitrate: str, overwrite: bool) -> bool:
    """Convert a single MP4/M4A file to MP3."""
    dest = dest_dir / (src.stem + ".mp3")

    if dest.exists() and not overwrite:
        print(f"  [skip]  {dest.name} already exists (use --overwrite to replace)")
        return False

    cmd = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-i", str(src),
        "-vn",
        "-ab", bitrate,
        "-map_metadata", "0",
        "-id3v2_version", "3",
        str(dest),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [ok]    {src.name}  →  {dest.name}")
        return True
    else:
        print(f"  [fail]  {src.name}")
        for line in result.stderr.splitlines():
            if "Error" in line or "error" in line or "Invalid" in line:
                print(f"          {line.strip()}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convert MP4/M4A files to MP3 while preserving tags and filenames."
    )
    parser.add_argument(
        "--letter",
        action="store_true",
        help="Process all albums under current letter directory"
    )
    parser.add_argument(
        "--artist",
        action="store_true",
        help="Process all albums under current artist directory"
    )
    parser.add_argument(
        "--album",
        action="store_true",
        help="Process current album directory"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output folder for MP3s (default: same as input folder)",
    )
    parser.add_argument(
        "-b", "--bitrate",
        default="320k",
        help="MP3 bitrate (default: 320k)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing MP3 files",
    )
    
    args = parser.parse_args()
    
    current_dir = Path.cwd()
    
    if args.letter:
        # Process: letter/artist/album
        folders = []
        for artist in current_dir.iterdir():
            if artist.is_dir():
                for album in artist.iterdir():
                    if album.is_dir():
                        folders.append(album)
    elif args.artist:
        # Process: artist/album
        folders = [album for album in current_dir.iterdir() if album.is_dir()]
    elif args.album:
        # Process: current album
        folders = [current_dir]
    else:
        print("Error: Must specify --letter, --artist, or --album")
        sys.exit(1)
    
    output_base = Path(args.output).expanduser().resolve() if args.output else current_dir
    
    get_ffmpeg()
    
    total_ok = 0
    total_fail = 0
    
    for folder in folders:
        # Print current album being processed
        if args.letter:
            # Show artist/album
            rel_path = folder.relative_to(current_dir)
            print(f"\nProcessing: {rel_path}")
        elif args.artist:
            # Show album name
            print(f"\nProcessing: {folder.name}")
        
        dest_dir = output_base if args.album else output_base / folder.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        files = [f for f in folder.iterdir() if f.suffix.lower() in {'.mp4', '.m4a'}]
        
        for f in files:
            if convert_file(f, dest_dir, args.bitrate, args.overwrite):
                total_ok += 1
            else:
                total_fail += 1
    
    print(f"\nDone — {total_ok} converted, {total_fail} failed.")


if __name__ == "__main__":
    main()

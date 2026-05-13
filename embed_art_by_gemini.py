#!/usr/bin/env python3

import os
import sys
import argparse
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC

def embed_artwork(album_path, replace_existing=False):
    """Embeds the first found image in the folder into all MP3s."""
    valid_extensions = ('.jpg', '.jpeg', '.png')
    image_file = None

    try:
        # Find the first valid image
        for f in os.listdir(album_path):
            if f.lower().endswith(valid_extensions):
                image_file = os.path.join(album_path, f)
                break
    except PermissionError:
        print(f"  [!] Permission denied: {album_path}")
        return

    if not image_file:
        # Silently skip folders without images
        return

    mime = 'image/jpeg' if image_file.lower().endswith(('.jpg', '.jpeg')) else 'image/png'

    try:
        with open(image_file, 'rb') as img:
            img_data = img.read()
    except Exception as e:
        print(f"  [!] Could not read image {image_file}: {e}")
        return

    mp3_files = [f for f in os.listdir(album_path) if f.lower().endswith('.mp3')]
    if not mp3_files:
        return

    print(f"  [+] Processing: {os.path.basename(album_path)} ({len(mp3_files)} files)")

    for f in sorted(mp3_files):
        mp3_path = os.path.join(album_path, f)
        try:
            audio = MP3(mp3_path, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()

            # Check for existing artwork frames
            has_artwork = any(frame.startswith("APIC") for frame in audio.tags.keys())

            if has_artwork and not replace_existing:
                continue

            audio.tags.delall("APIC")
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,
                    desc='Front Cover',
                    data=img_data
                )
            )
            audio.save()
        except Exception as e:
            print(f"    [!] Error in {f}: {e}")

def process_artist_folder(artist_path, replace_existing):
    """Iterates through album subdirectories."""
    # Check if this folder itself has MP3s (it's actually an album folder)
    if any(f.lower().endswith('.mp3') for f in os.listdir(artist_path)):
        embed_artwork(artist_path, replace_existing)
    else:
        # Otherwise, treat it as an Artist folder containing Album folders
        for item in sorted(os.listdir(artist_path)):
            album_path = os.path.join(artist_path, item)
            if os.path.isdir(album_path):
                embed_artwork(album_path, replace_existing)

def process_letter_folder(letter_path, replace_existing):
    """Processes a letter folder containing artist folders."""
    print(f"--- Processing letter folder: {os.path.basename(letter_path)} ---")
    for item in sorted(os.listdir(letter_path)):
        artist_path = os.path.join(letter_path, item)
        if os.path.isdir(artist_path):
            process_artist_folder(artist_path, replace_existing)

def main():
    parser = argparse.ArgumentParser(description="Universal MP3 Artwork Embedder")
    parser.add_argument("-r", "--replace", action="store_true", help="Replace existing artwork.")
    parser.add_argument("-l", "--level", type=int, choices=[1, 2], 
                       help="Processing level: 1=all artists in current letter folder, 2=single artist folder")
    args = parser.parse_args()

    current_dir = os.getcwd()

    if args.level == 1:
        # Level 1: Process all artists in the current letter folder
        print(f"--- Level 1 Mode: Processing all artists in {current_dir} ---")
        for item in sorted(os.listdir(current_dir)):
            artist_path = os.path.join(current_dir, item)
            if os.path.isdir(artist_path):
                process_artist_folder(artist_path, args.replace)
    elif args.level == 2:
        # Level 2: Process single artist folder (current directory is the artist folder)
        print(f"--- Level 2 Mode: Processing single artist: {os.path.basename(current_dir)} ---")
        process_artist_folder(current_dir, args.replace)
    else:
        # Default behavior: Smart detection for Single Artist or Single Album
        print(f"--- Smart Mode: Processing {current_dir} ---")
        process_artist_folder(current_dir, args.replace)

    print("\nProcessing complete.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)

#!/usr/bin/env python3

import os
import sys
import readline
from pathlib import Path

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TPE2, TALB, TDRC, TRCK, TPOS
except ImportError:
    print("Error: mutagen library not found.")
    print("Install it with: pip install mutagen")
    sys.exit(1)

def path_completer(text, state):
    """Tab completion for file paths"""
    line = readline.get_line_buffer()
    if line.startswith('~'):
        line = os.path.expanduser(line)

    if os.path.isdir(line):
        directory = line
        partial = ''
    else:
        directory = os.path.dirname(line) or '.'
        partial = os.path.basename(line)

    try:
        matches = []
        for item in os.listdir(directory):
            if item.startswith(partial):
                full_path = os.path.join(directory, item)
                matches.append(full_path + '/' if os.path.isdir(full_path) else full_path)
        return matches[state] if state < len(matches) else None
    except (OSError, PermissionError):
        return None

def setup_readline():
    readline.set_completer_delims('\t\n')
    readline.parse_and_bind('tab: complete')
    readline.set_completer(path_completer)

def get_mp3_files(folder):
    path = Path(folder)
    return sorted([f for f in path.glob('*.mp3')])

def get_common_tags(mp3_files):
    if not mp3_files: return None, None, None, None, None
    tags = {'TPE1': set(), 'TPE2': set(), 'TALB': set(), 'TDRC': set(), 'TPOS': set()}
    for mp3_file in mp3_files:
        try:
            audio = MP3(mp3_file, ID3=ID3)
            for key in tags:
                if key in audio: tags[key].add(str(audio[key]))
        except: pass
    return [list(tags[k])[0] if len(tags[k]) == 1 else None for k in ['TPE1', 'TPE2', 'TALB', 'TDRC', 'TPOS']]

def set_global_tags(mp3_files, artist, album_artist, album, year, disc):
    for mp3_file in mp3_files:
        try:
            audio = MP3(mp3_file, ID3=ID3)
            if artist: audio['TPE1'] = TPE1(encoding=3, text=artist)
            if album_artist: audio['TPE2'] = TPE2(encoding=3, text=album_artist)
            if album: audio['TALB'] = TALB(encoding=3, text=album)
            if year: audio['TDRC'] = TDRC(encoding=3, text=year)
            if disc: audio['TPOS'] = TPOS(encoding=3, text=disc)
            audio.save()
        except Exception as e:
            print(f"Error updating {mp3_file.name}: {e}")

def edit_track_tags(mp3_file, track_num):
    print(f"\nEditing: {mp3_file.name}")
    title = input(f"  New title (Enter to skip): ").strip()
    artist = input(f"  New artist (Enter to skip): ").strip()
    track = input(f"  Track number (Enter to skip): ").strip()
    
    try:
        audio = MP3(mp3_file, ID3=ID3)
        if title: audio['TIT2'] = TIT2(encoding=3, text=title)
        if artist: audio['TPE1'] = TPE1(encoding=3, text=artist)
        if track: audio['TRCK'] = TRCK(encoding=3, text=track)
        audio.save()
        print(f"  ✓ Updated")
    except Exception as e:
        print(f"  ✗ Error: {e}")

def get_albums_in_folder(folder):
    path = Path(folder)
    albums = []
    try:
        for item in path.iterdir():
            if item.is_dir():
                mp3_count = len(list(item.glob('*.mp3')))
                if mp3_count > 0: albums.append((item, mp3_count))
    except: pass
    return sorted(albums, key=lambda x: x[0].name)

def process_album(album_path):
    mp3_files = get_mp3_files(album_path)
    if not mp3_files: return
    
    print(f"\n--- Processing: {album_path.name} ---")
    common = get_common_tags(mp3_files)
    labels = ["Artist", "Album Artist", "Album", "Year", "Disc"]
    new_tags = []

    for label, existing in zip(labels, common):
        prompt = f"{label} (Current: {existing}): " if existing else f"{label}: "
        val = input(prompt).strip()
        new_tags.append(val if val else existing)

    set_global_tags(mp3_files, *new_tags)
    
    if input("\nEdit individual tracks? (y/n): ").lower() == 'y':
        for i, f in enumerate(mp3_files, 1):
            edit_track_tags(f, i)
            if i < len(mp3_files) and input("Next track? (y/n): ").lower() != 'y': break

def main():
    setup_readline()
    print("=== MP3 Tag Editor ===")
    
    folder = input("Enter root folder path: ").strip()
    folder = os.path.expanduser(folder)

    if not os.path.isdir(folder):
        print("Invalid directory.")
        return

    while True:
        albums = get_albums_in_folder(folder)
        mp3s_in_root = get_mp3_files(folder)

        if not albums and not mp3s_in_root:
            print("No MP3s or subfolders found.")
            break

        print(f"\nContents of: {folder}")
        options = []
        
        # Option to process MP3s in the current folder if they exist
        if mp3s_in_root:
            options.append((Path(folder), len(mp3s_in_root)))
            print(f"  0. [Files in current directory] ({len(mp3s_in_root)} MP3s)")

        for i, (path, count) in enumerate(albums, 1):
            options.append((path, count))
            print(f"  {i}. {path.name} ({count} MP3s)")

        choice = input("\nSelect number to process (or 'q' to quit, 'n' for new path): ").lower()
        
        if choice == 'q':
            break
        if choice == 'n':
            folder = os.path.expanduser(input("Enter new folder path: ").strip())
            continue

        try:
            idx = int(choice) if mp3s_in_root else int(choice) - 1
            if mp3s_in_root and idx == 0:
                process_album(Path(folder))
            else:
                # Adjust index if we showed option 0
                actual_idx = idx if not mp3s_in_root else idx - 1
                process_album(albums[actual_idx][0])
        except (ValueError, IndexError):
            print("Invalid selection.")

    print("Done!")

if __name__ == "__main__":
    main()

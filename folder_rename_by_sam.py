#!/usr/bin/env python3

import os
import re
import glob
import readline
import sys
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

# Setup for path completion
def complete_path(text, state):
    results = glob.glob(text + '*')
    return results[state] if state < len(results) else None

readline.set_completer_delims(' \t\n')
readline.parse_and_bind("tab: complete")
readline.set_completer(complete_path)

def get_metadata(mp3_path):
    try:
        audio = MP3(mp3_path, ID3=EasyID3)
        date_field = audio.get("date") or audio.get("originaldate") or audio.get("year")
        year = None
        if date_field:
            match = re.search(r"(\d{4})", str(date_field[0]))
            if match:
                year = match.group(1)
        album_field = audio.get("album")
        album = album_field[0] if album_field else None
        return year, album
    except Exception:
        return None, None

def sanitize_for_unix(text):
    text = text.strip().lower()
    text = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")

def resolve_conflict(options, folder_path, label):
    print(f"\n[!] CONFLICT: Multiple {label} tags found in: {folder_path}")
    options = list(filter(None, sorted(set(options))))
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    print(f"  m) Manual entry")
    
    while True:
        choice = input(f"Select the correct {label} (1-{len(options)} or 'm'): ").strip().lower()
        if choice == 'm':
            return input(f"Enter correct {label}: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except (ValueError, IndexError):
            pass
        print("Invalid selection.")

def process_album_folder(folder_path, log_file):
    years = []
    albums = []
    mp3_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".mp3")]
    
    if not mp3_files:
        return None

    for f in mp3_files:
        y, a = get_metadata(os.path.join(folder_path, f))
        if y: years.append(y)
        if a: albums.append(a)

    # --- YEAR RESOLUTION ---
    unique_years = list(set(years))
    if not unique_years:
        # LOG THE MISSING YEAR
        with open(log_file, "a") as log:
            log.write(f"MISSING YEAR: {folder_path}\n")
        
        # PROMPT USER (as originally requested)
        print(f"\n[?] Missing year in: {folder_path}")
        while True:
            y = input("    Enter 4-digit year: ").strip()
            if re.match(r"^\d{4}$", y):
                final_year = y
                break
    elif len(unique_years) > 1:
        final_year = resolve_conflict(unique_years, folder_path, "YEAR")
    else:
        final_year = unique_years[0]

    # --- ALBUM RESOLUTION ---
    unique_albums = list(set(albums))
    if not unique_albums:
        final_album = input(f"    No album tag. Enter name for {folder_path}: ").strip()
    elif len(unique_albums) > 1:
        final_album = resolve_conflict(unique_albums, folder_path, "ALBUM NAME")
    else:
        final_album = unique_albums[0]

    return final_year, final_album

def main():
    root_input = input("Enter root folder: ").strip()
    root_path = os.path.abspath(os.path.expanduser(root_input))

    if not os.path.isdir(root_path):
        print(f"Directory not found: {root_path}")
        sys.exit(1)

    log_file = "missing_years.log"
    # Ensure log is fresh
    open(log_file, 'w').close()

    print(f"\n--- Starting Scan in: {root_path} ---")
    
    last_parent = ""

    for dirpath, dirnames, filenames in os.walk(root_path, topdown=False):
        current_parent = os.path.dirname(dirpath)
        if current_parent != last_parent:
            print(f"\n[Scanning] {os.path.basename(current_parent)}/")
            last_parent = current_parent

        if any(f.lower().endswith(".mp3") for f in filenames):
            metadata = process_album_folder(dirpath, log_file)
            if not metadata: continue
                
            year, album_tag = metadata
            new_name = f"{year}-{sanitize_for_unix(album_tag)}"
            
            parent_dir = os.path.dirname(dirpath)
            old_name = os.path.basename(dirpath)
            new_path = os.path.join(parent_dir, new_name)

            if dirpath != new_path:
                if os.path.exists(new_path):
                    print(f"    [SKIP] Collision: {new_name}")
                else:
                    print(f"    [RENAME] {old_name} -> {new_name}")
                    os.rename(dirpath, new_path)
            else:
                print(f"    [OK] {old_name}")

    print(f"\n--- Complete. Missing years logged to {log_file} ---")

if __name__ == "__main__":
    main()

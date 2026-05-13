#!/usr/bin/env python3
import os
import unicodedata
import readline
import glob
import sys
import signal
from collections import defaultdict
from mutagen.id3 import ID3, TPE2

# --- Robust Path Completion ---
def path_completer(text, state):
    expanded_text = os.path.expanduser(text)
    matches = glob.glob(expanded_text + '*')
    results = [m + '/' if os.path.isdir(m) else m for m in matches]
    try: return results[state]
    except IndexError: return None

readline.set_completer_delims('')
readline.set_completer(path_completer)
readline.parse_and_bind("tab: complete")

# --- Safe Interrupt Logic ---
exit_requested = False
def signal_handler(sig, frame):
    global exit_requested
    if not exit_requested:
        print("\n\n[!] Interrupt received. Finishing current file and exiting safely...")
        exit_requested = True
    else:
        os._exit(1)

signal.signal(signal.SIGINT, signal_handler)

def is_letter_folder(name):
    """Identifies the structural letter/category folders."""
    return len(name) == 1 or name == "#"

def get_artist_from_path(path):
    """
    Analyzes a path to find the folder that represents the Artist.
    In your structure, the Artist is always the folder immediately 
    inside a Letter folder.
    """
    parts = path.strip(os.sep).split(os.sep)
    # Walk backwards from the file to find the folder whose parent is a letter
    for i in range(len(parts) - 1, 0, -1):
        if is_letter_folder(parts[i-1]):
            return parts[i]
    return None

def main():
    try:
        folder_raw = input("Target Folder: ").strip()
        target_path = os.path.abspath(os.path.expanduser(folder_raw).replace('\\ ', ' ')).rstrip(os.sep)
        
        if not os.path.isdir(target_path):
            print(f"Error: '{target_path}' is not a folder.")
            return

        print("Mapping Artist groups...")
        artist_map = defaultdict(lambda: defaultdict(list))
        
        for root, _, files in os.walk(target_path):
            if exit_requested: break
            mp3s = [os.path.join(root, f) for f in files if f.lower().endswith(".mp3")]
            if not mp3s: continue

            # Determine the artist based on the absolute path hierarchy
            artist_folder = get_artist_from_path(root)
            
            # If we are too deep or shallow to find a letter folder (e.g. running on /tmp)
            # fallback to the target_path name itself if it's not a letter
            if not artist_folder:
                dirname = os.path.basename(target_path)
                artist_folder = dirname if not is_letter_folder(dirname) else "Unknown"

            artist_map[artist_folder][root] = mp3s

        if not artist_map or "Unknown" in artist_map:
            if "Unknown" in artist_map:
                print("Error: Could not determine Artist. Ensure you are inside the 'mp3' tree.")
            else:
                print("No MP3s found.")
            return

        # --- TRUST MODE PROMPT ---
        trust_mode = False
        if len(artist_map) > 1:
            print(f"\nDetected {len(artist_map)} different artists.")
            preview = list(artist_map.keys())[:5]
            print(f"Preview: {', '.join(preview)}...")
            
            trust_choice = input("Trust script to auto-apply prettified names (spaces for underscores)? [y/N]: ").lower()
            if trust_choice == 'y':
                trust_mode = True

        total_updated = 0
        for folder_name, albums in sorted(artist_map.items()):
            if exit_requested: break
            
            suggested_tag = folder_name.replace('_', ' ')

            print(f"\n" + "="*60)
            print(f"ARTIST: {suggested_tag}")
            print(f"Source: {folder_name} ({len(albums)} albums)")
            print("="*60)
            
            if trust_mode:
                final_artist = suggested_tag
            else:
                choice = input(f"Apply '{suggested_tag}' to all? [Y/s/q/custom]: ").strip()
                if choice.lower() == 'q': break
                if choice.lower() == 's': continue
                final_artist = suggested_tag if (not choice or choice.lower() == 'y') else choice

            for album_path, files in albums.items():
                if exit_requested: break
                for i, file_path in enumerate(files, 1):
                    if exit_requested: break
                    try:
                        audio = ID3(file_path)
                        audio.add(TPE2(encoding=3, text=final_artist))
                        audio.save(v2_version=3)
                        total_updated += 1
                    except: continue
                print(f"  [✓] {os.path.basename(album_path)} updated.")

        print(f"\nFinished. Total files updated: {total_updated}")

    except (EOFError, KeyboardInterrupt):
        print("\nExiting...")

if __name__ == "__main__":
    main()

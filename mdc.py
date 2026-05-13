#!/usr/bin/env python3

import os
import sys
import readline
import glob
from pathlib import Path
import mutagen

# --- Tab Completion Setup ---
def path_completer(text, state):
    # Expand ~ to /home/user and handle spaces
    expanded_text = os.path.expanduser(text)
    matches = glob.glob(expanded_text + '*')
    results = [m + '/' if os.path.isdir(m) else m for m in matches]
    try:
        return results[state]
    except IndexError:
        return None

# Configure readline
if sys.platform != "win32":
    # Clear delimiters so spaces in folder names don't break completion
    readline.set_completer_delims('') 
    readline.set_completer(path_completer)
    readline.parse_and_bind("tab: complete")

def get_raw_tags(folder_path):
    exts = {'.mp3', '.ogg', '.m4a', '.flac'}
    folder_path = os.path.expanduser(folder_path)
    
    for root, dirs, files in os.walk(folder_path):
        for f in sorted(files):
            if Path(f).suffix.lower() in exts:
                file_path = os.path.join(root, f)
                try:
                    audio = mutagen.File(file_path)
                    if audio and audio.tags:
                        # Return the filename and the RAW tags dictionary
                        return f, audio.tags
                except Exception:
                    continue
    return None, None

def compare_artists():
    print("--- Metadata Comparison Tool ---")
    print("(Use TAB to complete folder paths)\n")
    
    try:
        path_a = input("Enter path for Philip Glass folder: ").strip()
        path_b = input("Enter path for Grace Jones folder: ").strip()
    except EOFError:
        return

    name_a, tags_a = get_raw_tags(path_a)
    name_b, tags_b = get_raw_tags(path_b)

    if not tags_a or not tags_b:
        print("\nError: Could not find music files or tags in one/both folders.")
        return

    print(f"\nComparing:")
    print(f"File A: {name_a}")
    print(f"File B: {name_b}")
    print(f"\n{'--- TAG KEY ---':<25} | {'PHILIP GLASS':<30} | {'GRACE JONES':<30}")
    print("-" * 95)

    # Get all unique keys from both files and sort them
    all_keys = sorted(set(list(tags_a.keys()) + list(tags_b.keys())))

    for key in all_keys:
        val_a = str(tags_a.get(key, "MISSING"))
        val_b = str(tags_b.get(key, "MISSING"))
        
        # Trim for display
        disp_a = (val_a[:27] + '..') if len(val_a) > 27 else val_a
        disp_b = (val_b[:27] + '..') if len(val_b) > 27 else val_b

        # Highlight differences
        marker = " <--- DIFF" if val_a != val_b else ""
        print(f"{key:<25} | {disp_a:<30} | {disp_b:<30}{marker}")

if __name__ == "__main__":
    compare_artists()

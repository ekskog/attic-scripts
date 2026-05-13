#!/usr/bin/env python3
import os
import re
import readline
import glob
import sys
import argparse
from pathlib import Path
from mutagen.id3 import ID3, TextFrame
from mutagen.easyid3 import EasyID3

# --- Autocompletion ---
def path_completer(text, state):
    matches = glob.glob(os.path.expanduser(text) + '*')
    try: return [m + '/' if os.path.isdir(m) else m for m in matches][state]
    except: return None

readline.set_completer_delims('')
readline.set_completer(path_completer)
readline.parse_and_bind("tab: complete")

GOLDEN_TAGS = {'TIT2', 'TALB', 'TPE1', 'TPE2', 'TRCK', 'TDRC', 'TPOS', 'TCOM', 'TPE3', 'TCMP'}

def shell_safe(name):
    clean = re.sub(r'[\/\\:*?"<>|()\'!&]', '', name)
    return clean.replace(' ', '_').lower().strip('_')

def process_file(mp3, mode):
    try:
        # Crucial: Ensure we are working with an absolute path
        mp3_path = Path(mp3).resolve()
        audio = ID3(str(mp3_path))
        to_delete = []

        if mode == 'verbose':
            print(f"\n" + "="*60)
            print(f"FILE: {mp3_path.name}")

        # 1. Tag Analysis
        for frame_id in list(audio.keys()):
            if frame_id in GOLDEN_TAGS:
                if mode == 'verbose': print(f"  [KEEP] {frame_id}")
            elif frame_id.startswith('APIC'):
                if mode == 'verbose': print(f"  [IMG]  {frame_id}")
                continue
            else:
                if mode == 'verbose': print(f"  [DEL]  {frame_id}")
                to_delete.append(frame_id)

        # 2. Rename Preparation
        ez = EasyID3(str(mp3_path))
        disc = ez.get('discnumber', ['01'])[0].split('/')[0].zfill(2)
        track = ez.get('tracknumber', ['00'])[0].split('/')[0].zfill(2)
        title = ez.get('title', ['unk'])[0]
        new_name = f"{disc}-{track}-{shell_safe(title)}.mp3"

        if mode == 'verbose':
            print(f"  [NAME] {mp3_path.name} -> {new_name}")
            confirm = input(f"  Apply changes? [y/N]: ").lower()
            if confirm != 'y':
                return False

        # 3. Apply Tag Changes
        for tag in to_delete:
            del audio[tag]
        for f_id in audio.keys():
            if f_id in GOLDEN_TAGS and isinstance(audio[f_id], TextFrame):
                audio[f_id].text = [str(t).lower() for t in audio[f_id].text]
        audio.save(v2_version=4)

        # 4. Apply Rename
        if mp3_path.name != new_name:
            target = mp3_path.parent / new_name
            if not target.exists():
                mp3_path.rename(target)
            elif mode == 'verbose':
                print(f"  [!] Rename failed: {new_name} already exists.")

        return True
    except Exception as e:
        if mode == 'verbose': print(f"  [ERROR] {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Navidrome Tag Harmonizer")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-b", "--blind", action="store_true")
    args = parser.parse_args()

    mode = 'verbose' if args.verbose else ('blind' if args.blind else None)

    if not mode:
        print("--- Mode Selection ---")
        print(" [V]erbose: Interactive, shows every tag change, requires 'y' to commit.")
        print(" [B]lind:   Automated, no prompts, progress bar only.")
        choice = input("\nSelect Mode (v/b): ").lower().strip()
        mode = 'verbose' if choice == 'v' else 'blind'

    try:
        print("\n--- Path Selection ---")
        root_input = input("Enter folder path (Tab to complete): ").strip()
    except EOFError: return

    root = Path(root_input).expanduser().resolve()
    if not root.is_dir():
        print("Invalid directory.")
        return

    # THE FIX: Cast generator to a static list immediately
    # This prevents the loop from breaking when filenames change on disk
    files = sorted([f.resolve() for f in root.rglob("*.mp3")])
    total = len(files)

    if total == 0:
        print("No MP3s found.")
        return

    print(f"\nProcessing {total} files in {mode.upper()} mode...")

    for i, mp3 in enumerate(files, 1):
        process_file(mp3, mode)
        if mode == 'blind':
            percent = (i / total) * 100
            sys.stdout.write(f"\rProgress: [{i}/{total}] {percent:.1f}%")
            sys.stdout.flush()

    print("\n\nHarmonization Complete.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import os
import re
import sys
import signal
import logging
import readline
from datetime import datetime
from pathlib import Path
import mutagen
from mutagen.easyid3 import EasyID3

# --- Tab Completion for Terminal ---
def path_completer(text, state):
    import glob
    expanded_text = os.path.expanduser(text)
    matches = glob.glob(expanded_text + '*')
    results = [m + '/' if os.path.isdir(m) else m for m in matches]
    try:
        return results[state]
    except IndexError:
        return None

if sys.platform != "win32":
    readline.set_completer_delims('')
    readline.set_completer(path_completer)
    readline.parse_and_bind("tab: complete")

def signal_handler(sig, frame):
    print("\n\nAborted. Finalizing log...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def setup_logging():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_fn = f"music_cleaner_{ts}.log"
    logging.basicConfig(
        filename=log_fn,
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    return log_fn

def sanitize_filename(name):
    illegal_chars = re.compile(r'[\/\\:*?"<>|()]')
    clean = illegal_chars.sub('', name)
    return clean.replace(' ', '_').lower()

def process_library():
    print("--- Navidrome Standardizer: The Nuclear Option ---")
    try:
        root_input = input("Enter music folder path: ").strip()
    except EOFError: return

    root_path = Path(root_input).expanduser().resolve()
    if not root_path.is_dir():
        print("Invalid directory."); return

    log_file = setup_logging()
    feat_pattern = re.compile(r"(.*?)\s+(?:feat\.?|ft\.?|featuring|with|vs\.?)\s+(.*)", re.IGNORECASE)

    exts = {'.mp3', '.ogg', '.m4a', '.flac'}
    all_files = [f for f in root_path.rglob('*') if f.suffix.lower() in exts]

    total = len(all_files)
    print(f"Found {total} files. Logging to: {log_file}")

    stats = {"scanned": 0, "cleaned": 0, "renamed": 0, "errors": 0}

    for idx, file_path in enumerate(all_files, 1):
        try:
            # Use Easy=True to get a standardized mapping across formats
            audio = mutagen.File(str(file_path), easy=True)
            
            if audio is None:
                logging.error(f"SKIPPED: Could not parse {file_path}")
                stats["errors"] += 1
                continue

            # 1. Capture Essential Data (Case-Insensitive)
            # We strip and provide defaults to avoid 'None' errors
            artist = str(audio.get('artist', [''])[0]).strip()
            title = str(audio.get('title', [''])[0]).strip()
            album = str(audio.get('album', [''])[0]).strip()
            album_artist = str(audio.get('albumartist', [''])[0]).strip()
            track = str(audio.get('tracknumber', ['0'])[0]).split('/')[0]
            disc = str(audio.get('discnumber', ['1'])[0]).split('/')[0]
            date = str(audio.get('date', [''])[0]).strip()

            # 2. Feat Logic: Move (feat. X) from Artist to Title
            match = feat_pattern.search(artist)
            if match:
                main_artist = match.group(1).strip()
                guest = match.group(2).strip()
                artist = main_artist
                feat_tag = f"(feat. {guest})".lower()
                if feat_tag not in title.lower():
                    title = f"{title} {feat_tag}"

            # 3. Album Artist Fallback
            if not album_artist or album_artist.lower() == 'none':
                album_artist = artist

            # --- THE KILL SWITCH ---
            # This wipes EVERY tag, including hidden MusicBrainz IDs and Sort tags
            audio.delete()
            # Re-initialize the object after deletion
            audio = mutagen.File(str(file_path), easy=True)
            
            # 4. Apply Cleaned, Lowercased Data
            audio['artist'] = artist.lower()
            audio['title'] = title.lower()
            audio['album'] = album.lower()
            audio['albumartist'] = album_artist.lower()
            audio['tracknumber'] = track
            audio['discnumber'] = disc
            if date:
                audio['date'] = date
            
            audio.save()
            stats["cleaned"] += 1

            # 5. Rename Logic
            safe_title = sanitize_filename(title.lower())
            new_name = f"{disc.zfill(2)}-{track.zfill(2)}-{safe_title}{file_path.suffix.lower()}"
            new_path = file_path.parent / new_name

            if file_path.name != new_name:
                if not new_path.exists():
                    file_path.rename(new_path)
                    stats["renamed"] += 1
                else:
                    logging.warning(f"COLLISION: {new_name} exists in {file_path.parent}")

            stats["scanned"] += 1
            if idx % 20 == 0 or idx == total:
                sys.stdout.write(f"\rProgress: {idx}/{total} | Cleaned: {stats['cleaned']} | Renamed: {stats['renamed']}")
                sys.stdout.flush()

        except Exception as e:
            logging.error(f"CRASH: {file_path} | Error: {str(e)}")
            stats["errors"] += 1

    print(f"\n\nStandardization Complete.\nTotal: {total}\nCleaned: {stats['cleaned']}\nErrors: {stats['errors']}")

if __name__ == "__main__":
    process_library()

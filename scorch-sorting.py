#!/usr/bin/env python3

import os
import sys
import logging
from pathlib import Path
import mutagen
from mutagen.id3 import ID3

def setup_logging():
    log_fn = "sort_purge_audit.log"
    logging.basicConfig(
        filename=log_fn, 
        level=logging.INFO, 
        format='%(message)s'
    )
    return log_fn

def purge_all_sort_tags():
    print("--- Mjolnir Library Purge: Removal & Audit ---")
    root_input = input("Enter root music folder path: ").strip()
    root_path = Path(root_input).expanduser().resolve()
    
    if not root_path.is_dir():
        print("Invalid directory."); return

    log_file = setup_logging()
    exts = {'.mp3', '.ogg', '.m4a', '.flac'}
    
    # Gathering files
    print("Gathering file list...")
    music_files = [f for f in root_path.rglob('*') if f.suffix.lower() in exts]
    total = len(music_files)
    
    print(f"Found {total} files. Purging tags and logging to {log_file}...")

    stats = {"scanned": 0, "cleaned": 0, "errors": 0}

    for idx, file_path in enumerate(music_files, 1):
        try:
            changed = False
            found_tags = []

            # 1. HANDLE MP3 (Raw ID3)
            if file_path.suffix.lower() == '.mp3':
                tags = ID3(str(file_path))
                
                # Frames that force surname sorting
                standard_sort_frames = ["TSOP", "TSO2", "TSOA", "TSOT", "TSOC", "TSOO", "XSOP"]
                
                for frame in standard_sort_frames:
                    if frame in tags:
                        found_tags.append(f"{frame}: {tags[frame]}")
                        tags.delall(frame)
                        changed = True
                
                # Check for TXXX user-defined sort tags (e.g., MusicBrainz)
                txxx_to_delete = []
                for tag in tags.getall("TXXX"):
                    if 'sort' in tag.desc.lower():
                        txxx_to_delete.append(tag.desc)
                
                for desc in txxx_to_delete:
                    found_tags.append(f"TXXX:{desc}")
                    tags.delall(f"TXXX:{desc}")
                    changed = True

                if changed:
                    tags.save(v2_version=3)

            # 2. HANDLE OTHER FORMATS (FLAC, OGG, M4A)
            else:
                audio = mutagen.File(str(file_path))
                if audio and audio.tags:
                    other_sort_keys = [
                        'artistsort', 'albumartistsort', 'albumsort', 
                        'titlesort', 'composersort', 'soar', 'soal', 'soon'
                    ]
                    for key in other_sort_keys:
                        if key in audio:
                            found_tags.append(key)
                            del audio[key]
                            changed = True
                    if changed:
                        audio.save()

            if changed:
                stats["cleaned"] += 1
                logging.info(f"PURGED: {file_path.name} | Removed: {', '.join(found_tags)}")

            stats["scanned"] += 1

            # Progress Indicator
            if idx % 20 == 0 or idx == total:
                sys.stdout.write(f"\rProgress: {idx}/{total} | Purged: {stats['cleaned']} | Errors: {stats['errors']}")
                sys.stdout.flush()

        except Exception as e:
            logging.error(f"ERROR: {file_path} | {str(e)}")
            stats["errors"] += 1

    print(f"\n\n--- Purge Complete ---")
    print(f"Total Scanned: {stats['scanned']}")
    print(f"Total Purged:  {stats['cleaned']}")
    print(f"Total Errors:  {stats['errors']}")
    print(f"Audit log saved to: {log_file}")

if __name__ == "__main__":
    purge_all_sort_tags()

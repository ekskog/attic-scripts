#!/usr/bin/env python3
"""
extract_covers.py

Traverses an MP3 library and extracts embedded cover art into cover.jpg.
Never modifies any tags. Logs albums where no cover could be found.

Modes (run from the relevant directory):
  --lib   cwd is library root:   <letter>/<artist>/<album>
  --let   cwd is a letter dir:   <artist>/<album>
  --art   cwd is an artist dir:  <album>

Examples:
  cd /var/lib/media/music/mp3    && extract_covers.py --lib
  cd /var/lib/media/music/mp3/i  && extract_covers.py --let
  cd .../mp3/i/ingrid_michaelson && extract_covers.py --art
"""

import os
import sys
import argparse
from mutagen.id3 import ID3, ID3NoHeaderError


LOG_DEFAULT = "missing_covers.log"


def subdirs(path):
    return sorted(
        e for e in os.listdir(path)
        if os.path.isdir(os.path.join(path, e))
    )


def find_cover_in_tags(album_dir):
    """
    Scans MP3 files in album_dir for an embedded cover image.
    Returns raw image bytes or None. Never modifies any tags.
    """
    for fname in sorted(os.listdir(album_dir)):
        fpath = os.path.join(album_dir, fname)
        if not os.path.isfile(fpath):
            continue
        if not fname.lower().endswith(".mp3"):
            continue

        try:
            tags = ID3(fpath)
        except ID3NoHeaderError:
            continue
        except Exception as e:
            print(f"  WARNING: could not read {fpath}: {e}", file=sys.stderr)
            continue

        apic_frames = tags.getall("APIC")
        if not apic_frames:
            continue

        # Prefer front cover (type 3), fall back to whatever is there
        apic_frames.sort(key=lambda f: (0 if f.type == 3 else 1))
        frame = apic_frames[0]

        if frame.data:
            return frame.data

    return None


def process_album(album_dir, log_entries):
    """
    If cover.jpg is missing, tries to extract it from tags.
    Appends to log_entries if nothing could be found.
    """
    cover_path = os.path.join(album_dir, "cover.jpg")

    if os.path.isfile(cover_path):
        return

    img_data = find_cover_in_tags(album_dir)

    if img_data:
        with open(cover_path, "wb") as f:
            f.write(img_data)
    else:
        log_entries.append(album_dir)


def iter_albums_lib(root):
    """Library root: <letter>/<artist>/<album>"""
    for letter in subdirs(root):
        print(f"[{letter}]", flush=True)
        letter_dir = os.path.join(root, letter)
        for artist in subdirs(letter_dir):
            artist_dir = os.path.join(letter_dir, artist)
            for album in subdirs(artist_dir):
                yield os.path.join(artist_dir, album)


def iter_albums_let(root):
    """Letter dir: <artist>/<album>"""
    print(f"[{os.path.basename(root)}]", flush=True)
    for artist in subdirs(root):
        artist_dir = os.path.join(root, artist)
        for album in subdirs(artist_dir):
            yield os.path.join(artist_dir, album)


def iter_albums_art(root):
    """Artist dir: <album>"""
    print(f"[{os.path.basename(root)}]", flush=True)
    for album in subdirs(root):
        yield os.path.join(root, album)


def run(root, mode, log_file):
    if not os.path.isdir(root):
        print(f"Error: '{root}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    iterators = {
        "lib": iter_albums_lib,
        "let": iter_albums_let,
        "art": iter_albums_art,
    }

    log_entries = []
    for album_dir in iterators[mode](root):
        process_album(album_dir, log_entries)

    if log_entries:
        with open(log_file, "w", encoding="utf-8") as f:
            for entry in log_entries:
                f.write(entry + "\n")
        print(f"\nDone. {len(log_entries)} album(s) without cover logged to: {log_file}")
    else:
        print("\nDone. All albums have a cover.")


def main():
    parser = argparse.ArgumentParser(
        description="Extract MP3 embedded cover art into cover.jpg files.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--lib", action="store_true", help="cwd is library root:   <letter>/<artist>/<album>")
    mode_group.add_argument("--let", action="store_true", help="cwd is a letter dir:   <artist>/<album>")
    mode_group.add_argument("--art", action="store_true", help="cwd is an artist dir:  <album>")
    parser.add_argument("--log", default=LOG_DEFAULT, help=f"log file for missing covers (default: {LOG_DEFAULT})")
    args = parser.parse_args()

    mode = "lib" if args.lib else "let" if args.let else "art"
    run(os.getcwd(), mode, args.log)


if __name__ == "__main__":
    main()

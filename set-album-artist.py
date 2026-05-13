#!/usr/bin/env python3
"""
set-album-artist.py

For each artist folder:
  1. Set the TPE2 (Album Artist) tag on every MP3
  2. Fetch artist thumbnail (Deezer or Fanart.tv) if cover.jpg missing at artist level
  3. Fetch album cover art (local → MusicBrainz → Deezer) per album
  4. Embed cover art into every MP3 in the album
  5. Offer to rename the artist folder to match naming convention

Artist level (default / cwd):
    set-album-artist.py
    set-album-artist.py /mp3/b/bob_seger

Letter level — iterates every artist sub-folder:
    set-album-artist.py --letter
    set-album-artist.py --letter /mp3/b

Dry run — shows everything that would happen, touches nothing:
    set-album-artist.py --dry-run
    set-album-artist.py --letter --dry-run

Artist thumbnail source (default: deezer):
    set-album-artist.py --fanart
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

import requests

try:
    from mutagen.id3 import ID3, TPE2, APIC, ID3NoHeaderError
    from mutagen.mp3 import MP3
except ImportError:
    sys.exit("mutagen not found — pip install mutagen")

try:
    import musicbrainzngs
    musicbrainzngs.set_useragent('attic-music-setup', '1.0', 'ekskog@gmail.com')
    HAS_MBZ = True
except ImportError:
    HAS_MBZ = False

UA          = 'attic-music-setup/1.0 (ekskog@gmail.com)'
FANART_KEY  = '534d55e821819637a0fa7fea2dd0bca4'
DRY         = '[DRY RUN] '


# ─── naming ──────────────────────────────────────────────────────────────────

def normalize_artist_name(name: str) -> str:
    """Replace & with 'and'. Used for both tag value and folder name."""
    name = re.sub(r'\s*&\s*', ' and ', name)
    return name.strip()


def to_folder_name(name: str) -> str:
    """Lowercase, filesystem-safe, preserves Unicode."""
    name = normalize_artist_name(name).lower()
    name = re.sub(r'[/\\:*?"<>|!]+', '_', name)
    name = name.replace(' ', '_')
    name = re.sub(r'_+', '_', name)
    return name.strip('_')


def normalize_album(folder_name: str) -> str:
    """Human-readable album name from folder name."""
    name = re.sub(r'^\d{4}[-_]', '', folder_name)
    return name.replace('_', ' ').replace('-', ' ').strip()


# ─── tag helpers ─────────────────────────────────────────────────────────────

def sample_album_artist(folder: str) -> str:
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith('.mp3'):
                try:
                    tags = ID3(os.path.join(root, f))
                    val = tags.get('TPE2')
                    if val:
                        return str(val)
                except (ID3NoHeaderError, Exception):
                    pass
    return ''


def set_album_artist_tags(folder: str, album_artist: str, dry_run: bool) -> tuple[int, int]:
    updated = errors = 0
    for root, _, files in os.walk(folder):
        for f in sorted(files):
            if not f.lower().endswith('.mp3'):
                continue
            path = os.path.join(root, f)
            if dry_run:
                print(f"  {DRY}would set TPE2='{album_artist}' on {f}")
                updated += 1
                continue
            try:
                try:
                    tags = ID3(path)
                except ID3NoHeaderError:
                    tags = ID3()
                tags['TPE2'] = TPE2(encoding=3, text=album_artist)
                tags.save(path)
                updated += 1
            except Exception as e:
                print(f"  ERROR {path}: {e}")
                errors += 1
    return updated, errors


def embed_cover(mp3_path: Path, cover_data: bytes, dry_run: bool) -> None:
    if dry_run:
        print(f"      {DRY}would embed cover into {mp3_path.name}")
        return
    try:
        audio = MP3(mp3_path, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        audio.tags.delall('APIC')
        audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_data))
        audio.save()
    except Exception as e:
        print(f"      tag error {mp3_path.name}: {e}")


# ─── artist thumbnail fetching ────────────────────────────────────────────────

def fetch_artist_thumb_deezer(artist_name: str) -> bytes | None:
    try:
        r = requests.get(
            'https://api.deezer.com/search/artist',
            params={'q': artist_name, 'limit': 1},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json().get('data')
            if data:
                url = data[0].get('picture_xl') or data[0].get('picture_big')
                if url:
                    img = requests.get(url, timeout=15)
                    if img.status_code == 200:
                        return img.content
    except Exception as e:
        print(f'  Deezer thumb error: {e}')
    return None


def fetch_artist_thumb_fanart(artist_name: str) -> bytes | None:
    if not HAS_MBZ:
        print('  musicbrainzngs not installed — cannot use Fanart.tv')
        return None
    try:
        result = musicbrainzngs.search_artists(artist=artist_name, limit=1)
        if not result['artist-list']:
            return None
        mbid = result['artist-list'][0]['id']
        r = requests.get(
            f'https://webservice.fanart.tv/v3/music/{mbid}',
            params={'api_key': FANART_KEY},
            timeout=10,
        )
        if r.status_code == 200:
            thumbs = r.json().get('artistthumb', [])
            if thumbs:
                img = requests.get(thumbs[0]['url'], timeout=15)
                if img.status_code == 200:
                    return img.content
    except Exception as e:
        print(f'  Fanart.tv error: {e}')
    return None


# ─── album cover fetching ─────────────────────────────────────────────────────

def fetch_album_cover_musicbrainz(artist: str, album: str) -> bytes | None:
    try:
        r = requests.get(
            'https://musicbrainz.org/ws/2/release',
            params={'query': f'artist:"{artist}" release:"{album}"', 'fmt': 'json', 'limit': 5},
            headers={'User-Agent': UA},
            timeout=10,
        )
        for release in r.json().get('releases', []):
            time.sleep(0.5)
            cover = requests.get(
                f'https://coverartarchive.org/release/{release["id"]}/front',
                headers={'User-Agent': UA},
                allow_redirects=True,
                timeout=10,
            )
            if cover.status_code == 200:
                return cover.content
    except Exception as e:
        print(f'    MusicBrainz error: {e}')
    return None


def fetch_album_cover_deezer(artist: str, album: str) -> bytes | None:
    try:
        r = requests.get(
            'https://api.deezer.com/search/album',
            params={'q': f'artist:"{artist}" album:"{album}"'},
            timeout=10,
        )
        for item in r.json().get('data', []):
            url = item.get('cover_xl') or item.get('cover_big')
            if url:
                img = requests.get(url, timeout=10)
                if img.status_code == 200:
                    return img.content
    except Exception as e:
        print(f'    Deezer error: {e}')
    return None


# ─── main per-artist logic ────────────────────────────────────────────────────

def process_artist(folder: str, dry_run: bool, use_fanart: bool) -> None:
    folder = os.path.abspath(folder)
    folder_basename = os.path.basename(folder)

    print(f"\n{'─' * 60}")
    print(f"Artist folder : {folder_basename}")

    current = normalize_artist_name(sample_album_artist(folder))
    if current:
        print(f"Current album artist: {current}")

    # ── Step 1: set album artist tag ─────────────────────────────────────────
    if not current:
        album_artist = input("No album artist tag found. Enter value (or 's' to skip): ").strip()
        if not album_artist or album_artist.lower() == 's':
            print("Skipped.")
            return
        album_artist = normalize_artist_name(album_artist)
    else:
        album_artist = current
        if album_artist != sample_album_artist(folder):
            print(f"Auto-normalized: {album_artist}")

    updated, errors = set_album_artist_tags(folder, album_artist, dry_run)
    if not dry_run:
        print(f"Updated {updated} file(s){f', {errors} error(s)' if errors else ''}.")
    else:
        print(f"  {DRY}would update {updated} file(s).")

    # ── Step 2: artist thumbnail ──────────────────────────────────────────────
    artist_dir  = Path(folder)
    artist_name = album_artist
    artist_cover = artist_dir / 'cover.jpg'

    if not artist_cover.exists():
        if dry_run:
            src = 'Fanart.tv' if use_fanart else 'Deezer'
            print(f'{DRY}would fetch artist thumbnail from {src} for "{artist_name}"')
        else:
            src = 'Fanart.tv' if use_fanart else 'Deezer'
            print(f'Fetching artist thumbnail from {src}...')
            thumb = fetch_artist_thumb_fanart(artist_name) if use_fanart else fetch_artist_thumb_deezer(artist_name)
            if thumb:
                artist_cover.write_bytes(thumb)
                print('  Saved artist cover.jpg')
            else:
                print('  No artist thumbnail found.')
    else:
        print('Artist cover.jpg exists — skipping thumbnail.')

    # ── Step 3 & 4: album covers + embed ─────────────────────────────────────
    for album_dir in sorted(d for d in artist_dir.iterdir() if d.is_dir()):
        album_name = normalize_album(album_dir.name)
        cover_path = album_dir / 'cover.jpg'
        print(f'\n  Album: {album_name}')

        if cover_path.exists():
            print('    cover.jpg exists — using local file.')
            cover_data = cover_path.read_bytes()
        elif dry_run:
            print(f'    {DRY}no cover.jpg — would search MusicBrainz then Deezer.')
            mp3s = sorted(album_dir.glob('*.mp3'))
            if mp3s:
                print(f'    {DRY}would embed cover into {len(mp3s)} MP3(s).')
            continue
        else:
            print('    Searching for cover...')
            cover_data = fetch_album_cover_musicbrainz(artist_name, album_name)
            if not cover_data:
                cover_data = fetch_album_cover_deezer(artist_name, album_name)

            if cover_data:
                cover_path.write_bytes(cover_data)
                print('    Downloaded and saved cover.jpg')
            else:
                print('    No cover found — skipping embed.')
                continue

        mp3s = sorted(album_dir.glob('*.mp3'))
        if mp3s:
            if not dry_run:
                print(f'    Embedding into {len(mp3s)} MP3(s)...')
            for mp3 in mp3s:
                embed_cover(mp3, cover_data, dry_run)

    # ── Step 5: offer folder rename ───────────────────────────────────────────
    new_name = to_folder_name(folder_basename)
    parent   = os.path.dirname(folder)
    new_path = os.path.join(parent, new_name)

    if new_path == folder:
        print("\nFolder name already matches — done.")
        return

    print(f"\nRename: {folder_basename}  →  {new_name}")
    if dry_run:
        print(f"{DRY}would rename folder (skipping confirmation in dry-run).")
        return

    if input("Confirm rename? [y/N] ").strip().lower() == 'y':
        os.rename(folder, new_path)
        print("Renamed.")
    else:
        print("Skipped rename.")


# ─── entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('path', nargs='?', default='.',
                        help='Artist folder (default) or letter folder with --letter')
    parser.add_argument('--letter', action='store_true',
                        help='Treat path as a letter directory and iterate all artist sub-folders')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would happen without writing anything')
    parser.add_argument('--fanart', action='store_true',
                        help='Use Fanart.tv for artist thumbnails instead of Deezer (requires musicbrainzngs)')
    args = parser.parse_args()

    if args.dry_run:
        print("*** DRY RUN — no files will be written or renamed ***\n")

    root = os.path.abspath(args.path)

    if args.letter:
        artists = sorted(
            d for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))
        )
        if not artists:
            sys.exit(f"No sub-folders found in {root}")
        print(f"Letter folder : {root}  ({len(artists)} artist(s))")
        for name in artists:
            process_artist(os.path.join(root, name), args.dry_run, args.fanart)
        print("\nAll done.")
    else:
        process_artist(root, args.dry_run, args.fanart)


if __name__ == '__main__':
    main()

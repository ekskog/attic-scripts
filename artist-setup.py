#!/usr/bin/env python3
import re
import os
import sys
import time
import subprocess
from pathlib import Path

import requests
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3

UA = 'attic-music-setup/1.0 (ekskog@gmail.com)'
# Direct path to the script your alias points to
THUMBS_SCRIPT = '/home/lucarv/scripts/media/fetch_artist_thumbs.py'

def normalize(folder_name):
    # Strips leading years like "1994-Album_Name"
    name = re.sub(r'^\d{4}[-_]', '', folder_name)
    return name.replace('_', ' ').replace('-', ' ').strip()

def fetch_musicbrainz(artist, album):
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

def fetch_deezer(artist, album):
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

def embed_cover(mp3_path, cover_data):
    try:
        audio = MP3(mp3_path, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        audio.tags.delall('APIC')
        audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_data))
        audio.save()
    except Exception as e:
        print(f'      tag error {mp3_path.name}: {e}')

def process_artist(artist_dir):
    artist_name = normalize(artist_dir.name)
    print(f'\n{"="*40}\nARTIST: {artist_name}\n{"="*40}')

    # ARTIST LEVEL: Only call thumbs if cover.jpg is missing
    artist_img = artist_dir / 'cover.jpg'
    if not artist_img.exists():
        print('Fetching artist avatar (thumbs -d)...')
        subprocess.run(
            [THUMBS_SCRIPT, '-d'], 
            cwd=artist_dir, 
            stdin=subprocess.DEVNULL, 
            check=False
        )
    else:
        print('Artist cover.jpg exists — skipping thumbs.')

    album_dirs = sorted([d for d in artist_dir.iterdir() if d.is_dir()])
    for album_dir in album_dirs:
        album_name = normalize(album_dir.name)
        cover_path = album_dir / 'cover.jpg'
        print(f'\n  Album: {album_name}')

        cover_data = None
        # ALBUM LEVEL: Only fetch if cover.jpg is missing
        if cover_path.exists():
            print('    cover.jpg exists — using local file.')
            cover_data = cover_path.read_bytes()
        else:
            print('    Searching for cover...')
            cover_data = fetch_musicbrainz(artist_name, album_name)
            if not cover_data:
                cover_data = fetch_deezer(artist_name, album_name)
            
            if cover_data:
                cover_path.write_bytes(cover_data)
                print('    Downloaded and saved cover.jpg')
            else:
                print('    No cover found — skipping embedding')
                continue

        mp3s = sorted(album_dir.glob('*.mp3'))
        if mp3s:
            print(f'    Embedding into {len(mp3s)} MP3s...')
            for mp3 in mp3s:
                embed_cover(mp3, cover_data)

def main():
    root_dir = Path.cwd()
    artist_dirs = sorted([d for d in root_dir.iterdir() if d.is_dir()])
    
    if not artist_dirs:
        print("No artist folders found.")
        return

    print(f"Starting batch process in: {root_dir}")
    for artist_dir in artist_dirs:
        process_artist(artist_dir)

if __name__ == '__main__':
    main()

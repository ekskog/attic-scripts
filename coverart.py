#!/usr/bin/env python3
import os
import requests
import time
import argparse
import re

# Update this with your email
API_USER_AGENT = "MusicCoverFetcher/1.5 ( your-email@example.com )"

def clean_artist_name(raw_name):
    """Simple cleanup for artist folders: underscores to spaces."""
    return raw_name.replace('_', ' ').strip().lower()

def clean_album_name(raw_name):
    """Regex cleanup for album folders: remove YYYY- and underscores."""
    name = re.sub(r'^\d{4}-', '', raw_name)
    return name.replace('_', ' ').strip().lower()

def get_album_art(artist_folder, album_folder):
    """
    Searches MusicBrainz by album title and filters results by artist name locally.
    """
    clean_artist = clean_artist_name(artist_folder)
    clean_album = clean_album_name(album_folder)

    search_url = "https://musicbrainz.org/ws/2/release/"
    params = {
        'query': f'release:"{clean_album}"',
        'fmt': 'json',
        'limit': 15
    }
    headers = {'User-Agent': API_USER_AGENT}

    try:
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        data = response.json()

        for release in data.get('releases', []):
            # Extract artist names from credits
            artist_credits = [c.get('name', '').lower() for c in release.get('artist-credit', [])]
            full_credit_string = " ".join(artist_credits)

            # Match if 'durutti column' is in 'the durutti column' or vice versa
            if clean_artist in full_credit_string or full_credit_string in clean_artist:
                mbid = release['id']
                caa_url = f"https://coverartarchive.org/release/{mbid}/front"

                # Check for image availability
                img_check = requests.head(caa_url, allow_redirects=True, timeout=5)
                if img_check.status_code == 200:
                    return caa_url
    except Exception:
        pass

    return None

def process_artist(artist_path):
    artist_folder = os.path.basename(artist_path)
    print(f"\n--- Artist: {clean_artist_name(artist_folder).upper()} ---")

    try:
        albums = [d for d in os.listdir(artist_path) if os.path.isdir(os.path.join(artist_path, d))]
    except PermissionError:
        return

    for album in sorted(albums):
        album_dir = os.path.join(artist_path, album)

        # Check for any existing image format
        files = os.listdir(album_dir)
        if any(f.lower().endswith(('.jpg', '.jpeg', '.png')) for f in files):
            print(f"  [-] {album}: Skipped")
            continue

        print(f"  [+] {album}: Searching...", end="\r")
        img_url = get_album_art(artist_folder, album)

        if img_url:
            try:
                img_res = requests.get(img_url, timeout=15, allow_redirects=True)
                if img_res.status_code == 200:
                    save_path = os.path.join(album_dir, 'cover.jpg')
                    with open(save_path, 'wb') as f:
                        f.write(img_res.content)
                    print(f"  [✓] {album}: Success!                          ")
                else:
                    print(f"  [x] {album}: Image link dead (404)             ")
            except Exception:
                print(f"  [!] {album}: Connection error                  ")
        else:
            print(f"  [x] {album}: No matching cover found           ")

        time.sleep(1.1)

def process_letter_folder(letter_path):
    """Processes a letter folder containing artist folders."""
    print(f"\n=== Processing letter folder: {os.path.basename(letter_path)} ===")
    artists = [d for d in os.listdir(letter_path) if os.path.isdir(os.path.join(letter_path, d))]
    for artist in sorted(artists):
        process_artist(os.path.join(letter_path, artist))

def main():
    parser = argparse.ArgumentParser(description="Music Cover Fetcher with Level Support")
    parser.add_argument("-l", "--level", type=int, choices=[1, 2], 
                       help="Processing level: 1=all artists in current letter folder, 2=single artist folder")
    args = parser.parse_args()

    current_path = os.getcwd()

    if args.level == 1:
        # Level 1: Process all artists in the current letter folder
        print(f"\n=== LEVEL 1 MODE: Processing all artists in {os.path.basename(current_path)} ===")
        process_letter_folder(current_path)
    elif args.level == 2:
        # Level 2: Process single artist folder (current directory is the artist folder)
        print(f"\n=== LEVEL 2 MODE: Processing single artist: {os.path.basename(current_path)} ===")
        process_artist(current_path)
    else:
        # Default behavior: Process single artist folder (legacy mode)
        print(f"\n=== LEGACY MODE: Processing {os.path.basename(current_path)} ===")
        process_artist(current_path)

    print("\n=== Processing complete ===")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        exit(0)

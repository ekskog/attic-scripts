#!/usr/bin/env python3
import os
import requests
import musicbrainzngs
import sys
import argparse

# --- CONFIGURATION ---
FANART_API_KEY = "534d55e821819637a0fa7fea2dd0bca4"
musicbrainzngs.set_useragent("ArtistThumbFetcher", "1.0", "you@me.com")

def get_deezer_thumb(artist_name):
    try:
        r = requests.get("https://api.deezer.com/search/artist", params={'q': artist_name, 'limit': 1}, timeout=10)
        if r.status_code == 200:
            data = r.json().get('data')
            if data: return data[0]['picture_xl']
    except Exception: pass
    return None

def get_artist_mbid(artist_name):
    try:
        result = musicbrainzngs.search_artists(artist=artist_name, limit=1)
        if result['artist-list']: return result['artist-list'][0]['id']
    except Exception: pass
    return None

def fetch_fanart_thumb(mbid):
    url = f"https://webservice.fanart.tv/v3/music/{mbid}"
    params = {'api_key': FANART_API_KEY}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            thumbs = data.get('artistthumb', [])
            if thumbs: return thumbs[0]['url']
    except Exception: pass
    return None

def save_image(url, destination):
    try:
        img_data = requests.get(url, timeout=15).content
        with open(destination, 'wb') as f:
            f.write(img_data)
        return True
    except Exception: return False

def process_folder(target_dir, use_deezer, dry_run, level):
    target_dir = os.path.abspath(target_dir)
    missing_artists = []
    processed_count = 0
    
    print(f"[*] Target: {target_dir}")
    print(f"[*] Level: {level} (Defaulted to 2 if not set) | Mode: {'Deezer' if use_deezer else 'Fanart'} | {'DRY RUN' if dry_run else 'LIVE'}\n")

    try:
        for root, dirs, files in os.walk(target_dir):
            rel_path = os.path.relpath(root, target_dir)
            # Calculate depth: 0 is current dir, 1 is child, 2 is grandchild
            depth = 0 if rel_path == "." else len(rel_path.split(os.sep))
            
            is_artist_folder = False
            if level == 1 and depth == 2:
                is_artist_folder = True
            elif level == 2 and depth == 1:
                is_artist_folder = True
            elif level == 3 and depth == 0:
                is_artist_folder = True

            if is_artist_folder:
                # IMPORTANT: Kill the 'dirs' list so os.walk stops here and skips album subfolders
                dirs[:] = []
                
                folder_name = os.path.basename(root)
                target_path = os.path.join(root, "cover.jpg")
                
                if os.path.exists(target_path):
                    if dry_run: print(f"  [~] Skipping {folder_name}: cover.jpg exists.")
                    continue

                clean_name = folder_name.replace('_', ' ')
                processed_count += 1

                if dry_run:
                    print(f"  [TEST] Identified Artist: '{clean_name}'")
                    print(f"         Saving to: {target_path}")
                    continue

                print(f"[*] Processing: {clean_name}")
                img_url = None
                if use_deezer:
                    img_url = get_deezer_thumb(clean_name)
                else:
                    mbid = get_artist_mbid(clean_name)
                    if mbid: img_url = fetch_fanart_thumb(mbid)

                if img_url:
                    if save_image(img_url, target_path):
                        print(f"  [+] Saved.")
                    else:
                        missing_artists.append(clean_name)
                else:
                    print(f"  [-] Not found.")
                    missing_artists.append(clean_name)
            
            # Prevent the crawler from wandering too deep before finding an artist
            if level == 1 and depth >= 2: dirs[:] = []
            if level == 2 and depth >= 1: dirs[:] = []

    except KeyboardInterrupt:
        print("\n[!] Aborted by user.")

    if not dry_run:
        if missing_artists:
            print(f"\nMissing images for: {', '.join(sorted(missing_artists))}")
        print(f"\nFinished. Processed {processed_count} artists.")
    else:
        print(f"\n[!] Dry run finished. {processed_count} artist folders identified.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Artist Thumbnail Fetcher: Downloads artist images as 'cover.jpg' without touching albums.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  # Run from inside a letter folder (Defaults to Level 2)
  python3 fetch.py -d .

  # Run from /mp3/ (Explicit Level 1)
  python3 fetch.py -l 1 -d /var/lib/media/music/mp3/

  # Always use -t first to verify folder identification!
  python3 fetch.py -d -t .
"""
    )
    parser.add_argument("path", nargs="?", default=".", help="Target directory (default: current)")
    parser.add_argument("-d", action="store_true", help="Use Deezer API")
    parser.add_argument("-t", action="store_true", help="Dry run: Identify folders without downloading")
    parser.add_argument("-l", type=int, choices=[1, 2, 3], default=2, 
                        help="Hierarchy Level (Default: 2):\n"
                             "1: Root Level (e.g., /mp3/)\n"
                             "2: Index Level (e.g., /mp3/a/)\n"
                             "3: Artist Level (e.g., /mp3/a/artist/)")
    
    args = parser.parse_args()
    process_folder(args.path, args.d, args.t, args.l)

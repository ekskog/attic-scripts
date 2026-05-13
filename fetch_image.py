#!/usr/bin/env python3
import os
import requests
import time
import urllib.parse
import sys

# --- CONFIGURATION ---
# Set this to the absolute path of your music folder
LIBRARY_ROOT = "./" 
# --- --- --- --- --- ---

def get_artist_image_url(artist_name):
    """
    Search Deezer for an artist and find the XL image URL.
    """
    try:
        # Deezer's public search API
        query = urllib.parse.quote(artist_name)
        url = f"https://api.deezer.com/search/artist?q={query}"
        
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
        
        data = response.json()
        if not data.get('data'):
            return None
        
        # The first result is typically the most accurate match
        artist_data = data['data'][0]
        
        # We prioritize 'picture_xl' (1000x1000) or 'picture_big' (500x500)
        return artist_data.get('picture_xl') or artist_data.get('picture_big')
                
    except Exception as e:
        print(f"Error communicating with Deezer API for {artist_name}: {e}")
    
    return None

def download_image(url, save_path):
    """Downloads the image from the URL to the specified path."""
    try:
        response = requests.get(url, stream=True, timeout=15)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
    return False

def main():
    # Ensure we are in the right directory
    if not os.path.exists(LIBRARY_ROOT):
        print(f"Error: {LIBRARY_ROOT} path not found.")
        sys.exit(1)

    # Traverse the alphabetical directories (a, b, c...)
    for initial in os.listdir(LIBRARY_ROOT):
        initial_path = os.path.join(LIBRARY_ROOT, initial)
        
        # Only process single-character directories (a-z, 0-9)
        if not os.path.isdir(initial_path) or len(initial) > 1:
            continue

        # Traverse the artist directories
        for artist_folder in sorted(os.listdir(initial_path)):
            artist_path = os.path.join(initial_path, artist_folder)
            if not os.path.isdir(artist_path):
                continue

            target_file = os.path.join(artist_path, "cover.jpg")
            
            # Skip if we already have an image
            if os.path.exists(target_file):
                continue

            # Clean artist name for searching (replace underscores with spaces)
            search_name = artist_folder.replace('_', ' ')
            print(f"Processing: {search_name}...")

            image_url = get_artist_image_url(search_name)
            
            if image_url:
                print(f"Found image for {search_name}, downloading...")
                if download_image(image_url, target_file):
                    print(f"Successfully saved to {target_file}")
                # Deezer isn't as aggressive with rate limits, but a small sleep is good practice
                time.sleep(0.1)
            else:
                print(f"No image found for {search_name} on Deezer.")
            
if __name__ == "__main__":
    main()

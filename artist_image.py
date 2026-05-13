#!/usr/bin/env python3
import os
import re
import requests
from PIL import Image
from io import BytesIO

TARGET_SIZE = (200, 200)
# This header is crucial; without it, most search engines return 403 Forbidden
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
}

def get_image_url(artist_name):
    """Scrapes DuckDuckGo for the first image result."""
    # Adding 'band' helps filter out random objects/numbers
    query = f"{artist_name} music band"
    url = f"https://duckduckgo.com/i.js?q={query}&o=json"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        # DuckDuckGo returns a JSON of results for this specific endpoint
        data = response.json()
        if data.get('results'):
            return data['results'][0].get('image')
    except Exception:
        return None
    return None

def download_and_save(url, folder_path):
    """Downloads, center-crops, and saves."""
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        img = Image.open(BytesIO(res.content)).convert('RGB')
        
        # Center square crop
        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) / 2
        top = (h - min_dim) / 2
        img = img.crop((left, top, left + min_dim, top + min_dim))
        
        img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        img.save(os.path.join(folder_path, 'folder.jpg'), "JPEG", quality=90)
        return True
    except Exception:
        return False

def process_folder(path):
    # a_certain_ratio -> a certain ratio
    artist_name = os.path.basename(path.rstrip('/')).replace('_', ' ')
    print(f"--> Artist: {artist_name}")
    
    if os.path.exists(os.path.join(path, 'folder.jpg')):
        print("    [SKIP] Already exists.")
        return

    img_url = get_image_url(artist_name)
    if img_url:
        if download_and_save(img_url, path):
            print(f"    [OK] Saved image.")
        else:
            print(f"    [FAIL] Download error.")
    else:
        print(f"    [FAIL] No image found.")

def main():
    target = input("Enter path: ").strip()
    if not os.path.isdir(target):
        return

    # Handle the index folders (a, b, c, 1) or specific artist folders
    base = os.path.basename(target.rstrip('/'))
    if len(base) == 1 or base == "#":
        for d in sorted(os.listdir(target)):
            full_path = os.path.join(target, d)
            if os.path.isdir(full_path) and not d.startswith('.'):
                process_folder(full_path)
    else:
        process_folder(target)

if __name__ == "__main__":
    main()

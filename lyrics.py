#!/usr/bin/env python3
import os
import readline
import requests
from mutagen.id3 import ID3, USLT, SYLT, Encoding
from mutagen.mp3 import MP3

# Setup tab completion for directory paths
def completer(text, state):
    path = os.path.expanduser(text)
    if os.path.isdir(path):
        items = os.listdir(path)
    else:
        items = os.listdir(os.path.dirname(path) or '.')
    
    matches = [i for i in items if i.startswith(os.path.basename(path))]
    return matches[state] + "/" if state < len(matches) else None

readline.set_completer_delims(' \t\n;')
readline.parse_and_bind("tab: complete")
readline.set_completer(completer)

def fetch_lrclib(artist, title, album, duration):
    """Fetches lyrics from LRCLIB API."""
    url = "https://lrclib.net/api/get"
    params = {'artist_name': artist, 'track_name': title, 'album_name': album, 'duration': duration}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching: {e}")
    return None

def apply_lyrics(file_path):
    try:
        audio = MP3(file_path, ID3=ID3)
        # Get metadata for search
        artist = str(audio.get('TPE1', ''))
        title = str(audio.get('TIT2', ''))
        album = str(audio.get('TALB', ''))
        duration = int(audio.info.length)

        print(f"Searching: {artist} - {title}...")
        data = fetch_lrclib(artist, title, album, duration)

        if data and data.get('plainLyrics'):
            # Add Unsynced Lyrics (USLT)
            audio.tags.add(USLT(encoding=3, lang='eng', desc='desc', text=data['plainLyrics']))
            
            # Navidrome/Amperfy also love .lrc files in the same folder
            lrc_path = os.path.splitext(file_path)[0] + ".lrc"
            if data.get('syncedLyrics'):
                with open(lrc_path, "w", encoding="utf-8") as f:
                    f.write(data['syncedLyrics'])
                print(f"  [✓] Saved Synced Lyrics (.lrc)")
            
            audio.save()
            print(f"  [✓] Embedded Plain Lyrics")
        else:
            print(f"  [✗] No lyrics found.")
            
    except Exception as e:
        print(f"  [!] Error processing {file_path}: {e}")

def main():
    path = input("Enter the path to your music folder (TAB for completion): ").strip()
    target_dir = os.path.expanduser(path)

    if not os.path.isdir(target_dir):
        print("Invalid directory.")
        return

    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.lower().endswith(".mp3"):
                apply_lyrics(os.path.join(root, file))

if __name__ == "__main__":
    main()

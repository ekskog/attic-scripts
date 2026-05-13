#!/usr/bin/env python3

import os
import sys
import readline
import musicbrainzngs
import re
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, TPE2, APIC

# Configure MusicBrainz
musicbrainzngs.set_useragent("MP3TaggerPro", "1.6", "your@email.com")

def setup_tab_completion():
    def complete(text, state):
        directory = os.path.dirname(text) if '/' in text else '.'
        prefix = os.path.basename(text) if '/' in text else text
        try:
            matches = []
            if not os.path.exists(directory): return None
            for item in os.listdir(directory):
                full_path = os.path.join(directory, item) if directory != '.' else item
                if item.startswith(prefix):
                    matches.append(full_path + '/' if os.path.isdir(full_path) else full_path)
            return matches[state] if state < len(matches) else None
        except: return None
    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(' \t\n')

def get_mp3_files(directory):
    if not os.path.isdir(directory): return []
    files = [os.path.join(directory, f) for f in sorted(os.listdir(directory)) if f.lower().endswith('.mp3')]
    print(f"---> Found {len(files)} MP3 files in this folder.")
    return files

def get_artist_albums(current_path):
    try:
        parent = os.path.dirname(current_path.rstrip('/'))
        if parent and os.path.isdir(parent):
            return parent, [d for d in sorted(os.listdir(parent)) if os.path.isdir(os.path.join(parent, d))]
    except: pass
    return None, []

def search_musicbrainz(artist, album, offset=0):
    # Clean up common folder prefixes like "1989-" for the search query
    clean_album = re.sub(r'^\d{4}[-_ ]', '', album)
    query = f'artist:({artist}) release:({clean_album})'
    try:
        result = musicbrainzngs.search_releases(query=query, limit=50, offset=offset)
        return result['release-list'], result.get('release-count', 0)
    except Exception as e:
        print(f"Search Error: {e}")
        return [], 0

def display_results(releases, artist_filter):
    if not releases:
        print("\nNo results found.")
        return []
    print(f"\nFiltering for exact artist: '{artist_filter}'")
    print(f"{'#':<3} | {'Artist':<15} | {'Album Title':<30} | {'Date':<11} | {'Tracks':<6} | {'Format'}")
    print("-" * 95)
    filtered_list = []
    display_idx = 1
    for r in releases:
        artist_name = r.get('artist-credit-phrase', 'Unknown')
        if artist_name.lower() == artist_filter.lower():
            title = r.get('title', 'Unknown')[:30]
            date = r.get('date', 'Unknown')
            tracks = r.get('medium-track-count', '??')
            m_list = r.get('medium-list', [])
            fmt = m_list[0].get('format', 'Unknown') if m_list else "Unknown"
            print(f"{display_idx:<3} | {artist_name[:15]:<15} | {title:<30} | {date:<11} | {tracks:<6} | {fmt}")
            filtered_list.append(r)
            display_idx += 1
    print("-" * 95)
    return filtered_list

def apply_tags(mp3_files, release_id):
    try:
        res = musicbrainzngs.get_release_by_id(release_id, includes=['artists', 'recordings'])
        details = res['release']
        album_art = None
        try:
            print("Fetching artwork...")
            album_art = musicbrainzngs.get_image_front(release_id, size=500)
        except: pass

        tracks = []
        for medium in details.get('medium-list', []):
            for track in medium.get('track-list', []):
                tracks.append(track)

        # STICK TO YEAR ONLY (YYYY)
        raw_date = details.get('date', '')
        year_only = raw_date[:4] if len(raw_date) >= 4 else raw_date

        for i, mp3_file in enumerate(mp3_files):
            if i >= len(tracks): break
            audio = MP3(mp3_file, ID3=ID3)
            if audio.tags is None: audio.add_tags()
            t = tracks[i]
            audio.tags['TIT2'] = TIT2(encoding=3, text=t['recording']['title'])
            audio.tags['TPE1'] = TPE1(encoding=3, text=details['artist-credit-phrase'])
            audio.tags['TALB'] = TALB(encoding=3, text=details['title'])
            audio.tags['TPE2'] = TPE2(encoding=3, text=details['artist-credit-phrase'])
            audio.tags['TDRC'] = TDRC(encoding=3, text=year_only)
            audio.tags['TRCK'] = TRCK(encoding=3, text=str(t['position']))
            if album_art:
                audio.tags['APIC'] = APIC(3, 'image/jpeg', 3, 'Front', album_art)
            audio.save()
            print(f"✓ {t['position']}. {t['recording']['title']}")
        print(f"Tagging complete with year: {year_only}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    setup_tab_completion()
    print("MP3 Tag Pro: MusicBrainz Edition")
    print("=" * 80)

    while True:
        path = input("\nEnter directory (or 'q' to exit): ").strip()
        if path.lower() == 'q': break
        
        files = get_mp3_files(path)
        if not files:
            print("No MP3 files found."); continue
        
        artist_input = input("Artist: ").strip()
        
        # Start with the folder name as the suggested album query
        album_suggestion = os.path.basename(path.rstrip('/'))

        while True:
            album_input = input(f"Album query for {artist_input} [{album_suggestion}]: ").strip()
            if not album_input: album_input = album_suggestion

            results, total = search_musicbrainz(artist_input, album_input)
            filtered_results = display_results(results, artist_input)
            
            if filtered_results:
                choice = input("Select #, 'r' to retry, or 'q' to skip: ").strip().lower()
                if choice.isdigit() and 1 <= int(choice) <= len(filtered_results):
                    apply_tags(files, filtered_results[int(choice)-1]['id'])
                elif choice == 'r': continue

            parent_dir, sibling_albums = get_artist_albums(path)
            if sibling_albums:
                print(f"\nAvailable folders in {parent_dir}:")
                for i, alb in enumerate(sibling_albums, 1):
                    print(f"  {i:>2}. {alb:<35}", end='\n' if i % 2 == 0 else "")
                print("")

            cont = input(f"\nTag another album for {artist_input}? (y/n): ").strip().lower()
            if cont == 'y':
                new_sel = input("Enter folder # or manual path: ").strip()
                if new_sel.isdigit() and 1 <= int(new_sel) <= len(sibling_albums):
                    folder_name = sibling_albums[int(new_sel)-1]
                    path = os.path.join(parent_dir, folder_name)
                    # Automatically update the next search suggestion
                    album_suggestion = folder_name 
                else:
                    path = new_sel
                    album_suggestion = os.path.basename(path.rstrip('/'))
                
                files = get_mp3_files(path)
                if not files:
                    print("No MP3s found in that directory.")
                    break
                continue
            break

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(0)

#!/usr/bin/env python3
import os
import sys
from mutagen.id3 import ID3, TPE1, TPE2, error as ID3Error

def folder_to_name(folder):
    return folder.replace('_', ' ')

def scan(root, apply=False):
    changes = []

    for letter in sorted(os.listdir(root)):
        letter_path = os.path.join(root, letter)
        if not os.path.isdir(letter_path):
            continue
        for artist_folder in sorted(os.listdir(letter_path)):
            artist_path = os.path.join(letter_path, artist_folder)
            if not os.path.isdir(artist_path):
                continue
            expected = folder_to_name(artist_folder)
            for dirpath, _, files in os.walk(artist_path):
                for f in files:
                    if not f.lower().endswith('.mp3'):
                        continue
                    mp3_path = os.path.join(dirpath, f)
                    try:
                        tags = ID3(mp3_path)
                    except ID3Error:
                        print(f'  SKIP (no tags): {mp3_path}')
                        continue

                    current_artist  = str(tags.get('TPE1', ''))
                    current_album_artist = str(tags.get('TPE2', ''))
                    needs_change = (current_artist != expected or current_album_artist != expected)

                    if needs_change:
                        changes.append((mp3_path, current_artist, current_album_artist, expected))
                        if apply:
                            tags['TPE1'] = TPE1(encoding=3, text=expected)
                            tags['TPE2'] = TPE2(encoding=3, text=expected)
                            tags.save()
    return changes

def main():
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} <music_root>')
        sys.exit(1)

    root = sys.argv[1]

    print('--- DRY RUN ---')
    changes = scan(root, apply=False)

    if not changes:
        print('Nothing to change.')
        return

    for path, artist, album_artist, expected in changes:
        print(f'\n{path}')
        if artist != expected:
            print(f'  artist:       {artist!r} → {expected!r}')
        if album_artist != expected:
            print(f'  albumartist:  {album_artist!r} → {expected!r}')

    print(f'\n{len(changes)} file(s) would be updated.')
    answer = input('Apply changes? [y/N] ')
    if answer.strip().lower() == 'y':
        scan(root, apply=True)
        print('Done.')
    else:
        print('Aborted.')

if __name__ == '__main__':
    main()

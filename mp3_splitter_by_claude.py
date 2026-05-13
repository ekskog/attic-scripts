#!/usr/bin/env python3
"""
MP3 Live Gig Splitter (Enhanced)
Splits a long MP3 recording into individual tracks based on timestamps.
Supports formats: "Song Name 00:00" or "00:00 Song Name"

Requirements:
    pip install pydub
    (System) sudo apt-get install ffmpeg
"""

from pydub import AudioSegment
import os
import re
import sys
import readline
import glob

def parse_cue_file(cue_path):
    """
    Parse the cue file and return a list of (song_name, time_in_ms) tuples.
    Handles:
    1. Track Name MM:SS (or HH:MM:SS)
    2. MM:SS Track Name (or HH:MM:SS Track Name)
    """
    songs = []

    if cue_path.lower().endswith(('.mp3', '.mp4', '.wav', '.flac', '.m4a')):
        raise ValueError("This appears to be an audio file, not a cue file!")

    try:
        with open(cue_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                # Regex explanation:
                # (\d+:)? matches optional HH:
                # (\d{1,2}):(\d{2}) matches MM:SS
                
                # Format A: <Name> <Time>
                match_a = re.match(r'^(.+?)\s+(?:(\d+):)?(\d{1,2}):(\d{2})$', line)
                # Format B: <Time> <Name>
                match_b = re.match(r'^(?:(\d+):)?(\d{1,2}):(\d{2})\s+(.+)$', line)

                if match_a:
                    song_name = match_a.group(1).strip()
                    h = int(match_a.group(2)) if match_a.group(2) else 0
                    m = int(match_a.group(3))
                    s = int(match_a.group(4))
                elif match_b:
                    h = int(match_b.group(1)) if match_b.group(1) else 0
                    m = int(match_b.group(2))
                    s = int(match_b.group(3))
                    song_name = match_b.group(4).strip()
                else:
                    print(f"Warning: Line {line_num} format not recognized, skipping: {line}")
                    continue

                time_ms = (h * 3600 + m * 60 + s) * 1000
                songs.append((song_name, time_ms))
    except UnicodeDecodeError:
        raise ValueError("Cannot read file as text. Check the file encoding (try saving as UTF-8).")

    return songs

def sanitize_filename(name):
    """Convert song name to safe filename"""
    safe = re.sub(r'[^\w\s-]', '', name)
    safe = re.sub(r'\s+', '_', safe)
    return safe.lower()

def path_completer(text, state):
    """Autocomplete file paths for the input prompt"""
    line = readline.get_line_buffer()
    if '~' in line:
        line = os.path.expanduser(line)
    matches = glob.glob(line + '*')
    matches = [m + '/' if os.path.isdir(m) else m for m in matches]
    try:
        return matches[state]
    except IndexError:
        return None

def input_with_autocomplete(prompt):
    """Input with tab completion functionality"""
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(path_completer)
    result = input(prompt).strip().strip('"\'')
    if result.startswith('~'):
        result = os.path.expanduser(result)
    return result

def display_songs(songs):
    """Display the parsed song list for confirmation"""
    print("\n" + "="*60)
    print(f"{'#':<3} {'TRACK NAME':<40} {'START TIME'}")
    print("-"*60)
    for i, (name, time_ms) in enumerate(songs, 1):
        total_sec = time_ms // 1000
        h = total_sec // 3600
        m = (total_sec % 3600) // 60
        s = total_sec % 60
        time_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        print(f"{i:02d}. {name[:39]:<40} {time_str}")
    print("="*60 + "\n")

def split_mp3(mp3_path, songs, output_dir="."):
    """Split the MP3 file based on song timestamps"""
    print(f"Loading audio file: {os.path.basename(mp3_path)}")
    audio = AudioSegment.from_mp3(mp3_path)
    total_duration_ms = len(audio)

    print(f"Splitting into {len(songs)} tracks...\n")

    for i, (song_name, start_time) in enumerate(songs):
        # End time is the start of next track, or end of file
        end_time = songs[i + 1][1] if i < len(songs) - 1 else total_duration_ms
        
        # Extract segment
        segment = audio[start_time:end_time]

        # Create filename
        safe_name = sanitize_filename(song_name)
        filename = f"{i+1:02d}-{safe_name}.mp3"
        filepath = os.path.join(output_dir, filename)

        # Export
        print(f"[{i+1}/{len(songs)}] Exporting: {filename}")
        segment.export(filepath, format="mp3")

    print(f"\n✓ Done! Files exported to: {output_dir}")

def main():
    print("="*60)
    print("MP3 LIVE GIG SPLITTER")
    print("="*60)

    cue_file = input_with_autocomplete("\nEnter path to cue/txt file: ")
    if not os.path.exists(cue_file):
        print(f"Error: File not found: {cue_file}")
        return

    try:
        songs = parse_cue_file(cue_file)
    except Exception as e:
        print(f"Error: {e}")
        return

    if not songs:
        print("Error: No valid tracks found.")
        return

    display_songs(songs)

    # Resolve MP3 File
    cue_dir = os.path.dirname(os.path.abspath(cue_file))
    mp3_files = [f for f in os.listdir(cue_dir) if f.lower().endswith('.mp3')]

    if not mp3_files:
        mp3_file = input_with_autocomplete("No MP3 found in cue folder. Enter path to MP3: ")
    elif len(mp3_files) == 1:
        mp3_file = os.path.join(cue_dir, mp3_files[0])
        print(f"Using: {mp3_files[0]}")
    else:
        print(f"Multiple MP3s found:")
        for i, f in enumerate(mp3_files, 1): print(f"  {i}. {f}")
        choice = input("Select number or enter path: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(mp3_files):
            mp3_file = os.path.join(cue_dir, mp3_files[int(choice)-1])
        else:
            mp3_file = choice

    if not os.path.exists(mp3_file):
        print("Error: MP3 file not found.")
        return

    # Execute Split
    output_dir = os.path.dirname(os.path.abspath(mp3_file))
    split_mp3(mp3_file, songs, output_dir)

    # Cleanup
    print(f"\n{'='*60}")
    delete = input("Delete original MP3 and cue file? (y/n): ").lower().strip()
    if delete == 'y':
        try:
            os.remove(mp3_file)
            os.remove(cue_file)
            print("✓ Original files deleted.")
        except Exception as e:
            print(f"Error during deletion: {e}")
    else:
        print("Original files preserved.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
    except Exception as e:
        print(f"\nUnexpected Error: {e}")

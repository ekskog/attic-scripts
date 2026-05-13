#!/usr/bin/env python3

import logging
import sys
import signal
import readline
import glob
import os
from datetime import datetime
from pathlib import Path
from mutagen.id3 import ID3, ID3NoHeaderError, TextFrame

# --- Tab Completion Setup ---
def complete_path(text, state):
    text = os.path.expanduser(text)
    matches = glob.glob(text + '*')
    matches = [m + '/' if Path(m).is_dir() else m for m in matches]
    return matches[state] if state < len(matches) else None

if sys.platform != "win32":
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(complete_path)

def signal_handler(sig, frame):
    print("\n\nAborted by user. Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def setup_logging():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"mp3_nuclear_lowercase_{timestamp}.log"
    logging.basicConfig(filename=log_filename, level=logging.INFO, format='%(asctime)s - %(message)s')
    return log_filename

def draw_progress_bar(current, total):
    percent = float(current) / total
    bar = '#' * int(round(percent * 30)) + '-' * (30 - int(round(percent * 30)))
    sys.stdout.write(f"\rProgress: [{bar}] {int(percent * 100)}% ({current}/{total})")
    sys.stdout.flush()

def process_total_lowercase():
    print("--- MP3 Nuclear Lowercase Utility ---")
    print("(Targeting: ALL text-based metadata frames)")

    try:
        root_input = input("Enter root MP3 folder: ").strip()
    except EOFError: return

    root_path = Path(root_input).expanduser().resolve()
    if not root_path.is_dir():
        print(f"Error: {root_path} is not a directory."); return

    log_file = setup_logging()

    all_files = list(root_path.rglob("*.mp3"))
    total_files = len(all_files)
    stats = {"scanned": 0, "updated": 0, "errors": 0}

    for mp3_file in all_files:
        try:
            stats["scanned"] += 1
            audio = ID3(str(mp3_file))
            file_changed = False

            # Iterate through every frame in the ID3 tag
            for frame_id in list(audio.keys()):
                frame = audio[frame_id]
                
                # We only care about frames that contain text
                if isinstance(frame, TextFrame):
                    new_text_list = []
                    frame_changed = False
                    
                    for val in frame.text:
                        original_str = str(val)
                        lowered_str = original_str.lower()
                        
                        if original_str != lowered_str:
                            new_text_list.append(lowered_str)
                            frame_changed = True
                            file_changed = True
                        else:
                            new_text_list.append(original_str)
                    
                    if frame_changed:
                        audio[frame_id].text = new_text_list

            if file_changed:
                # Save using v2.4 (UTF-8) for best Navidrome/Linux compatibility
                audio.save(v2_version=4)
                stats["updated"] += 1

            draw_progress_bar(stats["scanned"], total_files)

        except ID3NoHeaderError:
            continue
        except Exception as e:
            logging.error(f"Error in {mp3_file}: {e}")
            stats["errors"] += 1

    print(f"\n\nDone! Total files scanned: {stats['scanned']}")
    print(f"Updated: {stats['updated']} files.")
    print(f"Log: {log_file}")

if __name__ == "__main__":
    process_total_lowercase()

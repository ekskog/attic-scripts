#!/usr/bin/env python3
import os
import sys
import signal
import readline
import glob
from mutagen.id3 import ID3

# --- CONFIGURATION ---
GOLDEN_SET = [
    'TIT2', 'TALB', 'TPE1', 'TPE2', 'TRCK', 'TDRC', 
    'TPOS', 'TCOM', 'TPE3', 'APIC', 'TCMP'
]

# Tags used to ensure consistency across an album
GROUPING_TAGS = ['TALB', 'TPE2', 'TDRC', 'TPOS', 'TCMP']

# --- TERMINAL UTILS ---
def path_completer(text, state):
    line = readline.get_line_buffer()
    if '~' in text: text = os.path.expanduser(text)
    matches = glob.glob(text + '*')
    results = [m + '/' if os.path.isdir(m) else m for m in matches]
    return (results + [None])[state]

readline.set_completer_delims(' \t\n=')
readline.parse_and_bind("tab: complete")
readline.set_completer(path_completer)

def signal_handler(sig, frame):
    print("\n\n[!] Interrupt detected. Restoring terminal...")
    os.system('stty echo') 
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# --- CORE LOGIC ---
def process_folder(folder_path):
    mp3_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.mp3')]
    if not mp3_files: return

    print(f"\nProcessing: {os.path.basename(folder_path)}")
    
    # STEP 1: SANITIZE (Wipe non-golden tags)
    for f_path in mp3_files:
        try:
            audio = ID3(f_path)
            tags_present = list(audio.keys())
            for tag in tags_present:
                base_tag = tag.split(':')[0]
                if base_tag not in GOLDEN_SET:
                    audio.pop(tag)
            audio.save(v2_version=3)
        except Exception as e:
            print(f"  [Error Sanitizing] {os.path.basename(f_path)}: {e}")

    # STEP 2: ALIGN (Force consistency using the first file as blueprint)
    try:
        mp3_files.sort() # Ensure consistent order
        reference = ID3(mp3_files[0])
        blueprint = {tag: reference.get(tag) for tag in GROUPING_TAGS}

        for f_path in mp3_files:
            audio = ID3(f_path)
            modified = False
            for tag_name, ref_value in blueprint.items():
                if audio.get(tag_name) != ref_value:
                    if ref_value is None:
                        if tag_name in audio:
                            audio.pop(tag_name)
                            modified = True
                    else:
                        audio.add(ref_value)
                        modified = True
            
            if modified:
                audio.save(v2_version=3)
                print(f"  [Aligned] {os.path.basename(f_path)}")
    except Exception as e:
        print(f"  [Error Aligning] {folder_path}: {e}")

def main():
    try:
        target = input("Target Folder (Tab completion enabled): ").strip()
        target = os.path.abspath(os.path.expanduser(target))
        
        if not os.path.isdir(target):
            print("Error: Invalid path.")
            return

        print(f"This will: \n1. Wipe everything EXCEPT {GOLDEN_SET}\n2. Force consistency on {GROUPING_TAGS}")
        confirm = input("Proceed? [y/N]: ").lower()
        if confirm != 'y': return

        # Walk through directories
        for root, dirs, files in os.walk(target):
            if any(f.lower().endswith('.mp3') for f in files):
                process_folder(root)

        print("\nAll done! Your library is now 'Golden'.")

    except (EOFError, KeyboardInterrupt):
        signal_handler(None, None)

if __name__ == "__main__":
    main()

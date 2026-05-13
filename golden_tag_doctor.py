#!/usr/bin/env python3
import os
import readline
import glob
from collections import defaultdict
from mutagen.id3 import ID3

# --- Autocompletion ---
def path_completer(text, state):
    matches = glob.glob(os.path.expanduser(text) + '*')
    try: return [m + '/' if os.path.isdir(m) else m for m in matches][state]
    except: return None

readline.set_completer_delims('')
readline.set_completer(path_completer)
readline.parse_and_bind("tab: complete")

# --- Configuration ---
GOLDEN_TAGS = {'TIT2', 'TALB', 'TPE1', 'TPE2', 'TRCK', 'TDRC', 'TPOS', 'TCOM', 'TPE3', 'TCMP'}
CRITICAL_TAGS = {
    'TALB': 'Album Name',
    'TPE2': 'Album Artist',
    'TDRC': 'Date'
}

def main():
    try:
        folder_raw = input("Folder to Analyze (Tab to complete): ").strip()
    except EOFError: return
    
    target_path = os.path.abspath(os.path.expanduser(folder_raw))
    if not os.path.isdir(target_path):
        print("Invalid directory.")
        return

    all_dirs = [root for root, _, files in os.walk(target_path) if any(f.lower().endswith(".mp3") for f in files)]
    problem_count = 0

    for root in all_dirs:
        mp3s = [os.path.join(root, f) for f in os.listdir(root) if f.lower().endswith(".mp3")]
        group_check = defaultdict(lambda: defaultdict(list))
        junk_found = set()
        
        for f_path in mp3s:
            try:
                audio = ID3(f_path)
                # 1. Junk Check (Ignore anything starting with APIC)
                for k in audio.keys():
                    if k not in GOLDEN_TAGS and not k.startswith('APIC'):
                        junk_found.add(k)

                # 2. Consistency Check (Album, Artist, Date)
                for tag_id, label in CRITICAL_TAGS.items():
                    val = audio.get(tag_id, "MISSING")
                    v_str = str(val.text[0]).lower().strip() if hasattr(val, 'text') and val.text else str(val).lower().strip()
                    group_check[label][v_str].append(os.path.basename(f_path))
            except: continue

        conflicts = {l: v_m for l, v_m in group_check.items() if len(v_m) > 1}
        
        if conflicts or junk_found:
            problem_count += 1
            print(f"\n" + "="*80)
            print(f"FOLDER: {root}")
            if conflicts:
                for label, v_map in conflicts.items():
                    print(f"  [!] CONFLICT: {label}")
                    for v, f in v_map.items():
                        print(f"    -> '{v}' ({len(f)} tracks)")
            if junk_found:
                print(f"  [!] JUNK TAGS: {sorted(list(junk_found))}")

    print(f"\n" + "="*80)
    print(f"Scan Complete. {problem_count} folders need attention.")
    print("="*80)

if __name__ == "__main__":
    main()

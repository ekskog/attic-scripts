#!/usr/bin/env python3
import sys
import os

try:
    from mutagen import File
except ImportError:
    print("Error: mutagen is not installed. Run 'pip install mutagen'")
    sys.exit(1)

def format_val(val):
    """Normalizes various mutagen value types (lists, bytes, etc) to a string."""
    if isinstance(val, list):
        return ", ".join([str(x) for x in val])
    if isinstance(val, bytes):
        return val.decode('utf-8', errors='replace')
    return str(val)

def get_tags(filepath):
    """Extracts tags from MP3, MP4, M4A, or FLAC and flattens them."""
    audio = File(filepath)
    if audio is None:
        return None
    
    tags = {}
    
    # Handle MP4/M4A (Apple-style tags)
    if hasattr(audio, 'tags') and audio.tags is not None:
        for key, value in audio.tags.items():
            # MP4 tags often look like '\xa9nam' or 'soar'
            tags[key] = format_val(value)
    
    # Handle MP3 (ID3 style tags)
    elif hasattr(audio, 'keys'):
        for key in audio.keys():
            tags[key] = format_val(audio[key])
            
    return tags

def compare_files(file1, file2):
    if not os.path.exists(file1) or not os.path.exists(file2):
        print("Error: One or both files do not exist.")
        return

    tags1 = get_tags(file1)
    tags2 = get_tags(file2)

    if tags1 is None or tags2 is None:
        print("Error: Could not read metadata from one of the files.")
        return

    all_keys = sorted(set(tags1.keys()) | set(tags2.keys()))

    # Dynamic column widths based on terminal or fixed size
    col_width = 40
    print(f"\n{'TAG KEY':<20} | {'FILE 1':<{col_width}} | {'FILE 2':<{col_width}}")
    print("-" * (25 + col_width * 2))

    diff_count = 0
    for key in all_keys:
        val1 = tags1.get(key, "[MISSING]")
        val2 = tags2.get(key, "[MISSING]")
        
        marker = " "
        if val1 != val2:
            marker = "!"
            diff_count += 1

        # Truncate long values for display
        d_val1 = (val1[:col_width-3] + '...') if len(val1) > col_width else val1
        d_val2 = (val2[:col_width-3] + '...') if len(val2) > col_width else val2

        print(f"{marker} {key:<18} | {d_val1:<{col_width}} | {d_val2:<{col_width}}")

    if diff_count == 0:
        print("\n✅ Metadata is identical.")
    else:
        print(f"\n⚠️ Found {diff_count} differences (marked with !).")
        print("Note: If values look the same but are marked '!', check for hidden spaces or different encoding.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        f1 = input("Path to first file (MP3/M4A/MP4): ").strip().strip("'\"")
        f2 = input("Path to second file (MP3/M4A/MP4): ").strip().strip("'\"")
    else:
        f1 = sys.argv[1]
        f2 = sys.argv[2]

    compare_files(f1, f2)

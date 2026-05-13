#!/usr/bin/env python3

import os
import shutil
from pathlib import Path

def purge_mac_junk():
    root_input = input("Enter root music folder path to clean: ").strip()
    root_path = Path(root_input).expanduser().resolve()
    
    if not root_path.is_dir():
        print("Invalid directory.")
        return

    print(f"Scanning for macOS junk in {root_path}...")

    junk_patterns = [
        '.DS_Store',
        '.AppleDouble',
        '__MACOSX',
        '.Spotlight-V100',
        '.Trashes'
    ]

    deleted_count = 0

    for root, dirs, files in os.walk(root_path, topdown=False):
        # 1. Remove Junk Files (like .DS_Store and ._ prefixed files)
        for name in files:
            file_path = os.path.join(root, name)
            # Match specific junk names or files starting with ._
            if name in junk_patterns or name.startswith('._'):
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")

        # 2. Remove Junk Directories (like .AppleDouble)
        for name in dirs:
            dir_path = os.path.join(root, name)
            if name in junk_patterns:
                try:
                    shutil.rmtree(dir_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting directory {dir_path}: {e}")

    print(f"\nPurge complete. Removed {deleted_count} macOS metadata items.")

if __name__ == "__main__":
    purge_mac_junk()

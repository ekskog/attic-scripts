#!/usr/bin/env python3
import os

def clean_image_files():
    # Targets the directory where you are currently standing in the terminal
    target_dir = os.getcwd()
    
    no_image_count = 0
    total_folders = 0
    
    print(f"Starting cleanup in: {target_dir}")

    for root, dirs, files in os.walk(target_dir):
        total_folders += 1
        file_list = set(files)
        
        has_cover = 'cover.jpg' in file_list
        has_folder = 'folder.jpg' in file_list

        # If neither file exists, increment the empty folder counter
        if not has_cover and not has_folder:
            no_image_count += 1
            continue

        # Case 1: Both exist -> Delete folder.jpg
        if has_cover and has_folder:
            folder_path = os.path.join(root, 'folder.jpg')
            try:
                os.remove(folder_path)
                print(f"Deleted: {folder_path}")
            except OSError as e:
                print(f"Error deleting {folder_path}: {e}")

        # Case 2: Only folder.jpg exists -> Rename to cover.jpg
        elif has_folder and not has_cover:
            old_path = os.path.join(root, 'folder.jpg')
            new_path = os.path.join(root, 'cover.jpg')
            try:
                os.rename(old_path, new_path)
                print(f"Renamed: {old_path} -> cover.jpg")
            except OSError as e:
                print(f"Error renaming {old_path}: {e}")

    print("\n--- Summary ---")
    print(f"Total folders scanned: {total_folders}")
    print(f"Folders with no cover.jpg or folder.jpg: {no_image_count}")
    print("Task complete.")

if __name__ == "__main__":
    clean_image_files()

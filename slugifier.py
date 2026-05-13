#!/usr/bin/env python3
import os
import re
import readline

def complete_path(text, state):
    """Enables tab-completion for file paths."""
    return [x for x in os.listdir('.') if x.startswith(text)][state]

def clean_name(name):
    """
    Applies the renaming logic:
    1. Lowercase everything.
    2. Replace spaces with underscores.
    3. Remove '(' and ')'.
    4. Replace space-parenthesis combos with hyphens (e.g., ' (1973) ' -> '-1973-').
    5. Clean up double underscores or trailing hyphens.
    """
    # Convert to lowercase
    new_name = name.lower()
    
    # Handle the "(year) title" pattern specifically to turn it into "year-title"
    # This replaces "(2003) title" with "2003-title"
    new_name = re.sub(r'^\((\d+)\)\s*', r'\1-', new_name)
    
    # Replace remaining parentheses and brackets with hyphens or nothing
    new_name = new_name.replace('(', '').replace(')', '').replace('[', '').replace(']', '')
    
    # Replace spaces with underscores
    new_name = new_name.replace(' ', '_')
    
    # Clean up any resulting double underscores or hyphens
    new_name = re.sub(r'_+', '_', new_name)
    new_name = re.sub(r'-+', '-', new_name)
    new_name = new_name.strip('_').strip('-')
    
    return new_name

def rename_folders(root_path):
    # topdown=False is critical: rename children before parents
    for root, dirs, files in os.walk(root_path, topdown=False):
        for name in dirs:
            old_path = os.path.join(root, name)
            new_folder_name = clean_name(name)
            new_path = os.path.join(root, new_folder_name)
            
            if old_path != new_path:
                print(f"Renaming: {name} -> {new_folder_name}")
                try:
                    os.rename(old_path, new_path)
                except OSError as e:
                    print(f"Error renaming {name}: {e}")

if __name__ == "__main__":
    # Setup tab completion
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    
    path_input = input("Enter the path to your music library: ").strip()
    
    if os.path.isdir(path_input):
        confirm = input(f"Are you sure you want to rename subfolders in {path_input}? (y/n): ")
        if confirm.lower() == 'y':
            rename_folders(path_input)
            print("Done!")
        else:
            print("Operation cancelled.")
    else:
        print("Invalid directory path.")

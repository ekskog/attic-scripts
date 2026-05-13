#!/usr/bin/env python3
"""
Universal Audio Converter - Converts FLAC to MP3 or WAV to FLAC using ffmpeg
Features: Tab completion, shows current directory, loop until user quits
          Converts single file OR entire directories recursively
Works on: macOS, Linux, Windows
"""

import os
import subprocess
import sys
import platform
from pathlib import Path

# Try to import readline for tab completion (Unix-like systems)
try:
    import readline
    TAB_COMPLETION_AVAILABLE = True
except ImportError:
    TAB_COMPLETION_AVAILABLE = False

class Completer:
    """Custom completer for file path tab completion"""
    def complete(self, text, state):
        """Return possible completions for the current text"""
        if not text:
            directory = "."
            partial = ""
        else:
            directory = os.path.dirname(text)
            if not directory:
                directory = "."
                partial = text
            else:
                partial = os.path.basename(text)
        
        if directory.startswith('~'):
            directory = os.path.expanduser(directory)
        
        try:
            files = []
            if os.path.exists(directory):
                for f in os.listdir(directory):
                    full_path = os.path.join(directory, f)
                    if os.path.isdir(full_path):
                        f += "/"
                    if f.startswith(partial):
                        files.append(f)
            
            if state < len(files):
                if text and os.path.dirname(text):
                    dir_part = os.path.dirname(text)
                    if dir_part.endswith('/') or dir_part.endswith('\\'):
                        completion = dir_part + files[state]
                    else:
                        completion = dir_part + os.sep + files[state]
                else:
                    completion = files[state]
                return completion
            return None
        except:
            return None

def setup_tab_completion():
    """Set up tab completion for file paths"""
    if TAB_COMPLETION_AVAILABLE and platform.system().lower() != "windows":
        completer = Completer()
        readline.set_completer(completer.complete)
        readline.set_completer_delims(' \t\n;')
        readline.parse_and_bind("tab: complete")
        return True
    return False

def get_platform_info():
    """Detect operating system"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos", "brew install ffmpeg"
    elif system == "linux":
        try:
            with open("/etc/os-release") as f:
                os_info = f.read().lower()
                if "ubuntu" in os_info or "debian" in os_info:
                    return "linux", "sudo apt install ffmpeg"
                elif "fedora" in os_info:
                    return "linux", "sudo dnf install ffmpeg"
                elif "arch" in os_info:
                    return "linux", "sudo pacman -S ffmpeg"
        except:
            pass
        return "linux", "Use your package manager to install ffmpeg"
    elif system == "windows":
        return "windows", "Download from: https://ffmpeg.org/download.html"
    return "unknown", "Download from: https://ffmpeg.org/download.html"

def check_ffmpeg():
    """Check if ffmpeg is installed"""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True, "ffmpeg"
    except:
        return False, None

def show_current_directory():
    """Display current working directory"""
    cwd = os.getcwd()
    home = os.path.expanduser("~")
    if cwd.startswith(home):
        display_cwd = "~" + cwd[len(home):]
    else:
        display_cwd = cwd
    print(f"\n[Current directory: {display_cwd}]")
    return cwd

def find_audio_files(directory):
    """Recursively find all .flac and .wav files in directory"""
    audio_files = []
    directory_path = Path(directory)
    
    for ext in ['*.flac', '*.wav']:
        audio_files.extend(directory_path.rglob(ext))
    
    return sorted(audio_files)

def get_file_or_directory_from_user():
    """Get file or directory path from user"""
    cwd = show_current_directory()
    
    while True:
        print("\n[Tip: Press TAB to auto-complete]")
        print("[Enter a file path OR a directory path to convert all audio files inside]")
        path_input = input("\nEnter path (or 'q' to quit): ").strip().strip('"').strip("'")
        
        if path_input.lower() in ['q', 'quit', 'exit']:
            return None, None
        
        if not path_input:
            print("Please enter a path or 'q' to quit.")
            continue
        
        if path_input.startswith('~'):
            path_input = os.path.expanduser(path_input)
        
        if not os.path.isabs(path_input):
            path_input = os.path.join(cwd, path_input)
        
        if not os.path.exists(path_input):
            print(f"[ERROR] Path not found: {path_input}")
            continue
        
        # Check if it's a directory
        if os.path.isdir(path_input):
            audio_files = find_audio_files(path_input)
            if not audio_files:
                print(f"[WARNING] No .flac or .wav files found in: {path_input}")
                continue
            print(f"\n[INFO] Found {len(audio_files)} audio file(s) in directory and subdirectories")
            return path_input, audio_files
        
        # It's a file - check if it's supported
        elif os.path.isfile(path_input):
            ext = Path(path_input).suffix.lower()
            if ext not in ['.flac', '.wav']:
                print(f"[ERROR] Unsupported file format: {ext}")
                print("  Only .flac and .wav files are supported")
                continue
            return path_input, [Path(path_input)]
        
        else:
            print(f"[ERROR] Not a file or directory: {path_input}")
            continue

def detect_conversion_type(input_path):
    """Determine conversion type"""
    ext = Path(input_path).suffix.lower()
    if ext == '.flac':
        return 'flac_to_mp3', 'mp3'
    elif ext == '.wav':
        return 'wav_to_flac', 'flac'
    return None, None

def convert_audio(input_path, output_path, conversion_type, ffmpeg_cmd, index=None, total=None):
    """Perform conversion for a single file"""
    
    # Build progress indicator
    progress = ""
    if index is not None and total is not None:
        progress = f"[{index}/{total}] "
    
    # Handle case where output file already exists
    if output_path.exists():
        print(f"\n{progress}[WARNING] {output_path.name} already exists.")
        overwrite = input("  Overwrite? (y/n/s for skip): ").lower()
        if overwrite == 's':
            print("  Skipping.")
            return False
        elif overwrite != 'y':
            print("  Cancelled for this file.")
            return False
    
    # Build ffmpeg command based on conversion type
    if conversion_type == 'flac_to_mp3':
        cmd = [ffmpeg_cmd, "-i", str(input_path), 
               "-acodec", "libmp3lame", "-ab", "320k", "-ar", "44100", 
               "-y" if output_path.exists() else "-n", str(output_path)]
        codec_info = "MP3 (320kbps)"
    elif conversion_type == 'wav_to_flac':
        cmd = [ffmpeg_cmd, "-i", str(input_path), 
               "-acodec", "flac", "-compression_level", "8",
               "-y" if output_path.exists() else "-n", str(output_path)]
        codec_info = "FLAC (lossless)"
    else:
        print(f"{progress}[ERROR] Unsupported conversion")
        return False
    
    print(f"\n{progress}Converting: {input_path.name}")
    print(f"  {input_path.suffix.upper()[1:]} -> {output_path.suffix.upper()[1:]} ({codec_info})")
    print("  Processing...")
    
    try:
        shell_mode = (platform.system().lower() == "windows")
        result = subprocess.run(cmd, capture_output=True, text=True, shell=shell_mode)
        
        if result.returncode == 0 and output_path.exists():
            input_size = os.path.getsize(input_path) / (1024 * 1024)
            output_size = output_path.stat().st_size / (1024 * 1024)
            
            print(f"  [SUCCESS]")
            print(f"    Input size:  {input_size:.2f} MB")
            print(f"    Output size: {output_size:.2f} MB")
            if conversion_type == 'wav_to_flac' and input_size > 0:
                ratio = (1 - output_size/input_size) * 100
                print(f"    Compression: {ratio:.1f}% saved")
            return True
        else:
            print(f"  [ERROR] Conversion failed!")
            if result.stderr:
                for line in result.stderr.split('\n')[-3:]:
                    if line.strip():
                        print(f"    {line}")
            return False
    except Exception as e:
        print(f"  [ERROR] {str(e)}")
        return False

def convert_batch(audio_files, ffmpeg_cmd):
    """Convert multiple files in batch mode"""
    total = len(audio_files)
    successful = 0
    failed = 0
    skipped = 0
    
    print("\n" + "="*60)
    print(f"BATCH CONVERSION MODE: {total} file(s) to process")
    print("="*60)
    
    for idx, input_path in enumerate(audio_files, 1):
        # Determine output path
        conv_type, output_ext = detect_conversion_type(input_path)
        if not conv_type:
            print(f"\n[{idx}/{total}] Skipping unsupported: {input_path.name}")
            skipped += 1
            continue
        
        output_path = input_path.with_suffix(f'.{output_ext}')
        
        # Show what will happen
        print(f"\n[{idx}/{total}] Input:  {input_path.name}")
        print(f"            Output: {output_path.name}")
        
        # Convert
        success = convert_audio(input_path, output_path, conv_type, ffmpeg_cmd, idx, total)
        
        if success:
            successful += 1
        else:
            failed += 1
        
        # Show progress after each file
        print(f"\n[Progress: {successful} successful, {failed} failed, {skipped} skipped of {total}]")
    
    return successful, failed, skipped

def clear_screen():
    """Clear screen"""
    os.system('clear' if platform.system().lower() != "windows" else 'cls')

def print_banner():
    """Print banner"""
    banner = """
+----------------------------------------------------------+
|                                                          |
|     Universal Audio Converter                           |
|     FLAC <-> MP3  |  WAV <-> FLAC                       |
|     Single file OR entire directories (recursive)       |
|                                                          |
+----------------------------------------------------------+
    """
    print(banner)

def main():
    """Main program"""
    clear_screen()
    print_banner()
    
    os_name, install_cmd = get_platform_info()
    print(f"[OS: {os_name.upper()}]")
    
    if setup_tab_completion():
        print("[Tab completion: ENABLED]")
    
    ffmpeg_ok, ffmpeg_cmd = check_ffmpeg()
    if not ffmpeg_ok:
        print("\n[ERROR] ffmpeg not found.")
        print(f"  {install_cmd}")
        sys.exit(1)
    
    print(f"[ffmpeg: FOUND]")
    
    print("\nSupported conversions:")
    print("  - FLAC -> MP3 (320kbps)")
    print("  - WAV  -> FLAC (lossless)")
    print("  - Can process single files OR entire directories recursively")
    
    # Overall statistics across multiple sessions
    total_overall = 0
    successful_overall = 0
    failed_overall = 0
    skipped_overall = 0
    
    while True:
        # Get file or directory
        path, audio_files = get_file_or_directory_from_user()
        
        if path is None:
            print("\n[Goodbye!]")
            break
        
        # Convert based on what we got
        if len(audio_files) == 1:
            # Single file conversion
            input_file = audio_files[0]
            conv_type, output_ext = detect_conversion_type(input_file)
            output_path = input_file.with_suffix(f'.{output_ext}')
            
            print(f"\nPlan:")
            print(f"  Input:  {input_file.name}")
            print(f"  Output: {output_path.name}")
            
            confirm = input("\nProceed with conversion? (y/n): ").lower()
            if confirm != 'y':
                print("Cancelled.")
                continue
            
            success = convert_audio(input_file, output_path, conv_type, ffmpeg_cmd)
            
            total_overall += 1
            if success:
                successful_overall += 1
            else:
                failed_overall += 1
            
            print(f"\n[Overall: {successful_overall} successful, {failed_overall} failed, {skipped_overall} skipped of {total_overall}]")
        
        else:
            # Batch conversion for directory
            confirm = input(f"\nConvert ALL {len(audio_files)} file(s) in this directory and subdirectories? (y/n): ").lower()
            if confirm != 'y':
                print("Batch conversion cancelled.")
                continue
            
            successful, failed, skipped = convert_batch(audio_files, ffmpeg_cmd)
            
            total_overall += len(audio_files)
            successful_overall += successful
            failed_overall += failed
            skipped_overall += skipped
            
            print(f"\n[Overall across all sessions: {successful_overall} successful, {failed_overall} failed, {skipped_overall} skipped of {total_overall}]")
        
        # Ask if user wants to convert more
        another = input("\nConvert another file or directory? (y/n): ").lower()
        if another != 'y':
            print("\n[Goodbye!]")
            break
    
    # Final summary
    if total_overall > 0:
        print("\n" + "="*60)
        print(f"FINAL SUMMARY:")
        print(f"  Total files processed:  {total_overall}")
        print(f"  Successful conversions: {successful_overall}")
        print(f"  Failed conversions:     {failed_overall}")
        print(f"  Skipped:                {skipped_overall}")
        print("="*60)
    
    print("\nThanks for using Universal Audio Converter!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[Cancelled by user]")
        sys.exit(0)
    except Exception as e:
        print(f"\n[Unexpected error: {str(e)}]")
        sys.exit(1)

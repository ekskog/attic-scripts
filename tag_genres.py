#!/usr/bin/env python3
"""
MP3 Tagger — powered by MusicBrainz + Last.fm

Usage:
  tag_genres.py -g        Fill missing genre tags
  tag_genres.py -y        Fill missing year tags (picks oldest release)
  tag_genres.py -g -y     Fill both genre and year in one pass
  tag_genres.py -g -s     Genre mode, silent (progress bar only)
  tag_genres.py -h        Show help

Flags:
  -g, --genre    Fill genre tags (skips files that already have one)
  -y, --year     Fill year tags (skips files that already have one; picks oldest)
  -s, --silent   Progress bar only — no per-album detail
  -h, --help     Show this help message and exit

Genre lookup chain (genre mode):
  1. MusicBrainz album/release-group genres
  2. Last.fm album top tags  (fallback if MusicBrainz has no genre)
  3. Last.fm artist top tags (fallback if album tags unavailable)
  4. Majority genre across other albums by the same artist
  Set LASTFM_API_KEY in the script or as an env variable to enable Last.fm.

Year strategy:
  Search MusicBrainz for all releases matching artist + album title, collect
  all release dates, and apply the earliest year found.
"""

import os
import sys
import time
import threading
import argparse
import requests
from collections import Counter
from pathlib import Path

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TCON, TDRC, TYER, ID3NoHeaderError
except ImportError:
    print("Missing dependency: mutagen. Install with: pip install mutagen")
    sys.exit(1)


MUSICBRAINZ_API = "https://musicbrainz.org/ws/2"
LASTFM_API     = "https://ws.audioscrobbler.com/2.0/"
HEADERS = {"User-Agent": "MP3GenreTagger/1.0 (your@email.com)"}

# Set your Last.fm API key here or via the LASTFM_API_KEY environment variable.
# Get a free key at https://www.last.fm/api/account/create
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY", "")

SILENT = False  # set by -s


def log(*args, **kwargs):
    if not SILENT:
        print(*args, **kwargs)


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------

_progress      = {"current": 0, "total": 0, "label": "", "running": False}
_progress_lock = threading.Lock()


def _render_bar():
    with _progress_lock:
        current = _progress["current"]
        total   = _progress["total"]
        label   = _progress["label"]
    width  = 40
    filled = int(width * current / total) if total else 0
    bar    = "█" * filled + "░" * (width - filled)
    pct    = int(100 * current / total) if total else 0
    short  = label[:35].ljust(35) if label else " " * 35
    print(f"\r  [{bar}] {pct:3d}%  {current}/{total}  {short}", end="", flush=True)


def _progress_thread_fn():
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    tick = 0
    while _progress["running"]:
        _render_bar()
        sys.stdout.write(f" {spinner[tick % len(spinner)]}")
        sys.stdout.flush()
        tick += 1
        time.sleep(0.1)


def start_progress(total):
    _progress["current"] = 0
    _progress["total"]   = total
    _progress["label"]   = ""
    _progress["running"] = True
    t = threading.Thread(target=_progress_thread_fn, daemon=True)
    t.start()
    return t


def advance_progress(label=""):
    with _progress_lock:
        _progress["current"] += 1
        _progress["label"]    = label


def finish_progress(thread):
    _progress["running"] = False
    thread.join()
    total = _progress["total"]
    bar   = "█" * 40
    print(f"\r  [{bar}] 100%  {total}/{total}{'':36}", flush=True)


# ---------------------------------------------------------------------------
# ID3 helpers
# ---------------------------------------------------------------------------

def _frame_str(tags, *frame_ids):
    """Return the string value of the first non-empty frame found, or ''."""
    for fid in frame_ids:
        frame = tags.get(fid)
        if frame:
            val = str(frame).strip()
            if val and val != "0":
                return val
    return ""


def get_mp3_tags(filepath):
    """Return (artist, album, has_genre, has_year) from a file's ID3 tags."""
    try:
        audio = MP3(filepath, ID3=ID3)
        tags  = audio.tags
        if tags is None:
            return None, None, False, False
        artist   = _frame_str(tags, "TPE1", "TPE2") or None
        album    = _frame_str(tags, "TALB")         or None
        has_genre = bool(_frame_str(tags, "TCON"))
        has_year  = bool(_frame_str(tags, "TDRC", "TYER", "TDOR"))
        return artist, album, has_genre, has_year
    except Exception as e:
        log(f"  [!] Could not read tags from {filepath.name}: {e}")
        return None, None, False, False


def write_tags(filepath, genre=None, year=None):
    """Write genre and/or year to a single file in one save operation."""
    try:
        try:
            tags = ID3(filepath)
        except ID3NoHeaderError:
            tags = ID3()
        if genre is not None:
            tags.delall("TCON")
            tags.add(TCON(encoding=3, text=[genre]))
        if year is not None:
            tags.delall("TDRC")
            tags.delall("TYER")
            tags.add(TDRC(encoding=3, text=[str(year)]))
        tags.save(filepath)
        return True
    except Exception as e:
        log(f"  [!] Failed to write tags to {filepath.name}: {e}")
        return False


def tag_all_files(mp3_files, genre=None, year=None):
    """Write genre and/or year to all files in a list, one save per file."""
    applied = 0
    for f in mp3_files:
        if write_tags(f, genre=genre, year=year):
            applied += 1
    parts = []
    if genre is not None:
        parts.append(f"genre='{genre}'")
    if year is not None:
        parts.append(f"year={year}")
    log(f"  [✓] Tagged {applied}/{len(mp3_files)} file(s) — {', '.join(parts)}")


# ---------------------------------------------------------------------------
# MusicBrainz — shared search
# ---------------------------------------------------------------------------

def _mb_get(url, params):
    resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def search_releases(artist, album, limit=25):
    """Return raw list of MusicBrainz release dicts for artist+album."""
    query_parts = []
    if artist:
        query_parts.append(f'artist:"{artist}"')
    if album:
        query_parts.append(f'release:"{album}"')
    if not query_parts:
        return []
    try:
        data = _mb_get(
            f"{MUSICBRAINZ_API}/release",
            {"query": " AND ".join(query_parts), "fmt": "json", "limit": limit},
        )
        return data.get("releases", [])
    except Exception as e:
        log(f"  [!] MusicBrainz search error: {e}")
        return []


# ---------------------------------------------------------------------------
# MusicBrainz — genre lookup
# ---------------------------------------------------------------------------

GENERIC_GENRES = {
    "rock", "pop", "jazz", "blues", "folk", "classical", "country", "metal",
    "electronic", "dance", "hip hop", "hip-hop", "rap", "soul", "funk",
    "reggae", "punk", "alternative", "indie", "r&b", "rnb", "ambient",
    "world", "latin", "gospel", "ska", "grunge", "experimental", "noise",
    "hardcore", "emo", "acoustic", "instrumental", "soundtrack",
}


def pick_best_genre(items):
    if not items:
        return None
    sorted_items = sorted(items, key=lambda x: x.get("count", 0), reverse=True)
    top_name = sorted_items[0].get("name", "").strip()
    if top_name and top_name.lower() not in GENERIC_GENRES:
        return top_name.title()
    for item in sorted_items[1:]:
        name = item.get("name", "").strip()
        if name and name.lower() not in GENERIC_GENRES:
            log(f"  [i] '{top_name.title()}' is generic, using more specific: '{name.title()}'")
            return name.title()
    if top_name:
        log(f"  [i] Only generic genres found, using: '{top_name.title()}'")
        return top_name.title()
    return None


def extract_genre_from_mb_entity(data):
    for field in ("genres", "tags"):
        items = data.get(field, [])
        if items:
            g = pick_best_genre(items)
            if g:
                return g
    return None


def fetch_release_genre(release_id):
    try:
        data = _mb_get(f"{MUSICBRAINZ_API}/release/{release_id}",
                       {"inc": "genres+tags", "fmt": "json"})
        return extract_genre_from_mb_entity(data)
    except Exception:
        return None


def fetch_release_group_genre(rg_id):
    try:
        data = _mb_get(f"{MUSICBRAINZ_API}/release-group/{rg_id}",
                       {"inc": "genres+tags", "fmt": "json"})
        return extract_genre_from_mb_entity(data)
    except Exception:
        return None


def genre_from_releases(releases):
    """Walk a list of releases trying to find a genre. Returns genre or None."""
    for release in releases:
        release_id = release.get("id")
        if not release_id:
            continue
        time.sleep(0.5)
        genre = fetch_release_genre(release_id)
        if genre:
            return genre
        rg    = release.get("release-group", {})
        rg_id = rg.get("id") if rg else None
        if rg_id:
            time.sleep(0.5)
            genre = fetch_release_group_genre(rg_id)
            if genre:
                return genre
    return None


# ---------------------------------------------------------------------------
# MusicBrainz — year lookup
# ---------------------------------------------------------------------------

def _parse_year(date_str):
    """Extract a 4-digit year from a date string like '1998-06-15' or '1998'."""
    if not date_str:
        return None
    part = str(date_str).strip()[:4]
    if part.isdigit() and 1900 <= int(part) <= 2100:
        return int(part)
    return None


def year_from_releases(releases):
    """Walk a list of releases collecting all years; return the oldest."""
    years = []
    for r in releases:
        y = _parse_year(r.get("date", ""))
        if y:
            years.append(y)
        rg = r.get("release-group", {})
        if rg:
            y = _parse_year(rg.get("first-release-date", ""))
            if y:
                years.append(y)
    return min(years) if years else None


# ---------------------------------------------------------------------------
# Last.fm — genre fallback
# ---------------------------------------------------------------------------

def _lastfm_get(params):
    """Make a Last.fm API call. Returns parsed JSON or None on failure."""
    if not LASTFM_API_KEY:
        return None
    try:
        resp = requests.get(
            LASTFM_API,
            params={**params, "api_key": LASTFM_API_KEY, "format": "json"},
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # Last.fm signals errors inside the JSON body
        if "error" in data:
            return None
        return data
    except Exception:
        return None


def _tags_from_lastfm_response(data, key):
    """Extract a list of {name, count} dicts from a Last.fm toptags response."""
    try:
        raw = data[key]["toptags"]["tag"]
        # API returns a dict (not list) when there is only one tag
        if isinstance(raw, dict):
            raw = [raw]
        return [{"name": t["name"], "count": int(t.get("count", 0))} for t in raw if t.get("name")]
    except (KeyError, TypeError, ValueError):
        return []


def search_lastfm_genre(artist, album):
    """
    Try to find a genre via Last.fm:
      1. album.getTopTags  (most specific — tied to this exact album)
      2. artist.getTopTags (broader — reflects the artist's overall style)
    Returns a genre string or None.
    """
    if not LASTFM_API_KEY:
        return None

    # 1. Album top tags
    if artist and album:
        data = _lastfm_get({
            "method":      "album.getTopTags",
            "artist":      artist,
            "album":       album,
            "autocorrect": 1,
        })
        if data:
            items = _tags_from_lastfm_response(data, "album")
            genre = pick_best_genre(items)
            if genre:
                log(f"  [i] Genre via Last.fm album tags: '{genre}'")
                return genre

    # 2. Artist top tags
    if artist:
        time.sleep(0.3)
        data = _lastfm_get({
            "method":      "artist.getTopTags",
            "artist":      artist,
            "autocorrect": 1,
        })
        if data:
            items = _tags_from_lastfm_response(data, "artist")
            genre = pick_best_genre(items)
            if genre:
                log(f"  [i] Genre via Last.fm artist tags: '{genre}'")
                return genre

    return None


# ---------------------------------------------------------------------------
# Artist-level genre tracking (for two-pass genre fallback)
# ---------------------------------------------------------------------------

def artist_key(artist):
    return artist.strip().lower() if artist else ""


def majority_genre(genre_list):
    if not genre_list:
        return None
    return Counter(genre_list).most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Folder scanning
# ---------------------------------------------------------------------------

def find_mp3_folders(root):
    mp3_folders = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        if any(f.lower().endswith(".mp3") for f in filenames):
            mp3_folders.append(Path(dirpath))
    return sorted(mp3_folders)


# ---------------------------------------------------------------------------
# Per-folder processing
# ---------------------------------------------------------------------------

def process_folder(folder, do_genre, do_year, artist_genres, deferred, misses):
    """
    Process one album folder.
    - Reads tags from first MP3 to determine artist/album and what's missing.
    - Makes a single MusicBrainz search covering both genre and year needs.
    - Tags files in one pass (one save per file).
    - Defers genre misses for pass 2.
    """
    folder    = Path(folder)
    mp3_files = sorted([f for f in folder.iterdir() if f.suffix.lower() == ".mp3"])
    if not mp3_files:
        return

    log(f"\n📁 {folder}")

    first_mp3                          = mp3_files[0]
    artist, album, has_genre, has_year = get_mp3_tags(first_mp3)

    if not artist and not album:
        reason = f"No artist/album ID3 tags found in '{first_mp3.name}'"
        log(f"  [!] {reason}, skipping folder.")
        misses.append({"folder": str(folder), "artist": None, "album": None, "reason": reason})
        return

    log(f"  Artist : {artist or '(unknown)'}")
    log(f"  Album  : {album or '(unknown)'}")

    need_genre = do_genre and not has_genre
    need_year  = do_year  and not has_year

    if not need_genre and not need_year:
        log(f"  [–] All requested tags already present, skipping.")
        return

    if do_genre and not need_genre:
        log(f"  [–] Genre already tagged, skipping genre lookup.")
    if do_year and not need_year:
        log(f"  [–] Year already tagged, skipping year lookup.")

    # Single MusicBrainz search covers both genre and year needs
    releases = search_releases(artist, album) if (need_genre or need_year) else []

    if not releases and (need_genre or need_year):
        log(f"  [~] No MusicBrainz results for: {artist} / {album}")

    genre = None
    year  = None

    if need_genre:
        if releases:
            genre = genre_from_releases(releases)
        if genre:
            log(f"  Genre  : {genre}")
            artist_genres.setdefault(artist_key(artist), []).append(genre)
        else:
            # MusicBrainz miss — try Last.fm before deferring
            log(f"  [~] MusicBrainz genre not found, trying Last.fm…")
            time.sleep(0.3)
            genre = search_lastfm_genre(artist, album)
            if genre:
                artist_genres.setdefault(artist_key(artist), []).append(genre)
            else:
                log(f"  [~] Last.fm genre not found — deferring for artist fallback.")

    if need_year:
        if releases:
            year = year_from_releases(releases)
        if year:
            log(f"  Year   : {year}")
        else:
            log(f"  [~] Year not found on MusicBrainz.")
            misses.append({
                "folder": str(folder), "artist": artist, "album": album,
                "reason": "Year not found on MusicBrainz",
            })

    # Write everything in one pass — one save per file
    write_genre = genre if need_genre and genre else None
    write_year  = year  if need_year  and year  else None
    if write_genre or write_year:
        tag_all_files(mp3_files, genre=write_genre, year=write_year)

    # Defer genre if still missing
    if need_genre and not genre:
        deferred.append({
            "folder": folder, "artist": artist, "album": album,
            "mp3_files": mp3_files,
        })


def process_deferred_pass2(deferred, artist_genres, misses):
    if not deferred:
        return

    log(f"\n{'─' * 60}")
    log(f"  Pass 2: resolving {len(deferred)} deferred genre(s) via artist fallback")
    log(f"{'─' * 60}")

    for entry in deferred:
        folder    = entry["folder"]
        artist    = entry["artist"]
        album     = entry["album"]
        mp3_files = entry["mp3_files"]

        log(f"\n📁 {folder}")
        log(f"  Artist : {artist or '(unknown)'}")
        log(f"  Album  : {album or '(unknown)'}")

        fallback = majority_genre(artist_genres.get(artist_key(artist), []))

        if fallback:
            log(f"  Genre  : {fallback}  (artist fallback — majority across known albums)")
            tag_all_files(mp3_files, genre=fallback)
        else:
            # Last chance: try Last.fm (in case it was skipped or key was added later)
            log(f"  [~] No artist majority — trying Last.fm as last resort…")
            time.sleep(0.3)
            fallback = search_lastfm_genre(artist, album)
            if fallback:
                log(f"  Genre  : {fallback}  (Last.fm last-resort fallback)")
                tag_all_files(mp3_files, genre=fallback)
                artist_genres.setdefault(artist_key(artist), []).append(fallback)
            else:
                reason = (
                    "No genre found on MusicBrainz, Last.fm, or via artist inference"
                )
                log(f"  [✗] {reason}")
                misses.append({
                    "folder": str(folder), "artist": artist,
                    "album": album, "reason": reason,
                })


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def setup_tab_completion():
    try:
        import readline, glob

        def path_completer(text, state):
            expanded = os.path.expanduser(text)
            matches  = []
            for m in glob.glob(expanded + "*"):
                display = text + m[len(expanded):]
                if os.path.isdir(m) and not display.endswith(os.sep):
                    display += os.sep
                matches.append(display)
            try:
                return matches[state]
            except IndexError:
                return None

        readline.set_completer(path_completer)
        readline.set_completer_delims("\t\n;")
        if sys.platform == "darwin":
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
    except ImportError:
        pass


def prompt_folder():
    setup_tab_completion()
    print("=" * 60)
    print("  MP3 Tagger — powered by MusicBrainz")
    print("=" * 60)
    if not SILENT:
        print("  (Tip: use Tab to auto-complete folder paths)")
    while True:
        folder = input("\nEnter folder path to scan: ").strip()
        folder = os.path.expanduser(folder)
        if os.path.isdir(folder):
            return folder
        print(f"  [!] '{folder}' is not a valid directory. Please try again.")


# ---------------------------------------------------------------------------
# Log file
# ---------------------------------------------------------------------------

def _write_miss_log(misses, root, mode_label):
    """Write untagged albums to a timestamped log file next to the scanned root."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path  = Path(root) / f"mp3tagger_misses_{timestamp}.log"
    lines = [
        "mp3-tagger miss log",
        f"Date   : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Mode   : {mode_label}",
        f"Root   : {root}",
        f"Misses : {len(misses)}",
        "=" * 60,
        "",
    ]
    for m in misses:
        lines.append(f"Folder : {m['folder']}")
        if m["artist"] or m["album"]:
            lines.append(f"Artist : {m['artist'] or '(unknown)'}")
            lines.append(f"Album  : {m['album']  or '(unknown)'}")
        lines.append(f"Reason : {m['reason']}")
        lines.append("")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return log_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global SILENT

    parser = argparse.ArgumentParser(
        prog="tag_genres.py",
        description="Tag MP3 files using MusicBrainz metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tag_genres.py -g              Fill missing genre tags
  tag_genres.py -y              Fill missing year tags (oldest release)
  tag_genres.py -g -y           Fill both genre and year in one pass
  tag_genres.py -g -s           Genre mode, silent (progress bar only)
  tag_genres.py -g -y -s        Both modes, silent
  tag_genres.py -g -k <apikey>  Use a specific Last.fm API key

Last.fm API key:
  Get a free key at https://www.last.fm/api/account/create
  Set via -k/--lastfm-key, or the LASTFM_API_KEY environment variable.
  Without a key, Last.fm fallback is silently skipped.

At least one of -g or -y is required.
        """,
    )
    parser.add_argument("-g", "--genre",  action="store_true",
                        help="Fill missing genre tags from MusicBrainz")
    parser.add_argument("-y", "--year",   action="store_true",
                        help="Fill missing year tags from MusicBrainz (picks oldest release)")
    parser.add_argument("-s", "--silent", action="store_true",
                        help="Silent mode: progress bar only, no per-album detail")
    parser.add_argument("-k", "--lastfm-key", default="",
                        help="Last.fm API key (overrides LASTFM_API_KEY env variable)")
    args = parser.parse_args()

    SILENT = args.silent

    # Allow key override via CLI flag
    if args.lastfm_key:
        global LASTFM_API_KEY
        LASTFM_API_KEY = args.lastfm_key

    if args.genre and not LASTFM_API_KEY:
        print("  [i] No Last.fm API key set — Last.fm genre fallback disabled.")
        print("      Get a free key at https://www.last.fm/api/account/create")
        print("      Set it via -k <key> or export LASTFM_API_KEY=<key>\n")

    if not args.genre and not args.year:
        parser.print_help()
        sys.exit(0)

    mode_label = " + ".join(
        (["genre"] if args.genre else []) + (["year"] if args.year else [])
    )

    root = prompt_folder()

    mp3_folders = find_mp3_folders(root)
    if not mp3_folders:
        print("  No MP3 files found under the specified path.")
        sys.exit(0)

    total = len(mp3_folders)

    if SILENT:
        print(f"\n  Mode: {mode_label} | Found {total} album folder(s). Processing…\n")
    else:
        print(f"\nMode     : {mode_label}")
        print(f"Scanning : {root}")
        print(f"Folders  : {total}")
        print(f"\n{'─' * 60}")
        print(f"  Pass 1: MusicBrainz lookup")
        print(f"{'─' * 60}")

    artist_genres  = {}
    deferred       = []
    misses         = []

    progress_thread = start_progress(total) if SILENT else None

    for i, folder in enumerate(mp3_folders, 1):
        process_folder(folder, args.genre, args.year,
                       artist_genres, deferred, misses)
        if SILENT:
            advance_progress(folder.name)
        if i < total:
            time.sleep(1)

    if SILENT and deferred:
        with _progress_lock:
            _progress["label"] = "artist fallback…"

    if args.genre:
        process_deferred_pass2(deferred, artist_genres, misses)

    if SILENT:
        finish_progress(progress_thread)

    # Summary
    fallback_resolved = 0
    if args.genre and deferred:
        fallback_resolved = len(deferred) - sum(
            1 for m in misses if "No MusicBrainz genre" in m.get("reason", "")
        )

    print(f"\n{'=' * 60}")
    print(f"  Mode             : {mode_label}")
    print(f"  Albums processed : {total}")
    print(f"  Successfully tagged : {total - len(misses)}")
    if fallback_resolved:
        print(f"  Via artist fallback : {fallback_resolved}")
    if misses:
        print(f"  Could not tag    : {len(misses)}")
        log_path = _write_miss_log(misses, root, mode_label)
        print(f"  Miss log         : {log_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

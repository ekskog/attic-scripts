# attic-scripts

A collection of Python scripts for managing a self-hosted Navidrome music library. All active development is consolidated in `musiclib.py`; the other scripts are legacy reference.

## The canonical tool

**`musiclib.py`** — single interactive menu-driven CLI, ~2100 lines. Run it with:

```
python3 musiclib.py
```

All new features go here. Do not create new standalone scripts.

## Library structure

```
/mp3/          ← root
  a/           ← letter-index (1-2 chars: a-z, #, 0-9)
    artist/    ← artist folder
      album/   ← album folder (naming: YYYY-album_slug)
        *.mp3
        cover.jpg
```

## Menu sections

| Key | Section | Purpose |
|-----|---------|---------|
| A | Cover Art | Normalize artwork: folder→embed, APIC→extract, Deezer→fetch |
| B | Tags Cleanup | Sanitize to golden set, sort-tags, lowercase, TPE2, rename |
| C | Tags Enrich | Genre+year via MusicBrainz+Last.fm, interactive MB tagger, lyrics |
| D | Audit | Golden-set compliance report, file/folder tag diff |
| E | Convert | FLAC→MP3, WAV→FLAC, M4A→MP3 via ffmpeg |
| F | Utilities | MP3 splitter (cue file), macOS junk purge |
| G | Config | API keys, default library path → `~/.musiclib.json` |
| H | Workflows | Orchestrated onboarding pipeline (tags → sanitize → artwork) |

## Golden tag set

Only these ID3 tags are kept after sanitization:

```
TIT2  TALB  TPE1  TPE2  TRCK  TDRC  TPOS  TCOM  TPE3  APIC  TCMP
```

Grouping tags (must be consistent across an album): `TALB TPE2 TDRC TPOS TCMP`

## Hierarchy levels

`detect_hierarchy_level(path)` returns `root | letter | artist | album | unknown`.

All iterator functions (`iter_albums`, `iter_artists`) and batch functions accept an explicit `level` parameter. Always capture the level once from detection or `prompt_level()` and pass it through — never let functions re-detect independently, as the sampled probe is non-deterministic on large trees.

```python
level = detect_hierarchy_level(path)   # or prompt_level(path) in H workflows
sanitize_to_golden_set(path, level=level)
```

## Key design rules

- `cover.jpg` in the album folder is the single authority for artwork. `normalize_album_artwork` always overwrites APIC with the folder image, ensuring all files in an album are identical.
- Artist thumbnails (`artist/cover.jpg`) are separate from album covers (`artist/album/cover.jpg`). Section A handles albums only; the H workflow handles both.
- Compilation detection: if TPE1 varies but TPE2 is consistent, TPE1 variation is not flagged as an error.
- The `_exit_flag` global is set by SIGINT; all loops check it between items.
- `auto=True` on batch functions skips the dry-run confirm (used internally by workflow orchestration).

## External APIs

| API | Used for | Key location |
|-----|---------|-------------|
| Deezer | Album covers, artist thumbnails | No key needed |
| MusicBrainz | Genre, year, release lookup, interactive tagger | Email in config |
| Last.fm | Genre fallback | `lastfm_key` in config |
| LRCLIB | Lyrics | No key needed |
| Fanart.tv | (config slot kept, not currently wired) | `fanart_key` in config |

## Dependencies

Hard (exit on missing):
- `mutagen` — ID3 tag read/write
- `requests` — all HTTP calls

Soft (checked lazily at point of use):
- `musicbrainzngs` — C.4 interactive tagger
- `pydub` — F.1 MP3 splitter
- `ffmpeg` (binary) — E.* conversion

## Config file

`~/.musiclib.json` — created automatically on first save. Fields:
- `fanart_key` — pre-filled with a default key
- `lastfm_key` — blank by default, set via G menu
- `mb_email` — used in MusicBrainz User-Agent header
- `default_library_path` — remembered as prompt default across sessions

## Legacy scripts

All `.py` files other than `musiclib.py` are superseded. They remain for reference only and should not be modified.

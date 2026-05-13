# mp3-tagger

A command-line tool that automatically fills missing **genre** and **year** ID3 tags on MP3 files by querying the [MusicBrainz](https://musicbrainz.org/) database. It walks your entire music library — however deep the folder structure — and only touches tags that are actually missing.

---

## Features

- **Genre tagging** — looks up genre on MusicBrainz, prefers specific subgenres (e.g. *Punk Rock*) over broad ones (e.g. *Rock*)
- **Year tagging** — searches all known releases for an album and applies the oldest year found
- **Artist fallback** — if an album isn't found on MusicBrainz, the genre is inferred from the majority genre across the artist's other albums
- **Non-destructive** — skips any file that already has the tag being filled
- **Silent mode** — animated progress bar for unattended runs
- **Tab completion** — filesystem autocomplete when entering the folder path
- **Recursive** — works at any depth of your library tree

---

## Requirements

- Python 3.6+
- [mutagen](https://mutagen.readthedocs.io/) — reading and writing ID3 tags
- [requests](https://docs.python-requests.org/) — MusicBrainz API calls

Install dependencies with:

```bash
pip install mutagen requests
```

---

## Installation

```bash
git clone https://github.com/yourname/mp3-tagger.git
cd mp3-tagger
chmod +x tag_genres.py
```

Optionally add it to your PATH so you can call it from anywhere:

```bash
ln -s "$(pwd)/tag_genres.py" ~/.local/bin/tag_genres
```

Before running, edit the `User-Agent` string near the top of the script and replace `your@email.com` with your actual email address. MusicBrainz's fair-use policy requires a valid contact in API requests.

---

## Usage

```
tag_genres.py [-g] [-y] [-s] [-h]
```

| Flag | Description |
|------|-------------|
| `-g`, `--genre` | Fill missing genre tags |
| `-y`, `--year` | Fill missing year tags (picks oldest known release) |
| `-s`, `--silent` | Silent mode — progress bar only, no per-album detail |
| `-h`, `--help` | Show help and exit |

At least one of `-g` or `-y` is required. Flags can be freely combined.

### Examples

```bash
# Fill missing genre tags, verbose output
tag_genres.py -g

# Fill missing year tags, verbose output
tag_genres.py -y

# Fill both genre and year in a single pass
tag_genres.py -g -y

# Genre mode with progress bar only (good for large libraries)
tag_genres.py -g -s

# Both tags, silent
tag_genres.py -g -y -s
```

When you run the script, it will prompt you for the folder to scan, with tab completion:

```
Enter folder path to scan: ~/Music/mp3/
```

---

## Library structure

The script works with any folder depth. It recurses from whatever folder you provide and processes every subfolder that contains MP3 files. For example, with a library organised as:

```
mp3/
├── a/
│   └── ane_brun/
│       └── 2020_ane_brun/
└── b/
    ├── bob_marley/
    │   └── 1975_live/
    └── bob_mould/
        ├── 1998_bob_mould/
        └── 2025_here_we_go_crazy/
```

You can run it at any level:

```bash
tag_genres.py -g          # enter ./mp3       → processes everything
tag_genres.py -g          # enter ./mp3/b     → all artists starting with b
tag_genres.py -g          # enter ./mp3/b/bob_mould  → all Bob Mould albums
tag_genres.py -g          # enter ./mp3/b/bob_mould/2025_here_we_go_crazy  → one album
```

---

## How it works

### Artist and album detection

For each album folder, the script reads the `TPE1` (artist) and `TALB` (album) ID3 tags from the first MP3 file found. All other files in the same folder inherit the result.

### Genre — two-pass lookup

**Pass 1** — for each album, the script queries MusicBrainz using `artist:"..." AND release:"..."`. It checks up to 5 results, looking at both the individual release and its release group for genre/tag data. Curated genres are preferred over user-submitted tags, and specific subgenres are preferred over broad ones. On success, the genre is written and recorded against the artist. On failure, the album is deferred.

**Pass 2** — deferred albums are resolved using the most common genre found across all other albums by the same artist. This covers compilations, live albums, and obscure releases that MusicBrainz may not have genre data for.

The following broad genres trigger a search for a more specific subgenre before being used:

> Rock, Pop, Jazz, Blues, Folk, Classical, Country, Metal, Electronic, Dance, Hip Hop, Rap, Soul, Funk, Reggae, Punk, Alternative, Indie, R&B, Ambient, World, Latin, Gospel, Ska, Grunge, Experimental, Noise, Hardcore, Emo, Acoustic, Instrumental, Soundtrack

### Year — oldest-release lookup

The script searches up to 25 MusicBrainz releases for the artist+album combination and collects all available dates — both from individual releases and from the release group's `first-release-date`. The oldest valid year (between 1900 and 2100) is written to the `TDRC` tag.

### Rate limiting

The script sleeps 0.5 seconds between individual MusicBrainz API calls and 1 second between album folders to stay within MusicBrainz's rate limit guidelines.

---

## Output

### Verbose mode (default)

```
────────────────────────────────────────────────────────────
  Pass 1: MusicBrainz lookup
────────────────────────────────────────────────────────────

📁 ./mp3/b/bob_mould/2025_here_we_go_crazy
  Artist : Bob Mould
  Album  : Here We Go Crazy
  Genre  : Indie Rock
  [✓] Tagged 12/12 file(s) — genre='Indie Rock'

📁 ./mp3/b/bob_mould/1998_bob_mould
  Artist : Bob Mould
  Album  : Bob Mould
  [~] Genre not found — deferring for artist fallback.

────────────────────────────────────────────────────────────
  Pass 2: resolving 1 deferred genre(s) via artist fallback
────────────────────────────────────────────────────────────

📁 ./mp3/b/bob_mould/1998_bob_mould
  Artist : Bob Mould
  Album  : Bob Mould
  Genre  : Indie Rock  (artist fallback — majority across known albums)
  [✓] Tagged 11/11 file(s) — genre='Indie Rock'

============================================================
  Mode             : genre
  Albums processed : 2
  Successfully tagged : 2
  Via artist fallback : 1
============================================================
```

### Silent mode (`-s`)

```
  Mode: genre | Found 42 album folder(s). Processing…

  [████████████████░░░░░░░░░░░░░░░░░░░░░░░░]  40%  17/42  here_we_go_crazy ⠹

============================================================
  Mode             : genre
  Albums processed : 42
  Successfully tagged : 40
  Via artist fallback : 3
  Could not tag    : 2
────────────────────────────────────────────────────────────
  Untagged albums:

  📁 ./mp3/x/xiu_xiu/2003_a_promise
     Artist : Xiu Xiu
     Album  : A Promise
     Reason : No MusicBrainz genre match and no other albums found for this artist to infer a genre from

  📁 ./mp3/v/various/1998_compilation
     Reason : No artist/album ID3 tags found in '01-track.mp3'

============================================================
```

The miss list is always shown at the end — even in silent mode — so you never have to re-run in verbose mode just to find out what failed.

---

## Notes

- The script only fills **missing** tags. It will never overwrite an existing genre or year.
- Year tags are written as `TDRC` (ID3v2.4). Players that only read `TYER` (ID3v2.3) may not see them — use a tag editor like [MusicBrainz Picard](https://picard.musicbrainz.org/) to convert the tag version if needed.
- MusicBrainz data is community-contributed. Results vary by artist popularity and how well-catalogued the release is.

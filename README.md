# Needle

A private music guessing game with solo play, online multiplayer rooms, and a video race. Features animated records, reactive particles, and audio analysers.

## Running it

**Docker (recommended):**

```sh
docker compose up -d --build
```

Open http://localhost:3000

**Local (preview mode only, no extra packages needed):**

```sh
python server.py
```

## Requirements

- Python 3.12 (standard library only for preview mode)
- Docker (installs yt-dlp, FFmpeg, Node for YouTube videos)
- SQLite (bundled with Python)

## Environment (`.env`)

```env
# Use YouTube instead of Deezer preview audio (optional)
AUDIO_SOURCE=youtube

# Spotify playlists (optional)
SPOTIFY_ACCESS_TOKEN=...
# or for auto-renewal:
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REFRESH_TOKEN=...
```

Preserve `.env` and `data/` between deploys.

## Modes

- **Name the Song** — guess from snippets of 0.1 → 0.5 → 2 → 8 → 15 seconds
- **Pick the Song** — 5-second snippet, four choices
- **Video Race** — guess the song from a video; faster guesses score more (20–1 points)
- **Hottest Hits** — hit-based rounds (Party mode)
- **Party** — mix any of the above, shuffled in cycles

Online rooms support 2–8 players. Rooms and scores are in memory and reset on server restart.

## Tests

```sh
python -m unittest -q
node test_audio_ui.cjs
node test_mix_ui.cjs
```
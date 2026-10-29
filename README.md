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
- **Hottest Hits** — highly recognizable hit-based rounds
- **Song Duel** — online only, 2–8 players; 30 seconds to choose a song, 30 seconds to select five 5-second clips, then 45 seconds of unlimited plays and guesses. Includes volume, a visualizer, search suggestions, and reveal previews.
- **Party** — mix any of the above, shuffled in cycles; Song Duel can be included in online rooms
- **Custom Playlists** — play supported modes using a public YouTube or Spotify playlist
- **Daily Challenge** — five shared songs each day, with persistent results

The Anime rotation supports song/artist or anime-title answers (English, romaji, and Japanese). Anime Video Race plays opening videos and always asks for the anime title.

Online rooms support 2–8 players. Hosts can edit settings, switch modes, and start a rematch in the same lobby. Active rooms reset on server restart.

Scores, daily challenges, and name-based song history persist in SQLite under `data/` (created automatically; no manual database setup). Leaderboards are grouped by mode and difficulty. Song Duel, including Party duel rounds, does not add songs to repeat-exclusion history. Preserve `data/` between restarts and updates; the Docker Compose bind mount already does this.

## Tests

```sh
python -m unittest -q
node test_audio_ui.cjs
node test_mix_ui.cjs
```
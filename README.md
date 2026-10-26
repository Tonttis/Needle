# Needle
A private, self-hosted music guessing game. Dark responsive interface, two solo modes, genre discovery and 2–8-player rooms.

## Start
Install Docker with Compose. Extract this folder, open a terminal here, then:

```sh
docker compose up -d --build
```
Open http://localhost:3000 (or http://YOUR-SERVER-IP:3000).
Friends use the same server address. Create a room, copy the invite, wait for everyone, then start. For access outside your LAN, use your existing HTTPS reverse proxy or private VPN. The application has no account authentication: keep access private at the network/proxy layer. Room codes are invitations, not a security boundary.

## Audio sources
Default: Deezer metadata and preview audio. Version 2 uses an editorial artist registry in catalog.py instead of IP-sensitive chart discovery. Each new game selects up to four genre/language lanes and up to eight artists per lane, resolves exact artist names, and fetches their tracks live. Worldwide is the default; Europe includes Finland. North America and Finland are separate selectable scenes. Supported genres are Mixed, Pop, Rock, Metal, Rap / Hip Hop, Dance, Electronic and R&B. Unsupported combinations produce an explicit message instead of silently widening the selection.

Easy selects the five highest-ranked available tracks per artist; Normal selects the top fifteen; Hard selects tracks 6–40 when available. This is a familiarity heuristic, not a globally calibrated difficulty scale. Selection remains within the curated artist registry, which can be extended in catalog.py. Songs are fetched automatically; artist discovery itself is editorially bounded. Tracks unavailable in your region may still be absent, but local charts no longer decide the mix.

Guess mode now shows no suggestions until at least two characters are typed. Each query searches the full current game's matching genre/language lane, ranks matches, and returns up to 25 suggestions. Results change with the query; there is no fixed visible answer board. It searches the discovered game pool, not the entire Deezer catalog. Multiple choice still draws three comparable distractors and the real answer. Server validates guesses and awards points only for the real track ID. Duplicate remasters, live recordings, karaoke and remixes are filtered.

Track-detail lookups enrich suggestions, multiple-choice options and revealed answers with all contributor names supplied by Deezer. If the detail provider is unavailable, primary-artist metadata remains as a fallback. Credits unavailable in the provider cannot be recovered. Additional contributor names become searchable once hydrated in the current game's pool.

Language tags are curated at artist level, not verified from lyrics for each recording. Multilingual artists, collaborations and instrumental tracks can still cross languages. Region means artist scene/origin, not a song's language. Genre labels are editorial artist-level categories, so crossover tracks may appear. This avoids pretending Deezer supplies reliable track-language metadata. Exact language enforcement would require a verified per-recording catalog or review process.

Optional YouTube: create `.env` alongside compose.yaml containing:

```
AUDIO_SOURCE=youtube
```

Then `docker compose up -d`. Metadata still comes from Deezer; yt-dlp searches YouTube for artist + title + official audio and extracts the first 20 seconds. This can select a wrong version or intro silence, and YouTube may block server requests. This source is experimental. The Docker image includes yt-dlp and FFmpeg. Rebuild with `docker compose build --no-cache` to update the downloader. Downloads have a 100-second timeout and 30 MB file limit. YouTube files persist in `data`; remove old files when no sessions are playing to reclaim disk space. Preview mode does not save audio to disk.

## Rules
Name the song: 0.1, 0.5, 2, 8, 15 seconds. Search a title or artist and click to submit. Skip advances. Solo points: 5, 4, 3, 2, 1. Selection uses provider track IDs: alternate releases/remasters may not match.
Pick the song: five seconds, four choices, one point for a correct answer.
Multiplayer: everyone submits a hidden answer each stage. Once everyone answers or time expires, any correct players each earn one point; the answer is revealed. If nobody gets it, advance the snippet. Both simultaneous winners score. First stage allows 45 seconds; later stages allow 30. Host advances songs. Browser reload reconnects using sessionStorage. A missing player is handled by the stage timeout. Host leaving permanently requires a new room.

## Implementation
Python 3.12 standard-library HTTP server; vanilla JS/CSS; no frontend build. One-second state polling instead of WebSockets keeps deployment simple. AudioContext schedules clip lengths. Server controls answers, scoring and stage transitions. Browser receives full preview audio, so this is a friendly game, not cheat-proof competitive software.
Rooms live in memory and disappear on restart. Expired rooms are cleared when a new room is created. No persistent player history or decade/language filters yet. Genre classification uses the editorial registry. Audio errors are displayed for retry; automatic broken-song replacement is not yet implemented. Playback timers begin at round creation, rather than waiting for every audio download.

## Validation
Run `python -m unittest -v` in this folder. Eleven tests cover catalog filtering, difficulty bands, language-lane distractors, 25-answer boards, normalization, and stage advancement, waiting for both guesses, timeout, final miss, repeat avoidance and simultaneous winners without double scoring. Python compilation and JS syntax checks passed during creation.
Live catalog access returned non-JSON in the build environment, so catalog discovery, real audio, YouTube extraction and Docker build still need verification on your server. Browser visual QA was not performed. Treat this as a functional first implementation pending that integration check.

## Local development
`python server.py` then open http://localhost:3000. Preview mode has no Python package dependencies. YouTube mode additionally needs yt-dlp and FFmpeg on PATH.
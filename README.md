# Needle V5
Private music guessing with two modes, genre/scene/familiarity filters, animated vinyl, audio-reactive particles, and multiplayer rooms.

## Install or upgrade
Keep your `.env` and `data/` when replacing application files. Include the new `artist_seeds.py` file. From this folder:

```sh
docker compose up -d --build
```

Open http://localhost:3000 or your server's address. The header shows **V5**. For Coolify, replace/commit these application files in your repository and redeploy the Compose service. This ZIP does not modify your remote repository automatically.

Use a private VPN or access-controlled reverse proxy for friends outside your LAN. No user accounts are implemented; room links invite players but do not protect the whole service.

## What changed in V5
- 735 distinct discovery artists across 27 countries, including 137 Finnish artists. Artist/song availability depends on the provider.
- Country-balanced discovery replaces randomly selecting four genre/language lanes. Within countries, discovery rotates through genres.
- A new game normally attempts 80 artist anchors (or every eligible anchor for narrow selections), with up to 160 attempts when lookups fail. Tracks are fetched automatically.
- The game requires at least 12 distinct playable artists, or every eligible artist if a narrow genre has fewer than 12. Europe/Worldwide also require multiple represented countries. Failed lookups cannot silently start a two-artist game.
- Song selection is artist-first, not track-first. It selects least-used artists so a prolific artist cannot dominate. Artists repeat only after the eligible available artists have been used; a recent-artist window breaks ties.
- Europe balances countries and caps Finnish tracks at `ceil(rounds / 10)` per match: one for a 5- or 10-song game, two for 20, three for 30. Explicit Finland mode has no country cap.
- Same-language groups need only four playable tracks for multiple choice. Small country/language groups are no longer thrown out for failing to contain 25 tracks.
- The game displays its actual pool size: songs, artists, and countries.
- Metadata is cached in `data/catalog-cache.sqlite` for 24 hours. Up to seven-day-old metadata can be used if the provider is temporarily unavailable. Audio preview URLs can still expire. Outbound metadata requests are paced and use six loading workers.
- Dedicated final scoreboard: sorted scores, shared rank for ties, Home, and host-controlled Back to lobby. Returning to the lobby resets scores and round state while preserving the room, players and catalog. The next match avoids previously used tracks until the pool runs out. Create a new room for a fresh catalog draw.

## Music selection and limits
`artist_seeds.py` and `catalog.py` contain editorial discovery anchors, not a fixed list of songs. The registry is deliberately broad but is not the entire Deezer catalog, and it does not automatically discover new artists outside that registry. Track lists and popularity are fetched live. Regional availability can still remove individual recordings.

Region means artist origin/scene, not the language of every song. Language is a predominant-language hint at artist level; collaborations, multilingual artists and instrumentals can cross that label. Genres are editorial artist-level categories and may include crossover material. These are not verified recording-level language classifications.

Easy selects up to the five highest-ranked available tracks per artist. Normal selects up to fifteen. Hard selects tracks 6–40 when available, falling back for a small catalog. These are artist-relative familiarity bands, not universal/global popularity thresholds. Hard intentionally includes deeper cuts.

Guess search is empty until two characters are typed. It returns up to 25 query-dependent matches from the game's matching genre/language pool. It does not display all answers or search the entire provider catalog. Multiple choice chooses same-language distractors, preferring the same genre, nearby popularity and different artists. Track detail lookups enrich all displayed contributors when available; primary credits remain the fallback on provider failure.

## Rules
**Name the Song:** 0.1 → 0.5 → 2 → 8 → 15 seconds. Select a search result to submit, or skip. Solo points: 5, 4, 3, 2, 1.

**Pick the Song:** five seconds and four choices; a correct answer earns one point. Wrong/skip earns zero.

**Multiplayer:** 2–8 players join a room before the host starts. Everyone submits one hidden guess per stage. At the deadline or once everyone answers, correct players each earn one point and the answer is revealed. If nobody gets it, the next snippet unlocks. Host advances rounds and returns everyone to the lobby after the scoreboard. A missing player is handled by the timer. Browser reload reconnects through sessionStorage; a permanently absent host currently requires creating a new room.

First stage: 45 seconds; later stages: 30 seconds. Timing begins after round metadata hydration, but not after every player has downloaded audio. Rooms/scores live in memory and disappear on server restart. The browser receives preview audio, so this is a friendly game rather than a cheat-proof tournament platform.

## Audio and visuals
Default audio is Deezer preview audio. To enable optional YouTube extraction, create `.env`:

```
AUDIO_SOURCE=youtube
```

Restart with Docker Compose. Metadata still comes from Deezer. yt-dlp searches artist/title and extracts the first 20 seconds using FFmpeg. YouTube can block server requests or return the wrong version; this source remains experimental. Files persist in `data/`; remove old downloads when no sessions are using them to reclaim disk. Rebuild without cache to update yt-dlp. Default preview mode does not save audio on disk.

Vinyl rotates on home and game screens. Motion defaults to Full; header controls cycle Full / Calm / Off and remember your choice. This explicit application preference overrides OS reduced motion. Menu ambience is an original synthesized soft chord, opt-in with its own volume slider, fading out during gameplay or while the tab is hidden.

Real Web Audio frequency data drives particles, waves, center equalizer and side spectra during previews. On reveal, the available preview plays automatically once browser audio is unlocked through a user interaction. If browser autoplay rules prevent that, press Play. Home/Next stops playback.

## Validation
Run:

```sh
python -m unittest -v
```

23 tests cover matching, contributors, scoring, timeouts, discovery filtering and anti-repeat selection. A deterministic test runs 1,000 complete ten-song Europe matches against intentionally Finnish-heavy fixture data: each had ten different artists and countries and at most one Finnish track. Finnish sequences of 3, 10, 20 and 30 songs verify artist rotation and no consecutive repeat. A partial-provider-failure test verifies a two-artist result is rejected.

HTTP integration tests run actual two-player, ten-round games in both modes through creation, joining, guessing, scoring, final results, returning to the lobby and restarting. Catalog data is mocked for these tests.

Browser QA verified the V5 final-score layout, tied rankings, score reset, preserved players, and Back to lobby using an isolated UI fixture. V4 browser tests verified record rotation, audio analyzers and automatic reveal playback with synthesized test audio.

A live Deezer request in this environment returned an HTML "Site Unavailable" response. Real catalog coverage and real-song playback on your deployment are not verified here. No QA fixtures are included in the ZIP.

## Implementation
Python 3.12 standard-library HTTP server, SQLite metadata cache, vanilla JS/CSS and one-second room polling. Preview mode needs no Python packages. Run locally with `python server.py`; YouTube mode also needs yt-dlp and FFmpeg. Docker installs those automatically.

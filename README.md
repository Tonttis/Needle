# Needle V6
Private music guessing with two modes, genre/scene/familiarity filters, animated vinyl, audio-reactive particles, and multiplayer rooms.

## Install or upgrade
Keep your `.env` and `data/` when replacing application files. Include the new `artist_seeds.py` file. From this folder:

```sh
docker compose up -d --build
```

Open http://localhost:3000 or your server's address. The header shows **V6**. For Coolify, replace/commit these application files in your repository and redeploy the Compose service. This ZIP does not modify your remote repository automatically.

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

29 tests cover caching, latency, matching, contributors, scoring, timeouts, discovery filtering and anti-repeat selection. A deterministic test runs 1,000 complete ten-song Europe matches against intentionally Finnish-heavy fixture data: each had ten different artists and countries and at most one Finnish track. Finnish sequences of 3, 10, 20 and 30 songs verify artist rotation and no consecutive repeat. A partial-provider-failure test verifies a two-artist result is rejected.

HTTP integration tests run actual two-player, ten-round games in both modes through creation, joining, guessing, scoring, final results, returning to the lobby and restarting. Catalog data is mocked for these tests.

Browser QA verified the V5 final-score layout, tied rankings, score reset, preserved players, and Back to lobby using an isolated UI fixture. V4 browser tests verified record rotation, audio analyzers and automatic reveal playback with synthesized test audio.

A live Deezer request in this environment returned an HTML "Site Unavailable" response. Real catalog coverage and real-song playback on your deployment are not verified here. No QA fixtures are included in the ZIP.

## Implementation
Python 3.12 standard-library HTTP server, SQLite metadata cache, vanilla JS/CSS and one-second room polling. Preview mode needs no Python packages. Run locally with `python server.py`; YouTube mode also needs yt-dlp and FFmpeg. Docker installs those automatically.

## V6 performance audit
Catalog size and selection quality are preserved: the same 735 discovery artists, 80-anchor target, 160-attempt recovery budget, 12-second provider timeout, difficulty bands, country balancing and artist rotation remain. No smaller starter catalog is shipped.

- Search and Next perform no blocking provider requests. Contributor enrichment uses two background workers with a bounded pending set. Credits appear when returned by the provider; primary credits are available immediately.
- Catalogs preload when filters are selected, and completed full pools persist for 24 hours in `data/pool-full-*.json`. Concurrent requests share the same catalog job. Cold builds may still be slow because they fetch the full catalog; Start waits up to 20 seconds, then gives a retry message while preserving the job.
- Identical metadata requests share one in-flight fetch. Existing SQLite metadata caches are preserved and reused.
- Search computes normalization and fuzzy ranking once per candidate and works outside the global game lock. Pool statistics are computed once per room.
- Audio requests share an in-flight fetch and a bounded 64 MB / 15-minute RAM cache. Independent YouTube tracks no longer block behind one global download lock. Audio quality/encoding is unchanged.
- Browsers prefetch the current round's preview and retain up to three downloads. Choice buttons are not rebuilt every polling tick, preserving focus/click targets.
- HTTP/1.1 responses include Content-Length to allow connection reuse. Idle particle drawing is capped near 30 fps, active playback remains frame-rate driven, and hidden game canvases are skipped. Particle count and visual design remain intact.

New dependency-free source file: `audio_cache.py`. Preserve `.env` and `data/`, copy the complete package and rebuild. The header shows V6.

Controlled local latency regression tests deliberately delay contributor lookups and require cached-catalog creation, search and Next each to finish under 250 ms. Parallel audio listeners are tested to share one download, with cache bounds and failure recovery checks. These are local tests, not a promise about internet latency or uncached YouTube downloads.

V6 also renders mutation responses immediately and ignores polls begun before a newer action, preventing stale state from delaying Next or leaving a rejected guess disabled. The browser favicon is supplied in seven ICO sizes (16–256 px), SVG and 180 px Apple touch format. No runtime icon-generation dependency is needed.

Live V5 testing at the supplied deployment reproduced a slow startup (935 songs / 68 artists loaded) and search waiting until a stage transition. V6 has been tested locally, not deployed to that server. The full-catalog cache test verifies unchanged track counts, shared jobs and disk-cache reuse after clearing memory.

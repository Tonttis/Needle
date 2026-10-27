# Needle

A private three-mode music guessing game with solo play, online rooms, animated records, reactive particles and audio analysers. This release rebuilds song recognition and scene selection. See [CATALOG_RESEARCH.md](CATALOG_RESEARCH.md) for sources, rules and limitations.

## Deploy

```sh
docker compose up -d --build
```

Open http://localhost:3000 or your server's address. In Coolify, commit/copy the **complete package** into the application repository and rebuild/redeploy the Compose service. Preserve `.env` and `data/`. The header must show **V8**. This ZIP does not update GitHub or the live server automatically.

New required files include `recognition.py` and `recognition_data.tsv`; retain `audio_cache.py`. Docker copies them automatically. V7 ignores old pool selection files while reusing metadata/audio caches. A cold mix may still take time to build; Start waits up to 20 seconds and preserves the background job if it needs a retry. Selecting filters preloads the mix.

## Music selection

- 863 artist discovery anchors; 930 named-song calibration entries across 389 artists. Counts describe source metadata, not guaranteed playable provider tracks.
- 18 genres plus Mixed: Pop, Rock, Metal, Rap / Hip Hop, Dance, Electronic, R&B, Indie / Alternative, Punk / Pop Punk, Soul / Funk, Country, Jazz, Blues, Reggae, Latin, K-pop, J-pop and Afrobeats.
- 28 country scenes, plus Worldwide, Europe, North America, Nordics, Latin America, Asia, Africa and Oceania.
- **Europe is an audience-oriented mix**, including international crossover artists. Specific countries focus on their local artists. Neither follows your IP location.
- Easy requires a calibrated recognisable song. Medium adds popular favourites. Hard excludes Easy anchors. Expert and Impossible draw progressively deeper from the provider's available artist top 50. `Normal` remains a backwards-compatible alias for Medium.
- Least-used artists are selected before repeats. Europe caps Finland at one answer per ten rounds (rounded up), with soft country balancing rather than forced country rotation.
- Both game modes use the same difficulty rules. Choice distractors prefer similar familiarity and language. Guess search appears only after two characters, changes with the query, and shows at most 25 matches.
- Full fetched tracks remain available for search and distractors. Insufficient coverage produces a clear error rather than silently adding obscure Easy tracks. Unsupported combinations are greyed out before starting.

Calibration is editorial and informed by charts/streaming/radio sources; it cannot guarantee familiarity for every listener. The Easy anchor list is maintained in the source; metadata, previews and broader catalogue tracks are fetched automatically. Genre/language are artist-level hints and collaborations can cross categories. All contributor credits display when the provider supplies them; enrichment runs in the background.

## Rules

**Name the Song:** snippets of 0.1 → 0.5 → 2 → 8 → 15 seconds. Guess by selecting a search result or skip. Solo points: 5, 4, 3, 2, 1.

**Pick the Song:** five seconds, four choices. Correct earns one point; wrong/skip earns zero.

**Online:** 2–8 players join before the host starts. Everyone submits a hidden guess per snippet. Once all have answered or time expires, every correct player receives one point. If nobody is right, the next snippet unlocks. The host advances songs. Final results show ranked scores and ties, Home and host-controlled Back to lobby; lobby return resets scores and retains the players.

First snippet: 45 seconds; later snippets: 30 seconds. The clock does not wait for every browser's audio download. Rooms/scores are in memory and disappear on server restart. Reload reconnects through sessionStorage; an absent host requires a new room. Audio reaches the browser, so this is a friendly game rather than cheat-proof tournament software.

## Audio and visuals

Default audio is Deezer preview audio. Optional YouTube extraction uses `.env`:

```env
AUDIO_SOURCE=youtube
```

Restart/rebuild the Compose service. Metadata still comes from Deezer. yt-dlp searches artist/title and extracts the first 20 seconds with FFmpeg; it can be blocked or select the wrong recording. Downloaded files persist in `data/`. Preview mode uses a bounded RAM audio cache, not persistent audio files.

The in-game volume changes active playback immediately, including mute, and is remembered. Failed preview URLs trigger a fresh lookup of that exact track. Invalid responses are rejected and failed browser downloads can retry. Provider removals/blocks can still prevent playback.

Records spin on home/game screens. Full / Calm / Off motion controls remember your choice; Full overrides OS reduced motion. Menu ambience is an opt-in original synthesised chord, with its own volume, paused during games/hidden tabs. Real Web Audio frequencies drive the visuals. The answer reveal automatically plays the preview once browser audio is unlocked; use Play if autoplay is blocked.

## Implementation and performance

Python 3.12 standard library, SQLite metadata cache, vanilla JavaScript/CSS and one-second room polling. Preview mode needs no Python packages: `python server.py`. Docker installs yt-dlp, FFmpeg and Node for the optional YouTube mode.

Shared catalogue jobs and 24-hour persistent full-pool caches avoid rebuilding a mix for every player. Identical metadata/audio requests share in-flight work. Contributor enrichment never blocks search or Next. Audio RAM cache is bounded to 64 MB / 15 minutes. The browser prefetches current-round audio and keeps at most three downloads. Mutation responses render immediately and stale polls are ignored. Favicon formats: multi-size ICO, SVG and Apple touch PNG.

## Validation

```sh
python -m unittest -q
node test_audio_ui.cjs
node test_mix_ui.cjs
```
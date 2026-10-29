# Needle 11 — selection and history

The v11.1 Japanese catalog expansion is described in `JAPANESE_CATALOG.md`. The cached-provider audit below records v11.0, before that expansion.

## Selection contract

All catalog-based modes use the same picker. Song Duel is a separate online mode with player-selected songs; see `SONG_DUEL.md`. Party changes the round's mode/tier, then uses that picker. Custom playlists retain their own eligible tracks. Hottest Hits still requires its curated hit flag. Difficulty and decade are never widened to manufacture variety.

1. Filter to the selected difficulty and mode.
2. Exclude songs already assigned in the current game, matching both provider ID and normalized artist/title identity.
3. Prefer songs unheard by every participating profile. There is **no 10% replay lottery** anymore. No heard song is selected while an unheard eligible alternative remains in this pool.
4. If the eligible pool is exhausted, prefer the least-played, oldest songs. A finite playlist can eventually repeat; it never silently expands to another difficulty or decade.
5. Apply audience balance and the previous game's artist preferences within those candidates. These preferences yield when the pool cannot satisfy them.
6. Prefer the least-used artists within the game, then the artists with the lowest persistent exposure across the participating names. Draw an artist first, then a song, so larger discographies do not gain extra chances.

Worldwide and Europe broad-genre games cap the Spanish/Latin and French lanes at roughly 20% each and 30% combined, rounded down with a minimum of one slot. Five rounds therefore target one combined slot. English-language Latin crossover artists count toward the Latin lane. Explicit Latin, Reggae, Afrobeats, K-pop, J-pop, custom playlists, and local scenes retain their own scope. These are editorial mix preferences, not nationality or lyric detection.

## Persistent profiles and all modes

Every **assigned round** is recorded for each participating name, before it can be skipped, abandoned, or lost to a restart. This includes guessing, multiple choice, Hottest Hits, Video Race, Party, Daily Challenge, and custom playlists. Only selected answers count; search results, distractors, reveal replays, and background prefetch reservations do not.

The existing `played_songs` table stores both provider IDs and normalized identities, play counts, and timestamps. Artist exposure is derived from those identities. Older identity punctuation is normalized on read without deleting or rewriting history. Names remain the profile identity; there is no authentication layer.

The next-round reservation is revalidated against current persistent history. Another room using the same name can invalidate a reservation before it is used. The existing server lock serializes room transitions within this server process.

Daily Challenge remains one shared, persisted challenge per date. Existing snapshots do not change after an update. New daily snapshots use the same picker, five distinct artists, and the previous 30 daily snapshots for rotation. Daily songs enter personal history, but personal history does not change that day's shared answers.

## Catalog coverage

Reggaeton/Latin crossover seeds such as Bad Bunny, Daddy Yankee, J Balvin, and Pitbull no longer enter generic Rap / Hip Hop merely through inherited discovery tags. Their Latin/Pop discovery lanes remain available.

Rap Easy now has 38 global artist anchors and 103 explicit song entries. Familiarity remains a song-level editorial decision: an artist's unknown album cuts do not become Easy. The expansion includes Jay-Z, 2Pac, Missy Elliott, Run-D.M.C., The Notorious B.I.G., Nas, Lauryn Hill, and others.

Examples of corroborating chart history (these do not establish that every listener knows a song):

- https://www.officialcharts.com/songs/jay-z-ft-alicia-keys-empire-state-of-mind/
- https://www.officialcharts.com/songs/2pac-changes/
- https://www.officialcharts.com/artist/10450/Missy-Elliott/
- https://www.officialcharts.com/songs/run-dmcaerosmith-walk-this-way/

Pool building targets **eligible artists**, not a number of HTTP responses. Easy and Hits avoid fetching artist seeds that cannot qualify. Other tiers retain the bounded discovery budget and six-worker provider concurrency. Exact artist names take precedence over punctuation aliases; aliases accommodate provider spellings such as JAY Z. Sparse language lanes are no longer deleted from either the catalog or decade results.

## Performance and persistence

Round selection makes no provider requests. Metadata caching, background preparation, periodic pool replacement, and decade album batching remain in place. Canonical text matching is bounded-cache memoized. Profile reads use the existing primary-key index; single-profile reads avoid aggregation. SQLite connections are closed after use.

No database setup or migration is required. Keep the existing persistent `data/` volume and `.env` during deployment. This package contains neither user databases nor credentials. The supplied README is unchanged.

## Verification and limits

- Full regression suite: 150 tests passed with the supplied database-copy tests enabled; additional playlist, lane, identity, history, and latency regressions were run after final refinements.
- Synthetic selection matrix: 13,455 rounds across every advertised scene/genre/difficulty combination, plus separate mode/decade tests. These test selection contracts, not live catalog availability.
- Read-only provider-cache audit: `selection-audit-v11.0.json` contains all 192 Worldwide/Europe genre/tier checks. The supplied cache supports 92 of these and is incomplete for the others; unavailable combinations are explicitly reported, never filled with invented songs.
- The cache supports 65 distinct Easy Worldwide Rap songs from 27 artists, versus 47 songs from 20 artists in the previous package. Its first three five-round games use 15 songs by 15 artists. All 9,200 cached-pool simulated rounds have zero premature repeats.
- A local stress benchmark reading 20,000 history entries and selecting from 5,000 tracks measured approximately 70 ms median / 90 ms p95. This is local CPU/database time, not a promise about provider or media-download latency.
- All JavaScript regression checks passed. Live Deezer metadata could not be verified from this environment because the probe did not return valid JSON. Browser playback was not revalidated live for these backend changes.

Reproduce the cache audit without network access or database writes:

```sh
python3 audit_selection.py /path/to/catalog-cache.sqlite > report.json
```

Run regressions, optionally against read-only copies made from supplied databases:

```sh
NEEDLE_TEST_DATABASES=/path/to/database-folder python3 -m unittest discover -q
for f in test_*.cjs; do node "$f" || exit 1; done
```

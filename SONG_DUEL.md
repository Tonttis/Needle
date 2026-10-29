# Needle 12 — Song Duel

Song Duel is online only and requires exactly two players. Select its card on the home page, enter a name, create a room, and invite one friend. The host chooses the number of rounds in the lobby. Both players keep the same room and names for rematches.

## A round

1. **Choose the opponent's song — up to 30 seconds.** Search the music provider without catalog/genre filters, or paste a public YouTube video link. Confirm the song to send it to the opponent. For a YouTube pick, check the editable song title and artist: those are the accepted answers. Each player sees only their own pick's metadata.
2. **Choose five clips from the incoming song — up to 30 seconds.** The timeline shows the opponent's song duration without a title, artwork, waveform recording, or listening preview. Choose five start positions. Each selected part lasts five seconds and stays inside the song. Selections save as they are made and can be removed/replaced until locked. If time expires, missing positions fill automatically across the remaining timeline.
3. **Listen and guess — 45 seconds.** After both players' clips load, a short synchronized countdown starts the guessing window. Click any of the five clips in any order and replay them without a limit. Type guesses without a limit or cooldown. A correct song earns one point; both players can score. The round ends when both have guessed/skipped, or time expires. Titles and artists are revealed after the round ends.

The stage limits are maximums: both confirmed song choices can advance the first stage early, and both locked clip selections can advance the second stage early. Media download and audio preparation do not consume the clip-selection or guessing clocks.

## Answers and timeouts

The song title alone is enough; artist plus title also works. Matching ignores capitalization, accents, punctuation, common official-video title noise, and supported title aliases. Longer answers tolerate small typos. Artist-only guesses and arbitrary substrings do not count.

If only one player supplies a playable song before picking closes, that player wins the round by forfeit (+1). If neither picks, the round ends with no points. Missing clip selections are filled automatically. A correct guess or skip locks that player's own guessing controls while the other player continues.

Unavailable, private, live-streaming, blocked, or oversized videos may not be playable. The existing media download/cache limits still apply. A media or audio-loading failure pauses play and gives the host a retry or skip-round control. Retrying starts fresh picks within the same round and does not add another scoring maximum. Skipping the failed round awards no points.

## Privacy, persistence, and performance

- Round phases, deadlines, correct answers, and scores are server-authoritative. Clients cannot submit guesses after expiry or score twice.
- Only the owner sees their selected song before the reveal. The guessing player receives five separately encoded audio clips, never the full source file, source title, thumbnail, or source URL.
- Clip routes require the player's room, session token, private clip key, valid round, and active phase. Another player's token/key combination and stale rounds are rejected. Source title/artist metadata is stripped from encoded clips.
- Clip selection revisions prevent older requests from overwriting newer choices. Stale queued downloads and encoders are discarded when a pick is replaced or a round is retried.
- The incoming song is counted once in the guessing player's persistent song history when guessing begins. Name/title aliases use the existing history normalization. Explicit player picks may intentionally repeat; no automatic catalog draw is involved.
- Finished matches are saved in SQLite under mode `duel`, fixed difficulty `Duel`, multiplayer enabled. Normal profile stats, leaderboards, and history clearing still work. No database migration is required.
- Downloads use the existing bounded, persistent media cache; active duel source files are protected from cleanup. At most four duel media jobs run at once. Only the current round's short clips are retained in room memory, and ordinary catalog games do not invoke this pipeline.
- Refreshing the page resumes the same session, saved clip positions, and server clock. Mobile keyboard layout keeps the guess form visible. Room sessions, as with the other multiplayer modes, remain in server memory; historical scores and song exclusions remain persistent.

The supplied README is unchanged. Keep the existing `data/` volume and `.env` during deployment.

## Validation

`test_duel.py` covers HTTP lifecycle, two-player/host restrictions, cross-player clip privacy, deadlines, guessing/replay rules, scoring, persistent history and results, rematches, partial-selection autofill, failed/expired jobs, and real FFmpeg slicing without source metadata.

The optional `test_duel_browser.cjs` starts a localhost-only fixture server and exercises two real browser sessions with actual generated audio. It checks desktop, phone portrait, phone landscape, keyboard layout, refresh/reconnect, playback/volume effects, guesses, scoring, leaderboards, rematch, and a missed-pick timeout. The fixture's clock-control route exists only in `duel_browser_fixture.py`, never in the production server.

```sh
python3 -m unittest discover -q
for f in test_*.cjs; do node "$f" || exit 1; done
# Optional, with Playwright, Chromium, and FFmpeg installed:
NEEDLE_BROWSER_TESTS=1 NEEDLE_CHROME=/path/to/chrome node test_duel_browser.cjs
```

Live provider availability is separate from the fixture tests. Search and full-song downloads use the existing provider and yt-dlp setup; the new mode does not require additional credentials.

# Needle 12.3 — Song Duel

Song Duel is online only and supports 2–8 players. Select its card on the home page, enter a name, create a room, and invite friends. The host chooses the number of rounds in the lobby. Everyone keeps the same room and names for rematches. Each player supplies one song and receives one song each round. The server rotates assignments so everyone faces each other before that rotation repeats; nobody receives their own pick. The picker sees who they are choosing for, and the listener sees who supplied their mystery song.

## A round

1. **Choose the assigned player's song — up to 30 seconds.** Search the music provider without catalog/genre filters, or paste a public YouTube video link. Confirm the song to send it to the assigned player. For a YouTube pick, check the editable song title and artist: those are the accepted answers. Each player sees only their own pick's metadata.
2. **Choose five clips from the incoming song — up to 30 seconds.** The timeline shows the incoming song duration without a title, artwork, waveform recording, or listening preview. Choose five start positions. Each selected part lasts five seconds and stays inside the song. Selections save as they are made and can be removed/replaced until locked. Clips are sorted by start time after every change, on both the client and server. Clip saves are serialized and superseded draft requests are skipped, so a lock cannot overtake its preceding save. Their timeline numbers, slot numbers, encoded audio, and replay buttons always follow that same left-to-right order, including after refresh and automatic filling. If time expires, missing positions fill automatically across the remaining timeline.
3. **Listen and guess — 45 seconds.** After all active players' clips load, a short synchronized countdown starts the guessing window. Click any of the five clips in any order and replay them without a limit. Search song/artist suggestions or type guesses without a limit or cooldown. Selecting a suggestion submits it; suggestions come from the global provider search without adding the secret answer. A correct song earns one point; everyone can score. The round ends when everyone has guessed/skipped, or time expires. Titles and artists are revealed after the round ends. All submitted songs then play one by one for ten seconds each, using Deezer previews where available and prepared source audio as a fallback. Replay/stop controls are available, and the current song is highlighted. Reveal cards are paginated in pairs for larger groups, and the page follows the preview currently playing. Playback respects saved volume and feeds the visualizer; leaving the reveal stops playback. Browsers that block autoplay show a replay prompt.

The stage limits are maximums: all confirmed song choices can advance the first stage early, and all active players’ locked clip selections can advance the second stage early. Media download and audio preparation do not consume the clip-selection or guessing clocks.

## Answers and timeouts

The song title alone is enough; artist plus title also works. Matching ignores capitalization, accents, punctuation, common official-video title noise, and supported title aliases. Longer answers tolerate small typos. Artist-only guesses and arbitrary substrings do not count.

A player who misses their own song pick sits out that round and cannot guess. A player who supplied a playable song but receives none gets one forfeit point and waits while the rest continue. If nobody supplies a song, the round ends with no points. This keeps the original two-player forfeit behavior and allows partial groups to continue without awarding anyone more than one point per round. Missing clip selections are filled automatically. A correct guess or skip locks that player's own guessing controls while the remaining players continue.

Unavailable, private, live-streaming, blocked, or oversized videos may not be playable. The existing media download/cache limits still apply. A media or audio-loading failure pauses play and gives the host a retry or skip-round control. Retrying starts fresh picks within the same round and does not add another scoring maximum. Skipping the failed round awards no points.

## Privacy, persistence, and performance

- Round phases, deadlines, correct answers, and scores are server-authoritative. Clients cannot submit guesses after expiry or score twice.
- Only the owner sees their selected song before the reveal. The guessing player receives five separately encoded audio clips, never the full source file, source title, thumbnail, or source URL.
- Clip routes require the player's room, session token, private clip key, valid round, and active phase. Another player's token/key combination and stale rounds are rejected. Source title/artist metadata is stripped from encoded clips.
- Clip selection revisions prevent older requests from overwriting newer choices. Stale queued downloads and encoders are discarded when a pick is replaced or a round is retried.
- The incoming song is counted once in the guessing player's persistent song history when guessing begins. Name/title aliases use the existing history normalization. Explicit player picks may intentionally repeat; no automatic catalog draw is involved.
- Finished matches are saved in SQLite under mode `duel`, fixed difficulty `Duel`, multiplayer enabled. Normal profile stats, leaderboards, and history clearing still work. No database migration is required.
- Downloads use the existing bounded, persistent media cache; active duel source files are protected from cleanup. At most four duel media jobs run at once; larger rooms queue within that bound. Preparation timeouts allow for two batches in an eight-player room while the guessing clock remains paused. Only the current round's short clips are retained in room memory, and ordinary catalog games do not invoke this pipeline.
- Refreshing the page resumes the same session, saved clip positions, and server clock. Mobile keyboard layout keeps the guess form visible. Room sessions, as with the other multiplayer modes, remain in server memory; historical scores and song exclusions remain persistent.

The supplied README is unchanged. Keep the existing `data/` volume and `.env` during deployment.

## Validation

`test_duel.py` covers HTTP lifecycle, 2–8-player limits and host restrictions, balanced rotating assignments, complete group rounds, partial-group forfeits, cross-player clip privacy, reveal-only preview authorization, suggestion phase checks, preview fallback, deadlines, guessing/replay rules, scoring, persistent history and results, rematches, partial-selection autofill, failed/expired jobs, and real FFmpeg slicing without source metadata.

The optional `test_duel_browser.cjs` starts a localhost-only fixture server and exercises two real browser sessions with actual generated audio. It checks desktop, phone portrait, phone landscape, keyboard layout, refresh/reconnect, playback/volume effects, guesses, scoring, leaderboards, rematch, and a missed-pick timeout. The fixture's clock-control route exists only in `duel_browser_fixture.py`, never in the production server.

```sh
python3 -m unittest discover -q
for f in test_*.cjs; do node "$f" || exit 1; done
# Optional, with Playwright, Chromium, and FFmpeg installed:
NEEDLE_BROWSER_TESTS=1 NEEDLE_CHROME=/path/to/chrome node test_duel_browser.cjs
```

The optional `test_duel_group_browser.cjs` also exercises an eight-player room with two real browser clients and six HTTP participants: assignments, readiness, private clips, all-player guessing, paginated reveals, sequential previews, eight-player scoreboards, and phone portrait/landscape layouts.

Live provider availability is separate from the fixture tests. Search and full-song downloads use the existing provider and yt-dlp setup; the new mode does not require additional credentials.

## Volume and audio visualization

A labeled volume bar and percentage are visible throughout Song Duel, including the reveal. The slider changes the actual Web Audio gain immediately, supports mute at zero, and shares the saved volume with the other modes. Stop clears playback and its visualization. The volume remains available when the phone keyboard hides the clip buttons.

A combined spectrum and live waveform responds to the actual playing audio during five-second clips and the end-of-round previews. It also feeds the existing background audio effects. One canvas/animation loop is active per client, capped at 30 drawing updates per second and device-pixel ratio 2; there are no new server analysis jobs or media downloads. Stopping, changing phase, starting a different clip, or leaving cancels the old animation.

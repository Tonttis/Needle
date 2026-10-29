# Needle 11.1 — J-pop and Anime

The supplied README is unchanged. Keep the existing data volume and environment settings on update; no database migration is required.

## J-pop

The calibrated artist registry expands from six to 62 J-pop artists. It includes current pop, bands, solo singers, idol acts, city pop, and older Japanese hits. Examples include Mrs. GREEN APPLE, Official HIGE DANdism, King Gnu, Vaundy, Fujii Kaze, back number, Aimyon, Yorushika, RADWIMPS, Perfume, Mariya Takeuchi, Miki Matsubara, Tatsuro Yamashita, and Seiko Matsuda.

Curated signature songs qualify for Easy within the J-pop audience. Unknown songs never become Easy through provider popularity. The remaining songs use genre-relative positional tiers: Medium, Hard, Expert, and Impossible. Previously, a local Japanese profile outside Japan could send all its non-curated songs directly to Impossible, starving the middle tiers. That scope bug is fixed without promoting local-only songs in Europe/Worldwide Mixed.

## Anime

Anime is a separate selectable genre with 245 curated theme songs by 63 artists. The registry includes TV openings/endings and anime film songs, from older classics to modern series. It is available in Worldwide, Europe, Asia, and Japan. Country-specific scenes retain their country boundaries.

Each entry in `anime_songs.tsv` identifies an artist, theme song, anime credit, equivalent title spellings, and editorial familiarity score. These scores populate all five disjoint difficulty tiers:

| Tier | Eligible artists in the registry |
| --- | ---: |
| Easy | 60 |
| Medium | 56 |
| Hard | 46 |
| Expert | 30 |
| Impossible | 27 |

Import admits **only a matching theme song by the matching original artist**. A non-anime song such as Kenshi Yonezu's Lemon stays outside Anime even though KICK BACK is included. Unknown album tracks and unrelated cover artists cannot fill an Anime pool. Broad language caps yield to the explicitly chosen Anime audience.

The registry is discovery and calibration metadata, not bundled music. Provider previews and their regional availability still determine what can actually be played. Registry totals therefore do not promise that every listed song is available on every server or in every decade.

## Name lookup, history, and performance

`japanese_artist_aliases.tsv` lists exact official/native spellings. Lookup accepts these names and permits at most one native-name search retry if the primary lookup fails. It does not use broad fuzzy artist matching. The usual bounded provider workers, metadata cache, preparation jobs, and pool rotation remain in place.

Japanese/native artist names and explicitly listed translated song titles share history identities. Existing identities are normalized on read, preserving prior play counts. The existing name-based no-repeat and artist-exposure rules apply in all regular modes and playlists; shared daily snapshots retain their fixed answers. A catalog-version change invalidates old generated pools after updating.

## Evidence and verification

Representative primary sources used to corroborate artist/song/animation coverage:

- Billboard Japan Hot 100 year-end 2025: https://www.billboard-japan.com/charts/detail?a=hot100_year&year=2025
- Billboard Japan Hot Animation year-end 2025: https://www.billboard-japan.com/charts/detail?a=anime_year&year=2025
- Official Chainsaw Man music credits: https://chainsawman.dog/tvseries/music/
- Official fhána label biography: https://www.lantis.jp/artist/fhana/bio.html
- Official ClariS anime music credits: https://shiroseijyo-anime.com/music/op.html

Familiarity ratings are editorial judgments for genre fans, not claimed chart positions or measured listener recognition. These sources corroborate representative entries rather than certify the entire registry.

Validation includes the full Python regression suite, all JavaScript regression checks, and focused tests in `test_japan_anime.py` for every tier's import, theme-only admission, exact Japanese aliases, bounded native lookup retry, legacy history compatibility, audience boundaries, and selection without early repeats. Provider responses in the new import tests are fixtures. Expanded live-provider coverage and browser playback were not verified from this environment.

## V12.2 — choose what to guess

When **Your rotation = Anime**, the home setup and host's lobby controls show **Anime answer**:

- **Mode 1 · Song / artist** keeps the existing song-answer rules.
- **Mode 2 · Anime title** accepts the anime's English title, listed Japanese romanization, or Japanese title. Suggestions show anime titles rather than song metadata. A typed answer can be submitted with the Guess anime button or Enter; selecting a suggestion submits it too. Multiple choice shows distinct anime titles. Video Race now always guesses anime titles (see V12.4 below). Other eligible Party rounds use the selected anime-answer setting and retain their existing timing and scoring rules.

`anime_series.tsv` maps every one of the current registry's 166 series credits to English, romaji, Japanese, and explicitly accepted alternate titles. Related seasons/arcs are grouped where the main series title is a valid answer. Original catalog names remain accepted. Separate adaptations with shared parent titles never appear together as competing choices. Selecting a suggestion has the same meaning as submitting its displayed title.

Matching uses Unicode NFKC, case folding, optional punctuation/spacing, full-width Latin normalization, and katakana/hiragana equivalence. Kanji remain significant; partial anime names, unrelated titles, song IDs, and artist names cannot bypass the title check. Accepted abbreviated names are explicitly listed rather than guessed by fuzzy matching. Japanese phonetic readings that are not listed are not automatically transliterated into kanji.

Japanese IME composition does not trigger searches on incomplete text or submit a guess when Enter confirms a conversion. Committed text can be searched normally; the next Enter submits. Mobile keyboard layout keeps the answer form visible. A bundled Noto Sans JP fallback supplies Japanese glyphs without requiring a font service or a Japanese system font. Its Unicode subsets load only when needed and use versioned, cacheable URLs; see `static/fonts/NotoSansJP-LICENSE.txt` (SIL OFL 1.1).

All answer matching and suggestions use startup-loaded metadata. This adds no provider requests, media downloads, catalog builds, or database migrations to the guessing path. Song selection, difficulty calibration, persistent name-based song history, and existing mode/difficulty leaderboards continue to use the underlying song and match. Lobby settings survive a rematch in the same room. As with the other lobby settings, active rooms remain in server memory.

The aliases are editorial metadata. Representative English/romaji/native title checks used AniList's own catalog entries and official series sites:

- Frieren official site: https://frieren-anime.jp/onair/
- Frieren catalog: https://anilist.co/anime/154587/Sousou-no-Frieren/
- The Apothecary Diaries official site: https://kusuriyanohitorigoto.jp/season1/index.html
- Akashic Records: https://anilist.co/anime/21700/
- Destiny of the Shrine Maiden: https://anilist.co/anime/143/kannazuki-no-miko
- Doraemon's Earth Symphony: https://anilist.co/anime/166976/Doraemon-Nobita-no-Chikyuu-Symphony
- Regalia: https://anilist.co/anime/21707/Regalia-The-Three-Sacred-Stars/

`test_anime_answers.py` checks every registered theme's multilingual aliases, normalization, ambiguous choices, HTTP scoring, server validation, search, lobby authorization, rematches, history, and Video Race cooldowns. Optional `test_anime_browser.cjs` uses a localhost fixture with generated audio to check English/Japanese input, IME composition, suggestions, mobile keyboard layout, font loading, refresh, and normal song-mode behavior. It does not test an operating system's physical Japanese keyboard or live-provider availability.

## V12.4 — Anime Video Race

Video Race now exposes the normal rotation, scene, difficulty, and decade controls. Choose **Anime** to play anime opening sequences and guess **the anime title**, automatically. The answer selector is fixed to Anime title for these rounds, including host lobby settings. The server enforces anime-title matching even if an old client requests song answers. English, romaji, kanji/kana, IME handling, and local anime suggestions use the existing multilingual alias registry.

`anime_openings.tsv` explicitly identifies 183 opening themes within the existing song registry. Endings, insert songs, and film theme MVs do not enter this video pool. The available editorial opening counts are 74 Easy, 40 Medium, 31 Hard, 22 Expert, and 16 Impossible; provider availability and decade filtering can reduce actual playable counts. A mix must contain at least two eligible opening artists to start. Ordinary Anime snippet/multiple-choice pools retain their full theme registry. Anime video rounds inside Party also use opening-only draws and anime-title guesses.

The selected round and its prefetch carry an opening-only source marker. Video resolution uses a separate cache and explicit opening searches; an ordinary artist music-video cache cannot supply these rounds. Three representative official uploads are pinned as preferred sources, with searched alternatives if a source cannot load. Search candidates need opening markers, matching anime and song credits, and a 45–150 second TV-sized duration. Explicit endings, covers, lyric videos, AMVs, live performances, full versions, and compilations are rejected. Official/verified channels rank ahead of equivalent candidates. Candidate metadata is a heuristic, not analysis of the actual animation frames.

Downloaded files must contain audio and a real video stream; audio-only files and cover-art-only streams are rejected. Download failures offer retry/skip instead of falling back to a regular music video or audio-only playback. If the browser cannot decode a downloaded opening, skip remains available. The actual downloaded duration is checked again. At most three candidate downloads are tried, with a 60-second download limit per opening candidate. Searches use at most two batches of eight flat metadata results with 25-second timeouts, avoiding full extraction of every candidate. There is no video search for all 183 themes during mix preparation.

Successful opening video mappings are cached in memory and automatically in the `anime_opening_cache` table of the existing `data/catalog-cache.sqlite`, for 30 days. This table creates itself; no setup or manual migration is required. Existing score/history data is preserved. Media still uses the shared bounded 30-day / 2 GiB cache. The next video is prefetched as before, and media preparation does not consume guessing time. The 12% audio-only lead-in and two-second fade remain in place. Scores use the real opening video's duration; guesses and history refer to the underlying song and its associated anime.

Representative primary sources and technical references:

- Official Oshi no Ko movie page, whose opening iframe links to `PgBvV9ofjmA`: https://ichigoproduction.com/Season1/movie/
- MAPPA Chainsaw Man opening / KICK BACK: https://www.youtube.com/watch?v=dFlDRhvM4L0
- Aniplex USA Mashle opening / Bling-Bang-Bang-Born: https://www.youtube.com/watch?v=9rVKos-oGnQ
- yt-dlp metadata/search option documentation: https://github.com/yt-dlp/yt-dlp

`test_anime_video_race.py` checks opening-only coverage across all tiers, candidate rejection/ranking, persistent cache reuse, strict video requirements, prefetch, Party behavior, anime-only search and kanji guesses, and unchanged song-history recording. Optional `test_anime_race_browser.cjs` uses a generated 90-second MP4 with real video and audio to exercise the browser ready gate, fade, audio effects, English/Japanese guesses, lobby restrictions, and phone/desktop layouts. These fixture checks do not establish live YouTube download availability in a deployment.

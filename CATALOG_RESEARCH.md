# V7 recognition research and selection policy

Research date: 27 October 2026. This is a game calibration, not a claim to measure the probability that any individual listener knows a song.

## What was wrong
The previous Easy tier admitted any artist's five highest-ranked tracks. An obscure artist's most popular song can still be obscure. Europe also meant European artist origin and forced country balancing, excluding familiar American/Canadian hits while promoting less familiar local material. These are different questions from what a European audience is likely to recognise.

## Evidence reviewed
Chart consumption, enduring streaming reach, radio exposure and genre standards inform the calibration. They are not interchangeable measurements. UK charts are one European signal, not a proxy for every European country.

| Key | Source | How it informed the change |
| --- | --- | --- |
| ifpi24 | [IFPI Global Single Chart 2024](https://www.ifpi.org/benson-boones-beautiful-things-confirmed-by-ifpi-as-biggest-selling-global-single-of-the-year/) | Contemporary international singles such as Beautiful Things and Espresso. |
| ifpi25 | [IFPI Global Single Chart 2025](https://www.ifpi.org/rose-and-bruno-mars-apt-crowned-ifpis-biggest-selling-global-single-of-the-year-2025/) | More recent cross-border hits, including Ordinary and That's So True. |
| spotify20 | [Spotify's all-time most-streamed music, April 2026](https://newsroom.spotify.com/2026-04-23/spotify-20-most-streamed-music-podcasts-audiobooks/) | Persistent recognition across years; global streaming is not artist nationality. |
| uk-streams | [Official Charts: UK all-time most-streamed songs](https://www.officialcharts.com/chart-news/the-uks-official-most-streamed-songs-of-all-time__37837/) | International and older songs alongside British artists. A historical snapshot, not a current ranking. |
| uk24 | [Official Charts: biggest songs of 2024](https://www.officialcharts.com/chart-news/the-official-biggest-songs-of-2024/) | Additional European-market evidence for international crossover music. |
| germany24 | [GfK: German first-half 2024 charts](https://www.offiziellecharts.de/downloads/Halbjahrescharts2024.pdf) | International hits coexist with German-language successes. This is half-year, not full-year data. |
| sweden24 | [Sverigetopplistan: 2024 singles](https://sverigetopplistan.se/chart/43/?dspp=1&dspy=2024) | Swedish domestic hits belong in their scene; international hits also lead the market. |
| teosto24 | [Teosto: most-played songs in Finland, 2024](https://www.teosto.fi/jos-puhutaan-totta-on-vuoden-2024-soitetuin-kappale/) | Finnish radio/performance recognition is a local signal. Timanttei and Jos puhutaan totta do not automatically become pan-European Easy picks. |
| finland24 | [Klangi: Finnish 2024 streaming and album summary](https://www.klangi.fi/uutiset/vuoden-2024-suosituimmat-artistit-ja-albumit/) | Secondary reporting of Finnish streaming leaders; distinguished from Teosto's performance figures. |
| los40 | [LOS40: 2024 number-one songs](https://los40.com/2024/12/19/los-exitos-de-2024-las-canciones-que-han-sido-n1-en-la-lista-de-los40-este-ano/) | Spanish radio crossover; a station chart, not a population-wide recognition survey. |
| dance | [Official Dance Singles Chart](https://www.officialcharts.com/charts/dance-singles-chart/) | Durable dance titles; a changing chart and a genre-specific signal. |
| dance-download | [Official Charts: all-time dance downloads, 2014 snapshot](https://www.officialcharts.com/chart-news/the-uks-most-downloaded-dance-tracks-of-all-time-revealed-__4067/) | Established dance staples rather than an exclusively recent dance playlist. |
| queen | [Queen: Planet Rock listener poll](https://www.queenonline.com/news/planet-rock-votes-bohemian-rhapsody-greatest-rock-song-of-all-time) | Evidence of enduring rock familiarity; fan voting is not a general-population measure. |
| jazz | [Jazz24 listener poll](https://www.jazz24.org/the-jazz-100/) and [Jazz in America: Take Five](https://www.jazzinamerica.org/Media/Audio/19?KeepThis=true&TB_iframe=true&height=640&width=500) | Jazz standards are appropriate inside Jazz Easy; do not assume every Mixed player knows them. |
| country | [Opry: Country's Greatest Songs](https://www.opry.com/opry-100-album) | Fan-selected standards inform Country; the game still resolves studio recordings, not these live tribute performances. |
| afrobeats | [Spotify: Rema's billion-stream milestone](https://newsroom.spotify.com/2023-09-11/remas-calm-down-becomes-the-first-track-led-by-an-african-artist-to-join-spotifys-billions-club/) | Crossover evidence for Afrobeats. Other genre anchors remain editorial choices. |
| kpop | [Official Charts: PSY chart history](https://www.officialcharts.com/artist/7592/psy/) | Demonstrates cross-border recognition; K-pop Easy also assumes a genre-interested audience. |
| aria24 | [ARIA 2024 singles](https://www.aria.com.au/charts/2024/singles-chart) | Australian audience context and international overlaps. |
| aria-number1 | [ARIA number-one singles](https://www.aria.com.au/charts/news/all-the-aria-singles-chart-1s) | Recent hit calibration, including Man I Need. |
| portugal | [RTP: Portuguese enduring hits](https://media.rtp.pt/extra/pessoas/as-10-cancoes-portuguesas-mais-ouvidas-de-sempre/) | Portuguese scene anchors; editorial broadcaster list, not pan-European hits. |
| poland | [Kino Polska viewer poll, reported by Satkurier](https://satkurier.pl/news/115107/widzowie-kino-polska-muzyka-wybrali-przeboje.html) and [LP3 Autobiografia history](https://www.lp3.pl/utwor/129) | Polish scene standards. |
| austria | [ArGe Musik: Austrian streaming successes](https://www.arge-musik.at/charts/meiste-streams-auf-spotify-kuenstler-aus-oesterreich/) | Austrian scene and crossover anchors; secondary compilation. |
| swiss | [SRF: DJ BoBo's breakthrough](https://www.srf.ch/news/schweiz/30-jahre-dj-bobo-dj-bobo-hat-am-anfang-nicht-unbedingt-den-geschmack-getroffen) | Swiss scene/crossover context. |

The French SNEP chart index was reviewed, but its annual PDF could not be retrieved here. French song anchors are labelled editorial rather than presented as extracted SNEP results.

## What the data means
`recognition_data.tsv` contains explicit artist/title anchors, scene, predominant language, genre tags and reach. `editorial` means a judgement call, not a verified chart position. Even source-labelled rows can contain editorial companion titles: the source supports the calibration, not a claim that every song on the row has an identical measured reach. No artist-level rule declares every song by a famous artist Easy.

These anchors are calibration metadata, not bundled audio. Real titles, track IDs, credits, previews and provider ranks are fetched automatically. The broader artist registry remains available for discovery. New provider material is automatically available below Easy when it meets the fallback rules; **the named Easy calibration is maintained in the source file, not automatically scraped from these websites**. This avoids silently treating any new/local chart entry as universally recognisable.

## Rules shared by both game modes
- Easy: explicit song match with recognition score at least 85. Unknown songs never qualify from provider rank alone.
- Medium: scores 55 and above, mixing calibrated hits with provider-popular favourites. Legacy `Normal` requests map to Medium.
- Hard: scores 40–84, excluding the Easy anchors.
- Expert: scores 25–54, favouring less prominent catalogue material.
- Impossible: below 25, currently the lower end of an artist's available top-50 results. This is not exhaustive album/discography discovery.

Scores are internal ordered categories, **not percentages**. A match scores 94 in its local scene and generally 90 for its intended crossover audience. European-only anchors score lower in Worldwide. Specialist standards are not automatically promoted in Mixed. Below Easy, provider rank plus position within the artist's fetched tracks provide a fallback; these harder tiers are estimates, not scientifically validated difficulty levels. Hard/Expert overlap intentionally accommodates that uncertainty.

Europe includes European-origin discovery plus international crossover artists. Individual countries filter the artist's scene/origin, not the user's IP or every song's language. Broader area presets focus on their member scenes. Country assignments describe an artist/project scene and can simplify multinational careers. Genre and language tags are editorial artist-level hints, not verified track-level labels.

At most `ceil(rounds/10)` Finnish answers per Europe game. No forced one-country-per-song quota. Least-used artists are selected before repeats; recent artists are avoided when alternatives exist. Country frequency is a soft weight. Choice distractors prefer the same language and similar recognition, then genre/provider popularity. Search stays query-dependent and capped at 25 results.

## Catalogue size, performance and failure behaviour
The default 80-artist discovery target, 160-attempt recovery budget, six discovery workers, 12-second metadata timeout, persistent metadata cache and shared audio cache remain. Priority discovery now starts with relevant recognition anchors. Up to 50 tracks per successful artist are kept for search/distractors and harder answers instead of discarding all but a few.

If too few artists have eligible answers, the game reports insufficient coverage. It never pads Easy with obscure tracks or relaxes Impossible into Easy. Unsupported static genre/scene combinations are disabled in the interface; real provider availability can still be lower than the static estimate. Sparse scenes may have only four supported artists, while broad scenes require twelve to start.

Pool files use a V7 schema namespace: old V6 difficulty decisions are not reused. Preserve `data/`; the metadata cache and existing downloaded audio still help the first V7 build. First-time catalogues still require network requests.

## V8 reference: all-time recognisable hits
The user supplied [this Spotify playlist](https://open.spotify.com/playlist/50ozhW6x8mS6r64G4Dru0c). Direct and embedded Spotify access failed. An [indexed video description](https://socialcounts.org/youtube-video-live-view-count/vulK0wDSc24) links that exact playlist as the creator's version of an all-time most-recognisable-songs selection. That supports the intended theme, not a verified track listing. `hot_hits.tsv` is our independent, stricter editorial selection of 159 songs across 91 artists. It does not reproduce a claimed Spotify track list or use the video's fan-vote order. It inherits the earlier chart/recognition research and is explicitly all-time, not a claim about today's hottest releases.


## 2026 Nordic-oriented Europe mix

The Europe Mixed picker retains international and local music. IFPI Sweden’s 2025 singles chart and IFPI Denmark’s all-time streaming list illustrate that both international hits and local repertoire can be popular: https://www.ifpi.se/2026/03/18/ifpi-sverige-musikforsaljning-2025/ and https://ifpi.dk/stor-mand-slar-streamingrekord. Finland’s radio charts also show local and international tracks: https://ifpi.fi/lista/radio/2025/1/. IFPI’s 2025 Global Single Chart provides global context: https://www.ifpi.org/rose-and-bruno-mars-apt-crowned-ifpis-biggest-selling-global-single-of-the-year-2025/. These lists cover different years, markets and formats; they are not a representative Europe-wide survey or exact game probabilities.

In broad Mixed Europe games only, eligible Nordic artists receive a 1.5× selection weight, subject to difficulty rules and the Finland cap where possible. Spanish and French artist-language lanes are each limited to approximately 20% and jointly approximately 30% where alternatives exist. Limits relax if the remaining eligible pool is too narrow or keeping them would eliminate all unheard choices. The language field is an editorial artist-level hint, not detected track lyrics. Specialist genres and countries are not subject to these limits. Named player history is stored as provider track IDs and normalized artist/title keys in the existing scores database; for multiplayer, the histories of all players are combined. When both heard and unheard eligible tracks exist, the repeat branch is selected with 10% probability; exhausted pools can repeat more. Daily challenges use their shared fixed song order.

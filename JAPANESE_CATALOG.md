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

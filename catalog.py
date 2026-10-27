"""Editorial discovery lanes. Tracks are fetched live, not a fixed song list.
Region means artist scene/origin, language is a predominant-language editorial hint.
"""
import random, re, unicodedata
from concurrent.futures import ThreadPoolExecutor,as_completed

def norm(s):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c)).split())
SEEDS=[]
def add(region,language,genre,names):
    for name in names.split('|'): SEEDS.append(dict(name=name,region=region,language=language,genre=genre))
add('Europe','English','Rock','Queen|Coldplay|Muse|Oasis|Radiohead|The Beatles|Arctic Monkeys|The Rolling Stones|U2|Dire Straits')
add('North America','English','Rock','Foo Fighters|Nirvana|Red Hot Chili Peppers|Green Day|Linkin Park|The Killers|Bon Jovi|Guns N\' Roses|Eagles|Imagine Dragons')
add('Europe','English','Pop','ABBA|Adele|Dua Lipa|Ed Sheeran|Harry Styles|Elton John|George Michael|Robbie Williams')
add('North America','English','Pop','Taylor Swift|Lady Gaga|Madonna|Michael Jackson|Bruno Mars|Billie Eilish|Katy Perry|Miley Cyrus|The Weeknd|Beyoncé')
add('Europe','English','Metal','Iron Maiden|Judas Priest|Black Sabbath|Nightwish|HIM|Volbeat|Bring Me The Horizon|Ghost')
add('North America','English','Metal','Metallica|Slipknot|System Of A Down|Megadeth|Pantera|Korn|Avenged Sevenfold|Disturbed')
add('Europe','English','Dance','Avicii|Calvin Harris|David Guetta|Clean Bandit|Rudimental|Disclosure|Swedish House Mafia|Faithless')
add('North America','English','Dance','The Chainsmokers|Marshmello|Skrillex|Diplo')
add('Europe','English','Electronic','Daft Punk|The Chemical Brothers|The Prodigy|Massive Attack|Gorillaz|Depeche Mode|Pet Shop Boys')
add('North America','English','Rap / Hip Hop','Eminem|Drake|Kendrick Lamar|Kanye West|Jay-Z|50 Cent|Snoop Dogg|Outkast|Nicki Minaj|Travis Scott')
add('Europe','English','Rap / Hip Hop','Stormzy|Dave|Skepta|Central Cee')
add('North America','English','R&B','Usher|Alicia Keys|SZA|Frank Ocean|Mariah Carey|Whitney Houston|TLC|Destiny\'s Child')
add('Europe','English','R&B','Amy Winehouse|Sade|Craig David|Jorja Smith')
add('Finland','Finnish','Pop','Haloo Helsinki!|Jenni Vartiainen|Chisu|BEHM|Ellinoora|Vesala|Kaija Koo|Anna Puu|Antti Tuisku|BESS')
add('Finland','Finnish','Rock','Apulanta|Eppu Normaali|Popeda|Dingo|Yö|Juice Leskinen|Happoradio|Tehosekoitin')
add('Finland','Finnish','Rap / Hip Hop','Cheek|JVG|Elastinen|Petri Nygård|Gettomasa|Cledos|Gasellit|Mikael Gabriel')
add('Finland','Finnish','Metal','Mokoma|Stam1na|Kotiteollisuus|Turmion Kätilöt')
add('Finland','Finnish','Dance','Käärijä|Portion Boys|Movetron|Aikakone')
add('Europe','German','Metal','Rammstein|Eisbrecher|Oomph!|Megaherz')
add('Europe','French','Pop','Stromae|Angèle|Indila|Zaz|Louane|Clara Luciani')
add('Europe','Spanish','Pop','Enrique Iglesias|Rosalía|Álvaro Soler|Aitana')
add('North America','English','Electronic','Moby|ODESZA|Porter Robinson|Illenium')
# Finnish artists singing mainly in English remain a separate answer lane.
for seed in SEEDS:
    if seed['name'] in ['Nightwish','HIM']: seed['region']='Finland'
# Expand the initial anchors with explicit country metadata.
from artist_seeds import GROUPS, OVERRIDES, region_for
_COUNTRIES={
 'ABBA':'SE','Avicii':'SE','Swedish House Mafia':'SE','Ghost':'SE','Volbeat':'DK',
 'David Guetta':'FR','Daft Punk':'FR','U2':'IE','Enya':'IE','DJ Snake':'FR',
 'Rammstein':'DE','Eisbrecher':'DE','Oomph!':'DE','Megaherz':'DE',
 'Stromae':'BE','Angèle':'BE','Indila':'FR','Zaz':'FR','Louane':'FR','Clara Luciani':'FR',
 'Enrique Iglesias':'ES','Rosalía':'ES','Álvaro Soler':'ES','Aitana':'ES',
 'Drake':'CA','The Weeknd':'CA','Nicki Minaj':'US','Mariah Carey':'US','O-Zone':'MD','Loreen':'SE','Dr. Alban':'SE','Rednex':'SE','Björk':'IS','Of Monsters and Men':'IS','Kaleo':'IS','Sigur Rós':'IS','Dan Balan':'MD',"Carla's Dreams":'MD','Zdob și Zdub':'MD','Cher':'US','2 Unlimited':'NL','Corona':'IT','Robert Miles':'IT','Gala':'IT','Whigfield':'DK','Los del Rio':'ES','Pitbull':'US','Wiz Khalifa':'US','Alanis Morissette':'CA','Lil Nas X':'US','Doja Cat':'US','Juice WRLD':'US','Halsey':'US','Charlie Puth':'US','Marshmello':'US','Major Lazer':'US','Gotye':'AU','Savage Garden':'AU','Christina Aguilera':'US','Jennifer Lopez':'US','Destiny\'s Child':'US','James Arthur':'GB','Tom Odell':'GB','Robin Thicke':'US','Pharrell Williams':'US','Lizzo':'US','Jack Harlow':'US','Meghan Trainor':'US','Goo Goo Dolls':'US','Smash Mouth':'US','Santana':'US','Toni Braxton':'US','Boyz II Men':'US','Chubby Checker':'US','The Monkees':'US','Simon & Garfunkel':'US','Jackson 5':'US','Neil Diamond':'US','Joan Jett & The Blackhearts':'US','Survivor':'US','Kim Carnes':'US','Dexys Midnight Runners':'GB','Baha Men':'US','Fun.':'US','House of Pain':'US',
}
for seed in SEEDS:
    seed['country']=_COUNTRIES.get(seed['name'],'FI' if seed['region']=='Finland' else 'GB' if seed['region']=='Europe' else 'US')
for country,language,genre,names in GROUPS:
    for name in names.split('|'):
        SEEDS.append(dict(name=name,country=country,language=language,genre=genre,region=region_for(country)))
for seed in SEEDS:
    country,language=OVERRIDES.get(seed['name'],(seed['country'],seed['language']))
    seed.update(country=country,language=language,region=region_for(country))
for seed in SEEDS:
    if seed['name']=='Gojira':seed['genre']='Metal'
    if seed['name']=='Europe':seed['genre']='Rock'
    if seed['name'] in ['Ares','Damso']:seed['genre']='Rap / Hip Hop'
SEEDS=list({(norm(s['name']),s['genre']):s for s in SEEDS}.values())
from recognition import HOT_HITS, PROFILES, COUNTRIES, AREAS, VERSION, text_key, song_key, profile, recognition, classify_tracks, in_difficulty
# Merge per-artist tags: Mixed never fetches/weights one artist twice for crossover genres.
merged={}
for seed in SEEDS:
    key=text_key(seed['name'])
    if key not in merged:merged[key]=dict(seed,genres=[seed['genre']])
    elif seed['genre'] not in merged[key]['genres']:merged[key]['genres'].append(seed['genre'])
for key,p in PROFILES.items():
    if key not in merged:merged[key]=dict(name=p['name'],country=p['country'],region=region_for(p['country']),language=p['language'],genre=p['genres'][0],genres=[])
    seed=merged[key]
    seed.update(country=p['country'],region=region_for(p['country']),language=p['language'])
    seed['genres']=list(dict.fromkeys(seed['genres']+p['genres']))
SEEDS=list(merged.values())
REGIONS=['Worldwide','Europe','North America',*AREAS,*COUNTRIES]
GENRES=['Mixed','Pop','Rock','Metal','Rap / Hip Hop','Dance','Electronic','R&B','Indie / Alternative','Punk / Pop Punk','Soul / Funk','Country','Jazz','Blues','Reggae','Latin','K-pop','J-pop','Afrobeats']
DIFFICULTIES=['Easy','Medium','Hard','Expert','Impossible']
def eligible(genre,region):
    def matches(s):
        if region in COUNTRIES:return s.get('country','FI' if s['region']=='Finland' else '')==COUNTRIES[region]
        if region in AREAS:return s.get('country') in AREAS[region]
        if region=='Europe':return s['region'] in ('Europe','Finland') or bool(profile(s) and profile(s)['reach'] in ('global','europe'))
        return region=='Worldwide' or s['region']==region
    return [dict(s,genre=genre if genre!='Mixed' else s['genre']) for s in SEEDS if (genre=='Mixed' or genre in s.get('genres',[s['genre']])) and matches(s)]

def filter_options():
    # Static coverage check avoids advertising combinations with only one artist.
    support={}
    for region in REGIONS:
        support[region]={}
        for genre in GENRES:
            seeds=eligible(genre,region)
            if len(seeds)<4:continue
            from recognition import recognition
            easy=sum(any(recognition(seed,t,region,genre)>=85 for t in (profile(seed) or {}).get('examples',[])) for seed in seeds)
            support[region][genre]=[d for d in DIFFICULTIES if d!='Easy' or easy>=4]
    return dict(regions=REGIONS,genres=GENRES,difficulties=DIFFICULTIES,support=support)
def title_key(t):
    title=re.sub(r'\s*[\(\[].*?(?:remaster|version|edit).*?[\)\]]','',t['title'],flags=re.I)
    title=re.sub(r'\s*-\s*(?:\d{4}\s+)?remaster.*','',title,flags=re.I)
    return str(t.get('artist_id') or norm(t.get('seed_artist',t['artist'])))+'|'+song_key(title)
def band(tracks,difficulty):
    return [t for t in tracks if in_difficulty(t,difficulty)]

def build_pool(fetch,clean,genre,region,difficulty,target_artists=80,progress=None):
    seeds=eligible(genre,region)
    if not seeds: raise ValueError('That genre/region combination has no curated artists yet. Choose another mix.')
    # Country-first discovery prevents a heavily populated local lane dominating.
    # Interleave genres within countries; fetch many more independent artists.
    selected=discovery_order(seeds)
    if difficulty=='Hits':
        selected.sort(key=lambda seed:0 if text_key(seed['name']) in HOT_HITS else 1)
    if difficulty in ('Easy','Medium','Normal'):
        # Known hits are fetched first; retain the entire discovery registry.
        selected.sort(key=lambda seed:0 if any(recognition(seed,title,region,genre)>=85 for title in (profile(seed) or {}).get('examples',[])) else 1 if profile(seed) else 2)
    def load(seed):
        try:
            results=fetch('search/artist?limit=10&q='+__import__('urllib.parse',fromlist=['quote']).quote(seed['name'])).get('data',[])
            artist=next((a for a in results if norm(a['name'])==norm(seed['name'])),None)
            if not artist:return []
            rows=fetch(f"artist/{artist['id']}/top?limit=100").get('data',[])
            # Harder tiers go one page deeper: top index 50 mostly holds album
            # cuts and older singles the first 50 miss.
            if difficulty in ('Hard','Expert','Impossible','Hits'):
                try:
                    extra=fetch(f"artist/{artist['id']}/top?limit=50&index=50").get('data',[])
                    seen={str(t.get('id')) for t in rows}
                    rows=list(rows)+[t for t in extra if str(t.get('id')) not in seen]
                except (ValueError,KeyError):pass
            dedup={}
            for raw in rows:
                if not raw.get('preview') or str(raw['artist']['id'])!=str(artist['id']): continue
                if re.search(r'\b(live|karaoke|tribute|sped up|slowed|remix)\b',raw.get('title_version','')+' '+raw['title'],re.I):continue
                t=clean(raw);t.update(seed_artist=seed['name'],genre=seed['genre'],language=seed['language'],region=seed['region'],country=seed.get('country','FI' if seed['region']=='Finland' else 'GB'),artist_id=str(artist['id']),rank=raw.get('rank',0))
                k=title_key(t)
                if k not in dedup or t['rank']>dedup[k]['rank']:dedup[k]=t
            return classify_tracks(list(dedup.values()),seed,region,genre)
        except (ValueError,KeyError):return []
    groups=[]
    minimum=min(12,len({norm(s['name']) for s in seeds}))
    if difficulty=='Easy':
        known=sum(any(recognition(seed,title,region,genre)>=85 for title in (profile(seed) or {}).get('examples',[])) for seed in seeds)
        minimum=min(12,max(4,known))
    target=min(target_artists,len(selected))
    # Retry with fresh artists if some lookups fail, rather than silently starting
    # a tiny game from the first two artists whose requests happened to succeed.
    if progress:progress('artists',0,target)
    with ThreadPoolExecutor(max_workers=6) as workers:
        for start in range(0,min(len(selected),160),40):
            futures=[workers.submit(load,seed) for seed in selected[start:start+40]]
            for future in as_completed(futures):
                groups.append(future.result())
                if progress:progress('artists',len(groups),target)
            if start==0 and not any(groups):
                raise ValueError('The music provider returned no playable artists. Check connectivity and retry.')
            tracks={t['id']:t for group in groups for t in group}
            counts={}
            for t in tracks.values(): counts[t['language']]=counts.get(t['language'],0)+1
            result=[t for t in tracks.values() if counts[t['language']]>=4]
            playable=band(result,difficulty)
            artists={artist_key(t) for t in playable}
            countries={t['country'] for t in playable}
            diverse=len(artists)>=minimum
            if start+40>=target and diverse: break
    if not result or not diverse:
        raise ValueError('Not enough distinct artists have playable tracks at this difficulty. Try another genre, scene or difficulty; Easy was not filled with obscure songs.')
    return result

def discovery_order(seeds):
    countries={}
    for seed in seeds:
        country=seed.get('country',seed['region'])
        countries.setdefault(country,{}).setdefault(seed['genre'],[]).append(seed)
    queues={}
    for country,genres in countries.items():
        for group in genres.values(): random.shuffle(group)
        queue=[]
        while any(genres.values()):
            keys=list(genres);random.shuffle(keys)
            for key in keys:
                if genres[key]:queue.append(genres[key].pop())
        queues[country]=queue
    order=[]
    while any(queues.values()):
        keys=list(queues);random.shuffle(keys)
        for key in keys:
            if queues[key]:order.append(queues[key].pop(0))
    return order

def artist_key(t):
    return str(t.get('artist_id') or norm(t['artist']))

def choose_song(r):
    playable=[t for t in r['pool'] if 'recognition' not in t or in_difficulty(t,r.get('difficulty','Medium'))]
    if r.get('mode')=='hits':playable=[t for t in playable if not t.get('playlist_track') or t.get('hot_hit')]
    if not playable:raise ValueError('No tracks meet this difficulty. Choose another mix.')
    # Cross-game variety: avoid repeating the last game's artists/songs when
    # the pool is large enough to allow it. Rooms hand over their tail via
    # previous_artists/previous_songs on lobby return; solo hands it over via
    # create payload from localStorage.
    avoid_artists=set(r.get('previous_artists',[]))
    avoid_songs=set(r.get('previous_songs',[]))
    candidates=[t for t in playable if t['id'] not in r['used']]
    if avoid_songs or avoid_artists:
        fresh=[t for t in candidates if t['id'] not in avoid_songs and artist_key(t) not in avoid_artists]
        if len({artist_key(t) for t in fresh})>=4:candidates=fresh
    if not candidates:r['used']=[];candidates=[t for t in playable if t['id'] not in avoid_songs] or playable[:]
    history=r.setdefault('artist_counts',{})
    country_counts=r.setdefault('country_counts',{})
    if r.get('region')=='Europe':
        limit=max(1,(r.get('rounds',10)+9)//10)
        if country_counts.get('FI',0)>=limit:
            candidates=[t for t in candidates if t.get('country')!='FI']
            if not candidates:
                candidates=[t for t in playable if t.get('country')!='FI']
            if not candidates:raise ValueError('Europe needs available non-Finnish artists. Create a new mix.')
    # Only least-used eligible artists can be drawn, regardless of track count.
    least=min(history.get(artist_key(t),0) for t in candidates)
    candidates=[t for t in candidates if history.get(artist_key(t),0)==least]
    # Soft country weights preserve variety without demanding one obscure artist
    # from every country. Artist uniformity prevents prolific catalogs dominating.
    by_artist={}
    for track in candidates:by_artist.setdefault(artist_key(track),[]).append(track)
    recent=r.get('recent_artists',[])
    artists=sorted(a for a in by_artist if a not in recent[-3:]) or sorted(by_artist)
    weights=[1/(1+country_counts.get(by_artist[a][0].get('country','?'),0)*.35) for a in artists]
    artist=random.choices(artists,weights=weights,k=1)[0]
    tracks=by_artist[artist]
    song=random.choice(tracks)
    country=song.get('country','?')
    history[artist]=history.get(artist,0)+1;country_counts[country]=country_counts.get(country,0)+1
    r.setdefault('recent_artists',[]).append(artist)
    return song

def round_choices(song,tracks):
    lane=[t for t in tracks if t.get('language')==song.get('language') and t['id']!=song['id']]
    # Prefer genre, nearby popularity and different artists. A sparse genre may
    # use same-language neighbors instead of deleting that country from the pool.
    lane.sort(key=lambda t:(t.get('genre')!=song.get('genre'),abs(t.get('recognition',0)-song.get('recognition',0)),abs(t.get('rank',0)-song.get('rank',0))))
    board=random.sample(lane[:80],min(24,len(lane)))+[song]
    random.shuffle(board)
    neighbors=lane[:60]
    if 'recognition' in song:
        for distance in (15,30):
            close=[t for t in lane if abs(t.get('recognition',0)-song['recognition'])<=distance]
            if len({artist_key(t) for t in close if artist_key(t)!=artist_key(song)})>=3:
                neighbors=close[:60];break
    other_artists={}
    for t in neighbors:
        if artist_key(t)!=artist_key(song):other_artists.setdefault(artist_key(t),[]).append(t)
    distractors=[random.choice(other_artists[a]) for a in random.sample(list(other_artists),min(3,len(other_artists)))]
    if len(distractors)<3:
        ids={t['id'] for t in distractors}
        distractors+=random.sample([t for t in lane if t['id'] not in ids],3-len(distractors))
    choices=distractors+[song];random.shuffle(choices)
    return board,choices

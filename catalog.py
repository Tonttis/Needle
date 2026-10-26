"""Editorial discovery lanes. Tracks are fetched live, not a fixed song list.
Region means artist scene/origin, language is a predominant-language editorial hint.
"""
import random, re, unicodedata
from concurrent.futures import ThreadPoolExecutor

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
 'David Guetta':'FR','Daft Punk':'FR','U2':'IE','Enya':'IE',
 'Rammstein':'DE','Eisbrecher':'DE','Oomph!':'DE','Megaherz':'DE',
 'Stromae':'BE','Angèle':'BE','Indila':'FR','Zaz':'FR','Louane':'FR','Clara Luciani':'FR',
 'Enrique Iglesias':'ES','Rosalía':'ES','Álvaro Soler':'ES','Aitana':'ES',
 'Drake':'CA','The Weeknd':'CA','Nicki Minaj':'US',
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
REGIONS=['Worldwide','Europe','North America','Finland']
GENRES=['Mixed','Pop','Rock','Metal','Rap / Hip Hop','Dance','Electronic','R&B']
DIFFICULTIES=['Easy','Normal','Hard']
def eligible(genre,region):
    return [s for s in SEEDS if (genre=='Mixed' or s['genre']==genre) and (region=='Worldwide' or s['region']==region or region=='Europe' and s['region']=='Finland')]
def title_key(t):
    title=re.sub(r'\s*[\(\[].*?(?:remaster|version|edit).*?[\)\]]','',t['title'],flags=re.I)
    title=re.sub(r'\s*-\s*(?:\d{4}\s+)?remaster.*','',title,flags=re.I)
    return norm(t['artist'])+'|'+norm(title)
def band(tracks,difficulty):
    # Artist-relative popularity, never a claim of global chart positions.
    tracks=sorted(tracks,key=lambda t:t.get('rank',0),reverse=True)
    if difficulty=='Easy': return tracks[:5]
    if difficulty=='Normal': return tracks[:15]
    return tracks[5:40] or tracks

def build_pool(fetch,clean,genre,region,difficulty):
    seeds=eligible(genre,region)
    if not seeds: raise ValueError('That genre/region combination has no curated artists yet. Choose another mix.')
    # Country-first discovery prevents a heavily populated local lane dominating.
    # Interleave genres within countries; fetch many more independent artists.
    selected=discovery_order(seeds)
    def load(seed):
        try:
            results=fetch('search/artist?limit=10&q='+__import__('urllib.parse',fromlist=['quote']).quote(seed['name'])).get('data',[])
            artist=next((a for a in results if norm(a['name'])==norm(seed['name'])),None)
            if not artist:return []
            rows=fetch(f"artist/{artist['id']}/top?limit=50").get('data',[])
            dedup={}
            for raw in rows:
                if not raw.get('preview') or str(raw['artist']['id'])!=str(artist['id']): continue
                if re.search(r'\b(live|karaoke|tribute|sped up|slowed|remix)\b',raw.get('title_version','')+' '+raw['title'],re.I):continue
                t=clean(raw);t.update(genre=seed['genre'],language=seed['language'],region=seed['region'],country=seed.get('country','FI' if seed['region']=='Finland' else 'GB'),artist_id=str(artist['id']),rank=raw.get('rank',0))
                k=title_key(t)
                if k not in dedup or t['rank']>dedup[k]['rank']:dedup[k]=t
            return band(list(dedup.values()),difficulty)
        except (ValueError,KeyError):return []
    groups=[]
    minimum=min(12,len({norm(s['name']) for s in seeds}))
    target=min(80,len(selected))
    # Retry with fresh artists if some lookups fail, rather than silently starting
    # a tiny game from the first two artists whose requests happened to succeed.
    with ThreadPoolExecutor(max_workers=6) as workers:
        for start in range(0,min(len(selected),160),40):
            groups.extend(workers.map(load,selected[start:start+40]))
            if start==0 and not any(groups):
                raise ValueError('The music provider returned no playable artists. Check connectivity and retry.')
            tracks={t['id']:t for group in groups for t in group}
            counts={}
            for t in tracks.values(): counts[t['language']]=counts.get(t['language'],0)+1
            result=[t for t in tracks.values() if counts[t['language']]>=4]
            artists={artist_key(t) for t in result}
            countries={t['country'] for t in result}
            diverse=len(artists)>=minimum and (region not in ['Europe','Worldwide'] or len(countries)>=min(4,len({x.get('country','?') for x in seeds})))
            if start+40>=target and diverse: break
    if not result or not diverse:
        raise ValueError('Not enough distinct artists are available for a varied game. Please retry or broaden this selection; no narrow game was started.')
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
    candidates=[t for t in r['pool'] if t['id'] not in r['used']]
    if not candidates:r['used']=[];candidates=r['pool'][:]
    history=r.setdefault('artist_counts',{})
    country_counts=r.setdefault('country_counts',{})
    if r.get('region')=='Europe':
        limit=max(1,(r.get('rounds',10)+9)//10)
        if country_counts.get('FI',0)>=limit:
            candidates=[t for t in candidates if t.get('country')!='FI']
            if not candidates:
                candidates=[t for t in r['pool'] if t.get('country')!='FI']
            if not candidates:raise ValueError('Europe needs available non-Finnish artists. Create a new mix.')
    # Only least-used eligible artists can be drawn, regardless of track count.
    least=min(history.get(artist_key(t),0) for t in candidates)
    candidates=[t for t in candidates if history.get(artist_key(t),0)==least]
    countries={t.get('country','?') for t in candidates}
    least_country=min(country_counts.get(c,0) for c in countries)
    country=random.choice(sorted(c for c in countries if country_counts.get(c,0)==least_country))
    candidates=[t for t in candidates if t.get('country','?')==country]
    artists=sorted({artist_key(t) for t in candidates})
    recent=r.get('recent_artists',[])
    artist=random.choice([a for a in artists if a not in recent[-3:]] or artists)
    song=random.choice([t for t in candidates if artist_key(t)==artist])
    history[artist]=history.get(artist,0)+1;country_counts[country]=country_counts.get(country,0)+1
    r.setdefault('recent_artists',[]).append(artist)
    return song

def round_choices(song,tracks):
    lane=[t for t in tracks if t.get('language')==song.get('language') and t['id']!=song['id']]
    # Prefer genre, nearby popularity and different artists. A sparse genre may
    # use same-language neighbors instead of deleting that country from the pool.
    lane.sort(key=lambda t:(t.get('genre')!=song.get('genre'),abs(t.get('rank',0)-song.get('rank',0))))
    board=random.sample(lane[:80],min(24,len(lane)))+[song]
    random.shuffle(board)
    neighbors=lane[:60]
    other_artists={}
    for t in neighbors:
        if artist_key(t)!=artist_key(song):other_artists.setdefault(artist_key(t),[]).append(t)
    distractors=[random.choice(other_artists[a]) for a in random.sample(list(other_artists),min(3,len(other_artists)))]
    if len(distractors)<3:
        ids={t['id'] for t in distractors}
        distractors+=random.sample([t for t in lane if t['id'] not in ids],3-len(distractors))
    choices=distractors+[song];random.shuffle(choices)
    return board,choices

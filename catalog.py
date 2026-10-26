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
    # Sample a musical lane first; keep at least 25 comparable tracks per lane.
    lanes={}
    for s in seeds: lanes.setdefault((s['genre'],s['language']),[]).append(s)
    chosen=random.sample(list(lanes.values()),min(4,len(lanes)))
    selected=[s for lane in chosen for s in random.sample(lane,min(8,len(lane)))]
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
                t=clean(raw);t.update(genre=seed['genre'],language=seed['language'],region=seed['region'],rank=raw.get('rank',0))
                k=title_key(t)
                if k not in dedup or t['rank']>dedup[k]['rank']:dedup[k]=t
            return band(list(dedup.values()),difficulty)
        except (ValueError,KeyError):return []
    with ThreadPoolExecutor(max_workers=4) as workers: groups=list(workers.map(load,selected))
    tracks={title_key(t):t for group in groups for t in group}
    buckets={}
    for t in tracks.values():buckets.setdefault((t['genre'],t['language']),[]).append(t)
    result=[t for bucket in buckets.values() if len(bucket)>=25 for t in bucket]
    if not result:raise ValueError('Could not find 25 comparable playable songs for this mix. Try Normal difficulty or another genre; the catalog may also be unavailable.')
    return result

def round_choices(song,tracks):
    lane=[t for t in tracks if t.get('genre')==song.get('genre') and t.get('language')==song.get('language') and t['id']!=song['id']]
    # Closest available popularity neighbors; randomize within that neighborhood.
    lane.sort(key=lambda t:abs(t.get('rank',0)-song.get('rank',0)))
    board=random.sample(lane[:60],min(24,len(lane)))+[song]
    random.shuffle(board)
    choices=random.sample([t for t in board if t['id']!=song['id']],3)+[song]
    random.shuffle(choices)
    return board,choices

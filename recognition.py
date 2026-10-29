"""Explicit song-level calibration; chart references and editorial choices are distinct.
Popularity ranks are only a secondary signal, never proof that a song is Easy.
"""
import pathlib,re,unicodedata
from functools import lru_cache
VERSION='v11-japan-anime-1'
# Russian phonetic keyboard: user types Latin letters while on Cyrillic layout
# (or vice versa). Map both directions so search works on the wrong layout.
_RU_PHONETIC=str.maketrans({
 'q':'й','w':'ц','e':'у','r':'к','t':'е','y':'н','u':'г','i':'ш','o':'щ','p':'з','[':'х',']':'ъ',
 'a':'ф','s':'ы','d':'в','f':'а','g':'п','h':'р','j':'о','k':'л','l':'д',';':'ж',"'":'э',
 'z':'я','x':'ч','c':'с','v':'м','b':'и','n':'т','m':'ь',',':'б','.':'ю',
 'й':'q','ц':'w','у':'e','к':'r','е':'t','н':'y','г':'u','ш':'i','щ':'o','з':'p','х':'[','ъ':']',
 'ф':'a','ы':'s','в':'d','а':'f','п':'g','р':'h','о':'j','л':'k','д':'l','ж':';','э':"'",
 'я':'z','ч':'x','с':'c','м':'v','и':'b','т':'n','ь':'m','б':',','ю':'.',
})
COUNTRIES={'Finland':'FI','Russia':'RU','United Kingdom':'GB','Ireland':'IE','Sweden':'SE','Norway':'NO','Denmark':'DK','Germany':'DE','France':'FR','Belgium':'BE','Netherlands':'NL','Italy':'IT','Spain':'ES','Portugal':'PT','Poland':'PL','Austria':'AT','Switzerland':'CH','Moldova':'MD','Iceland':'IS','United States':'US','Canada':'CA','Australia':'AU','New Zealand':'NZ','Brazil':'BR','Colombia':'CO','Puerto Rico':'PR','South Korea':'KR','Japan':'JP','Jamaica':'JM','Nigeria':'NG','South Africa':'ZA'}
AREAS={'Nordics':{'FI','SE','NO','DK','IS'},'Latin America':{'BR','CO','PR','MX','AR','CL','CU','DO'},'Asia':{'JP','KR','IN','TH','PH'},'Africa':{'NG','ZA','GH','CM','KE'},'Oceania':{'AU','NZ'}}
@lru_cache(maxsize=65536)
def text_key(value):
 value=''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))
 return re.sub(r'[^\w]+','',value)

def layout_variants(value):
  """Return the query as-typed plus the opposite-keyboard-layout version.

  Covers RU phonetic QWERTY<->ЙЦУКЕН swaps. Cheap: only returns a second
  candidate when the swap actually changes the string.
  """
  swapped=value.translate(_RU_PHONETIC)
  return (value,) if swapped==value else (value,swapped)
def song_key(value):
 # Remove only credit/mastering suffixes. Keep meaningful subtitles intact.
 value=re.sub(r'\s*[\[(](?:feat\.?|ft\.?|with)\s+[^\])]*[\])]','',value,flags=re.I)
 value=re.sub(r'\s*[-–]\s*(?:\d{4}\s+)?(?:remaster(?:ed)?|radio edit|single version|original mix).*$', '',value,flags=re.I)
 value=re.sub(r'\s*[\[(](?:\d{4}\s+)?(?:remaster(?:ed)?|radio edit|single version|original mix)[^\])]*[\])]','',value,flags=re.I)
 return text_key(value)
HOT_HITS={}
for line in pathlib.Path(__file__).with_name('hot_hits.tsv').read_text(encoding='utf-8').splitlines():
 if not line or line.startswith('#'):continue
 artist,titles=line.split('|')
 HOT_HITS[text_key(artist)]={song_key(t) for t in titles.split(';')}
def is_hot_hit(artist,title):return song_key(title) in HOT_HITS.get(text_key(artist),set())

PROFILES={}
for line in pathlib.Path(__file__).with_name('recognition_data.tsv').read_text(encoding='utf-8').splitlines():
 if not line or line.startswith('#'):continue
 parts=line.split('|')
 if len(parts)!=7:continue
 country,language,genres,artist,reach,titles,evidence=parts
 PROFILES[text_key(artist)]=dict(name=artist,country=country,language=language,genres=genres.split(';'),reach=reach,titles={song_key(t) for t in titles.split(';')},examples=titles.split(';'),evidence=evidence)
# Exact artist aliases avoid fuzzy matches to unrelated artists/covers.
ARTIST_ALIASES={}
for line in pathlib.Path(__file__).with_name('japanese_artist_aliases.tsv').read_text(encoding='utf-8').splitlines():
 if not line or line.startswith('#'):continue
 name,aliases=line.split('|')
 ARTIST_ALIASES[text_key(name)]=aliases.split(';')
ARTIST_CANONICAL={text_key(alias):name for name,aliases in ARTIST_ALIASES.items() for alias in aliases}
def artist_names(name):return [name,*ARTIST_ALIASES.get(text_key(name),[])]
def canonical_artist_key(name):return ARTIST_CANONICAL.get(text_key(name),text_key(name))

ANIME_SONGS={}
for line in pathlib.Path(__file__).with_name('anime_songs.tsv').read_text(encoding='utf-8').splitlines():
 if not line or line.startswith('#'):continue
 artist,score,series,titles=line.split('|')
 aliases=titles.split(';');key=canonical_artist_key(artist)
 entry=dict(artist=artist,score=int(score),series=series,titles=aliases,canonical=aliases[0])
 lane=ANIME_SONGS.setdefault(key,{})
 for title in aliases:
  token=song_key(title)
  if token in lane and lane[token]['canonical']!=entry['canonical']:raise ValueError('Conflicting Anime title: '+artist+' / '+title)
  lane[token]=entry
 if key not in PROFILES:
  PROFILES[key]=dict(name=artist,country='JP',language='Japanese',genres=['Anime'],reach='local',titles=set(),examples=[],evidence='editorial-anime')
 if 'Anime' not in PROFILES[key]['genres']:PROFILES[key]['genres'].append('Anime')
def anime_song(artist,title):return ANIME_SONGS.get(canonical_artist_key(artist),{}).get(song_key(title))
def canonical_title(artist,title):
 entry=anime_song(artist,title)
 return entry['canonical'] if entry else title

def known_titles(seed,genre):
 if genre=='Anime':return list(ANIME_SONGS.get(canonical_artist_key(seed.get('name') or seed.get('seed_artist') or seed.get('artist','')),{}))
 return (profile(seed) or {}).get('examples',[])

# Specialist standards are Easy inside their genre; Medium in Mixed unless proven crossover.
SPECIALIST={'Jazz','Blues','K-pop','J-pop','Anime','Afrobeats','Country','Metal','Soul / Funk'}
MIXED_CROSSOVER={text_key(a) for a in ['Metallica','Evanescence','System Of A Down','Rammstein','Nightwish','HIM','Lordi','Johnny Cash','Dolly Parton','John Denver','Shania Twain','Shaboozey','Dasha','Louis Armstrong','Frank Sinatra','Stevie Wonder','Earth, Wind & Fire','Bill Withers','Ben E. King','PSY','BTS','BLACKPINK','ROSÉ','Rema','Tyla','Master KG','Aretha Franklin','Marvin Gaye','Nina Simone','Ella Fitzgerald','Etta James','B.B. King','Bob Marley & The Wailers','Bob Marley','Shaggy','Sean Paul','Nat King Cole','Wizkid','Burna Boy','CKay','Ayra Starr','Fireboy DML','Tems','Jung Kook','TWICE','NewJeans','Stray Kids','Iron Maiden','Black Sabbath','Judas Priest','Karol G','J Balvin','Anitta','Shakira','Daddy Yankee','Eric Clapton','Elvis Presley','Whitney Houston','Mariah Carey','Celine Dion','Adele','Ed Sheeran']}
def profile(seed):return PROFILES.get(canonical_artist_key(seed.get('seed_artist') or seed.get('name') or seed.get('artist','')))
def recognition(seed,title,region,genre):
  p=profile(seed)
  if genre=='Anime':
   entry=anime_song(seed.get('name') or seed.get('seed_artist') or seed.get('artist',''),title)
   return entry['score'] if entry else 0
  if not p or song_key(title) not in p['titles']:return 0
  country=COUNTRIES.get(region)
  local=country==p['country'] or region in AREAS and p['country'] in AREAS[region]
  genre_fan=genre in ('K-pop','J-pop','Anime') and genre in p['genres']
  if not local and p['reach']=='local' and not genre_fan:return 0
  if not local and genre=='Mixed' and set(p['genres'])<=SPECIALIST and text_key(p['name']) not in MIXED_CROSSOVER:return 68
  # Europe is an audience mix: european-reach hits are Easy in Europe,
  # solid Medium worldwide. North America penalises non-global less.
  if not local and region=='Europe' and p['reach'] in ('europe','global'):return 90
  if not local and region=='Worldwide' and p['reach']=='europe' and not genre_fan:return 68
  if not local and region=='North America' and p['reach']!='global' and not genre_fan:return 60
  return 94 if local else 90

def classify_tracks(tracks,seed,region,genre):
  # Provider rank is not a regional chart position. Positional tiers are conservative
  # fallbacks ONLY below Easy, with no relaxation when a pool is too small.
  tracks=sorted(tracks,key=lambda t:t.get('rank',0),reverse=True)
  for position,t in enumerate(tracks):
   known=recognition(seed,t['title'],region,genre)
   rank=max(0,min(1_000_000,int(t.get('rank') or 0)))
   if known:
     score=known
   else:
     # Local-only titles out of scope never get promoted by provider rank.
     # Deeper catalogue (positions 30+) feeds Expert/Impossible tails.
     p=profile(seed)
     local=bool(p and (COUNTRIES.get(region)==p['country'] or p['country'] in AREAS.get(region,set())))
     fan=bool(p and genre in ('K-pop','J-pop','Anime') and genre in p['genres'])
     if p and p['reach']=='local' and not (local or fan):
       score=16
     elif fan and genre=='J-pop':
       # J-pop tiers are relative to its own audience, not global provider
       # popularity. Curated signature tracks above remain Easy only.
       score=68 if position<8 else 52 if position<25 else 32 if position<45 else 16
     else:
       score=(68 if position<3 and rank>=400_000 else 60 if position<8 and rank>=150_000 else 48 if position<15 and rank>=80_000 else 32 if position<45 and rank>=20_000 else 16)
   t.update(hot_hit=is_hot_hit(seed['name'],t['title']),recognition=score,recognition_source=profile(seed)['evidence'] if known else 'provider-relative',seed_artist=seed['name'],artist_position=position)
  return tracks

def in_difficulty(t,difficulty):
  score=t.get('recognition',0)
  # Disjoint ladder: Easy curated only, Medium known crossovers + top provider,
  # Hard catalogue favourites, Expert deep cuts, Impossible tail.
  return {'Hits':t.get('hot_hit',False),'Easy':score>=85,'Medium':65<=score<85,'Normal':65<=score<85,'Hard':45<=score<65,'Expert':25<=score<45,'Impossible':score<25}.get(difficulty,False)

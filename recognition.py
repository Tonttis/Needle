"""Explicit song-level calibration; chart references and editorial choices are distinct.
Popularity ranks are only a secondary signal, never proof that a song is Easy.
"""
import pathlib,re,unicodedata
VERSION='v9-hits-2'
COUNTRIES={'Finland':'FI','United Kingdom':'GB','Ireland':'IE','Sweden':'SE','Norway':'NO','Denmark':'DK','Germany':'DE','France':'FR','Belgium':'BE','Netherlands':'NL','Italy':'IT','Spain':'ES','Portugal':'PT','Poland':'PL','Austria':'AT','Switzerland':'CH','Moldova':'MD','Iceland':'IS','United States':'US','Canada':'CA','Australia':'AU','New Zealand':'NZ','Brazil':'BR','Colombia':'CO','Puerto Rico':'PR','South Korea':'KR','Japan':'JP','Jamaica':'JM','Nigeria':'NG','South Africa':'ZA'}
AREAS={'Nordics':{'FI','SE','NO','DK','IS'},'Latin America':{'BR','CO','PR','MX','AR','CL','CU','DO'},'Asia':{'JP','KR','IN','TH','PH'},'Africa':{'NG','ZA','GH','CM','KE'},'Oceania':{'AU','NZ'}}
def text_key(value):
 value=''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))
 return re.sub(r'[^\w]+','',value)
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
 country,language,genres,artist,reach,titles,evidence=line.split('|')
 PROFILES[text_key(artist)]=dict(name=artist,country=country,language=language,genres=genres.split(';'),reach=reach,titles={song_key(t) for t in titles.split(';')},examples=titles.split(';'),evidence=evidence)
# Specialist standards are Easy inside their genre; Medium in Mixed unless proven crossover.
SPECIALIST={'Jazz','Blues','K-pop','J-pop','Afrobeats','Country','Metal','Soul / Funk'}
MIXED_CROSSOVER={text_key(a) for a in ['Metallica','Evanescence','System Of A Down','Rammstein','Nightwish','HIM','Lordi','Johnny Cash','Dolly Parton','John Denver','Shania Twain','Shaboozey','Dasha','Louis Armstrong','Frank Sinatra','Stevie Wonder','Earth, Wind & Fire','Bill Withers','Ben E. King','PSY','BTS','BLACKPINK','ROSÉ','Rema','Tyla','Master KG','Aretha Franklin','Marvin Gaye','Nina Simone','Ella Fitzgerald','Etta James','B.B. King','Bob Marley & The Wailers','Bob Marley','Shaggy','Sean Paul','Nat King Cole','Wizkid','Burna Boy','CKay','Ayra Starr','Fireboy DML','Tems','Jung Kook','TWICE','NewJeans','Stray Kids','Iron Maiden','Black Sabbath','Judas Priest','Karol G','J Balvin','Anitta','Shakira','Daddy Yankee','Eric Clapton','Elvis Presley','Whitney Houston','Mariah Carey','Celine Dion','Adele','Ed Sheeran']}
def profile(seed):return PROFILES.get(text_key(seed.get('seed_artist') or seed.get('name') or seed.get('artist','')))
def recognition(seed,title,region,genre):
  p=profile(seed)
  if not p or song_key(title) not in p['titles']:return 0
  country=COUNTRIES.get(region)
  local=country==p['country'] or region in AREAS and p['country'] in AREAS[region]
  genre_fan=genre in ('K-pop','J-pop') and genre in p['genres']
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
     p=profile(seed)
     if p and p['reach']=='local':
       score=16
     else:
       score=(68 if position<3 and rank>=400_000 else 60 if position<8 and rank>=150_000 else 48 if position<15 and rank>=80_000 else 32 if position<30 and rank>=20_000 else 16)
   t.update(hot_hit=is_hot_hit(seed['name'],t['title']),recognition=score,recognition_source=profile(seed)['evidence'] if known else 'provider-relative',seed_artist=seed['name'],artist_position=position)
  return tracks

def in_difficulty(t,difficulty):
  score=t.get('recognition',0)
  # Disjoint ladder: Easy curated only, Medium known crossovers + top provider,
  # Hard catalogue favourites, Expert deep cuts, Impossible tail.
  return {'Hits':t.get('hot_hit',False),'Easy':score>=85,'Medium':65<=score<85,'Normal':65<=score<85,'Hard':45<=score<65,'Expert':25<=score<45,'Impossible':score<25}.get(difficulty,False)

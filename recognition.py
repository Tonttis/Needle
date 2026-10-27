"""Explicit song-level calibration; chart references and editorial choices are distinct.
Popularity ranks are only a secondary signal, never proof that a song is Easy.
"""
import pathlib,re,unicodedata
VERSION='v8-hits-1'
COUNTRIES={'Finland':'FI','United Kingdom':'GB','Ireland':'IE','Sweden':'SE','Norway':'NO','Denmark':'DK','Germany':'DE','France':'FR','Belgium':'BE','Netherlands':'NL','Italy':'IT','Spain':'ES','Portugal':'PT','Poland':'PL','Austria':'AT','Switzerland':'CH','United States':'US','Canada':'CA','Australia':'AU','New Zealand':'NZ','Brazil':'BR','Colombia':'CO','Puerto Rico':'PR','South Korea':'KR','Japan':'JP','Jamaica':'JM','Nigeria':'NG','South Africa':'ZA'}
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
for line in pathlib.Path(__file__).with_name('hot_hits.tsv').read_text().splitlines():
 if not line or line.startswith('#'):continue
 artist,titles=line.split('|')
 HOT_HITS[text_key(artist)]={song_key(t) for t in titles.split(';')}
def is_hot_hit(artist,title):return song_key(title) in HOT_HITS.get(text_key(artist),set())

PROFILES={}
for line in pathlib.Path(__file__).with_name('recognition_data.tsv').read_text().splitlines():
 if not line or line.startswith('#'):continue
 country,language,genres,artist,reach,titles,evidence=line.split('|')
 PROFILES[text_key(artist)]=dict(name=artist,country=country,language=language,genres=genres.split(';'),reach=reach,titles={song_key(t) for t in titles.split(';')},examples=titles.split(';'),evidence=evidence)
# Specialist standards are Easy inside their genre; not automatically Easy in Mixed.
SPECIALIST={'Jazz','Blues','K-pop','J-pop','Afrobeats','Country','Metal','Soul / Funk'}
MIXED_CROSSOVER={text_key(a) for a in ['Metallica','Evanescence','System Of A Down','Rammstein','Nightwish','HIM','Lordi','Johnny Cash','Dolly Parton','John Denver','Shania Twain','Shaboozey','Dasha','Louis Armstrong','Frank Sinatra','Stevie Wonder','Earth, Wind & Fire','Bill Withers','Ben E. King','PSY','BTS','BLACKPINK','ROSÉ','Rema','Tyla','Master KG']}
def profile(seed):return PROFILES.get(text_key(seed.get('seed_artist') or seed.get('name') or seed.get('artist','')))
def recognition(seed,title,region,genre):
 p=profile(seed)
 if not p or song_key(title) not in p['titles']:return 0
 country=COUNTRIES.get(region)
 local=country==p['country'] or region in AREAS and p['country'] in AREAS[region]
 genre_fan=genre in ('K-pop','J-pop') and genre in p['genres']
 if not local and p['reach']=='local' and not genre_fan:return 0
 if not local and region=='Worldwide' and p['reach']=='europe' and not genre_fan:return 78
 if not local and region=='North America' and p['reach']!='global' and not genre_fan:return 72
 if not local and genre=='Mixed' and set(p['genres'])<=SPECIALIST and text_key(p['name']) not in MIXED_CROSSOVER:return 76
 return 94 if local else 90

def classify_tracks(tracks,seed,region,genre):
 # Provider rank is not a regional chart position. Positional tiers are conservative
 # fallbacks ONLY below Easy, with no relaxation when a pool is too small.
 tracks=sorted(tracks,key=lambda t:t.get('rank',0),reverse=True)
 for position,t in enumerate(tracks):
  known=recognition(seed,t['title'],region,genre)
  rank=max(0,min(1_000_000,int(t.get('rank') or 0)))
  score=known or (68 if position<3 and rank>=400_000 else 60 if position<8 and rank>=150_000 else 48 if position<15 else 32 if position<30 else 16)
  t.update(hot_hit=is_hot_hit(seed['name'],t['title']),recognition=score,recognition_source=profile(seed)['evidence'] if known else 'provider-relative',seed_artist=seed['name'],artist_position=position)
 return tracks

def in_difficulty(t,difficulty):
 score=t.get('recognition',0)
 return {'Hits':t.get('hot_hit',False),'Easy':score>=85,'Medium':score>=55,'Normal':score>=55,'Hard':40<=score<85,'Expert':25<=score<55,'Impossible':score<25}.get(difficulty,False)

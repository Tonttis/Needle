"""Opening-only catalog and separately cached video resolution for Anime Video Race."""
import json,math,pathlib,re,sqlite3,subprocess,threading,time,unicodedata
from anime_answers import SERIES,title_key
from recognition import anime_song,canonical_artist_key,song_key
VERSION='anime-op-v1'
TTL=30*86400
OPENINGS={}
for line in pathlib.Path(__file__).with_name('anime_openings.tsv').read_text(encoding='utf-8').splitlines():
 if not line or line.startswith('#'):continue
 artist,title,video=line.split('|');theme=anime_song(artist,title)
 if not theme:raise ValueError('Unknown opening: '+artist+' / '+title)
 if video and not re.fullmatch(r'[A-Za-z0-9_-]{11}',video):raise ValueError('Invalid opening video ID')
 OPENINGS[(canonical_artist_key(artist),song_key(theme['canonical']))]=dict(theme,video_id=video)
_cache={};_locks={};_guard=threading.Lock()

def opening(song):
 artist=song.get('seed_artist') or song.get('artist','');theme=anime_song(artist,song.get('title',''))
 return OPENINGS.get((canonical_artist_key(artist),song_key(theme['canonical']))) if theme else None

def pool(tracks,difficulty=None):
 from recognition import in_difficulty
 rows=[t for t in tracks if opening(t)]
 playable=[t for t in rows if 'recognition' not in t or in_difficulty(t,difficulty)]
 if len({canonical_artist_key(t.get('seed_artist') or t['artist']) for t in playable})<2:raise ValueError('Not enough anime openings in this mix. Try another difficulty or decade.')
 return rows

def valid_duration(value):
 try:return not isinstance(value,bool) and math.isfinite(float(value)) and 45<=float(value)<=150
 except (ValueError,TypeError):return False

def contains(text,alias):
 text=unicodedata.normalize('NFKC',str(text)).casefold();alias=unicodedata.normalize('NFKC',alias).casefold()
 if re.search(r'[\u3040-\u30ff\u3400-\u9fff]',alias):return len(title_key(alias))>=2 and title_key(alias) in title_key(text)
 words=re.findall(r'[a-z0-9]+',unicodedata.normalize('NFKD',alias))
 if sum(map(len,words))<2:return False
 if sum(map(len,words))<4:return bool(re.search(r'(?<![a-z0-9])'+re.escape(alias)+r'(?![a-z0-9])',text))
 return bool(re.search(r'(?<![a-z0-9])'+r'[^a-z0-9]*'.join(map(re.escape,words))+r'(?![a-z0-9])',text))

def candidate_score(item,theme):
 ident=item.get('id','');title=str(item.get('title') or '');description=str(item.get('description') or '')[:2000];text=title+' '+description
 if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',ident) or not valid_duration(item.get('duration')) or item.get('is_live') or item.get('live_status')=='is_live':return None
 if not re.search(r'\bopening\b|\bop\s*\d*\b|\bncop\b|オープニング|ノンクレジット\s*OP',title,re.I):return None
 if re.search(r'\b(?:ending|ed\d*|amv|mad|cover|karaoke|reaction|lyrics?|compilation|playlist|live|full|instrumental)\b|エンディング|歌ってみた|弾いてみた|踊ってみた|耐久|作業用|主題歌集|オープニング集',title,re.I):return None
 if not any(contains(text,alias) for alias in theme['titles']):return None
 series=SERIES[theme['series']]
 if not any(contains(text,alias) for alias in series['aliases']):return None
 channel=str(item.get('channel') or item.get('uploader') or '')
 official=bool(item.get('channel_is_verified')) or bool(re.search(r'mappa|toho|aniplex|crunchyroll|kadokawa|アニプレックス|公式',channel,re.I))
 return 30*official+8*any(contains(title,alias) for alias in theme['titles'])+5*bool(re.search(r'creditless|ノンクレジット',title,re.I))-abs(float(item['duration'])-90)/30

def key_for(theme):return VERSION+'|'+canonical_artist_key(theme['artist'])+'|'+song_key(theme['canonical'])

def read_cache(data,key):
 if key in _cache and time.time()-_cache[key][0]<TTL:return _cache[key][1]
 try:
  with sqlite3.connect(data/'catalog-cache.sqlite',timeout=20) as db:
   db.execute('CREATE TABLE IF NOT EXISTS anime_opening_cache (query TEXT PRIMARY KEY,saved REAL,candidates TEXT)')
   row=db.execute('SELECT saved,candidates FROM anime_opening_cache WHERE query=?',(key,)).fetchone()
  if row and time.time()-row[0]<TTL:
   rows=json.loads(row[1]);rows=[r for r in rows if isinstance(r,dict) and isinstance(r.get('id'),str) and re.fullmatch(r'[A-Za-z0-9_-]{11}',r['id']) and isinstance(r.get('title'),str)][:8]
   _cache[key]=(row[0],rows);return rows
 except (OSError,sqlite3.Error,ValueError,TypeError):pass
 return []

def save_cache(data,key,rows):
 rows=rows[:8];saved=time.time();_cache[key]=(saved,rows)
 try:
  data.mkdir(exist_ok=True,parents=True)
  with sqlite3.connect(data/'catalog-cache.sqlite',timeout=20) as db:
   db.execute('CREATE TABLE IF NOT EXISTS anime_opening_cache (query TEXT PRIMARY KEY,saved REAL,candidates TEXT)')
   db.execute('INSERT OR REPLACE INTO anime_opening_cache VALUES (?,?,?)',(key,saved,json.dumps(rows)))
 except (OSError,sqlite3.Error):pass

def remember(song,data,ident,title):
 theme=opening(song);key=key_for(theme)
 rows=[dict(id=ident,title=title)]+[r for r in read_cache(data,key) if r['id']!=ident]
 save_cache(data,key,rows)

def candidates(song,data):
 theme=opening(song)
 if not theme:raise ValueError('This theme is not a registered anime opening.')
 key=key_for(theme)
 with _guard:mutex=_locks.setdefault(key,threading.Lock())
 # A per-theme mutex prevents duplicate searches from concurrent rooms/prefetch.
 with mutex:
  seen=set()
  cached=read_cache(data,key)
  for row in cached:
   seen.add(row['id']);yield row['id'],row['title']
  if theme['video_id'] and theme['video_id'] not in seen:
   seen.add(theme['video_id']);yield theme['video_id'],theme['series']+' opening / '+theme['canonical']
  series=SERIES[theme['series']];latin=next((t for t in theme['titles'] if re.search('[a-zA-Z]',t)),theme['canonical'])
  queries=[series['title']+' '+latin+' '+theme['artist']+' creditless opening',series['japanese']+' '+theme['canonical']+' ノンクレジットOP']
  for query in dict.fromkeys(queries):
   try:
    result=subprocess.run(['yt-dlp','--js-runtimes','node','--flat-playlist','--skip-download','--dump-single-json','--no-warnings','--socket-timeout','10','--retries','1','ytsearch8:'+query],capture_output=True,text=True,timeout=25,check=True)
    rows=json.loads(result.stdout).get('entries',[]);ranked=[]
    for item in rows[:8]:
     if not isinstance(item,dict):continue
     score=candidate_score(item,theme)
     if score is not None:ranked.append((score,dict(id=item['id'],title=str(item['title'])[:500])))
    found=[row for _,row in sorted(ranked,key=lambda r:-r[0])]
    if found:save_cache(data,key,found)
    for row in found:
     if row['id'] not in seen:seen.add(row['id']);yield row['id'],row['title']
   except (subprocess.SubprocessError,OSError,ValueError,TypeError):continue

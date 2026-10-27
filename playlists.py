"""Import playlist metadata, then resolve tracks to the game's preview provider."""
import base64,json,os,re,subprocess,threading,time,urllib.parse,urllib.request
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor,as_completed
from catalog import norm
from recognition import is_hot_hit

MAX_ITEMS=1000
def identify(url):
 u=urllib.parse.urlparse(url)
 if u.scheme!='https' or u.username or u.password or u.port:raise ValueError('Use an HTTPS playlist link.')
 host=(u.hostname or '').lower()
 if host in ('youtube.com','www.youtube.com','music.youtube.com','m.youtube.com','youtu.be'):
  list_id=urllib.parse.parse_qs(u.query).get('list',[''])[0]
  if not re.fullmatch(r'[A-Za-z0-9_-]{10,120}',list_id):raise ValueError('This YouTube link has no valid playlist ID.')
  return 'youtube',list_id
 if host=='open.spotify.com':
  m=re.fullmatch(r'/(?:intl-[A-Za-z-]+/)?playlist/([A-Za-z0-9]{22})/?',u.path)
  if m:return 'spotify',m.group(1)
 raise ValueError('Use a public YouTube playlist or Spotify playlist link.')

_token_lock=threading.Lock()
_token_cache={'value':'','expires':0}
def spotify_token():
 direct=os.getenv('SPOTIFY_ACCESS_TOKEN','').strip()
 if direct:return direct
 client=os.getenv('SPOTIFY_CLIENT_ID','').strip();secret=os.getenv('SPOTIFY_CLIENT_SECRET','').strip();refresh=os.getenv('SPOTIFY_REFRESH_TOKEN','').strip()
 if not all((client,secret,refresh)):raise ValueError('Spotify import needs a Spotify user access token or configured client and refresh token on the server. Development Mode can read only playlists that user owns or collaborates on.')
 with _token_lock:
  if _token_cache['value'] and time.time()<_token_cache['expires']:return _token_cache['value']
  body=urllib.parse.urlencode({'grant_type':'refresh_token','refresh_token':refresh}).encode()
  basic=base64.b64encode((client+':'+secret).encode()).decode()
  request=urllib.request.Request('https://accounts.spotify.com/api/token',data=body,headers={'Authorization':'Basic '+basic,'Content-Type':'application/x-www-form-urlencoded'})
  try:
   with urllib.request.urlopen(request,timeout=15) as response:data=json.load(response)
   token=data['access_token'];expires=int(data.get('expires_in',3600))
  except Exception as e:raise ValueError('Spotify authorization refresh failed. Check your server credentials.') from e
  _token_cache.update(value=token,expires=time.time()+max(1,expires-60));return token

def source_tracks(url):
 provider,identifier=identify(url)
 if provider=='youtube':
  canonical='https://www.youtube.com/playlist?list='+identifier
  try:
   proc=subprocess.run(['yt-dlp','--js-runtimes','node','--flat-playlist','--dump-single-json','--skip-download','--playlist-end',str(MAX_ITEMS+1),'--',canonical],check=True,capture_output=True,text=True,timeout=120)
   data=json.loads(proc.stdout);entries=data.get('entries') or []
  except (subprocess.SubprocessError,ValueError) as e:raise ValueError('Could not read this YouTube playlist. Check that it is public and available to your server.') from e
  if len(entries)>MAX_ITEMS:raise ValueError(f'This playlist exceeds the {MAX_ITEMS}-track import limit.')
  output=[]
  for e in entries:
   if not e:continue
   title=e.get('track') or e.get('title') or '';artist=e.get('artist') or ''
   if not artist and ' - ' in title:artist,title=title.split(' - ',1)
   if not artist:artist=re.sub(r'\s*-\s*Topic$', '',e.get('channel') or e.get('uploader') or '',flags=re.I)
   title=re.sub(r'\s*[\(\[]\s*(?:official|lyrics?|audio|video|visualizer)[^\])]*[\])]','',title,flags=re.I).strip()
   video_id=e.get('id','');video_id=video_id if re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id) else ''
   if title and artist:output.append(dict(artist=artist,title=title,video_id=video_id))
  return output,len(entries),provider
 token=spotify_token()
 output=[];offset=0;total=None
 while total is None or offset<total:
  url='https://api.spotify.com/v1/playlists/'+identifier+'/items?limit=50&offset='+str(offset)
  request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json','User-Agent':'Needle/9'})
  try:
   with urllib.request.urlopen(request,timeout=15) as response:data=json.load(response)
  except Exception as e:raise ValueError('Spotify refused access. Check the token and that its user owns or collaborates on this playlist.') from e
  total=data.get('total',0)
  if total>MAX_ITEMS:raise ValueError(f'This playlist exceeds the {MAX_ITEMS}-track import limit.')
  items=data.get('items',[])
  if not items and offset<total:raise ValueError('Spotify did not return all playlist pages. Please retry.')
  for entry in items:
   t=(entry or {}).get('item') or (entry or {}).get('track') or {};artists=t.get('artists') or []
   if t.get('type','track')=='track' and not t.get('is_local') and t.get('name') and artists:
    output.append(dict(artist=artists[0].get('name',''),title=t['name'],video_id='',spotify_id=t.get('id','') if re.fullmatch(r'[A-Za-z0-9]{22}',str(t.get('id',''))) else ''))
  offset+=len(items)
 return output,total,provider

def match_playlist(url,fetch,clean,progress=None):
 if progress:progress('reading',0,None)
 source,total,provider=source_tracks(url)
 if progress:progress('matching',0,len(source))
 def match(item):
  try:
   query=urllib.parse.quote(item['artist']+' '+item['title'])
   rows=fetch('search?limit=10&q='+query).get('data',[])
   def similarity(a,b):return SequenceMatcher(None,norm(a),norm(b)).ratio()
   candidates=[]
   for raw in rows:
    title=raw.get('title','');artist=raw.get('artist',{}).get('name','')
    if not raw.get('preview') or not title or not artist:continue
    ts=similarity(item['title'],title);ar=similarity(item['artist'],artist)
    if ts>=.73 and ar>=.65:candidates.append((ts+ar,raw))
   if not candidates:return None
   raw=max(candidates,key=lambda x:x[0])[1];track=clean(raw)
   track.update(genre='Playlist',language='Playlist',region='Playlist',country='?',artist_id=str(raw['artist']['id']),rank=raw.get('rank',0),youtube_id=item['video_id'],hot_hit=is_hot_hit(raw['artist']['name'],raw['title']),playlist_track=True)
   spotify_id=item.get('spotify_id','')
   if re.fullmatch(r'[A-Za-z0-9]{22}',spotify_id):track.update(spotify_id=spotify_id,spotify_url='https://open.spotify.com/track/'+spotify_id)
   return track
  except (KeyError,ValueError):return None
 with ThreadPoolExecutor(max_workers=6) as workers:
  futures=[workers.submit(match,item) for item in source];matched=[]
  for future in as_completed(futures):
   matched.append(future.result())
   if progress:progress('matching',len(matched),len(source))
 tracks=list({t['id']:t for t in matched if t}.values())
 if len(tracks)<4:raise ValueError('Fewer than four playlist songs could be matched to playable previews. Try another playlist.')
 return tracks,dict(provider=provider,total=total,matched=len(tracks),unmatched=total-len(tracks))

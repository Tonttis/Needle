import math
from race_media import prepare as prepare_race_media, start_janitor
from audio_cache import AudioCache
from recognition import VERSION as CATALOG_VERSION, in_difficulty
from catalog import filter_options
import hashlib
import copy
import sqlite3
import json, os, secrets, time, random, threading, urllib.request, urllib.parse, subprocess, pathlib, mimetypes
from catalog import choose_song, artist_key, build_pool, round_choices, norm, REGIONS, DIFFICULTIES, GENRES as CATALOG_GENRES
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
ROOT=pathlib.Path(__file__).parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
STEPS=[.1,.5,2,8,15]
GENRES={'Mixed':0,'Pop':132,'Rock':152,'Metal':464,'Rap / Hip Hop':116,'Dance':113,'Electronic':106,'R&B':165,'Jazz':129,'Classical':98}
rooms={}; lock=threading.RLock(); cache={}
request_lock=threading.Lock()
last_request=0.0

def _fetch(path, fresh=False):
    global last_request
    now=time.time()
    if not fresh and path in cache and now-cache[path][0]<86400:return cache[path][1]
    # Metadata only. Persistent cache survives container rebuilds via /app/data.
    with sqlite3.connect(DATA/'catalog-cache.sqlite',timeout=20) as db:
        db.execute('CREATE TABLE IF NOT EXISTS responses (path TEXT PRIMARY KEY, saved REAL, body TEXT)')
        row=db.execute('SELECT saved,body FROM responses WHERE path=?',(path,)).fetchone()
    if not fresh and row and now-row[0]<86400:
        value=json.loads(row[1]);cache[path]=(row[0],value);return value
    try:
        with request_lock:
            delay=.09-(time.monotonic()-last_request)
            if delay>0:time.sleep(delay)
            last_request=time.monotonic()
        request=urllib.request.Request('https://api.deezer.com/'+path,headers={'Accept':'application/json','Accept-Language':'en','User-Agent':'Needle/5'})
        with urllib.request.urlopen(request,timeout=12) as response:value=json.load(response)
        if not isinstance(value,dict) or 'error' in value:raise ValueError('Music provider unavailable')
    except Exception as error:
        if not fresh and row and now-row[0]<7*86400:return json.loads(row[1])
        raise ValueError('Music catalog could not be reached. Check server internet access and try again.') from error
    cache[path]=(now,value)
    with sqlite3.connect(DATA/'catalog-cache.sqlite',timeout=20) as db:
        db.execute('INSERT OR REPLACE INTO responses VALUES (?,?,?)',(path,now,json.dumps(value)))
    return value
metadata_locks={}
metadata_guard=threading.Lock()
def fetch(path, fresh=False):
    with metadata_guard:mutex=metadata_locks.setdefault(path,threading.Lock())
    with mutex:return _fetch(path,fresh)
def clean(t):
    names=list(dict.fromkeys(a['name'] for a in [t['artist']]+t.get('contributors',[]) if a.get('name')))
    artist=', '.join(names)
    query=urllib.parse.quote(artist+' '+t['title'])
    return {'id':str(t['id']),'title':t['title'],'artist':artist,'preview':t.get('preview',''),'art':t.get('album',{}).get('cover_medium',''),'link':t.get('link',''),
            'spotify_url':'https://open.spotify.com/search/'+query}
def credit(t):
    if t.get('_credits'): return t
    try:
        detail=fetch('track/'+t['id'])
        t['artist']=clean(detail)['artist']; t['_credits']=True
    except (ValueError,KeyError): pass
    return t

def suggestions(r,term):
    from recognition import layout_variants
    terms=[norm(v) for v in layout_variants(term)]
    terms=[t for t in terms if len(t)>=2]
    if not terms:return []
    song=r['song']
    rows=[t for t in r['pool'] if t.get('genre')==song.get('genre') and t.get('language')==song.get('language')]
    scored=[]
    for variant in terms:
     words=variant.split()
     for t in rows:
        title=norm(t['title']); artist=norm(t['artist']); text=title+' '+artist
        score=3 if title==variant or artist==variant else 2 if all(w in text for w in words) else SequenceMatcher(None,variant,title).ratio()
        if score>.55:scored.append((-score,title,artist,t['id'],t))
    seen={}
    for s in sorted(scored,key=lambda x:x[:4]):
        seen.setdefault(s[3],s)
    return [s[4] for s in sorted(seen.values(),key=lambda x:x[:3])[:25]]

catalog_workers=ThreadPoolExecutor(max_workers=2)
credit_workers=ThreadPoolExecutor(max_workers=2)
catalog_jobs={}
catalog_started={}
catalog_guard=threading.Lock()
credit_pending=set()
def queue_credit(t):
    if t.get('_credits') or t['id'] in credit_pending or len(credit_pending)>=48:return
    credit_pending.add(t['id'])
    def run():
        try:credit(t)
        finally:credit_pending.discard(t['id'])
    credit_workers.submit(run)
def prepare_catalog(genre,region,difficulty):
    if difficulty=='Normal':difficulty='Medium'
    if genre not in CATALOG_GENRES or region not in REGIONS or difficulty not in DIFFICULTIES+['Hits']:
        raise ValueError('Invalid music filters')
    key=(genre,region,difficulty)
    with catalog_guard:
        job=catalog_jobs.get(key)
        if job and (not job.done() or (job.exception() is None and time.time()-catalog_started.get(key,0)<86400)):return job
        def build():
            path=DATA/('pool-'+CATALOG_VERSION+'-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]+'.json')
            if path.exists() and time.time()-path.stat().st_mtime<86400:
                try:return json.loads(path.read_text())
                except (ValueError,OSError):pass
            rows=build_pool(fetch,clean,*key)
            tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(rows));tmp.replace(path)
            return rows
        job=catalog_workers.submit(build);catalog_jobs[key]=job;catalog_started[key]=time.time();return job
def pool(genre,region='Worldwide',difficulty='Normal'):
    try:return copy.deepcopy(prepare_catalog(genre,region,difficulty).result(timeout=20))
    except TimeoutError:raise ValueError('This new mix is still loading in the background. Try Start again shortly; the work is being reused.')
def race_points(elapsed,duration):
    """Twenty equal intervals over the track: 20 at the start, 1 at the end."""
    try:elapsed=float(elapsed);duration=float(duration)
    except (TypeError,ValueError):return 0
    if not math.isfinite(elapsed) or not math.isfinite(duration) or duration<=0 or elapsed>=duration:return 0
    return max(1,20-math.floor(20*max(0,elapsed)/duration))

RACE_FORMAT='bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best'
RACE_MAX_BYTES=80*1024*1024
RACE_BUFFER_TIMEOUT=150

def advance(r):
    r['song']=choose_song(r); r['used'].append(r['song']['id'])
    r['stage']=0; r['guesses']={}; r['history']=[]; r['round']+=1; r['phase']='playing'; r['deadline']=time.time()+45
    r['guess_times']={}; r['race_cooldowns']={}; r['race_wrong']={}; r['race_started']=None
    if r.get('mode')=='race':
        # Gated path: video (720p mp4 via yt-dlp, audio muxed in) or at the
        # very least full-length audio must be ready BEFORE the guess clock
        # starts. Deadline = full track length once ready; guessing blocked
        # until then. Buffering timeout keeps a stuck download from hanging.
        r['videoId']=None; r['videoTitle']=None; r['race_video']=None; r.pop('race_path',None)
        r['race_status']='buffering'; r['race_error']=None; r['race_duration']=0
        r['race_started']=None; r['deadline']=0; r['race_ready']=set();r['race_audio_only']=False
    r['board'],r['options']=round_choices(r['song'],r['pool'])
    r['history'].append({'answer':r['song']['id'],'artist':artist_key(r['song'])})
    if r.get('hydrate',False):
        for track in r['options']:queue_credit(track)
    r['audioKey']=secrets.token_urlsafe(24)
    r['deadline']=r['deadline'] if r.get('mode')=='race' else time.time()+45
    if r.get('mode')=='race':queue_youtube(r)
    r['reveal_metadata']={};r['reveal_pending']=False;r['reveal_done']=False
def settle(r):
    if r['phase']!='playing': return
    if r.get('mode')=='race':return settle_race(r)
    if len(r['guesses'])<len(r['players']) and time.time()<r['deadline']: return
    wins=[p for p,g in r['guesses'].items() if g==r['song']['id']]
    if r.get('history'):r['history'][-1].update(stage=r['stage'],correct=len(wins))
    else:r['history'].append({'answer':r['song']['id'],'artist':artist_key(r['song']),'stage':r['stage'],'correct':len(wins)})
    if wins or r['stage']==4 or r['mode']=='choice':
        for p in wins: r['players'][p]['score']+= (5-r['stage']) if not r['multi'] and r['mode']!='choice' else 1
        r['phase']='reveal'; r['winners']=wins
    else:
        r['stage']+=1; r['guesses']={}; r['deadline']=time.time()+30

def settle_race(r):
    """Speed race: solo scores by elapsed time; multiplayer is winner-takes-it.

    Correct guess locks the player. Solo ends on correct/skip/timeout.
    Multi ends on first correct, all-answered, or timeout. Only the fastest
    correct player scores; slower correct players get 0.
    """
    if not r.get('race_started'):return
    now=time.time()
    started=r['race_started']
    def elapsed(p):return r.get('guess_times',{}).get(p,now-started)
    duration=r.get('race_duration') or r['deadline']-started
    correct=[p for p,g in r['guesses'].items() if g==r['song']['id']]
    total=len(r.get('players',{}))
    answered=len(r.get('guesses',{}))
    timeout=now>=r.get('deadline',started+30)
    if r.get('multi'):
        if correct:
            first=min(correct,key=lambda p:elapsed(p))
            # 250ms tie window: near-simultaneous correct both score.
            winners=[p for p in correct if abs(elapsed(p)-elapsed(first))<=0.25]
            pts=race_points(elapsed(first),duration)
            for p in winners:r['players'][p]['score']+=pts
            r['phase']='reveal'; r['winners']=winners
            if r.get('history'):r['history'][-1].update(stage=0,correct=len(winners),race_points=pts,race_elapsed=round(elapsed(first),2))
            return
        if answered>=total or timeout:
            r['phase']='reveal'; r['winners']=[]
            if r.get('history'):r['history'][-1].update(stage=0,correct=0,race_points=0,race_elapsed=round(now-started,2))
            return
        return
    # solo
    if correct or timeout or answered>=1:
        p=correct[0] if correct else None
        pts=race_points(elapsed(p),duration) if p else 0
        if p:r['players'][p]['score']+=pts
        r['phase']='reveal'; r['winners']=correct[:1]
        if r.get('history'):r['history'][-1].update(stage=0,correct=len(correct),race_points=pts,race_elapsed=round(elapsed(p) if p else now-started,2))
        return

def state(r,p):
    settle(r)
    out={k:r[k] for k in ['code','mode','multi','phase','round','rounds','stage','deadline','genre','history']}
    # History carries answer ids + artists so the client can de-prioritise
    # repeats in the next game; stage/correct kept for the timeline.
    out['history']=[dict(stage=h.get('stage',0),correct=h.get('correct',0),artist=h.get('artist'),song=h.get('answer')) for h in r.get('history',[])]
    out['players']=[dict(name=v['name'],score=v['score'],me=k==p,host=k==r['host'],submitted=k in r['guesses']) for k,v in r['players'].items()]
    if '_stats' not in r:
        playable=[t for t in r['pool'] if 'recognition' not in t or in_difficulty(t,r.get('difficulty','Medium'))]
        r['_stats']={'tracks':len(r['pool']),'answers':len(playable),'artists':len({artist_key(t) for t in playable}),'countries':len({t.get('country','?') for t in playable})}
    out['catalog']=r['_stats']
    out['region']=r.get('region','Worldwide'); out['difficulty']=r.get('difficulty','Normal')
    if r['phase'] in ['reveal','finished']:
        out['correct']=p in r.get('winners',[])
        out['result']='correct' if out['correct'] else 'incorrect' if r['guesses'].get(p) else 'skipped'
    if r.get('multi') and r['phase']=='reveal':
        out['correct_players']=[r['players'][winner]['name'] for winner in r.get('winners',[]) if winner in r['players']]
        if r.get('mode')=='race':out['race_winners']=out['correct_players']
    out['host']=p==r['host']; out['submitted']=p in r['guesses']; out['serverTime']=time.time()
    if r['phase']!='lobby': out['audio']='/audio/'+r['audioKey']; out['seconds']=r.get('race_duration',0) if r.get('mode')=='race' else (5 if r['mode']=='choice' else STEPS[r['stage']])
    if r.get('mode')=='race':
        out.update(race_cooldown_until=r.get('race_cooldowns',{}).get(p,0),race_wrong=r.get('race_wrong',{}).get(p,False),race_status=r.get('race_status'),race_error=r.get('race_error'),race_duration=r.get('race_duration',0),race_started=r.get('race_started'),elapsed=max(0,time.time()-(r.get('race_started') or time.time())))
        if r.get('race_path'):out['race_url']='/race-media/'+r['audioKey'];out['race_type']=r['race_type']
    if r['mode']=='choice' and r['phase']=='playing': out['options']=[{k:t[k] for k in ['id','title','artist']} for t in r['options']]
    if r['phase']=='reveal':
        ans={k:v for k,v in r['song'].items() if k not in ['preview','_credits']}
        if r.get('videoId'):ans['videoId']=r['videoId'];ans['videoTitle']=r.get('videoTitle','')
        if r.get('mode')=='race':
            hist=r.get('history',[])
            if hist:ans['race_points']=hist[-1].get('race_points',0);ans['race_elapsed']=hist[-1].get('race_elapsed',0)
        # Spotify check: no API key needed. iTunes Search (Apple) returns a
        # 30s best-part preview + artwork + trackViewUrl for most tracks, and
        # doubles as the Spotify-link resolver input. Deezer stays the game
        # audio; this is reveal-only enrichment and never blocks reveal.
        ans.update(r.get('reveal_metadata',{}))
        ans['preview_pending']=bool(r.get('reveal_pending') and not r.get('reveal_done'))
        if not r.get('reveal_pending') and not r.get('reveal_metadata') and str(r['song'].get('preview','')).startswith('http'):
            r['reveal_pending']=True
            key=r['audioKey'];artist=ans['artist'];title=ans['title']
            def enrich():
                try:metadata=spotify_enrich(artist,title)
                except Exception:metadata={}
                with lock:
                    if r.get('audioKey')==key:r.update(reveal_metadata=metadata,reveal_done=True)
            credit_workers.submit(enrich)
        ans['preview_pending']=bool(r.get('reveal_pending') and not r.get('reveal_done'))
        out['answer']=ans
    return out

def _itunes_search(artist,title):
    """Direct iTunes Search API call (not via Deezer fetch cache)."""
    q=urllib.parse.quote((artist+' '+title).strip())
    if not q:return None
    url='https://itunes.apple.com/search?media=music&entity=song&limit=5&term='+q
    request=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'Needle/5'})
    with urllib.request.urlopen(request,timeout=10) as response:
        return json.load(response)
    return None

def spotify_enrich(artist,title):
    """Best-effort reveal enrichment: Spotify search link + preview audio.

    Uses the public iTunes Search API (no key, JSON) to find the track, then
    builds an open.spotify.com search URL. Returns preview_url (usually the
    chorus/best-part 30s), artwork and spotify link. Empty dict on miss.
    Cached in-memory + sqlite like other metadata.
    """
    out={}
    q=(artist+' '+title).strip()
    if q:out['spotify_url']='https://open.spotify.com/search/'+urllib.parse.quote(q)
    try:
        with request_lock:
            delay=.09-(time.monotonic()-last_request)
            if delay>0:time.sleep(delay)
        data=_itunes_search(artist,title)
        if not isinstance(data,dict) or not data.get('results'):return out
        want=norm(title)
        best=None
        for row in data['results']:
            name=norm(str(row.get('trackName','')))
            if not name:continue
            if name==want or want in name or name in want:
                best=row;break
        if not best:return out
        if best.get('previewUrl'):out['spotify_preview']=best['previewUrl']
        if best.get('artworkUrl100'):out['spotify_art']=best['artworkUrl100'].replace('100x100','300x300')
        if best.get('trackViewUrl'):out['apple_url']=best['trackViewUrl']
    except Exception:pass
    return out
download_locks={}
download_guard=threading.Lock()
def download_lock(track_id):
    with download_guard:return download_locks.setdefault(track_id,threading.Lock())
def load_audio(song):
    if os.getenv('AUDIO_SOURCE','preview')=='youtube':
        target=DATA/(song['id']+'.mp3')
        with download_lock(song['id']):
            if not target.exists():
                subprocess.run(['yt-dlp','--no-playlist','--max-filesize','30M','--download-sections','*0-20','-x','--audio-format','mp3','-o',str(DATA/(song['id']+'.%(ext)s')),'ytsearch1:'+song['artist']+' '+song['title']+' official audio'],check=True,timeout=100,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        b=target.read_bytes(); typ='audio/mpeg'
    else:
        try:
            return read_preview(song.get('preview',''))
        except Exception:
            # Stored catalog URLs can expire before the catalog itself does.
            # Refresh the exact track, bypassing both metadata caches.
            try:
                detail=fetch('track/'+song['id'],fresh=True)
                return read_preview(detail.get('preview',''))
            except Exception as error:
                raise ValueError('This track preview is unavailable from the music provider. Retry playback or skip this track.') from error
    return b,typ

def read_preview(url):
    if not url or urllib.parse.urlparse(url).scheme not in ('https','http'):
        raise ValueError('Track has no preview URL')
    request=urllib.request.Request(url,headers={'User-Agent':'Needle/6.1','Accept':'audio/*'})
    with urllib.request.urlopen(request,timeout=20) as response:
        content=response.headers.get('Content-Type','audio/mpeg').split(';')[0].lower()
        data=response.read(5_000_001)
        if not data or len(data)>5_000_000 or content in ('text/html','application/json','text/plain'):
            raise ValueError('Music provider returned an invalid audio preview')
        return data,content

audio_cache=AudioCache(load_audio)
spotify_cache=AudioCache(lambda song: read_preview(song.get('spotify_preview','')))
video_workers=ThreadPoolExecutor(max_workers=2)
youtube_mem={}

def resolve_youtube(artist,title):
    """Resolve a YouTube video ID for artist+title. Cached 30d. None on miss."""
    q=(artist+' '+title).strip()
    if not q:return None,None
    key='youtube:'+q.lower()
    now=time.time()
    if key in youtube_mem and now-youtube_mem[key][0]<30*86400:
        return youtube_mem[key][1],youtube_mem[key][2]
    try:
        with sqlite3.connect(DATA/'catalog-cache.sqlite',timeout=20) as db:
            db.execute('CREATE TABLE IF NOT EXISTS youtube_cache (query TEXT PRIMARY KEY, saved REAL, videoId TEXT, videoTitle TEXT)')
            row=db.execute('SELECT saved,videoId,videoTitle FROM youtube_cache WHERE query=?',(q,)).fetchone()
        if row and now-row[0]<30*86400:
            youtube_mem[key]=(row[0],row[1],row[2]);return row[1],row[2]
    except Exception:row=None
    video_id,video_title=None,None
    try:
        for suffix in [' official video',' official audio']:
            try:
                proc=subprocess.run(['yt-dlp','--js-runtimes','node','--no-playlist','--print','id','--print','title','--no-warnings','ytsearch1:'+q+suffix],
                    capture_output=True,text=True,timeout=35)
                # yt-dlp prints id then title on separate lines; take first pair.
                lines=[l.strip() for l in (proc.stdout or '').splitlines() if l.strip()]
                if len(lines)>=1 and len(lines[0])==11:
                    video_id=lines[0];video_title=lines[1] if len(lines)>1 else q
                    break
                if len(lines)>=2:
                    # fallback: first non-empty line that looks like an id
                    for i,l in enumerate(lines):
                        if len(l)==11 and ' ' not in l:
                            video_id=l;video_title=lines[i+1] if i+1<len(lines) else q;break
                    if video_id:break
            except Exception:continue
    except Exception:video_id=None
    if video_id:
        try:
            with sqlite3.connect(DATA/'catalog-cache.sqlite',timeout=20) as db:
                db.execute('INSERT OR REPLACE INTO youtube_cache VALUES (?,?,?,?)',(q,now,video_id,video_title or q))
        except Exception:pass
        youtube_mem[key]=(now,video_id,video_title or q)
        return video_id,video_title or q
    return None,None

def queue_youtube(r):
    song=dict(r['song']);code=r['code'];key=r['audioKey'];audio_only=r.get('race_audio_only',False)
    r['race_status']='buffering';r['race_error']=None
    def run():
        try:
            vid,title=resolve_youtube(song['artist'],song['title'])
            if not vid:raise ValueError('No playable video found. Retry or skip this song.')
            def active_media():
                with lock:return [x.get('race_path') for x in rooms.values() if x.get('phase')=='playing']
            path,duration,typ=prepare_race_media(DATA,vid,audio_only=audio_only,protected=active_media)
            result=dict(race_path=path,race_duration=duration,race_type=typ,race_status='ready',videoId=vid,videoTitle=title)
        except Exception as e:result=dict(race_status='error',race_error=str(e))
        with lock:
            cur=rooms.get(code)
            if cur and cur.get('audioKey')==key:cur.update(result)
    video_workers.submit(run)
def active_race_media():
    with lock:return [r.get('race_path') for r in rooms.values() if r.get('phase')=='playing']
start_janitor(DATA,active_race_media)
FILTER_OPTIONS=filter_options()
class Handler(BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def setup(self):
        super().setup(); self.connection.settimeout(30)
    def reply(self,v,status=200):
        b=json.dumps(v).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        try:
            u=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(u.query)
            if u.path=='/api/warm':
                job=prepare_catalog(q.get('genre',['Mixed'])[0],q.get('region',['Worldwide'])[0],q.get('difficulty',['Normal'])[0])
                return self.reply({'ready':job.done() and job.exception() is None})
            if u.path=='/api/genres': return self.reply(CATALOG_GENRES)
            if u.path=='/api/config': return self.reply(FILTER_OPTIONS)
            if u.path=='/api/invite':
                code=q.get('room',[''])[0].upper()
                with lock:
                    r=rooms.get(code)
                    if not r:return self.reply({'error':'This room could not be found. Ask for a new invite.'},404)
                    if not r.get('multi'):return self.reply({'error':'This is not a multiplayer room.'},400)
                    return self.reply({'room':code,'host':r['players'][r['host']]['name'],'mode':r['mode'],'genre':r['genre'],'region':r['region'],'difficulty':r['difficulty'],'rounds':r['rounds'],'players':len(r['players']),'joinable':r['phase']=='lobby' and len(r['players'])<8,'reason':'This game has already started.' if r['phase']!='lobby' else 'This room is full.' if len(r['players'])>=8 else ''})
            if u.path=='/api/search':
                with lock:
                    r=rooms[q.get('room',[''])[0]]
                    if q.get('token',[''])[0] not in r['players']: raise ValueError('Invalid session')
                    term=q.get('q',[''])[0][:100]
                    search_room={'pool':r['pool'],'song':r.get('song')} if r['phase']=='playing' and r['mode'] in ('guess','hits','race') else None
                    round_number=r['round']; stage=r['stage']
                rows=suggestions(search_room,term) if search_room else []
                # Search never waits for external contributor lookups.
                for track in rows:queue_credit(track)
                return self.reply({'round':round_number,'stage':stage,'results':[{k:t[k] for k in ['id','title','artist']} for t in rows]})
            if u.path=='/api/state':
                with lock:
                    r=rooms[q.get('room',[''])[0]]; p=q.get('token',[''])[0]
                    if p not in r['players']: raise ValueError('Invalid player session')
                    return self.reply(state(r,p))
            if u.path.startswith('/race-media/'):
                with lock:r=next((x for x in rooms.values() if x.get('audioKey')==u.path.split('/')[-1]),None);path=r.get('race_path') if r else None;typ=r.get('race_type') if r else None
                if not path:return self.reply({'error':'Media not ready'},404)
                b=pathlib.Path(path).read_bytes()
                self.send_response(200);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
            if u.path.startswith('/audio/'):
                key=u.path.split('/')[-1]
                with lock: r=next((r for r in rooms.values() if r.get('audioKey')==key),None); song=dict(r['song']) if r else None
                if not song: return self.reply({'error':'Audio expired'},404)
                b,typ=audio_cache.get(os.getenv('AUDIO_SOURCE','preview')+':'+song['id'],song)
                self.send_response(200); self.send_header('Content-Type',typ); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','private, max-age=300'); self.end_headers(); self.wfile.write(b); return
            if u.path.startswith('/spotify-audio/'):
                key=u.path.split('/')[-1]
                with lock: r=next((r for r in rooms.values() if r.get('audioKey')==key),None); ans=dict(r['song']) if r else None
                if not ans: return self.reply({'error':'Audio expired'},404)
                try:ans.update(spotify_enrich(ans.get('artist',''),ans.get('title','')))
                except Exception:pass
                preview_url=ans.get('spotify_preview','')
                if not preview_url: return self.reply({'error':'No Spotify preview for this track'},404)
                try:b,typ=spotify_cache.get('spotify:'+preview_url,{'spotify_preview':preview_url})
                except Exception as e: return self.reply({'error':str(e)},404)
                self.send_response(200); self.send_header('Content-Type',typ); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','private, max-age=300'); self.end_headers(); self.wfile.write(b); return
            path=ROOT/'static'/('index.html' if u.path=='/' else u.path.lstrip('/'))
            if not path.resolve().is_relative_to((ROOT/'static').resolve()) or not path.is_file(): return self.reply({'error':'Not found'},404)
            b=path.read_bytes(); self.send_response(200); self.send_header('Cache-Control','no-store'); self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'text/plain'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
        except Exception as e: self.reply({'error':str(e)},400)
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length',0))
            if n>4096: raise ValueError('Request too large')
            d=json.loads(self.rfile.read(n)); action=self.path.split('/')[-1]
            if action=='create':
                if d.get('mode')=='hits':d.update(genre='Mixed',region='Worldwide',difficulty='Hits')
                tracks=pool(d.get('genre','Mixed'),d.get('region','Worldwide'),d.get('difficulty','Normal'))
                with lock:
                    for c in list(rooms):
                        if time.time()-rooms[c]['created']>86400: del rooms[c]
                    if len(rooms)>100: raise ValueError('Server room limit reached')
                    code=secrets.token_hex(3).upper(); p=secrets.token_urlsafe(24)
                    r={'code':code,'hydrate':True,'created':time.time(),'players':{p:{'name':str(d.get('name','You'))[:24] or 'You','score':0}},'host':p,'pool':tracks,'used':[],'mode':d.get('mode') if d.get('mode') in ('choice','hits','race') else 'guess','multi':bool(d.get('multi')),'genre':d.get('genre','Mixed'),'region':d.get('region','Worldwide'),'difficulty':d.get('difficulty','Normal'),'phase':'lobby','round':0,'rounds':max(1,min(30,int(d.get('rounds',10)))),'stage':0,'deadline':0,'guesses':{},'history':[],
                       'previous_artists':[str(a) for a in d.get('previous_artists',[]) or []][:24],'previous_songs':[str(s) for s in d.get('previous_songs',[]) or []][:40]}
                    rooms[code]=r
                    if not r['multi']: advance(r)
                    return self.reply({'room':code,'token':p})
            with lock:
                r=rooms.get(str(d['room']).upper())
                if not r:raise ValueError('This room could not be found. Ask for a new invite.')
                if action=='join':
                    if r['phase']!='lobby' or len(r['players'])>=8: raise ValueError('Room started or full')
                    p=secrets.token_urlsafe(24); r['players'][p]={'name':str(d.get('name','Friend'))[:24] or 'Friend','score':0}; return self.reply({'room':r['code'],'token':p})
                p=d['token']
                if p not in r['players']: raise ValueError('Invalid player session')
                settle(r)
                if action in ('race-ready','race-retry','race-skip','race-audio'):
                    if r.get('mode')!='race' or r['phase']!='playing' or d.get('round')!=r['round']:raise ValueError('Round changed')
                    if action=='race-ready' and r.get('race_status') in ('ready','playing'):
                        r['race_ready'].add(p)
                        if not r.get('race_started') and r['race_ready']>=set(r['players'])-set(r['guesses']):
                            r['race_started']=time.time()+2;r['deadline']=r['race_started']+r['race_duration'];r['race_status']='playing'
                    elif action=='race-audio' and not r.get('race_started') and not r.get('race_audio_only'):
                        r['race_audio_only']=True;r['audioKey']=secrets.token_urlsafe(24);r['race_ready']=set();r.pop('race_path',None);queue_youtube(r)
                    elif action=='race-retry' and r.get('race_status')=='error':queue_youtube(r)
                    elif action=='race-skip':
                        r['guesses'][p]=''
                        if len(r['guesses'])==len(r['players']):r['phase']='reveal';r['winners']=[]
                        elif not r.get('race_started') and r.get('race_status')=='ready' and r['race_ready']>=set(r['players'])-set(r['guesses']):
                            r['race_started']=time.time()+2;r['deadline']=r['race_started']+r['race_duration'];r['race_status']='playing'
                    return self.reply(state(r,p))
                if action=='guess':
                    if r.get('mode')=='race' and (not r.get('race_started') or time.time()<r['race_started']):raise ValueError('Waiting for media playback')
                    if r['phase']!='playing' or p in r['guesses']: raise ValueError('Guess already locked')
                    if r.get('mode')=='race':
                        if d.get('round')!=r['round']: raise ValueError('Stage changed; try again')
                    elif d.get('round')!=r['round'] or d.get('stage')!=r['stage']: raise ValueError('Stage changed; try again')
                    guess=str(d.get('id',''))
                    if r.get('mode')=='race' and time.time()<r.get('race_cooldowns',{}).get(p,0):raise ValueError('Please wait for your guess cooldown')
                    allowed=r['options'] if r['mode']=='choice' else [t for t in r['pool'] if t.get('genre')==r['song'].get('genre') and t.get('language')==r['song'].get('language')]
                    if guess and guess not in {t['id'] for t in allowed}: raise ValueError('Choose an answer from this round')
                    if r.get('mode')=='race' and guess and guess!=r['song']['id']:
                        r.setdefault('race_cooldowns',{})[p]=time.time()+5
                        r.setdefault('race_wrong',{})[p]=True
                    else:
                        r['guesses'][p]=guess; r.setdefault('guess_times',{})[p]=time.time()-(r.get('race_started') or time.time()); settle(r)
                elif action=='lobby':
                    if p!=r['host'] or r['phase']!='finished':raise ValueError('Only the host can return a finished match to the lobby')
                    for player in r['players'].values():player['score']=0
                    # Remember this match's tail so the next match in the same
                    # room (or the same browser's next solo game) avoids
                    # immediate repeats when the pool is large enough.
                    tail=[t for t in r.get('pool',[]) if t['id'] in r.get('used',[])[-20:]]
                    r.update(phase='lobby',round=0,stage=0,guesses={},history=[],winners=[],
                             previous_artists=[artist_key(t) for t in tail],
                             previous_songs=[t['id'] for t in tail],
                             artist_counts={},country_counts={},recent_artists=[])
                elif action=='next':
                    if p!=r['host'] or r['phase'] not in ['lobby','reveal']: raise ValueError('Only host can continue')
                    if r['round']>=r['rounds']: r['phase']='finished'
                    else: advance(r)
                else: raise ValueError('Unknown action')
                return self.reply(state(r,p))
        except Exception as e: self.reply({'error':str(e)},400)
if __name__=='__main__': ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT',3000))),Handler).serve_forever()

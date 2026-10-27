from audio_cache import AudioCache
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
    return {'id':str(t['id']),'title':t['title'],'artist':', '.join(names),'preview':t.get('preview',''),'art':t.get('album',{}).get('cover_medium',''),'link':t.get('link','')}
def credit(t):
    if t.get('_credits'): return t
    try:
        detail=fetch('track/'+t['id'])
        t['artist']=clean(detail)['artist']; t['_credits']=True
    except (ValueError,KeyError): pass
    return t

def suggestions(r,term):
    term=norm(term)
    if len(term)<2:return []
    song=r['song']
    rows=[t for t in r['pool'] if t.get('genre')==song.get('genre') and t.get('language')==song.get('language')]
    scored=[]
    words=term.split()
    for t in rows:
        title=norm(t['title']); artist=norm(t['artist']); text=title+' '+artist
        score=3 if title==term or artist==term else 2 if all(w in text for w in words) else SequenceMatcher(None,term,title).ratio()
        if score>.55:scored.append((-score,title,artist,t))
    scored.sort(key=lambda x:x[:3])
    return [x[3] for x in scored[:25]]

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
    if genre not in CATALOG_GENRES or region not in REGIONS or difficulty not in DIFFICULTIES:
        raise ValueError('Invalid music filters')
    key=(genre,region,difficulty)
    with catalog_guard:
        job=catalog_jobs.get(key)
        if job and (not job.done() or (job.exception() is None and time.time()-catalog_started.get(key,0)<86400)):return job
        def build():
            path=DATA/('pool-full-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]+'.json')
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
def advance(r):
    r['song']=choose_song(r); r['used'].append(r['song']['id'])
    r['stage']=0; r['guesses']={}; r['history']=[]; r['round']+=1; r['phase']='playing'; r['deadline']=time.time()+45
    r['board'],r['options']=round_choices(r['song'],r['pool'])
    if r.get('hydrate',False):
        for track in r['options']:queue_credit(track)
    r['audioKey']=secrets.token_urlsafe(24)
    r['deadline']=time.time()+45
def settle(r):
    if r['phase']!='playing': return
    if len(r['guesses'])<len(r['players']) and time.time()<r['deadline']: return
    wins=[p for p,g in r['guesses'].items() if g==r['song']['id']]
    r['history'].append({'stage':r['stage'],'correct':len(wins)})
    if wins or r['stage']==4 or r['mode']=='choice':
        for p in wins: r['players'][p]['score']+= (5-r['stage']) if not r['multi'] and r['mode']=='guess' else 1
        r['phase']='reveal'; r['winners']=wins
    else:
        r['stage']+=1; r['guesses']={}; r['deadline']=time.time()+30

def state(r,p):
    settle(r)
    out={k:r[k] for k in ['code','mode','multi','phase','round','rounds','stage','deadline','genre','history']}
    out['players']=[dict(name=v['name'],score=v['score'],me=k==p,host=k==r['host'],submitted=k in r['guesses']) for k,v in r['players'].items()]
    if '_stats' not in r:r['_stats']={'tracks':len(r['pool']),'artists':len({artist_key(t) for t in r['pool']}),'countries':len({t.get('country','?') for t in r['pool']})}
    out['catalog']=r['_stats']
    out['region']=r.get('region','Worldwide'); out['difficulty']=r.get('difficulty','Normal')
    if r['phase'] in ['reveal','finished']:
        out['correct']=p in r.get('winners',[])
        out['result']='correct' if out['correct'] else 'incorrect' if r['guesses'].get(p) else 'skipped'
    out['host']=p==r['host']; out['submitted']=p in r['guesses']; out['serverTime']=time.time()
    if r['phase']!='lobby': out['audio']='/audio/'+r['audioKey']; out['seconds']=5 if r['mode']=='choice' else STEPS[r['stage']]
    if r['mode']=='choice' and r['phase']=='playing': out['options']=[{k:t[k] for k in ['id','title','artist']} for t in r['options']]
    if r['phase']=='reveal': out['answer']={k:v for k,v in r['song'].items() if k not in ['preview','_credits']}
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
            if u.path=='/api/search':
                with lock:
                    r=rooms[q.get('room',[''])[0]]
                    if q.get('token',[''])[0] not in r['players']: raise ValueError('Invalid session')
                    term=q.get('q',[''])[0][:100]
                    search_room={'pool':r['pool'],'song':r.get('song')} if r['phase']=='playing' and r['mode']=='guess' else None
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
            if u.path.startswith('/audio/'):
                key=u.path.split('/')[-1]
                with lock: r=next((r for r in rooms.values() if r.get('audioKey')==key),None); song=dict(r['song']) if r else None
                if not song: return self.reply({'error':'Audio expired'},404)
                b,typ=audio_cache.get(os.getenv('AUDIO_SOURCE','preview')+':'+song['id'],song)
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
                tracks=pool(d.get('genre','Mixed'),d.get('region','Worldwide'),d.get('difficulty','Normal'))
                with lock:
                    for c in list(rooms):
                        if time.time()-rooms[c]['created']>86400: del rooms[c]
                    if len(rooms)>100: raise ValueError('Server room limit reached')
                    code=secrets.token_hex(3).upper(); p=secrets.token_urlsafe(24)
                    r={'code':code,'hydrate':True,'created':time.time(),'players':{p:{'name':str(d.get('name','You'))[:24] or 'You','score':0}},'host':p,'pool':tracks,'used':[],'mode':'choice' if d.get('mode')=='choice' else 'guess','multi':bool(d.get('multi')),'genre':d.get('genre','Mixed'),'region':d.get('region','Worldwide'),'difficulty':d.get('difficulty','Normal'),'phase':'lobby','round':0,'rounds':max(1,min(30,int(d.get('rounds',10)))),'stage':0,'deadline':0,'guesses':{},'history':[]}
                    rooms[code]=r
                    if not r['multi']: advance(r)
                    return self.reply({'room':code,'token':p})
            with lock:
                r=rooms[str(d['room']).upper()]
                if action=='join':
                    if r['phase']!='lobby' or len(r['players'])>=8: raise ValueError('Room started or full')
                    p=secrets.token_urlsafe(24); r['players'][p]={'name':str(d.get('name','Friend'))[:24] or 'Friend','score':0}; return self.reply({'room':r['code'],'token':p})
                p=d['token']
                if p not in r['players']: raise ValueError('Invalid player session')
                settle(r)
                if action=='guess':
                    if r['phase']!='playing' or p in r['guesses']: raise ValueError('Guess already locked')
                    if d.get('round')!=r['round'] or d.get('stage')!=r['stage']: raise ValueError('Stage changed; try again')
                    guess=str(d.get('id',''))
                    allowed=r['options'] if r['mode']=='choice' else [t for t in r['pool'] if t.get('genre')==r['song'].get('genre') and t.get('language')==r['song'].get('language')]
                    if guess and guess not in {t['id'] for t in allowed}: raise ValueError('Choose an answer from this round')
                    r['guesses'][p]=guess; settle(r)
                elif action=='lobby':
                    if p!=r['host'] or r['phase']!='finished':raise ValueError('Only the host can return a finished match to the lobby')
                    for player in r['players'].values():player['score']=0
                    r.update(phase='lobby',round=0,stage=0,guesses={},history=[],winners=[],artist_counts={},country_counts={},recent_artists=[])
                elif action=='next':
                    if p!=r['host'] or r['phase'] not in ['lobby','reveal']: raise ValueError('Only host can continue')
                    if r['round']>=r['rounds']: r['phase']='finished'
                    else: advance(r)
                else: raise ValueError('Unknown action')
                return self.reply(state(r,p))
        except Exception as e: self.reply({'error':str(e)},400)
if __name__=='__main__': ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT',3000))),Handler).serve_forever()

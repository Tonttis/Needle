import json, os, secrets, time, random, threading, urllib.request, urllib.parse, subprocess, pathlib, mimetypes
from catalog import build_pool, round_choices, norm, REGIONS, DIFFICULTIES, GENRES as CATALOG_GENRES
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
ROOT=pathlib.Path(__file__).parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
STEPS=[.1,.5,2,8,15]
GENRES={'Mixed':0,'Pop':132,'Rock':152,'Metal':464,'Rap / Hip Hop':116,'Dance':113,'Electronic':106,'R&B':165,'Jazz':129,'Classical':98}
rooms={}; lock=threading.RLock(); cache={}
def fetch(path):
    if path in cache and time.time()-cache[path][0]<3600: return cache[path][1]
    try:
        with urllib.request.urlopen('https://api.deezer.com/'+path,timeout=15) as r: v=json.load(r)
    except Exception as e:
        raise ValueError('Music catalog could not be reached. Check server internet access and try again.') from e
    if 'error' in v: raise ValueError('Music provider unavailable. Try again shortly.')
    cache[path]=(time.time(),v); return v
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
    def relevance(t):
        title=norm(t['title']); artist=norm(t['artist']); text=title+' '+artist
        return (3 if title==term or artist==term else 2 if all(w in text for w in term.split()) else SequenceMatcher(None,term,title).ratio())
    rows=[t for t in rows if relevance(t)>.55]
    return sorted(rows,key=lambda t:(-relevance(t),norm(t['title']),norm(t['artist'])))[:25]

def pool(genre,region='Worldwide',difficulty='Normal'):
    if genre not in CATALOG_GENRES or region not in REGIONS or difficulty not in DIFFICULTIES:
        raise ValueError('Invalid music filters')
    return build_pool(fetch,clean,genre,region,difficulty)
def advance(r):
    candidates=[t for t in r['pool'] if t['id'] not in r['used']]
    if not candidates: r['used']=[]; candidates=r['pool'][:]
    r['song']=random.choice(candidates); r['used'].append(r['song']['id'])
    r['stage']=0; r['guesses']={}; r['history']=[]; r['round']+=1; r['phase']='playing'; r['deadline']=time.time()+45
    r['board'],r['options']=round_choices(r['song'],r['pool'])
    if r.get('hydrate',False):
        with ThreadPoolExecutor(max_workers=4) as workers: list(workers.map(credit,r['options']))
    r['audioKey']=secrets.token_urlsafe(24)
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
    out['region']=r.get('region','Worldwide'); out['difficulty']=r.get('difficulty','Normal')
    if r['phase'] in ['reveal','finished']:
        out['correct']=p in r.get('winners',[])
        out['result']='correct' if out['correct'] else 'incorrect' if r['guesses'].get(p) else 'skipped'
    out['host']=p==r['host']; out['submitted']=p in r['guesses']; out['serverTime']=time.time()
    if r['phase']!='lobby': out['audio']='/audio/'+r['audioKey']; out['seconds']=5 if r['mode']=='choice' else STEPS[r['stage']]
    if r['mode']=='choice' and r['phase']=='playing': out['options']=[{k:t[k] for k in ['id','title','artist']} for t in r['options']]
    if r['phase'] in ['reveal','finished']: out['answer']={k:v for k,v in r['song'].items() if k not in ['preview','_credits']}
    return out
class Handler(BaseHTTPRequestHandler):
    def reply(self,v,status=200):
        b=json.dumps(v).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        try:
            u=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(u.query)
            if u.path=='/api/genres': return self.reply(CATALOG_GENRES)
            if u.path=='/api/search':
                with lock:
                    r=rooms[q.get('room',[''])[0]]
                    if q.get('token',[''])[0] not in r['players']: raise ValueError('Invalid session')
                    term=q.get('q',[''])[0][:100]
                    rows=suggestions(r,term) if r['phase']=='playing' and r['mode']=='guess' else []
                    round_number=r['round']; stage=r['stage']
                with ThreadPoolExecutor(max_workers=4) as workers: rows=list(workers.map(credit,rows))
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
                if os.getenv('AUDIO_SOURCE','preview')=='youtube':
                    target=DATA/(song['id']+'.mp3')
                    with audio_lock:
                        if not target.exists():
                            subprocess.run(['yt-dlp','--no-playlist','--max-filesize','30M','--download-sections','*0-20','-x','--audio-format','mp3','-o',str(DATA/(song['id']+'.%(ext)s')),'ytsearch1:'+song['artist']+' '+song['title']+' official audio'],check=True,timeout=100,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    b=target.read_bytes(); typ='audio/mpeg'
                else:
                    with urllib.request.urlopen(song['preview'],timeout=20) as a: b=a.read(5_000_000); typ=a.headers.get('Content-Type','audio/mpeg')
                self.send_response(200); self.send_header('Content-Type',typ); self.send_header('Cache-Control','private, max-age=300'); self.end_headers(); self.wfile.write(b); return
            path=ROOT/'static'/('index.html' if u.path=='/' else u.path.lstrip('/'))
            if not path.resolve().is_relative_to((ROOT/'static').resolve()) or not path.is_file(): return self.reply({'error':'Not found'},404)
            b=path.read_bytes(); self.send_response(200); self.send_header('Cache-Control','no-store'); self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'text/plain'); self.end_headers(); self.wfile.write(b)
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
                elif action=='next':
                    if p!=r['host'] or r['phase'] not in ['lobby','reveal']: raise ValueError('Only host can continue')
                    if r['round']>=r['rounds']: r['phase']='finished'
                    else: advance(r)
                else: raise ValueError('Unknown action')
                return self.reply(state(r,p))
        except Exception as e: self.reply({'error':str(e)},400)
audio_lock=threading.Lock()
if __name__=='__main__': ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT',3000))),Handler).serve_forever()

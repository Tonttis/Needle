import math
import unicodedata
import logging
import leaderboard as boards
import spotify_lookup
from race_media import prepare as prepare_race_media, start_janitor
from playlists import match_playlist, identify as identify_playlist
from audio_cache import AudioCache
from recognition import VERSION as CATALOG_VERSION, in_difficulty
from catalog import filter_options
import hashlib
import copy
import sqlite3
import json, os, secrets, time, random, threading, urllib.request, urllib.parse, subprocess, pathlib, mimetypes
from catalog import choose_song, artist_key, build_pool, round_choices, norm, song_history_keys, REGIONS, DIFFICULTIES, GENRES as CATALOG_GENRES
from difflib import SequenceMatcher
from concurrent.futures import Future,ThreadPoolExecutor,as_completed
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
    return {'id':str(t['id']),'album_id':str(t.get('album',{}).get('id','')),'album_release_date':str(t.get('album',{}).get('release_date','')),'title':t['title'],'artist':artist,'preview':t.get('preview',''),'art':t.get('album',{}).get('cover_medium',''),'link':t.get('link',''),
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
catalog_status={};catalog_tokens={}
catalog_started={}
catalog_accessed={}
CATALOG_ROTATE_SECONDS=6*60*60
CATALOG_CHECK_SECONDS=15*60
CATALOG_BOOTSTRAP=(('Mixed','Europe','Easy','All'),('Mixed','Worldwide','Easy','All'),('Mixed','Worldwide','Hits','All'))
catalog_guard=threading.Lock()
credit_pending=set()
def queue_credit(t):
    if t.get('_credits') or t['id'] in credit_pending or len(credit_pending)>=48:return
    credit_pending.add(t['id'])
    def run():
        try:credit(t)
        finally:credit_pending.discard(t['id'])
    credit_workers.submit(run)
DECADES=['All','1980s','1990s','2000s','2010s','2020s']
def filter_decade(rows,decade,progress=None):
    start=int(decade[:4]);ids={str(t.get('album_id')) for t in rows if t.get('album_id')}
    def year_of(value):
        try:
            year=int(str(value)[:4]);return year if 1800<=year<=2200 else None
        except (ValueError,TypeError):return None
    years={}
    for t in rows:
        album_id=str(t.get('album_id',''));year=year_of(t.get('album_release_date'))
        if album_id in ids and year is not None:years[album_id]=year
    if progress:progress('dates',len(years),len(ids))
    # Artist album lists carry the same album release dates as individual album
    # details. Only accept exact album ID matches; compilations, incomplete
    # pages, errors and missing dates are resolved individually below.
    groups={}
    for t in rows:
        artist=str(t.get('artist_id',''));album_id=str(t.get('album_id',''))
        if artist and album_id in ids and album_id not in years:groups.setdefault(artist,set()).add(album_id)
    def artist_albums(item):
        artist,wanted=item;found={};offset=0
        try:
            while wanted-set(found) and offset<200:
                data=fetch('artist/'+artist+'/albums?limit=100&index='+str(offset)).get('data',[])
                if not isinstance(data,list):break
                for album in data:
                    album_id=str(album.get('id',''));year=year_of(album.get('release_date'))
                    if album_id in wanted and year is not None:found[album_id]=year
                if len(data)<100:break
                offset+=100
        except (ValueError,KeyError,TypeError):pass
        return found
    useful=[(artist,album_ids) for artist,album_ids in groups.items() if len(album_ids)>=4]
    if useful:
        with ThreadPoolExecutor(max_workers=6) as workers:
            futures=[workers.submit(artist_albums,item) for item in useful]
            for future in as_completed(futures):
                years.update(future.result())
                if progress:progress('dates',len(years),len(ids))
    def lookup(album_id):
        try:return album_id,year_of(fetch('album/'+album_id).get('release_date'))
        except (ValueError,KeyError,TypeError):return album_id,None
    missing=ids-set(years)
    with ThreadPoolExecutor(max_workers=6) as workers:
        futures=[workers.submit(lookup,album_id) for album_id in missing]
        for future in as_completed(futures):
            album_id,year=future.result();years[album_id]=year
            if progress:progress('dates',len(years),len(ids))
    result=[dict(t,release_year=years[str(t['album_id'])]) for t in rows if str(t.get('album_id','')) in years and years[str(t['album_id'])] is not None and start<=years[str(t['album_id'])]<start+10]
    counts={}
    for track in result:
        language=track.get('language','');counts[language]=counts.get(language,0)+1
    result=[track for track in result if counts[track.get('language','')]>=4]
    if len(result)<4:raise ValueError('Not enough dated tracks for this decade and mix. Try a broader selection.')
    return result
def prepare_catalog(genre,region,difficulty,decade='All'):
    if difficulty=='Normal':difficulty='Medium'
    if genre not in CATALOG_GENRES or region not in REGIONS or difficulty not in DIFFICULTIES+['Hits']:
        raise ValueError('Invalid music filters')
    if decade not in DECADES:raise ValueError('Invalid decade')
    key=(genre,region,difficulty,decade)
    with catalog_guard:
        catalog_accessed[key]=time.time()
        job=catalog_jobs.get(key)
        # Keep serving the last successful generation while a replacement is
        # built. The scheduler swaps it atomically after successful preparation.
        if job and (not job.done() or job.exception() is None):return job
        catalog_status[key]={'phase':'starting','completed':0,'total':None}
        def progress(phase,completed,total):
            with catalog_guard:catalog_status[key]={'phase':phase,'completed':completed,'total':total}
        def build():
            path=DATA/('pool-v9-'+CATALOG_VERSION+'-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]+'.json')
            if path.exists() and time.time()-path.stat().st_mtime<86400:
                try:return json.loads(path.read_text())
                except (ValueError,OSError):pass
            rows=None
            # Reuse a finished unfiltered pool across decade choices; never
            # wait on another job here, avoiding worker-pool deadlocks.
            if decade!='All':
                base_key=(genre,region,difficulty,'All')
                with catalog_guard:base_job=catalog_jobs.get(base_key);base_started=catalog_started.get(base_key,0)
                if base_job and time.time()-base_started<86400 and base_job.done() and base_job.exception() is None:rows=copy.deepcopy(base_job.result())
                if rows is None:
                    base_path=DATA/('pool-v9-'+CATALOG_VERSION+'-'+hashlib.sha256('|'.join(base_key).encode()).hexdigest()[:20]+'.json')
                    if base_path.exists() and time.time()-base_path.stat().st_mtime<86400:
                        try:rows=json.loads(base_path.read_text())
                        except (ValueError,OSError):pass
            if rows is None:rows=build_pool(fetch,clean,genre,region,difficulty,progress=progress)
            if decade!='All':
                rows=filter_decade(rows,decade,progress=progress)
                playable=[t for t in rows if in_difficulty(t,difficulty)]
                if len({artist_key(t) for t in playable})<4:raise ValueError('Not enough artists with dated tracks for this difficulty and decade. Try a broader selection.')

            tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(rows));tmp.replace(path)
            return rows
        job=catalog_workers.submit(build);catalog_jobs[key]=job;catalog_started[key]=time.time();return job
def catalog_cache_path(key):
    return DATA/('pool-v9-'+CATALOG_VERSION+'-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]+'.json')

def discard_saved_mixes():
    # The metadata, profiles, scores, daily snapshots and media are separate.
    # Only remove mix files from previous processes, never user data.
    import re
    pattern=re.compile(r'^pool-(?:full-[0-9a-f]{20}|v[0-9]+-.+-[0-9a-f]{20})(?:\.(?:json|tmp)|\.json\.[0-9a-f]{12}\.tmp)$')
    removed=0
    for path in DATA.glob('pool-*'):
        if path.is_file() and pattern.fullmatch(path.name):
            path.unlink(missing_ok=True);removed+=1
    return removed

def refresh_catalog(key):
    """Build a fresh generation; keep old usable until a full replacement exists."""
    with catalog_guard:
        old=catalog_jobs.get(key)
        if old is None or not old.done() or old.exception() is not None:return False
    genre,region,difficulty,decade=key
    rows=build_pool(fetch,clean,genre,region,difficulty)
    if decade!='All':
        rows=filter_decade(rows,decade)
        if len({artist_key(t) for t in rows if in_difficulty(t,difficulty)})<4:
            raise ValueError('Not enough artists with dated tracks for this refreshed mix.')
    path=catalog_cache_path(key)
    tmp=path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
    try:
        tmp.write_text(json.dumps(rows))
        ready=Future();ready.set_result(rows)
        with catalog_guard:
            # Do not replace a newer foreground generation or a running job.
            if catalog_jobs.get(key) is not old:return False
            tmp.replace(path)
            catalog_jobs[key]=ready;catalog_started[key]=time.time()
            catalog_status[key]={'phase':'ready','completed':0,'total':None}
        return True
    finally:tmp.unlink(missing_ok=True)

def catalog_rotation_loop(stop_event=None):
    """Warm popular mixes serially, then refresh active mixes in the background."""
    stop_event=stop_event or threading.Event()
    for key in CATALOG_BOOTSTRAP:
        if stop_event.is_set():return
        try:prepare_catalog(*key).result()
        except Exception as exc:logging.warning('Catalog warm-up failed for %s: %s',key,exc)  # Other mixes must still warm.
    while not stop_event.wait(CATALOG_CHECK_SECONDS):
        now=time.time()
        with catalog_guard:
            # Quiet, unused mixes are discarded rather than refreshed forever.
            stale=[key for key,job in catalog_jobs.items() if key not in CATALOG_BOOTSTRAP
                   and job.done() and now-catalog_accessed.get(key,0)>=86400]
            for key in stale:
                try:catalog_cache_path(key).unlink(missing_ok=True)
                except OSError:pass
                catalog_jobs.pop(key,None);catalog_started.pop(key,None)
                catalog_status.pop(key,None);catalog_accessed.pop(key,None)
                for token in [t for t,k in catalog_tokens.items() if k==key]:catalog_tokens.pop(token,None)
            due=[(catalog_started.get(key,0),key) for key,job in catalog_jobs.items()
                 if job.done() and job.exception() is None
                 and now-catalog_started.get(key,0)>=CATALOG_ROTATE_SECONDS
                 and (key in CATALOG_BOOTSTRAP or now-catalog_accessed.get(key,0)<86400)]
        for _,key in sorted(due):
            if stop_event.is_set():return
            try:refresh_catalog(key)
            except Exception as exc:logging.warning('Catalog refresh failed for %s: %s',key,exc)  # Retain the working generation.

def start_catalog_rotation():
    discard_saved_mixes()
    thread=threading.Thread(target=catalog_rotation_loop,name='catalog-rotation',daemon=True)
    thread.start();return thread

def pool(genre,region='Worldwide',difficulty='Normal',decade='All'):
    try:return copy.deepcopy(prepare_catalog(genre,region,difficulty,decade).result(timeout=20))
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

playlist_workers=ThreadPoolExecutor(max_workers=2)
playlist_jobs={};playlist_started={};playlist_status={};playlist_tokens={};playlist_guard=threading.Lock()
def prepare_playlist(url,decade='All'):
    identify_playlist(url)
    if decade not in DECADES:raise ValueError('Invalid decade')
    key=(url,decade)
    with playlist_guard:
        job=playlist_jobs.get(key)
        if not job or (job.done() and (job.exception() is not None or time.time()-playlist_started.get(key,0)>900)):
            token=secrets.token_urlsafe(24)
            playlist_tokens[token]=key;playlist_status[key]={'phase':'reading','completed':0,'total':None}
            def progress(phase,completed,total):
                with playlist_guard:playlist_status[key]={'phase':phase,'completed':completed,'total':total}
            def build():
                tracks,report=match_playlist(url,fetch,clean,progress=progress)
                if decade!='All':
                    progress('filtering',0,None);tracks=filter_decade(tracks,decade);report=dict(report,matched=len(tracks),decade=decade)
                if len(tracks)<4:raise ValueError('Not enough playable tracks remain in this playlist.')
                return tracks,report
            job=playlist_workers.submit(build);playlist_jobs[key]=job;playlist_started[key]=time.time()
        else:
            token=next(t for t,k in playlist_tokens.items() if k==key)
        return token,job

def playlist_pool(url,decade='All'):
    _,job=prepare_playlist(url,decade)
    try:return copy.deepcopy(job.result(timeout=120))
    except TimeoutError:raise ValueError('Playlist preparation is taking longer than expected. Please retry shortly.')

def choose_round(r):
    if r.get('game_mode')=='party':
        choices=r['party_modes'];cycle=r.setdefault('party_cycle',[])
        if not cycle:
            cycle[:]=choices[:];random.shuffle(cycle)
            if len(cycle)>1 and cycle[-1]==r.get('previous_mode'):cycle[0],cycle[-1]=cycle[-1],cycle[0]
        r['mode']=cycle.pop();r['previous_mode']=r['mode'];r['difficulty']='Hits' if r['mode']=='hits' else r['base_difficulty']
    return choose_song(r)

_SELECTION_KEYS=('used','artist_counts','country_counts','language_counts','recent_artists','party_cycle','mode','difficulty','previous_mode')
def reserve_next_round(r):
    if r.get('game_mode',r.get('mode')) not in ('race','party') or r['round']>=r.get('rounds',1):return
    shadow=dict(r)
    for key in _SELECTION_KEYS:
        if key in shadow:shadow[key]=copy.deepcopy(shadow[key])
    try:
        song=choose_round(shadow)
    except (ValueError,KeyError):return
    pending={'song':song,'selection':{key:shadow[key] for key in _SELECTION_KEYS if key in shadow},'future':None}
    r['_next_round']=pending
    if shadow['mode']=='race':pending['future']=queue_prefetch(dict(song))

def advance(r):
    names=[player.get('name','') for player in r.get('players',{}).values()]
    prior_seen=r.get('_played_song_ids',set())
    r['_played_song_ids']=boards.played_song_ids(names)
    pending=r.pop('_next_round',None)
    # Another concurrent game may have played the reserved track since it was
    # selected. Re-select rather than use an outdated prefetch decision.
    if pending and song_history_keys(pending['song']) & (r['_played_song_ids']-prior_seen):pending=None
    if r.get('daily_ids'):
        r['song']=next(t for t in r['pool'] if t['id']==r['daily_ids'][r['round']]);r['_current_prefetch']=None
    elif pending:
        r.update(pending['selection']);r['song']=pending['song'];r['_current_prefetch']=pending.get('future')
    else:
        r['song']=choose_round(r);r['_current_prefetch']=None
    r['score_max']=r.get('score_max',0)+(20 if r['mode']=='race' else 1 if r['mode']=='choice' or r.get('multi') else 5)
    r['used'].append(r['song']['id'])
    r['stage']=0; r['guesses']={}; r['history']=[]; r['round']+=1; r['phase']='playing'; r['deadline']=time.time()+45
    r['round_started']=time.time();r['recap_recorded']=False
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
    if r.get('mode')!='race':
        keys=song_history_keys(r['song']);identity=next((k for k in keys if k.startswith('song:')),None)
        boards.record_played(names,r['song']['id'],identity);r['_played_song_ids'].update(keys)
    reserve_next_round(r)
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
    if r['phase']=='finished' and r.get('match_id'):boards.record_match(r)
    if r['phase']=='reveal' and not r.get('recap_recorded'):
        track=r['song'];winners=r.get('winners',[])
        r.setdefault('recap',[]).append(dict(round=r['round'],mode=r['mode'],title=track['title'],artist=track['artist'],art=track.get('art',''),link=track.get('link',''),spotify_url=track.get('spotify_url',''),winners=[dict(name=r['players'][w]['name'],seconds=round(r.get('guess_times',{}).get(w,0),1)) for w in winners if w in r['players']]))
        r['recap_recorded']=True
    out={k:r[k] for k in ['code','mode','multi','phase','round','rounds','stage','deadline','genre','history']}
    # History carries answer ids + artists so the client can de-prioritise
    # repeats in the next game; stage/correct kept for the timeline.
    out['history']=[dict(stage=h.get('stage',0),correct=h.get('correct',0),artist=h.get('artist'),song=h.get('answer')) for h in r.get('history',[])]
    out['players']=[dict(name=v['name'],score=v['score'],me=k==p,host=k==r['host'],submitted=k in r['guesses']) for k,v in r['players'].items()]
    if '_stats' not in r:
        playable=[t for t in r['pool'] if 'recognition' not in t or in_difficulty(t,r.get('difficulty','Medium'))]
        r['_stats']={'tracks':len(r['pool']),'answers':len(playable),'artists':len({artist_key(t) for t in playable}),'countries':len({t.get('country','?') for t in playable})}
    out['catalog']=r['_stats']
    if r['phase']=='finished':out['recap']=r.get('recap',[])
    out['daily_date']=r.get('daily_date');out['score_max']=r.get('score_max',0);out['playlist_url']=r.get('playlist_url','') if p==r['host'] and r['phase']=='lobby' else '';out['base_difficulty']=r.get('base_difficulty',r.get('difficulty','Normal'));out['playlist_report']=r.get('playlist_report');out['game_mode']=r.get('game_mode',r['mode']);out['party_modes']=r.get('party_modes',[]);out['decade']=r.get('decade','All');out['region']=r.get('region','Worldwide'); out['difficulty']=r.get('difficulty','Normal')
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
        # Resolve Spotify in the background; gameplay and reveal never wait.
        ans.update(r.get('reveal_metadata',{}))
        if not r.get('reveal_pending') and not r.get('reveal_done'):
            r['reveal_pending']=True
            key=r['audioKey'];artist=r['song'].get('seed_artist') or ans['artist'].split(',')[0].strip();title=ans['title']
            known_id=str(r['song'].get('spotify_id',''))
            def enrich():
                try:
                    if __import__('re').fullmatch(r'[A-Za-z0-9]{22}',known_id):metadata={'spotify_id':known_id,'spotify_url':'https://open.spotify.com/track/'+known_id}
                    else:metadata=spotify_lookup.resolve(artist,title)
                except Exception as exc:metadata={'spotify_error':str(exc)}
                with lock:
                    if r.get('audioKey')==key:r.update(reveal_metadata=metadata,reveal_done=True)
            credit_workers.submit(enrich)
        ans['preview_pending']=bool(r.get('reveal_pending') and not r.get('reveal_done'))
        out['answer']=ans
    return out

download_locks={}
download_guard=threading.Lock()
def download_lock(track_id):
    with download_guard:return download_locks.setdefault(track_id,threading.Lock())
def load_deezer_preview(song):
    try:
        return read_preview(song.get('preview',''))
    except Exception:
        # Expired URLs are refreshed for this exact track.
        try:
            detail=fetch('track/'+song['id'],fresh=True)
            return read_preview(detail.get('preview',''))
        except Exception as error:
            raise ValueError('This track preview is unavailable from the music provider. Retry playback or skip this track.') from error

def load_audio(song):
    if os.getenv('AUDIO_SOURCE','preview')!='youtube':return load_deezer_preview(song)
    target=DATA/(song['id']+'.mp3')
    with download_lock(song['id']):
        if not target.exists():
            subprocess.run(['yt-dlp','--no-playlist','--max-filesize','30M','--download-sections','*0-20','-x','--audio-format','mp3','-o',str(DATA/(song['id']+'.%(ext)s')),'ytsearch1:'+song['artist']+' '+song['title']+' official audio'],check=True,timeout=100,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return target.read_bytes(),'audio/mpeg'

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
deezer_reveal_cache=AudioCache(load_deezer_preview)
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

prefetch_workers=ThreadPoolExecutor(max_workers=2)
def active_race_media():
    with lock:
        paths=[]
        for room in rooms.values():
            if room.get('phase') in ('playing','reveal'):
                paths.append(room.get('race_path'))
                future=(room.get('_next_round') or {}).get('future')
                if future and future.done() and not future.cancelled():
                    try:paths.append(future.result()[2])
                    except Exception:pass
        return paths

def fetch_race_media(song,audio_only=False):
    vid,title=(song.get('youtube_id'),song['title']) if song.get('youtube_id') else resolve_youtube(song['artist'],song['title'])
    if not vid:raise ValueError('No playable video found. Retry or skip this song.')
    path,duration,typ=prepare_race_media(DATA,vid,audio_only=audio_only,protected=active_race_media)
    return vid,title,path,duration,typ

def queue_prefetch(song):
    return prefetch_workers.submit(fetch_race_media,song)

def queue_youtube(r):
    song=dict(r['song']);code=r['code'];key=r['audioKey'];audio_only=r.get('race_audio_only',False);future=r.get('_current_prefetch')
    r['race_status']='buffering';r['race_error']=None
    def run():
        try:
            if future and not audio_only:
                try:vid,title,path,duration,typ=future.result(timeout=200)
                except Exception:vid,title,path,duration,typ=fetch_race_media(song,audio_only)
            else:vid,title,path,duration,typ=fetch_race_media(song,audio_only)
            if not pathlib.Path(path).is_file():vid,title,path,duration,typ=fetch_race_media(song,audio_only)
            result=dict(race_path=path,race_duration=duration,race_type=typ,race_status='ready',videoId=vid,videoTitle=title)
        except Exception as e:result=dict(race_status='error',race_error=str(e))
        with lock:
            cur=rooms.get(code)
            if cur and cur.get('audioKey')==key:cur.update(result)
    video_workers.submit(run)
start_janitor(DATA,active_race_media)
FILTER_OPTIONS=filter_options()
def require_player_name(value):
    if not isinstance(value,str):raise ValueError('Enter your name (up to 24 characters).')
    name=value.strip()
    if not name or len(name)>24 or not any(not ch.isspace() and not unicodedata.category(ch).startswith('C') for ch in name):
        raise ValueError('Enter your name (up to 24 characters).')
    return name

class Handler(BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def setup(self):
        super().setup(); self.connection.settimeout(30)
    def reply(self,v,status=200):
        b=json.dumps(v).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        try:
            u=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(u.query)
            if u.path=='/api/leaderboard':
                mode=q.get('mode',['guess'])[0];difficulty=q.get('difficulty',['Easy'])[0];multi=q.get('multi',['0'])[0]=='1';daily=q.get('daily',[''])[0]
                if mode not in ('guess','choice','race','hits','party') or difficulty not in DIFFICULTIES+['Hits','Playlist','Normal']:raise ValueError('Invalid leaderboard filter')
                if daily and (len(daily)!=10 or not all(c.isdigit() or c=='-' for c in daily)):raise ValueError('Invalid date')
                return self.reply({'entries':boards.leaderboard(mode,difficulty,multi,daily or None),'date':daily or None})
            if u.path=='/api/daily':return self.reply({'date':boards.day_utc(),'rounds':5,'mode':'guess','difficulty':'Easy','region':'Europe','ready':boards.daily_existing(boards.day_utc()) is not None})
            if u.path=='/api/profile':return self.reply(boards.profile(q.get('name',[''])[0][:24]))
            if u.path=='/api/warm':
                job=prepare_catalog(q.get('genre',['Mixed'])[0],q.get('region',['Worldwide'])[0],q.get('difficulty',['Normal'])[0],q.get('decade',['All'])[0])
                return self.reply({'ready':job.done() and job.exception() is None})
            if u.path=='/api/catalog-status':
                token=q.get('job',[''])[0]
                with catalog_guard:
                    key=catalog_tokens.get(token);job=catalog_jobs.get(key) if key else None
                    if not job:return self.reply({'error':'Preparation expired. Please start again.'},404)
                    status=dict(catalog_status.get(key,{'phase':'starting'}));done=job.done()
                if done:
                    error=job.exception()
                    if error:return self.reply({'phase':'error','error':str(error)})
                    status.update(phase='ready')
                return self.reply(status)
            if u.path=='/api/playlist-status':
                token=q.get('job',[''])[0]
                with playlist_guard:
                    key=playlist_tokens.get(token);job=playlist_jobs.get(key) if key else None
                    if not job:return self.reply({'error':'Import expired. Please start again.'},404)
                    status=dict(playlist_status[key]);done=job.done()
                if done:
                    error=job.exception()
                    if error:return self.reply({'phase':'error','error':str(error)})
                    report=job.result()[1];status.update(phase='ready',matched=report['matched'],total=report['total'])
                return self.reply(status)
            if u.path=='/api/genres': return self.reply(CATALOG_GENRES)
            if u.path=='/api/config': return self.reply(FILTER_OPTIONS)
            if u.path=='/api/invite':
                code=q.get('room',[''])[0].upper()
                with lock:
                    r=rooms.get(code)
                    if not r:return self.reply({'error':'This room could not be found. Ask for a new invite.'},404)
                    if not r.get('multi'):return self.reply({'error':'This is not a multiplayer room.'},400)
                    return self.reply({'room':code,'host':r['players'][r['host']]['name'],'mode':r.get('game_mode',r['mode']),'genre':r['genre'],'region':r['region'],'difficulty':r['difficulty'],'decade':r.get('decade','All'),'rounds':r['rounds'],'players':len(r['players']),'joinable':r['phase']=='lobby' and len(r['players'])<8,'reason':'This game has already started.' if r['phase']!='lobby' else 'This room is full.' if len(r['players'])>=8 else ''})
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
            if u.path.startswith('/reveal-audio/'):
                key=u.path.split('/')[-1]
                with lock:
                    r=next((r for r in rooms.values() if r.get('audioKey')==key and r.get('phase')=='reveal'),None)
                    song=dict(r['song']) if r else None
                if not song:return self.reply({'error':'Reveal audio unavailable or expired'},404)
                source=os.getenv('AUDIO_SOURCE','preview')
                cache=deezer_reveal_cache if source=='youtube' else audio_cache
                cache_key=('deezer' if source=='youtube' else source)+':'+song['id']
                b,typ=cache.get(cache_key,song)
                self.send_response(200);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','private, max-age=300');self.end_headers();self.wfile.write(b);return
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
            if action=='clear-history':
                name=str(d.get('name','')).strip()
                if not name or len(name)>24:raise ValueError('Enter a valid name (up to 24 characters).')
                # Names have no authentication. This action affects only history,
                # and the UI explicitly confirms the scope before sending it.
                with lock:
                    count=boards.clear_played(name)
                    for room in rooms.values():
                        if any(boards.profile_key(p.get('name',''))==boards.profile_key(name) for p in room.get('players',{}).values()):
                            # Existing games retain their within-game no-repeat
                            # state. Reset the legacy match tail on rematch.
                            room['_history_cleared']=True
                            if room.get('phase')=='lobby':
                                room['previous_artists']=[];room['previous_songs']=[];room['_next_round']=None
                return self.reply({'cleared':count})
            if action=='catalog-prepare':
                genre=d.get('genre','Mixed');region=d.get('region','Worldwide');difficulty=d.get('difficulty','Normal');decade=d.get('decade','All')
                job=prepare_catalog(genre,region,difficulty,decade)
                key=(genre,region,'Medium' if difficulty=='Normal' else difficulty,decade)
                with catalog_guard:
                    token=next((t for t,k in catalog_tokens.items() if k==key),None)
                    if not token:token=secrets.token_urlsafe(24);catalog_tokens[token]=key
                return self.reply({'job':token})
            if action=='playlist-prepare':
                token,_=prepare_playlist(str(d.get('url','')).strip());return self.reply({'job':token})
            if action=='daily-create':
                name=require_player_name(d.get('name'))
                day=boards.day_utc();snapshot=boards.daily_existing(day)
                if snapshot is None:snapshot=boards.daily_snapshot(day,pool('Mixed','Europe','Easy'))
                tracks,ids=snapshot
                with lock:
                    code=secrets.token_hex(3).upper();p=secrets.token_urlsafe(24)
                    r={'code':code,'match_id':secrets.token_urlsafe(24),'score_max':0,'daily_date':day,'daily_ids':ids,'hydrate':True,'created':time.time(),'players':{p:{'name':name,'score':0}},'host':p,'pool':tracks,'used':[],'mode':'guess','game_mode':'guess','party_modes':[],'base_difficulty':'Easy','multi':False,'genre':'Mixed','region':'Europe','difficulty':'Easy','decade':'All','phase':'lobby','round':0,'rounds':5,'stage':0,'deadline':0,'guesses':{},'history':[]}
                    rooms[code]=r;advance(r);return self.reply({'room':code,'token':p})
            if action=='create':
                name=require_player_name(d.get('name'))
                if d.get('mode')=='hits':d.update(genre='Mixed',region='Worldwide',difficulty='Hits')
                playlist_url=str(d.get('playlist_url','')).strip()
                playlist_report=None
                if playlist_url:
                    tracks,playlist_report=playlist_pool(playlist_url,'All')
                    d['decade']='All'
                    d.update(genre='Playlist',region='Playlist',difficulty='Playlist')
                elif d.get('decade','All')=='All':tracks=pool(d.get('genre','Mixed'),d.get('region','Worldwide'),d.get('difficulty','Normal'))
                else:tracks=pool(d.get('genre','Mixed'),d.get('region','Worldwide'),d.get('difficulty','Normal'),d['decade'])
                if playlist_url and d.get('mode')=='hits' and len([t for t in tracks if t.get('hot_hit')])<4:raise ValueError('This playlist has too few Hottest Hits. Choose another mode.')
                party_modes=d.get('party_modes',['guess','choice','race','hits']) if d.get('mode')=='party' else []
                if not isinstance(party_modes,list) or any(m not in ('guess','choice','race','hits') for m in party_modes) or (d.get('mode')=='party' and not party_modes):raise ValueError('Choose at least one Party mode.')
                party_modes=list(dict.fromkeys(party_modes))
                if 'hits' in party_modes and len({artist_key(t) for t in tracks if t.get('hot_hit')})<4:raise ValueError('Not enough Hottest Hits in this mix for Party mode. Broaden the mix or deselect that mode.')
                with lock:
                    for c in list(rooms):
                        if time.time()-rooms[c]['created']>86400: del rooms[c]
                    if len(rooms)>100: raise ValueError('Server room limit reached')
                    code=secrets.token_hex(3).upper(); p=secrets.token_urlsafe(24)
                    r={'code':code,'match_id':secrets.token_urlsafe(24),'score_max':0,'hydrate':True,'created':time.time(),'players':{p:{'name':name,'score':0}},'host':p,'pool':tracks,'used':[],'mode':d.get('mode') if d.get('mode') in ('choice','hits','race','party') else 'guess','game_mode':'party' if d.get('mode')=='party' else d.get('mode','guess'),'party_modes':party_modes,'playlist_report':playlist_report,'playlist_url':playlist_url,'base_difficulty':d.get('difficulty','Normal'),'multi':bool(d.get('multi')),'genre':d.get('genre','Mixed'),'region':d.get('region','Worldwide'),'difficulty':d.get('difficulty','Normal'),'decade':d.get('decade','All'),'phase':'lobby','round':0,'rounds':max(1,min(30,int(d.get('rounds',10)))),'stage':0,'deadline':0,'guesses':{},'history':[],
                       'previous_artists':[],'previous_songs':[]}
                    rooms[code]=r
                    if not r['multi']: advance(r)
                    return self.reply({'room':code,'token':p})
            if action=='settings':
                # Perform provider work outside the global room lock, and validate again
                # before applying: a host may have started or left while loading.
                code=str(d.get('room','')).upper(); token=d.get('token')
                with lock:
                    room=rooms.get(code)
                    if not room or token!=room['host'] or room['phase']!='lobby':raise ValueError('Only the host can edit a lobby')
                mode=d.get('mode'); party_modes=d.get('party_modes',[])
                if mode not in ('guess','choice','race','hits','party'):raise ValueError('Invalid game mode')
                if not isinstance(party_modes,list) or any(m not in ('guess','choice','race','hits') for m in party_modes) or (mode=='party' and not party_modes):raise ValueError('Choose at least one Party mode.')
                party_modes=list(dict.fromkeys(party_modes)) if mode=='party' else []
                url=str(d.get('playlist_url','')).strip(); decade=d.get('decade','All')
                genre=d.get('genre','Mixed');region=d.get('region','Worldwide');difficulty=d.get('difficulty','Easy')
                report=None
                if url:
                    tracks,report=playlist_pool(url,'All');genre=region=difficulty='Playlist';decade='All'
                else:
                    if mode=='hits':genre,region,difficulty='Mixed','Worldwide','Hits'
                    tracks=pool(genre,region,difficulty,decade)
                if (mode=='hits' or 'hits' in party_modes) and len({artist_key(t) for t in tracks if t.get('hot_hit')})<4:raise ValueError('Not enough Hottest Hits in this mix. Choose another mode or broaden the mix.')
                rounds=max(1,min(30,int(d.get('rounds',10))))
                with lock:
                    r=rooms.get(code)
                    if r is not room or token!=r['host'] or r['phase']!='lobby':raise ValueError('Lobby changed while preparing settings')
                    r.update(pool=tracks,mode=mode,game_mode=mode,party_modes=party_modes,party_cycle=[],playlist_url=url,playlist_report=report,genre=genre,region=region,difficulty=difficulty,base_difficulty=difficulty,decade=decade,rounds=rounds,used=[],artist_counts={},country_counts={},language_counts={},recent_artists=[],_next_round=None)
                    r.pop('_stats',None)
                    return self.reply(state(r,token))
            with lock:
                r=rooms.get(str(d['room']).upper())
                if not r:raise ValueError('This room could not be found. Ask for a new invite.')
                if action=='join':
                    name=require_player_name(d.get('name'))
                    if r['phase']!='lobby' or len(r['players'])>=8: raise ValueError('Room started or full')
                    p=secrets.token_urlsafe(24); r['players'][p]={'name':name,'score':0}; return self.reply({'room':r['code'],'token':p})
                p=d['token']
                if p not in r['players']: raise ValueError('Invalid player session')
                settle(r)
                if action in ('race-ready','race-retry','race-skip','race-audio'):
                    if r.get('mode')!='race' or r['phase']!='playing' or d.get('round')!=r['round']:raise ValueError('Round changed')
                    if action=='race-ready' and r.get('race_status') in ('ready','playing'):
                        r['race_ready'].add(p)
                        if not r.get('race_started') and r['race_ready']>=set(r['players'])-set(r['guesses']):
                            r['race_started']=time.time()+2;r['deadline']=r['race_started']+r['race_duration'];r['race_status']='playing'
                            keys=song_history_keys(r['song']);identity=next((k for k in keys if k.startswith('song:')),None)
                            boards.record_played([v.get('name','') for k,v in r['players'].items() if k not in r['guesses']],r['song']['id'],identity);r.setdefault('_played_song_ids',set()).update(keys)
                    elif action=='race-audio' and not r.get('race_started') and not r.get('race_audio_only'):
                        r['race_audio_only']=True;r['audioKey']=secrets.token_urlsafe(24);r['race_ready']=set();r.pop('race_path',None);queue_youtube(r)
                    elif action=='race-retry' and r.get('race_status')=='error':queue_youtube(r)
                    elif action=='race-skip':
                        r['guesses'][p]=''
                        if len(r['guesses'])==len(r['players']):r['phase']='reveal';r['winners']=[]
                        elif not r.get('race_started') and r.get('race_status')=='ready' and r['race_ready']>=set(r['players'])-set(r['guesses']):
                            r['race_started']=time.time()+2;r['deadline']=r['race_started']+r['race_duration'];r['race_status']='playing'
                            keys=song_history_keys(r['song']);identity=next((k for k in keys if k.startswith('song:')),None)
                            boards.record_played([v.get('name','') for k,v in r['players'].items() if k not in r['guesses']],r['song']['id'],identity);r.setdefault('_played_song_ids',set()).update(keys)
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
                        r['guesses'][p]=guess; r.setdefault('guess_times',{})[p]=time.time()-(r.get('race_started') or r.get('round_started') or time.time()); settle(r)
                elif action=='lobby':
                    if p!=r['host'] or r['phase']!='finished':raise ValueError('Only the host can return a finished match to the lobby')
                    for player in r['players'].values():player['score']=0
                    # Remember this match's tail so the next match in the same
                    # room (or the same browser's next solo game) avoids
                    # immediate repeats when the pool is large enough.
                    tail=[] if r.pop('_history_cleared',False) else [t for t in r.get('pool',[]) if t['id'] in r.get('used',[])[-20:]]
                    r.update(match_id=secrets.token_urlsafe(24),score_max=0,_scores_recorded=False,phase='lobby',mode='party' if r.get('game_mode')=='party' else r['mode'],difficulty=r.get('base_difficulty',r['difficulty']),party_cycle=[],round=0,stage=0,guesses={},history=[],winners=[],
                             recap=[],used=[],deadline=0,guess_times={},race_cooldowns={},race_wrong={},race_started=None,recap_recorded=False,_next_round=None,_current_prefetch=None,previous_artists=[artist_key(t) for t in tail],
                             previous_songs=[t['id'] for t in tail],
                             artist_counts={},country_counts={},language_counts={},recent_artists=[])
                elif action=='next':
                    if p!=r['host'] or r['phase'] not in ['lobby','reveal']: raise ValueError('Only host can continue')
                    if r['round']>=r['rounds']:
                        r['phase']='finished';boards.record_match(r)
                    else: advance(r)
                else: raise ValueError('Unknown action')
                return self.reply(state(r,p))
        except Exception as e: self.reply({'error':str(e)},400)
if __name__=='__main__':
    http=ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT',3000))),Handler)
    start_catalog_rotation()
    http.serve_forever()

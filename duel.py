"""Two-player, private-song duel. All clocks and permissions live on the server."""
import copy,json,math,pathlib,re,secrets,subprocess,threading,time,urllib.parse
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
import leaderboard as boards
from catalog import history_identity
from recognition import anime_song,layout_variants,song_key

PICK_SECONDS=30
CLIP_SECONDS=30
GUESS_SECONDS=45
CLIP_LENGTH=5


def youtube_id(value):
    try:
        url=urllib.parse.urlsplit(value.strip())
        if url.scheme not in ('http','https') or url.username or url.password:return None
        host=(url.hostname or '').lower()
        if host in ('youtu.be','www.youtu.be'):ident=url.path.strip('/').split('/')[0]
        elif host in ('youtube.com','www.youtube.com','m.youtube.com','music.youtube.com'):
            parts=url.path.strip('/').split('/')
            ident=parts[1] if len(parts)==2 and parts[0] in ('shorts','embed','live') else urllib.parse.parse_qs(url.query).get('v',[''])[0] if url.path=='/watch' else ''
        else:return None
        return ident if re.fullmatch(r'[A-Za-z0-9_-]{11}',ident) else None
    except (ValueError,AttributeError):return None


def answer_text(value):
    value=re.sub(r'\s*[\[(][^\])]*(?:official|lyrics?|music video|visuali[sz]er|audio|\bhd\b|\b4k\b)[^\])]*[\])]','',str(value),flags=re.I)
    value=re.sub(r'\s*[-|]\s*(?:official\s*)?(?:music\s*)?(?:video|audio|lyrics?)\s*$', '',value,flags=re.I)
    return value.strip()


def correct_guess(song,guess):
    title=answer_text(song['title']);artist=song.get('seed_artist') or song.get('artist','')
    entry=anime_song(artist,title)
    titles=[title,*song.get('answer_aliases',[]),*(entry['titles'] if entry else [])]
    accepted=set()
    for title in titles:
        accepted.update(filter(None,(song_key(title),song_key(artist+' '+title),song_key(title+' '+artist))))
    for variant in layout_variants(guess):
        key=song_key(answer_text(variant))
        if key in accepted:return True
        # A small typo allowance for longer answers, never artist-only/substring matching.
        if len(key)>=8 and any(len(target)>=8 and abs(len(key)-len(target))<=2 and SequenceMatcher(None,key,target).ratio()>=.94 for target in accepted):return True
    return False


def fill_positions(chosen,duration):
    end=max(0,duration-CLIP_LENGTH)
    values=list(chosen)
    defaults=[round(end*i/4,3) for i in range(5)]
    for value in defaults:
        if len(values)>=5:break
        if end<.5 or all(abs(value-old)>.05 for old in values):values.append(value)
    # Closely grouped manual selections can collide with the default grid.
    for i in range(101):
        if len(values)>=5:break
        value=round(end*i/100,3)
        if all(abs(value-old)>.001 for old in values):values.append(value)
    while len(values)<5:values.append(end)
    return values[:5]


def cut_clip(path,start,length=CLIP_LENGTH):
    result=subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(start),'-i',str(path),'-t',str(length),'-vn','-map_metadata','-1','-c:a','libmp3lame','-b:a','128k','-f','mp3','pipe:1'],capture_output=True,check=True,timeout=20)
    if not result.stdout:raise ValueError('An audio clip could not be prepared.')
    return result.stdout


class Duel:
    def __init__(self,rooms,lock,data,fetch,clean,load_media):
        self.rooms=rooms;self.lock=lock;self.data=data;self.fetch=fetch;self.clean=clean;self.load_media=load_media
        self.workers=ThreadPoolExecutor(max_workers=4,thread_name_prefix='duel-media')

    def start_clock(self):
        def run():
            while True:
                try:
                    with self.lock:
                        for room in list(self.rooms.values()):
                            if room.get('mode')=='duel':self.tick(room)
                except Exception:__import__('logging').exception('Song Duel clock failed')
                threading.Event().wait(.25)
        threading.Thread(target=run,daemon=True,name='duel-clock').start()

    def create(self,name,multi,rounds):
        if multi is not True:raise ValueError('Song Duel is online only and needs exactly two players.')
        if isinstance(rounds,bool):raise ValueError('Invalid round count')
        rounds=max(1,min(30,int(rounds)))
        with self.lock:
            for key in list(self.rooms):
                if time.time()-self.rooms[key]['created']>86400:del self.rooms[key]
            if len(self.rooms)>=100:raise ValueError('Too many active rooms. Try again later.')
            code=secrets.token_hex(3).upper()
            while code in self.rooms:code=secrets.token_hex(3).upper()
            token=secrets.token_urlsafe(24)
            self.rooms[code]=dict(code=code,created=time.time(),match_id=secrets.token_urlsafe(24),mode='duel',game_mode='duel',multi=True,
                players={token:dict(name=name,score=0)},host=token,phase='lobby',round=0,rounds=rounds,deadline=0,
                genre='Anything',region='Worldwide',difficulty='Duel',base_difficulty='Duel',decade='All',score_max=0,recap=[],duel=None)
            return dict(room=code,token=token)

    def other(self,r,p):return next((key for key in r['players'] if key!=p),None)

    def authenticate(self,code,token):
        r=self.rooms.get(str(code).upper())
        if not r or r.get('mode')!='duel' or token not in r['players']:raise ValueError('Invalid Song Duel session.')
        self.tick(r)
        return r

    def begin(self,r,retry=False):
        if len(r['players'])!=2:raise ValueError('Song Duel needs exactly two players before starting.')
        if not retry:r['round']+=1;r['score_max']+=1
        r.update(phase='picking',deadline=time.time()+PICK_SECONDS)
        r['duel']=dict(generation=secrets.token_urlsafe(16),songs={},candidates={p:{} for p in r['players']},positions={},revisions={},locked=set(),ready=set(),done={},feedback={},attempts={},clips={},clip_keys={},clip_pending=set(),recorded=set(),starts_at=0)

    def candidate(self,raw):
        track=self.clean(raw)
        return dict(id=track['id'],title=track['title'],artist=track['artist'],seed_artist=track.get('seed_artist',track['artist']),art=track.get('art',''),link=track.get('link',''),preview=track.get('preview',''),custom=False)

    def inspect_youtube(self,ident):
        canonical='https://www.youtube.com/watch?v='+ident
        info=json.loads(subprocess.check_output(['yt-dlp','--js-runtimes','node','--no-playlist','--skip-download','--dump-single-json','--',canonical],timeout=22,stderr=subprocess.DEVNULL))
        if info.get('is_live') or info.get('live_status')=='is_live':raise ValueError('Choose a finished song/video, not a live stream.')
        title=answer_text(info.get('track') or info.get('title') or '')
        artist=str(info.get('artist') or info.get('creator') or '').strip()
        if not info.get('track') and not artist and ' - ' in title:artist,title=title.split(' - ',1)
        artist=artist or str(info.get('uploader') or 'YouTube')
        if not title:raise ValueError('This video has no usable title.')
        return dict(id='yt:'+ident,youtube_id=ident,title=title[:160],artist=artist[:120],seed_artist=artist[:120],art='',link=canonical,preview='',custom=True)

    def search(self,code,p,query,round_number,generation):
        if not isinstance(query,str) or not 2<=len(query.strip())<=200:raise ValueError('Enter a song/artist or paste a YouTube video link.')
        query=query.strip()
        with self.lock:
            r=self.authenticate(code,p);d=r['duel']
            if r['phase']!='picking' or r['round']!=round_number or d['generation']!=generation:raise ValueError('Song picking has ended.')
        if '://' in query:
            ident=youtube_id(query)
            if not ident:raise ValueError('Paste a valid public YouTube video link.')
            rows=[self.inspect_youtube(ident)]
        else:
            raw=self.fetch('search?limit=12&q='+urllib.parse.quote(query)).get('data',[])
            rows=[self.candidate(t) for t in raw if isinstance(t,dict) and t.get('id') and t.get('title') and t.get('artist')]
        with self.lock:
            cur=self.authenticate(code,p)
            if cur is not r or cur['phase']!='picking' or cur['round']!=round_number or cur['duel']['generation']!=generation:raise ValueError('Song picking has ended.')
            out=[]
            for song in rows[:12]:
                key=secrets.token_urlsafe(18);d['candidates'][p][key]=song
                out.append(dict(selection=key,title=song['title'],artist=song['artist'],custom=song['custom']))
            # Keep bounded candidate storage, including the newest search results.
            entries=d['candidates'][p]
            while len(entries)>48:entries.pop(next(iter(entries)))
            return dict(round=r['round'],generation=generation,results=out)

    def guess_search(self,code,p,query,round_number,generation):
        if not isinstance(query,str) or not 2<=len(query.strip())<=100:raise ValueError('Enter at least two characters.')
        def validate():
            r=self.authenticate(code,p)
            if r['phase']!='playing' or r['round']!=round_number or r['duel']['generation']!=generation or p in r['duel']['done']:raise ValueError('Guessing has ended.')
        with self.lock:validate()
        raw=self.fetch('search?limit=12&q='+urllib.parse.quote(query.strip())).get('data',[])
        rows=[self.candidate(t) for t in raw if isinstance(t,dict) and t.get('id') and t.get('title') and t.get('artist')]
        with self.lock:validate()
        return dict(results=[dict(title=t['title'],artist=t['artist']) for t in rows[:12]])

    def preview_song(self,code,p,index,round_number,generation):
        with self.lock:
            r=self.authenticate(code,p);d=r.get('duel')
            if not d or r['phase'] not in ('reveal','finished') or r['round']!=round_number or d['generation']!=generation:raise ValueError('Previews are available after the round ends.')
            songs=list(d['songs'].values())
            if not isinstance(index,int) or not 0<=index<len(songs):raise ValueError('Preview unavailable.')
            song=songs[index]
            if song.get('status')!='ready':raise ValueError('Preview unavailable.')
            return dict(song)

    def pick(self,r,p,payload):
        d=r['duel'];song=copy.deepcopy(d['candidates'][p].get(payload.get('selection')))
        if not song:raise ValueError('Search for a song and select a result first.')
        if song['custom']:
            title=payload.get('title',song['title']);artist=payload.get('artist',song['artist'])
            if not isinstance(title,str) or not 1<=len(title.strip())<=160 or not isinstance(artist,str) or not 1<=len(artist.strip())<=120:raise ValueError('Enter the song title and artist used for guessing.')
            song.update(title=title.strip(),artist=artist.strip(),seed_artist=artist.strip())
        song.update(status='loading',job=secrets.token_urlsafe(16))
        d['songs'][p]=song
        code=r['code'];generation=d['generation'];job=song['job']
        def load():
            with self.lock:
                if self.rooms.get(code) is not r or r.get('duel') is not d or d['songs'].get(p,{}).get('job')!=job or r['phase'] not in ('picking','preparing'):return
            try:
                vid,_,path,duration,typ=self.load_media(dict(song),True)
                if not math.isfinite(duration) or duration<CLIP_LENGTH:raise ValueError('The chosen song must contain at least five seconds of audio.')
                if not pathlib.Path(path).is_file():raise ValueError('The chosen audio could not be loaded.')
                result=dict(status='ready',path=str(path),duration=duration,youtube_id=vid)
            except Exception:result=dict(status='error',error='This song could not be downloaded. Try another song or retry the round.')
            with self.lock:
                cur=self.rooms.get(code)
                if cur is r and cur.get('duel') is d and d['generation']==generation and d['songs'].get(p,{}).get('job')==job:
                    d['songs'][p].update(result);self.tick(cur)
        self.workers.submit(load)

    def start_clips(self,r,now):
        d=r['duel'];r.update(phase='clips',deadline=now+CLIP_SECONDS)
        for p in r['players']:
            if self.other(r,p) not in d['songs']:d['done'][p]='no-song';d['locked'].add(p)
            d['positions'][p]=[];d['revisions'][p]=0

    def prepare_clips(self,r,now):
        d=r['duel'];r.update(phase='preparing-clips',deadline=0);d['media_deadline']=now+65
        active=[p for p in r['players'] if p not in d['done']]
        if not active:self.finish(r);return
        d['clip_pending'].update(active)
        for p in active:
            song=d['songs'][self.other(r,p)];positions=fill_positions(d['positions'].get(p,[]),song['duration'])
            d['positions'][p]=positions;d['clip_keys'][p]=secrets.token_urlsafe(24);d['clip_pending'].add(p)
            def render(p=p,song=song,positions=positions):
                try:
                    result=[]
                    for start in positions:
                        with self.lock:
                            if self.rooms.get(r['code']) is not r or r.get('duel') is not d or r['phase']!='preparing-clips':return
                        result.append(cut_clip(song['path'],start))
                    failure=False
                except Exception:result=[];failure=True
                with self.lock:
                    if self.rooms.get(r['code']) is not r or r.get('duel') is not d:return
                    d['clip_pending'].discard(p)
                    if failure:d['error']='The five-second clips could not be prepared. Retry this round.'
                    else:d['clips'][p]=result
                    self.tick(r)
            self.workers.submit(render)

    def start_guessing(self,r,now):
        d=r['duel']
        try:
            for p in r['players']:
                if p in d['done']:continue
                song=d['songs'][self.other(r,p)]
                if p not in d['recorded']:
                    boards.record_played([r['players'][p]['name']],song['id'],history_identity(song.get('seed_artist') or song['artist'],song['title']))
                    d['recorded'].add(p)
        except Exception:
            d['error']='Song history could not be saved. Check the server data storage, then retry this round.'
            r.update(phase='duel-error',deadline=0);return
        started=time.time()+1
        d['starts_at']=started;r.update(phase='playing',deadline=started+GUESS_SECONDS)

    def finish(self,r):
        d=r['duel']
        if r['phase']=='reveal':return
        results=[]
        for owner,song in d['songs'].items():
            receiver=self.other(r,owner);correct=d['done'].get(receiver)=='correct'
            results.append(dict(owner=r['players'][owner]['name'],guesser=r['players'][receiver]['name'],title=song['title'],artist=song['artist'],correct=correct,result=d['done'].get(receiver,'skipped'),link='https://www.youtube.com/watch?v='+song['youtube_id'] if song.get('youtube_id') else song.get('link','')))
        r['recap'].append(dict(round=r['round'],songs=results))
        r.update(phase='reveal',deadline=0)

    def tick(self,r,now=None):
        now=time.time() if now is None else now
        if r['phase'] in ('lobby','reveal','finished','duel-error'):return
        d=r['duel']
        for _ in range(7):
            phase=r['phase']
            if phase=='picking':
                if now<r['deadline'] and len(d['songs'])<2:return
                r.update(phase='preparing',deadline=0);d['media_deadline']=now+175
            elif phase=='preparing':
                if any(song['status']=='error' for song in d['songs'].values()) or now>=d['media_deadline']:
                    d['error']='A selected song could not load. Retry picking or skip this round.';r.update(phase='duel-error',deadline=0);return
                if any(song['status']=='loading' for song in d['songs'].values()):return
                if not d['songs']:self.finish(r);return
                if len(d['songs'])==1:
                    owner=next(iter(d['songs']));missing=self.other(r,owner)
                    d['done'].update({owner:'forfeit-win',missing:'no-pick'})
                    r['players'][owner]['score']+=1
                    d['notice']=r['players'][missing]['name']+' did not choose a song. '+r['players'][owner]['name']+' wins this round by forfeit (+1).'
                    self.finish(r);return
                self.start_clips(r,now)
            elif phase=='clips':
                if now<r['deadline'] and not all(p in d['locked'] for p in r['players']):return
                self.prepare_clips(r,now)
            elif phase=='preparing-clips':
                if d.get('error') or now>=d['media_deadline']:
                    d['error']=d.get('error') or 'Audio preparation timed out. Retry this round.';r.update(phase='duel-error',deadline=0);return
                if d['clip_pending']:return
                r.update(phase='loading',deadline=now+40)
            elif phase=='loading':
                active={p for p in r['players'] if p not in d['done']}
                if not active:self.finish(r);return
                if active<=d['ready']:self.start_guessing(r,now)
                elif now>=r['deadline']:
                    d['error']='Both players need to load their clips. Check the connection and retry.';r.update(phase='duel-error',deadline=0)
                return
            elif phase=='playing':
                if now>=r['deadline']:
                    for p in r['players']:d['done'].setdefault(p,'timeout')
                if len(d['done'])==2:self.finish(r)
                return
            else:return

    def handle(self,r,p,action,payload):
        self.tick(r)
        if action in ('duel-next','duel-lobby','duel-settings','duel-retry'):
            if p!=r['host']:raise ValueError('Only the host can do this.')
            if action=='duel-settings':
                if r['phase']!='lobby':raise ValueError('Settings can only change in the lobby.')
                count=payload.get('rounds')
                if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=30:raise ValueError('Choose 1–30 rounds.')
                r['rounds']=count
            elif action=='duel-lobby':
                if r['phase']!='finished':raise ValueError('Finish the match before returning to the lobby.')
                for player in r['players'].values():player['score']=0
                r.update(phase='lobby',round=0,deadline=0,duel=None,score_max=0,recap=[],match_id=secrets.token_urlsafe(24),_scores_recorded=False)
            elif action=='duel-retry':
                if r['phase']!='duel-error':raise ValueError('This round does not need retrying.')
                self.begin(r,retry=True)
            else:
                if r['phase'] not in ('lobby','reveal','duel-error'):raise ValueError('Finish the current round first.')
                if r['phase']=='duel-error':self.finish(r)
                if r['round']>=r['rounds']:r.update(phase='finished',deadline=0);boards.record_match(r)
                else:self.begin(r)
            return self.state(r,p)
        d=r['duel']
        if not d or payload.get('round')!=r['round'] or payload.get('generation')!=d['generation']:raise ValueError('The round has changed. Refresh and try again.')
        if action=='duel-pick':
            if r['phase']!='picking':raise ValueError('Song picking has ended.')
            self.pick(r,p,payload)
        elif action=='duel-clips':
            if r['phase']!='clips' or p in d['done']:raise ValueError('Clip picking is locked.')
            positions=payload.get('positions');revision=payload.get('revision')
            if not isinstance(positions,list) or len(positions)>5 or not isinstance(revision,int) or isinstance(revision,bool) or not 1<=revision<=2147483647 or not isinstance(payload.get('locked',False),bool):raise ValueError('Choose up to five valid clip positions.')
            if revision<=d['revisions'].get(p,0):return self.state(r,p)
            if p in d['locked']:raise ValueError('Clip picking is locked.')
            end=d['songs'][self.other(r,p)]['duration']-CLIP_LENGTH
            if any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) or not 0<=x<=end+.001 for x in positions):raise ValueError('Every five-second clip must stay inside the song.')
            if revision>d['revisions'].get(p,0):d['positions'][p]=[min(end,float(x)) for x in positions];d['revisions'][p]=revision
            if payload.get('locked'):
                if len(d['positions'][p])!=5:raise ValueError('Choose five clips before locking them.')
                d['locked'].add(p)
        elif action=='duel-ready':
            if r['phase'] not in ('loading','playing') or p not in d['clips']:raise ValueError('Your audio clips are not ready.')
            d['ready'].add(p)
        elif action in ('duel-guess','duel-skip'):
            if r['phase']!='playing' or now_before(d['starts_at']) or p in d['done']:raise ValueError('You cannot guess at this moment.')
            if action=='duel-skip':d['done'][p]='skipped'
            else:
                guess=payload.get('guess')
                if not isinstance(guess,str) or not 1<=len(guess.strip())<=200:raise ValueError('Type a song title, with the artist if you want.')
                d['attempts'][p]=d['attempts'].get(p,0)+1
                if correct_guess(d['songs'][self.other(r,p)],guess):d['done'][p]='correct';d['feedback'][p]='Correct!';r['players'][p]['score']+=1
                else:d['feedback'][p]='Not that song. Keep listening and try again.'
        else:raise ValueError('Unknown Song Duel action.')
        self.tick(r)
        return self.state(r,p)

    def state(self,r,p):
        self.tick(r)
        if r['phase']=='finished':boards.record_match(r)
        d=r.get('duel');other=self.other(r,p)
        out={key:r[key] for key in ('code','phase','round','rounds','deadline','mode','game_mode','multi','genre','region','difficulty','base_difficulty','decade','score_max')}
        out.update(host=p==r['host'],serverTime=time.time(),stage=0,history=[],players=[dict(name=v['name'],score=v['score'],me=k==p,host=k==r['host'],submitted=bool(d and k in d['done']),picked=bool(d and k in d['songs']),clips_locked=bool(d and k in d['locked']),audio_ready=bool(d and k in d['ready'])) for k,v in r['players'].items()])
        if not d:return out
        own=d['songs'].get(p);target=d['songs'].get(other)
        public=dict(generation=d['generation'],positions=d['positions'].get(p,[]),revision=d['revisions'].get(p,0),locked=p in d['locked'],ready=p in d['ready'],done=d['done'].get(p),feedback=d['feedback'].get(p,''),attempts=d['attempts'].get(p,0),starts_at=d['starts_at'],error=d.get('error',''))
        if d.get('notice'):public['notice']=d['notice']
        if own:public['picked']=dict(title=own['title'],artist=own['artist'],status=own['status'],error=own.get('error',''))
        if r['phase'] not in ('picking','preparing') and target and target.get('status')=='ready':public['duration']=target['duration']
        if r['phase'] in ('loading','playing','reveal') and p in d['clips']:public['clip_key']=d['clip_keys'][p]
        if r['phase']=='reveal':public['answers']=r['recap'][-1]['songs']
        if r['phase']=='finished':out['recap']=r['recap']
        out['duel']=public
        return out

    def clip(self,code,p,key,index,round_number):
        with self.lock:
            r=self.authenticate(code,p);d=r['duel']
            if not d or r['phase'] not in ('loading','playing','reveal') or r['round']!=round_number or d['clip_keys'].get(p)!=key:raise ValueError('This clip is private or has expired.')
            if not isinstance(index,int) or not 0<=index<5 or p not in d['clips']:raise ValueError('Clip not ready.')
            return d['clips'][p][index]

    def protected_paths(self):
        return [song['path'] for r in self.rooms.values() if r.get('mode')=='duel' and r.get('phase')!='finished' for song in (r.get('duel') or {}).get('songs',{}).values() if song.get('path')]


def now_before(timestamp):return time.time()<timestamp

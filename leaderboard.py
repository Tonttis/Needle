"""Persistent named scores and shared daily challenge snapshots."""
import datetime, hashlib, json, random, sqlite3
from pathlib import Path

DB_PATH=Path(__file__).parent/'data'/'needle-scores.sqlite3'

def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db=sqlite3.connect(DB_PATH,timeout=20)
    db.execute('PRAGMA busy_timeout=20000')
    db.execute('CREATE TABLE IF NOT EXISTS scores (match_id TEXT NOT NULL, player_key TEXT NOT NULL, name TEXT NOT NULL, mode TEXT NOT NULL, difficulty TEXT NOT NULL, multiplayer INTEGER NOT NULL, points INTEGER NOT NULL, maximum INTEGER NOT NULL, rounds INTEGER NOT NULL, daily_date TEXT, played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(match_id,player_key))')
    db.execute('CREATE INDEX IF NOT EXISTS scores_filter ON scores(mode,difficulty,multiplayer,daily_date)')
    db.execute('CREATE TABLE IF NOT EXISTS daily_challenges (day TEXT PRIMARY KEY, pool_json TEXT NOT NULL, song_ids_json TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS played_songs (profile_key TEXT NOT NULL, song_id TEXT NOT NULL, first_played TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, last_played TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, plays INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(profile_key,song_id))')
    return db

def day_utc(): return datetime.datetime.now(datetime.timezone.utc).date().isoformat()

def daily_existing(day):
    with connection() as db:
        row=db.execute('SELECT pool_json,song_ids_json FROM daily_challenges WHERE day=?',(day,)).fetchone()
    return (json.loads(row[0]),json.loads(row[1])) if row else None

def daily_snapshot(day, tracks):
    existing=daily_existing(day)
    if existing:return existing
    candidates=[t for t in tracks if t.get('preview') and ('recognition' not in t or __import__('recognition').in_difficulty(t,'Easy'))]
    if len(candidates)<5:raise ValueError('Not enough songs are available for today’s challenge. Try again later.')
    rng=random.Random(int(hashlib.sha256(('Needle-daily-v1:'+day).encode()).hexdigest(),16))
    # Select uniformly by artist first, so prolific artists do not gain extra
    # chances simply by having more tracks. Apply Europe Mixed's soft lanes.
    groups={}
    for track in sorted(candidates,key=lambda t:str(t['id'])):
        key=str(track.get('artist_id') or track.get('artist','')).casefold()
        groups.setdefault(key,[]).append(track)
    if len(groups)<5:raise ValueError('Not enough different artists for today’s challenge.')
    chosen=[];language_counts={};country_counts={}
    while len(chosen)<5:
        available=sorted(groups)
        def fits(key):
            track=groups[key][0];language=track.get('language','');country=track.get('country','')
            if country=='FI' and country_counts.get('FI',0)>=1:return False
            if language in ('French','Spanish'):
                if language_counts.get(language,0)>=1:return False
                if sum(language_counts.get(x,0) for x in ('French','Spanish'))>=2:return False
            return True
        balanced=[key for key in available if fits(key)] or available
        def weight(key):
            country=groups[key][0].get('country','')
            return (1.5 if country in ('FI','SE','NO','DK','IS') else 1)/(1+country_counts.get(country,0)*.35)
        artist=rng.choices(balanced,weights=[weight(key) for key in balanced],k=1)[0]
        track=rng.choice(groups.pop(artist));chosen.append(track['id'])
        language=track.get('language','');country=track.get('country','')
        language_counts[language]=language_counts.get(language,0)+1;country_counts[country]=country_counts.get(country,0)+1
    with connection() as db:
        db.execute('INSERT OR IGNORE INTO daily_challenges VALUES (?,?,?)',(day,json.dumps(tracks),json.dumps(chosen)))
    return daily_existing(day)

def record_match(r):
    if r.get('_scores_recorded'):return
    maximum=r.get('score_max',0)
    if maximum<=0:return
    difficulty=r.get('base_difficulty',r.get('difficulty','Easy'))
    mode=r.get('game_mode',r.get('mode','guess'))
    with connection() as db:
        for token,p in r['players'].items():
            name=str(p.get('name','You')).strip()[:24] or 'You'
            db.execute('INSERT OR IGNORE INTO scores(match_id,player_key,name,mode,difficulty,multiplayer,points,maximum,rounds,daily_date) VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (r['match_id'],token,name,mode,difficulty,int(r.get('multi',False)),int(p['score']),maximum,r['rounds'],r.get('daily_date')))
    r['_scores_recorded']=True

def leaderboard(mode,difficulty,multiplayer,daily_date=None):
    with connection() as db:
        rows=db.execute('''SELECT name,points,maximum,rounds,played_at FROM (
          SELECT name,points,maximum,rounds,played_at,ROW_NUMBER() OVER
          (PARTITION BY lower(trim(name)) ORDER BY 1.0*points/maximum DESC,points DESC,played_at ASC) AS position
          FROM scores WHERE mode=? AND difficulty=? AND multiplayer=? AND ((? IS NULL AND daily_date IS NULL) OR daily_date=?))
          WHERE position=1 ORDER BY 1.0*points/maximum DESC,points DESC,played_at ASC LIMIT 100''',
          (mode,difficulty,int(multiplayer),daily_date,daily_date)).fetchall()
    return [dict(name=a,points=b,maximum=c,rounds=d,played_at=e,percentage=round(100*b/c,1)) for a,b,c,d,e in rows]


def profile(name):
    with connection() as db:
        row=db.execute("SELECT COUNT(*), COALESCE(SUM(points),0), COALESCE(MAX(1.0*points/maximum),0), COUNT(DISTINCT daily_date) FROM scores WHERE lower(trim(name))=lower(trim(?))",(name,)).fetchone()
    return dict(games=row[0],total_points=row[1],best_percentage=round(row[2]*100,1),daily_days=row[3])


def profile_key(name):
    return ' '.join(str(name or '').strip().casefold().split())[:24]

def played_song_ids(names):
    keys=list(dict.fromkeys(filter(None,(profile_key(n) for n in names))))
    if not keys:return set()
    with connection() as db:
        placeholders=','.join('?' for _ in keys)
        return {row[0] for row in db.execute('SELECT DISTINCT song_id FROM played_songs WHERE profile_key IN ('+placeholders+')',keys)}

def record_played(names,song_id,identity=None):
    keys=list(dict.fromkeys(filter(None,(profile_key(n) for n in names))))
    if not keys or not song_id:return
    with connection() as db:
        db.executemany("INSERT INTO played_songs(profile_key,song_id) VALUES(?,?) ON CONFLICT(profile_key,song_id) DO UPDATE SET plays=plays+1,last_played=CURRENT_TIMESTAMP",[(key,entry) for key in keys for entry in dict.fromkeys([str(song_id)]+([identity] if identity else []))])


def clear_played(name):
    key=profile_key(name)
    if not key:raise ValueError('Enter a name.')
    with connection() as db:
        cursor=db.execute('DELETE FROM played_songs WHERE profile_key=?',(key,))
        return cursor.rowcount

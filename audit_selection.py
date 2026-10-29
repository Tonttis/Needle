"""Offline audit of a real provider cache; never modifies it or calls providers.

Usage: python3 audit_selection.py /path/to/catalog-cache.sqlite > report.json
Missing entries are reported as unavailable, not replaced by invented tracks.
"""
import collections,json,random,sqlite3,sys,time
from pathlib import Path
import catalog as c
from recognition import in_difficulty
from server import clean

def audit(path):
 with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as db:
  cache={key:json.loads(body) for key,body in db.execute('SELECT path,body FROM responses')}
 misses=set();report=[];pick_times=[]
 def fetch(key):
  if key not in cache:misses.add(key);return {'data':[]}
  return cache[key]
 for region in ('Worldwide','Europe'):
  for genre in c.GENRES:
   for difficulty in c.DIFFICULTIES+(['Hits'] if genre=='Mixed' else []):
    row=dict(region=region,genre=genre,difficulty=difficulty)
    random.seed(7801)
    try:pool=c.build_pool(fetch,clean,genre,region,difficulty)
    except ValueError as error:
     row.update(status='unavailable_in_cache',reason=str(error));report.append(row);continue
    eligible=c.band(pool,difficulty)
    row.update(status='ok',songs=len({c.history_identity(t['seed_artist'],t['title']) for t in eligible}),artists=len({c.artist_key(t) for t in eligible}))
    seen=set();exposure={};stats={};chosen=[];early_repeats=0;first=[]
    for game in range(20):
     room=dict(pool=pool,used=[],region=region,genre=genre,difficulty=difficulty,mode='hits' if difficulty=='Hits' else ('guess','choice','race')[game%3],rounds=5,
       _played_song_ids=seen,_artist_play_counts=exposure,_song_play_counts=stats)
     for round_number in range(5):
      started=time.perf_counter();t=c.choose_song(room);pick_times.append((time.perf_counter()-started)*1000)
      if c.song_was_played(t,seen) and any(not c.song_was_played(x,seen) for x in eligible):early_repeats+=1
      assert in_difficulty(t,difficulty)
      room['used'].append(t['id']);keys=c.song_history_keys(t);seen.update(keys)
      identity=c.history_identity(t['seed_artist'],t['title']);chosen.append(identity)
      if len(first)<15:first.append(t['seed_artist'])
      for key in keys:stats[key]=(stats.get(key,(0,''))[0]+1,f'{game*5+round_number:08}')
      artist=c.text_key(t['seed_artist']);exposure[artist]=exposure.get(artist,0)+1
    row.update(rounds=100,premature_repeats=early_repeats,unique_songs=len(set(chosen)),first_15_artists=len(set(first)))
    assert early_repeats==0,row
    report.append(row)
 ordered=sorted(pick_times)
 return dict(cache_entries=len(cache),missing_provider_requests=len(misses),combinations=len(report),
             playable_combinations=sum(r['status']=='ok' for r in report),rounds=len(pick_times),
             picker_median_ms=round(ordered[len(ordered)//2],3) if ordered else None,
             picker_p95_ms=round(ordered[int(len(ordered)*.95)],3) if ordered else None,results=report)

if __name__=='__main__':print(json.dumps(audit(sys.argv[1]),indent=2))

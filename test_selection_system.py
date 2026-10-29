"""Cross-game regression and selection contracts for the entire filter surface.

Synthetic matrix isolates selection invariants from provider availability.
The optional cached-provider test exercises the real import/classification path.
"""
import collections,json,os,random,sqlite3,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import catalog as c, leaderboard as lb, recognition as rec, server as s
from test_variety import HTTPGameTests

def tracks(artists=40,songs=5,score=90):
 return [dict(id=f'{a}-{j}',artist=f'Artist {a}',seed_artist=f'Artist {a}',artist_id=str(a),
              title=f'Track {j}',preview='fixture',art='',link='',country='US',language='English',
              recognition=score,hot_hit=True,release_year=2014)
         for a in range(artists) for j in range(songs)]

def history(room,names):
 room['_played_song_ids'],room['_artist_play_counts'],room['_song_play_counts']=lb.selection_history(names)

def record(track,names):
 lb.record_played(names,track['id'],c.history_identity(track.get('seed_artist') or track['artist'],track['title']))

class SelectionContracts(unittest.TestCase):
 def test_three_fresh_games_have_fifteen_songs_and_artists(self):
  for seed in range(30):
   with tempfile.TemporaryDirectory() as tmp,patch.object(lb,'DB_PATH',Path(tmp)/'db'):
    selected=[];rng=random.Random(seed)
    for game in range(3):
     room=dict(pool=tracks(),used=[],rounds=5,mode='guess',genre='Rap / Hip Hop',region='Worldwide',difficulty='Easy')
     for _ in range(5):
      history(room,['Alice']);track=c.choose_song(room,rng);record(track,['Alice'])
      room['used'].append(track['id']);selected.append(track)
    self.assertEqual(len({t['id'] for t in selected}),15)
    self.assertEqual(len({t['artist_id'] for t in selected}),15)
 def test_exhaustion_uses_least_played_oldest_and_stays_in_tier(self):
  pool=tracks(2,2)
  room=dict(pool=pool+[dict(tracks(1,1,score=16)[0],id='wrong')],used=[],difficulty='Easy',
            _played_song_ids={t['id'] for t in pool},_song_play_counts={t['id']:(4,'2026-01-02') for t in pool})
  room['_song_play_counts']['1-1']=(1,'2026-01-01')
  self.assertEqual(c.choose_song(room)['id'],'1-1')
  room['_song_play_counts']['1-0']=(1,'2025-01-01')
  self.assertEqual(c.choose_song(room)['id'],'1-0')
 def test_artist_exposure_survives_new_connections_and_duplicate_release(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(lb,'DB_PATH',Path(tmp)/'db'):
   pool=tracks(20,2)
   for track in pool[:10]:record(track,['Alice','Bob'])
   room=dict(pool=pool,used=[],difficulty='Easy');history(room,['ALICE',' bob '])
   self.assertEqual(room['_artist_play_counts']['artist0'],4)
   picked=c.choose_song(room);self.assertGreaterEqual(int(picked['artist_id']),5)
   original=pool[0];alternate=dict(original,id='another-release',title=original['title']+' - 2011 Remaster')
   self.assertTrue(c.song_was_played(alternate,room['_played_song_ids']))
   lb.clear_played('Alice');self.assertTrue(lb.selection_history(['Bob'])[0]);self.assertFalse(lb.selection_history(['Alice'])[0])
 def test_genre_assignments_and_easy_rap_breadth(self):
  names={t['name'] for t in c.eligible('Rap / Hip Hop','Worldwide')}
  self.assertFalse(names&{'Bad Bunny','Daddy Yankee','J Balvin','Pitbull','Don Omar','Ozuna','Maluma'})
  latin={t['name'] for t in c.eligible('Latin','Worldwide')}
  self.assertTrue({'Bad Bunny','Daddy Yankee','J Balvin','Pitbull'}<=latin)
  anchors=[seed for seed in c.eligible('Rap / Hip Hop','Worldwide') if any(rec.recognition(seed,title,'Worldwide','Rap / Hip Hop')>=85 for title in (rec.profile(seed) or {}).get('examples',[]))]
  self.assertGreaterEqual(len(anchors),35)
 def test_language_caps_apply_to_every_broad_genre(self):
  for genre in c.GENRES:
   if genre in ('Latin','Reggae','Afrobeats','K-pop','J-pop'):continue
   pool=tracks(90,1)
   for i,t in enumerate(pool):t['language']=('Spanish','French','English')[i%3]
   for seed in range(20):
    room=dict(pool=pool,used=[],genre=genre,region='Worldwide',difficulty='Easy',rounds=5)
    selected=[]
    for _ in range(5):
     t=c.choose_song(room,random.Random(seed+len(selected)));selected.append(t);room['used'].append(t['id'])
    self.assertLessEqual(sum(t['language']=='Spanish' for t in selected),1)
    self.assertLessEqual(sum(t['language']=='French' for t in selected),1)
 def test_english_latin_crossover_counts_toward_short_game_cap(self):
  pool=tracks(50,1)
  for track in pool[:40]:track['genres']=['Pop','Latin']
  for seed in range(30):
   room=dict(pool=pool,used=[],genre='Mixed',region='Worldwide',difficulty='Easy',rounds=5)
   selected=[]
   for _ in range(5):
    track=c.choose_song(room,random.Random(seed+len(selected)));selected.append(track);room['used'].append(track['id'])
   self.assertLessEqual(sum('Latin' in t.get('genres',[]) for t in selected),1)
 def test_all_filter_dimensions_share_no_repeat_and_tier_contract(self):
  count=0
  scores=dict(zip(c.DIFFICULTIES,[90,68,48,32,16]));scores['Hits']=90
  # Every supported region/genre/tier plus every selectable decade and mode.
  config=c.filter_options()['support']
  for region,genres in config.items():
   for genre,tiers in genres.items():
    for tier in tiers:
     pool=tracks(18,2,scores[tier]);seen=set();exposure={}
     for game in range(3):
      room=dict(pool=pool,used=[],genre=genre,region=region,difficulty=tier,rounds=5,
                _played_song_ids=seen,_artist_play_counts=exposure)
      for _ in range(5):
       t=c.choose_song(room,random.Random(count));count+=1
       self.assertTrue(rec.in_difficulty(t,tier));self.assertFalse(c.song_history_keys(t)&seen)
       room['used'].append(t['id']);seen.update(c.song_history_keys(t));key=rec.text_key(t['artist']);exposure[key]=exposure.get(key,0)+1
     self.assertEqual(len(exposure),15)
  for decade in s.DECADES:
   for mode in ('guess','choice','race','hits','party'):
    for tier in scores:
     pool=tracks(20,3,scores[tier]);room=dict(pool=pool,used=[],mode=mode,game_mode=mode,
      party_modes=['guess','choice','race','hits'],base_difficulty=tier,difficulty='Hits' if mode=='hits' else tier,
      decade=decade,rounds=15,_played_song_ids=set())
     for _ in range(15):
      t=s.choose_round(room);self.assertFalse(c.song_history_keys(t)&room['_played_song_ids'])
      room['used'].append(t['id']);room['_played_song_ids'].update(c.song_history_keys(t))
  print(f'\nSelection matrix: {count} rounds across all advertised scene/genre/difficulty combinations')

class AllModeHistoryTests(HTTPGameTests):
 def test_every_mode_counts_assignment_once_for_every_player_and_not_prefetch(self):
  with patch.object(s,'pool',return_value=tracks()),patch.object(s,'queue_youtube'),patch.object(s,'queue_prefetch'),patch.object(s,'queue_credit'):
   for mode in ('guess','choice','race','hits','party'):
    host=self.post('create',dict(name='Alice',mode=mode,multi=True,difficulty='Easy',rounds=2,party_modes=['race','guess']))
    guest=self.post('join',dict(room=host['room'],name='Bob'))
    self.post('next',host);room=s.rooms[host['room']];track=room['song']
    for name in ('Alice','Bob'):
     seen,_,stats=lb.selection_history([name]);self.assertIn(track['id'],seen);self.assertEqual(stats[track['id']][0],1)
    if room.get('_next_round'):
     self.assertNotIn(room['_next_round']['song']['id'],lb.played_song_ids(['Alice','Bob']))
    del s.rooms[host['room']]
 def test_daily_rounds_count_in_personal_history(self):
  with patch.object(s,'pool',return_value=tracks()),patch.object(s,'queue_credit'):
   host=self.post('daily-create',dict(name='Alice'));room=s.rooms[host['room']]
   daily=[]
   for round_number in range(1,6):
    daily.append(room['song']['id'])
    self.post('guess',dict(**host,id=room['song']['id'],round=round_number,stage=0))
    self.post('next',host)
   self.assertTrue(set(daily)<=lb.played_song_ids(['Alice']))
   del s.rooms[host['room']]
   regular=self.post('create',dict(name='Alice',mode='guess',difficulty='Easy',rounds=1))
   self.assertNotIn(s.rooms[regular['room']]['song']['id'],daily)
   del s.rooms[regular['room']]

 def test_playlist_songs_count_across_all_modes(self):
  pool=tracks()
  for track in pool:track.pop('recognition');track['playlist_track']=True
  with patch.object(s,'playlist_pool',return_value=(pool,dict(total=len(pool),matched=len(pool)))),patch.object(s,'queue_youtube'),patch.object(s,'queue_prefetch'),patch.object(s,'queue_credit'):
   selected=[]
   for mode in ('guess','choice','race','hits','party'):
    session=self.post('create',dict(name='Playlist listener',mode=mode,playlist_url='https://www.youtube.com/playlist?list=PL_fixture',rounds=1,party_modes=['race','hits']))
    room=s.rooms[session['room']];selected.append(room['song']['id'])
    self.assertIn(room['song']['id'],lb.played_song_ids(['Playlist listener']))
    del s.rooms[session['room']]
   self.assertEqual(len(set(selected)),5)

class IdentityAndDecadeTests(unittest.TestCase):
 def test_old_identity_history_matches_punctuation_aliases(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(lb,'DB_PATH',Path(tmp)/'db'):
   lb.record_played(['Alice'],'old-id','song:jay-z|empirestateofmind')
   room=dict(pool=[],used=[]);history(room,['Alice'])
   alternate=dict(id='new-id',artist='JAY Z',title='Empire State Of Mind - 2009 Remaster')
   self.assertTrue(c.song_was_played(alternate,room['_played_song_ids']))
   self.assertEqual(room['_artist_play_counts']['jayz'],1)
 def test_every_decade_boundary_is_preserved_without_network(self):
  rows=[dict(t,id=f'{year}-{t["id"]}',album_id=f'{year}-{t["id"]}',release_year=year,album_release_date=f'{year}-06-01') for year in range(1979,2031) for t in tracks(4,1)]
  with patch.object(s,'fetch',side_effect=AssertionError('dates already known')):
   for decade in s.DECADES:
    if decade=='All':continue
    start=int(decade[:4]);result=s.filter_decade(rows,decade)
    self.assertEqual(len(result),40)
    self.assertTrue(all(start<=t['release_year']<start+10 for t in result))
   sparse=[dict(t,language=str(i)) for i,t in enumerate(rows)];self.assertEqual(len(s.filter_decade(sparse,'2010s')),40)
 def test_artist_lookup_prefers_exact_name_over_punctuation_imposter(self):
  seed=dict(name='Eminem',country='US',region='North America',language='English',genre='Rap / Hip Hop')
  requests=[]
  def fetch(path):
   requests.append(path)
   if path.startswith('search/'):
    return {'data':[dict(id=9,name="Emine'm",nb_fan=9999),dict(id=13,name='Eminem',nb_fan=99)]}
   return {'data':[]}
  with patch.object(c,'SEEDS',[seed]):
   with self.assertRaises(ValueError):c.build_pool(fetch,s.clean,'Rap / Hip Hop','Worldwide','Easy')
  self.assertIn('artist/13/top?limit=100',requests)
  self.assertNotIn('artist/9/top?limit=100',requests)

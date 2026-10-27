import random,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import catalog as c, leaderboard as lb, server as s
from test_variety import HTTPGameTests, fixture_tracks

def tracks():
 return [dict(id=f'{language}-{i}',artist=f'{language} Artist {i}',artist_id=f'{language}-{i}',title=f'Song {i}',language=language,country=country,genre='Pop',preview='fixture',art='',link='') for language,country in [('Spanish','US'),('French','FR'),('English','GB')] for i in range(30)]

class SongBalanceTests(unittest.TestCase):
 def test_language_balance_random_and_artist_variety(self):
  for region in ('Europe','Worldwide'):
   for seed in range(150):
    random.seed(seed);r=dict(pool=tracks(),used=[],mode='guess',region=region,genre='Mixed',difficulty='Easy',rounds=10)
    selected=[]
    for _ in range(10):
     song=c.choose_song(r);r['used'].append(song['id']);selected.append(song)
    self.assertLessEqual(sum(t['language']=='Spanish' for t in selected),2)
    self.assertLessEqual(sum(t['language']=='French' for t in selected),2)
    self.assertLessEqual(sum(t['language'] in ('Spanish','French') for t in selected),3)
    self.assertEqual(len({t['artist_id'] for t in selected}),10)
 def test_nordic_preference_is_modest_and_not_a_quota(self):
  pool=[dict(id=f'{country}-{i}',artist_id=f'{country}-{i}',artist=f'A {country} {i}',title='Hit',country=country,language='English',genre='Pop') for country in ('SE','NO','GB','US') for i in range(30)]
  counts={'Europe':0,'Worldwide':0}
  for region in counts:
   for seed in range(1200):
    random.seed(seed);r=dict(pool=pool,used=[],mode='guess',region=region,genre='Mixed',rounds=10)
    if c.choose_song(r)['country'] in ('SE','NO'):counts[region]+=1
  self.assertGreater(counts['Europe'],counts['Worldwide']+50)
  self.assertGreater(counts['Europe'],500);self.assertLess(counts['Europe'],850)
 def test_unheard_track_is_not_removed_to_force_language_cap(self):
  pool=tracks();unheard={t['id'] for t in pool if t['language']=='French'}
  r=dict(pool=pool,used=[],mode='guess',region='Europe',genre='Mixed',rounds=10,language_counts={'French':2,'Spanish':1},_played_song_ids={t['id'] for t in pool}-unheard)
  with patch.object(c.random,'random',return_value=.99):
   self.assertIn(c.choose_song(r)['id'],unheard)
 def test_specialized_genres_are_not_limited(self):
  pool=[t for t in tracks() if t['language']=='Spanish'];r=dict(pool=pool,used=[],mode='guess',region='Worldwide',genre='Latin',rounds=10)
  for _ in range(10):
   song=c.choose_song(r);r['used'].append(song['id'])
  self.assertEqual(len(r['used']),10)
 def test_repeat_probability_and_fallback(self):
  pool=[t for t in tracks() if t['language']=='English'];seen={t['id'] for t in pool[:15]};r=dict(pool=pool,used=[],mode='guess',region='Worldwide',genre='Mixed',rounds=10,_played_song_ids=seen)
  counts=0
  for seed in range(3000):
   random.seed(seed);r.update(artist_counts={},country_counts={},language_counts={},recent_artists=[])
   if c.choose_song(r)['id'] in seen:counts+=1
  self.assertGreater(counts,200);self.assertLess(counts,360)
  r['_played_song_ids']={t['id'] for t in pool};self.assertIn(c.choose_song(r)['id'],r['_played_song_ids'])
 def test_same_song_different_provider_id_is_seen(self):
  original={'id':'one','artist':'The Artist','title':'The Song'};duplicate={'id':'two','artist':'The Artist','title':'The Song'}
  self.assertTrue(c.song_was_played(duplicate,c.song_history_keys(original)))
  self.assertFalse(c.song_was_played(dict(duplicate,title='Different'),c.song_history_keys(original)))
 def test_history_is_persistent_and_combines_players(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(lb,'DB_PATH',Path(directory)/'scores.sqlite3'):
   lb.record_played(['Alice'],'1');lb.record_played(['Bob'],'2');lb.record_played(['Alice','Bob'],'3')
   self.assertEqual(lb.played_song_ids(['alice']),{'1','3'})
   self.assertEqual(lb.played_song_ids(['Alice','Bob']),{'1','2','3'})
   self.assertEqual(lb.played_song_ids(['Someone']),set())

class ProfileIntegrationTests(HTTPGameTests):
 def test_history_records_start_and_handles_preloaded_round(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(lb,'DB_PATH',Path(folder)/'scores.sqlite3'),patch.object(s,'pool',return_value=fixture_tracks()),patch.object(s,'queue_youtube'),patch.object(s,'queue_prefetch'),patch.object(s,'queue_credit'):
   host=self.post('create',dict(mode='guess',multi=True,rounds=2,name='Alice'));guest=self.post('join',dict(room=host['room'],name='Bob'));view=self.post('next',host);room=s.rooms[host['room']];song=room['song']['id']
   self.assertIn(song,lb.played_song_ids(['alice']));self.assertIn(song,lb.played_song_ids(['bob']))
   self.post('guess',dict(**host,id=song,round=1,stage=0));self.post('guess',dict(**guest,id='',round=1,stage=0));self.post('next',host)
   self.assertEqual(len([x for x in lb.played_song_ids(['Alice','Bob']) if not x.startswith('song:')]),2);del s.rooms[host['room']]

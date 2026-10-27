import unittest,random
from unittest.mock import patch
import catalog as c
import recognition as rec
import server as s
import test_variety as fixtures

class HitsSelectionTests(unittest.TestCase):
 def test_every_hit_has_discovery_anchor(self):
  seeds={rec.text_key(t['name']) for t in c.SEEDS}
  self.assertTrue(set(rec.HOT_HITS)<=seeds)
  self.assertGreaterEqual(sum(map(len,rec.HOT_HITS.values())),150)
 def test_only_explicit_hits_are_selected(self):
  tracks=[dict(id=str(i),title='Hit '+str(i),artist='Artist '+str(i),artist_id=str(i),country='US',recognition=90,hot_hit=i<20) for i in range(40)]
  r=dict(pool=tracks,used=[],difficulty='Hits',rounds=10,region='Worldwide')
  for _ in range(20):
   t=c.choose_song(r);r['used'].append(t['id']);self.assertTrue(t['hot_hit'])
  self.assertEqual(len(r['artist_counts']),20)
 def test_famous_artist_does_not_qualify_every_song(self):
  self.assertTrue(rec.is_hot_hit('Queen','We Will Rock You'))
  self.assertFalse(rec.is_hot_hit('Queen','The Prophet\'s Song'))
  self.assertTrue(rec.is_hot_hit('Eminem','Without Me - 2002 Remaster'))
  def test_hits_are_a_separate_filter(self):
   self.assertTrue(rec.in_difficulty({'hot_hit':True,'recognition':78},'Hits'))
   self.assertFalse(rec.in_difficulty({'hot_hit':False,'recognition':94},'Hits'))

 def test_race_points_and_first_wins(self):
  from server import race_points, settle_race
  self.assertEqual([race_points(x,100) for x in [0,4.9,5,50,95,99.9,100]],[20,20,19,10,1,1,0])
  room=dict(pool=[],used=[],difficulty='Medium',rounds=3,region='Worldwide',mode='race',multi=False,
            players={'a':{'name':'A','score':0}},song={'id':'s1','artist_id':'x'},race_started=1000.0,deadline=1030.0,guesses={'a':'s1'},guess_times={'a':2.0})
  import server as s
  s.settle_race(room)
  self.assertEqual(room['phase'],'reveal');self.assertEqual(room['players']['a']['score'],19)
  room=dict(pool=[],used=[],difficulty='Medium',rounds=3,region='Worldwide',mode='race',multi=True,
            players={'a':{'name':'A','score':0},'b':{'name':'B','score':0}},song={'id':'s1','artist_id':'x'},race_started=1000.0,deadline=1030.0,
            guesses={'a':'s1','b':'s1'},guess_times={'a':9.0,'b':2.0})
  s.settle_race(room)
  self.assertEqual(room['winners'],['b']);self.assertEqual(room['players']['b']['score'],19);self.assertEqual(room['players']['a']['score'],0)

class HitsHTTPTests(fixtures.HTTPGameTests):
 def test_hits_preset_search_scoring_and_online(self):
  rows=fixtures.fixture_tracks()
  for t in rows:t.update(recognition=90,hot_hit=True)
  with patch.object(s,'pool',return_value=rows) as pool,patch.object(s,'credit',side_effect=lambda t:t):
   for multiplayer in (False,True):
    host=self.post('create',dict(mode='hits',multi=multiplayer,genre='Metal',region='Finland',difficulty='Impossible',rounds=1))
    pool.assert_called_with('Mixed','Worldwide','Hits')
    if multiplayer:self.post('next',host)
    room=s.rooms[host['room']];self.assertEqual(room['mode'],'hits')
    import urllib.request,json
    with urllib.request.urlopen(self.url+'search?room='+host['room']+'&token='+host['token']+'&q=Track') as response:
     self.assertTrue(json.load(response)['results'])
    view=self.post('guess',dict(**host,id=room['song']['id'],round=1,stage=0))
    self.assertEqual(view['phase'],'reveal');self.assertTrue(view['correct'])
    self.assertEqual(view['players'][0]['score'],1 if multiplayer else 5)
    view=self.post('next',host);self.assertEqual(view['phase'],'finished')
    del s.rooms[host['room']]

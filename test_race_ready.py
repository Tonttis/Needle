import unittest,time
import server as s
class RaceReadyTests(unittest.TestCase):
 def room(self):return dict(mode='race',phase='playing',race_started=None,deadline=0,guesses={},players={'a':{'score':0}},song={'id':'1'},history=[])
 def test_buffering_never_expires(self):
  r=self.room();s.settle_race(r);self.assertEqual(r['phase'],'playing')
 def test_full_duration_not_thirty_seconds(self):
  r=self.room();r.update(race_started=time.time()-40,deadline=time.time()+200)
  s.settle_race(r);self.assertEqual(r['phase'],'playing')
 def test_end_of_song_reveals(self):
  r=self.room();r.update(race_started=time.time()-240,deadline=time.time()-1)
  s.settle_race(r);self.assertEqual(r['phase'],'reveal')
 def test_correct_after_thirty_seconds_still_scores(self):
  r=self.room();r.update(race_started=time.time()-100,deadline=time.time()+100,guesses={'a':'1'},guess_times={'a':100})
  s.settle_race(r);self.assertEqual(r['players']['a']['score'],1)

from unittest.mock import patch
import test_variety as fixtures
class RaceHTTPTests(fixtures.HTTPGameTests):
 def test_all_players_ready_before_full_length_clock(self):
  with patch.object(s,'pool',return_value=fixtures.fixture_tracks()),patch.object(s,'queue_youtube'),patch.object(s,'credit',side_effect=lambda t:t):
   host=self.post('create',dict(mode='race',multi=True))
   guest=self.post('join',dict(room=host['room'],name='Guest'))
   view=self.post('next',host);room=s.rooms[host['room']]
   self.assertIsNone(view['race_started']);self.assertEqual(view['deadline'],0)
   room.update(race_status='ready',race_duration=245)
   view=self.post('race-ready',dict(**host,round=1));self.assertIsNone(view['race_started'])
   view=self.post('race-ready',dict(**guest,round=1));self.assertEqual(view['deadline']-view['race_started'],245)
   start=view['race_started']
   view=self.post('race-ready',dict(**host,round=1));self.assertEqual(view['race_started'],start)
   with patch.object(s.time,'time',return_value=start+100):
    view=self.post('guess',dict(**host,round=1,id=room['song']['id']))
   self.assertEqual(view['phase'],'reveal');self.assertTrue(view['correct'])
   del s.rooms[host['room']]
 def test_skip_failed_media(self):
  with patch.object(s,'pool',return_value=fixtures.fixture_tracks()),patch.object(s,'queue_youtube'),patch.object(s,'credit',side_effect=lambda t:t):
   host=self.post('create',dict(mode='race',multi=False));s.rooms[host['room']]['race_status']='error'
   view=self.post('race-skip',dict(**host,round=1));self.assertEqual(view['phase'],'reveal')
   del s.rooms[host['room']]
 def test_wrong_guesses_retry_after_cooldown_and_skip(self):
  import urllib.error
  with patch.object(s,'pool',return_value=fixtures.fixture_tracks()),patch.object(s,'queue_youtube'),patch.object(s,'credit',side_effect=lambda t:t):
   host=self.post('create',dict(mode='race',multi=False));room=s.rooms[host['room']]
   start=time.time()-20;room.update(race_started=start,race_status='playing',deadline=start+300)
   correct=room['song'];wrong=next(t for t in room['pool'] if t['id']!=correct['id'] and t['genre']==correct['genre'] and t['language']==correct['language'])
   with patch.object(s.time,'time',return_value=start+21):
    view=self.post('guess',dict(**host,round=1,id=wrong['id']))
    self.assertEqual(view['phase'],'playing');self.assertFalse(view['submitted']);self.assertEqual(view['race_cooldown_until'],start+26)
    with self.assertRaises(urllib.error.HTTPError):self.post('guess',dict(**host,round=1,id=correct['id']))
   with patch.object(s.time,'time',return_value=start+26):
    view=self.post('guess',dict(**host,round=1,id=correct['id']))
   self.assertEqual(view['phase'],'reveal');self.assertTrue(view['correct'])
   del s.rooms[host['room']]

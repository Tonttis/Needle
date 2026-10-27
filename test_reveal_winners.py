import unittest
from unittest.mock import patch
import server as s
import test_variety as fixtures
class RevealWinnerTests(fixtures.HTTPGameTests):
 def test_winner_list_all_modes_without_early_leak(self):
  for mode in ('guess','hits','choice','race'):
   with self.subTest(mode=mode),patch.object(s,'pool',return_value=fixtures.fixture_tracks()),patch.object(s,'queue_youtube'),patch.object(s,'queue_prefetch'),patch.object(s,'credit',side_effect=lambda t:t):
    host=self.post('create',dict(mode=mode,multi=True,name='Alice'))
    guest=self.post('join',dict(room=host['room'],name='Bob'))
    view=self.post('next',host);self.assertNotIn('correct_players',view)
    room=s.rooms[host['room']]
    if mode=='race':
     import time
     room.update(race_started=time.time()-1,deadline=time.time()+100,race_status='playing')
    a=self.post('guess',dict(**host,round=1,stage=0,id=room['song']['id']))
    if mode!='race':
     self.assertNotIn('correct_players',a)
     self.post('guess',dict(**guest,round=1,stage=0,id=''))
    view=s.state(room,guest['token']);self.assertEqual(view['correct_players'],['Alice']);self.assertFalse(view['correct']);self.assertEqual(view['result'],'skipped')
    del s.rooms[host['room']]
 def test_multiple_correct_players(self):
  with patch.object(s,'pool',return_value=fixtures.fixture_tracks()),patch.object(s,'credit',side_effect=lambda t:t):
   host=self.post('create',dict(mode='choice',multi=True,name='Alice'));guest=self.post('join',dict(room=host['room'],name='Bob'));self.post('next',host);room=s.rooms[host['room']]
   self.post('guess',dict(**host,round=1,stage=0,id=room['song']['id']));view=self.post('guess',dict(**guest,round=1,stage=0,id=room['song']['id']))
   self.assertEqual(view['correct_players'],['Alice','Bob']);self.assertTrue(view['correct']);del s.rooms[host['room']]

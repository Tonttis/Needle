import json,time,tempfile,pathlib,unittest
from concurrent.futures import Future
from unittest.mock import patch
import server as s
import test_variety as fixtures
class PreloadTests(fixtures.HTTPGameTests):
 def test_video_reservation_is_hidden_and_used_next(self):
  tracks=fixtures.fixture_tracks()
  with patch.object(s,'pool',return_value=tracks),patch.object(s,'queue_youtube'),patch.object(s,'queue_prefetch',return_value=Future()) as prefetch,patch.object(s,'credit',side_effect=lambda t:t):
   host=self.post('create',dict(mode='race',multi=False,rounds=2));room=s.rooms[host['room']]
   pending=room['_next_round'];self.assertEqual(prefetch.call_count,1);self.assertNotEqual(room['song']['id'],pending['song']['id'])
   view=s.state(room,host['token']);self.assertNotIn(pending['song']['id'],json.dumps({k:v for k,v in view.items() if k not in ('history',)}));self.assertNotIn('_next_round',view)
   room.update(race_started=time.time()-3,race_duration=100,deadline=time.time()+97,race_status='playing')
   self.post('guess',dict(**host,round=1,id=room['song']['id']))
   self.post('next',host);self.assertEqual(room['song']['id'],pending['song']['id']);self.assertIs(room['_current_prefetch'],pending['future'])
   del s.rooms[host['room']]
 def test_party_preloads_only_if_next_round_is_video(self):
  tracks=fixtures.fixture_tracks()
  def reverse(items):items.reverse()
  with patch.object(s,'pool',return_value=tracks),patch.object(s,'queue_youtube'),patch.object(s,'queue_prefetch',return_value=Future()) as prefetch,patch.object(s,'credit',side_effect=lambda t:t),patch.object(s.random,'shuffle',side_effect=reverse):
   host=self.post('create',dict(mode='party',party_modes=['guess','race'],multi=False,rounds=2));room=s.rooms[host['room']]
   self.assertEqual(room['mode'],'guess');self.assertEqual(room['_next_round']['selection']['mode'],'race');self.assertEqual(prefetch.call_count,1)
   self.post('guess',dict(**host,round=1,stage=0,id=room['song']['id']));self.post('next',host)
   self.assertEqual(room['mode'],'race');self.assertEqual(prefetch.call_count,1);del s.rooms[host['room']]
 def test_finished_prefetch_reused_and_failed_prefetch_retried(self):
  for fails in (False,True):
   with self.subTest(fails=fails),tempfile.TemporaryDirectory() as folder:
    path=pathlib.Path(folder)/'video.mp4';path.write_bytes(b'fixture');value=('abcdefghijk','title',str(path),123,'video/mp4');future=Future()
    if fails:future.set_exception(ValueError('blocked'))
    else:future.set_result(value)
    room={'code':'PREFETCH','audioKey':'key','song':{'id':'1','title':'title','artist':'artist'},'_current_prefetch':future,'race_audio_only':False,'phase':'playing'};s.rooms[room['code']]=room
    with patch.object(s,'fetch_race_media',return_value=value) as load:
     s.queue_youtube(room)
     deadline=time.monotonic()+3
     while room.get('race_status')=='buffering' and time.monotonic()<deadline:time.sleep(.01)
     self.assertEqual(room.get('race_status'),'ready');self.assertEqual(load.call_count,1 if fails else 0)
    del s.rooms[room['code']]

import unittest,urllib.request,urllib.error
from unittest.mock import patch
import server as s
from test_variety import HTTPGameTests,fixture_tracks

class DeezerRevealTests(HTTPGameTests):
 def test_reveal_uses_deezer_even_if_game_audio_is_youtube(self):
  with patch.dict(s.os.environ,{'AUDIO_SOURCE':'youtube'}),patch.object(s,'pool',return_value=fixture_tracks()),patch.object(s,'queue_credit'),patch.object(s,'read_preview',return_value=(b'preview','audio/mpeg')) as read:
   host=self.post('create',dict(mode='choice',multi=True,rounds=1));self.post('next',host);room=s.rooms[host['room']];key=room['audioKey']
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(self.url.replace('/api/','/')+'reveal-audio/'+key)
   self.post('guess',dict(**host,round=1,stage=0,id=room['song']['id']))
   with urllib.request.urlopen(self.url.replace('/api/','/')+'reveal-audio/'+key) as response:self.assertEqual(response.read(),b'preview')
   read.assert_called_once();del s.rooms[host['room']]
 def test_deezer_fallback_refreshes_expired_preview(self):
  with patch.object(s,'read_preview',side_effect=[OSError('expired'),(b'new','audio/mpeg')]),patch.object(s,'fetch',return_value={'preview':'https://fresh'}) as fetch:
   self.assertEqual(s.load_deezer_preview({'id':'123','preview':'expired'}),(b'new','audio/mpeg'));fetch.assert_called_once_with('track/123',fresh=True)

import json,unittest,urllib.request,urllib.error
from unittest.mock import patch
import server as s
import test_variety as fixtures
class InviteTests(fixtures.HTTPGameTests):
 def get(self,code):
  with urllib.request.urlopen(self.url+'invite?room='+code) as response:return json.load(response)
 def test_invite_details_and_room_lifecycle(self):
  with patch.object(s,'pool',return_value=fixtures.fixture_tracks()),patch.object(s,'credit',side_effect=lambda t:t):
   host=self.post('create',dict(mode='choice',multi=True,region='Europe',genre='Rock',difficulty='Easy',rounds=5,name='Host'))
   info=self.get(host['room'].lower());self.assertEqual((info['host'],info['mode'],info['rounds'],info['players']),('Host','choice',5,1));self.assertTrue(info['joinable']);self.assertNotIn('token',info);self.assertNotIn('song',info)
   guest=self.post('join',dict(room=host['room'],name='Friend'));self.assertEqual(self.get(host['room'])['players'],2)
   self.post('next',host);info=self.get(host['room']);self.assertFalse(info['joinable']);self.assertIn('started',info['reason'])
   with self.assertRaises(urllib.error.HTTPError):self.post('join',dict(room=host['room'],name='Late'))
   del s.rooms[host['room']]
   with self.assertRaises(urllib.error.HTTPError) as missing:self.get(host['room'])
   self.assertEqual(missing.exception.code,404)
 def test_full_room_is_not_joinable(self):
  with patch.object(s,'pool',return_value=fixtures.fixture_tracks()):
   host=self.post('create',dict(mode='guess',multi=True));room=s.rooms[host['room']]
   for i in range(7):room['players'][str(i)]={'name':str(i),'score':0}
   info=self.get(host['room']);self.assertFalse(info['joinable']);self.assertIn('full',info['reason']);del s.rooms[host['room']]

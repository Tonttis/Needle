import unittest, urllib.error
from unittest.mock import patch
import server as s
from test_variety import HTTPGameTests, fixture_tracks

class LobbyRematchTests(HTTPGameTests):
 def test_rematch_settings_and_authorization(self):
  with patch.object(s,'pool',return_value=fixture_tracks()),patch.object(s,'credit',side_effect=lambda t:t):
   host=self.post('create',dict(mode='guess',multi=True,rounds=1,region='Europe',genre='Rock',name='Host'))
   guest=self.post('join',dict(room=host['room'],name='Guest'))
   self.post('next',host);room=s.rooms[host['room']];answer=room['song']['id']
   for player in [host,guest]: self.post('guess',dict(**player,id=answer,round=1,stage=0))
   self.assertEqual(self.post('next',host)['phase'],'finished')
   view=self.post('lobby',host);self.assertEqual(view['phase'],'lobby');self.assertEqual(len(view['players']),2);self.assertEqual(room['used'],[])
   settings=dict(mode='choice',genre='Rock',region='Europe',difficulty='Easy',decade='All',rounds=5,party_modes=[])
   with self.assertRaises(urllib.error.HTTPError): self.post('settings',dict(**guest,**settings))
   view=self.post('settings',dict(**host,**settings));self.assertEqual((view['mode'],view['rounds']),('choice',5))
   self.assertEqual(self.post('next',host)['phase'],'playing')
   with self.assertRaises(urllib.error.HTTPError): self.post('settings',dict(**host,**settings))
   self.assertEqual(len(room['players']),2);del s.rooms[host['room']]

import json,unittest,urllib.request,urllib.error
from unittest.mock import patch
import server as s
from test_variety import HTTPGameTests,fixture_tracks

class NameRequirementTests(HTTPGameTests):
 def raw_post(self,path,data):
  req=urllib.request.Request(self.url+path,json.dumps(data).encode(),{'Content-Type':'application/json'})
  with urllib.request.urlopen(req) as response:return json.load(response)
 def assert_bad(self,path,data):
  with self.assertRaises(urllib.error.HTTPError) as exc:self.raw_post(path,data)
  self.assertEqual(exc.exception.code,400)
  self.assertIn('name',json.load(exc.exception)['error'].lower())
 def test_missing_and_invisible_names_rejected_before_expensive_preparation(self):
  with patch.object(s,'pool',side_effect=AssertionError('must validate first')),patch.object(s.boards,'daily_existing',side_effect=AssertionError('must validate first')):
   for name in (None,'','  ','\u200b\u200d',123,'x'*25):
    for mode in ('guess','choice','race','hits','party'):
     self.assert_bad('create',{'mode':mode,'name':name})
    self.assert_bad('daily-create',{'name':name})
   self.assert_bad('create',{'mode':'guess'});self.assert_bad('daily-create',{})
 def test_all_modes_and_join_accept_trimmed_name(self):
  tracks=fixture_tracks();report={'matched':len(tracks),'total':len(tracks)}
  with patch.object(s,'pool',return_value=tracks),patch.object(s,'playlist_pool',return_value=(tracks,report)),patch.object(s,'queue_youtube'),patch.object(s,'queue_prefetch'),patch.object(s,'queue_credit'):
   for mode in ('guess','choice','race','hits','party'):
    body={'name':'  Listener  ','mode':mode,'multi':True,'party_modes':['guess','choice']}
    host=self.raw_post('create',body);room=s.rooms[host['room']];self.assertEqual(room['players'][host['token']]['name'],'Listener')
    for bad in ('','   ',None,'\u200b'):self.assert_bad('join',{'room':host['room'],'name':bad})
    self.assert_bad('join',{'room':host['room']})
    guest=self.raw_post('join',{'room':host['room'],'name':'  Friend  '});self.assertEqual(room['players'][guest['token']]['name'],'Friend');del s.rooms[host['room']]
   playlist=self.raw_post('create',{'name':'DJ','mode':'choice','multi':True,'playlist_url':'https://example.test/list'})
   self.assertEqual(s.rooms[playlist['room']]['players'][playlist['token']]['name'],'DJ');del s.rooms[playlist['room']]
 def test_daily_requires_and_preserves_trimmed_name(self):
  tracks=fixture_tracks();ids=[t['id'] for t in tracks[:5]]
  with patch.object(s.boards,'daily_existing',return_value=(tracks,ids)),patch.object(s,'queue_credit'):
   player=self.raw_post('daily-create',{'name':'   Daily DJ   '});self.assertEqual(s.rooms[player['room']]['players'][player['token']]['name'],'Daily DJ');del s.rooms[player['room']]

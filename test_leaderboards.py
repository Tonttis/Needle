import json,tempfile,unittest,urllib.request
from pathlib import Path
from unittest.mock import patch
import leaderboard as lb
import server as s
from test_variety import HTTPGameTests,fixture_tracks

class ScorePersistenceTests(unittest.TestCase):
 def test_persistence_best_per_name_and_filters(self):
  with tempfile.TemporaryDirectory() as directory, patch.object(lb,'DB_PATH',Path(directory)/'scores.sqlite3'):
   def finish(match,name,points,mode='guess',difficulty='Easy',daily=None):
    lb.record_match(dict(match_id=match,players={'token':dict(name=name,score=points)},score_max=25,rounds=5,mode=mode,base_difficulty=difficulty,daily_date=daily))
   finish('a','Alex',10);finish('b','alex',20);finish('c','Alex',25,'choice');finish('d','Bob',15)
   result=lb.leaderboard('guess','Easy',False)
   self.assertEqual([(v['name'],v['points']) for v in result],[('alex',20),('Bob',15)])
   self.assertEqual(lb.profile('Alex')['games'],3)
   self.assertEqual(len(lb.leaderboard('choice','Easy',False)),1)
   self.assertEqual(lb.leaderboard('guess','Hard',False),[])
   self.assertTrue(lb.DB_PATH.exists())
 def test_daily_snapshot_persists_exact_order(self):
  with tempfile.TemporaryDirectory() as directory, patch.object(lb,'DB_PATH',Path(directory)/'scores.sqlite3'):
   tracks=fixture_tracks();a=lb.daily_snapshot('2026-10-27',tracks)
   self.assertEqual(len(a[1]),5);self.assertEqual(a,lb.daily_snapshot('2026-10-27',[]));self.assertEqual(a,lb.daily_existing('2026-10-27'))

class DailyHTTPTests(HTTPGameTests):
 def test_daily_play_score_and_snapshot_after_restart(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(lb,'DB_PATH',Path(directory)/'scores.sqlite3'),patch.object(s,'pool',return_value=fixture_tracks()),patch.object(s,'credit',side_effect=lambda t:t),patch.object(s,'queue_credit'):
   a=self.post('daily-create',{'name':'Alice'});b=self.post('daily-create',{'name':'Bob'})
   room=s.rooms[a['room']];other=s.rooms[b['room']];self.assertEqual(room['daily_ids'],other['daily_ids'])
   for i in range(5):
    room=s.rooms[a['room']];self.assertEqual(room['song']['id'],other['daily_ids'][i]);self.post('guess',dict(**a,id=room['song']['id'],round=i+1,stage=0));result=self.post('next',a)
   self.assertEqual(result['phase'],'finished');self.assertEqual(result['players'][0]['score'],25)
   self.assertEqual(lb.leaderboard('guess','Easy',False,lb.day_utc())[0]['percentage'],100)
   self.assertEqual(lb.profile('Alice')['games'],1)
   self.assertEqual(lb.daily_existing(lb.day_utc())[1],other['daily_ids'])
   del s.rooms[a['room']];del s.rooms[b['room']]

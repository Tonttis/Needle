import json,os,sqlite3,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
import catalog as c,leaderboard as lb,server as server
from test_variety import HTTPGameTests

class PickerAuditTests(unittest.TestCase):
 def track(self,ident,artist,title,language='English',country='GB'):
  return dict(id=ident,artist_id=artist,artist=artist,title=title,language=language,country=country,genre='Pop',preview='fixture',art='',link='',recognition=90)
 def test_duplicate_release_not_repeated_within_game(self):
  one=self.track('1','Artist','One');alternate=self.track('2','Artist','One');other=self.track('3','Other','Other');r=dict(pool=[one,alternate,other],used=['1'],mode='guess',region='Worldwide',genre='Mixed',difficulty='Easy',rounds=5)
  self.assertEqual(c.choose_song(r)['id'],'3')
 def test_mixed_language_options_fallback_to_other_lanes(self):
  song=self.track('1','A','One','French','FR');pool=[song]+[self.track(str(i),str(i),str(i),'English','GB') for i in range(2,6)]
  _,options=c.round_choices(song,pool);self.assertEqual(len(options),4);self.assertEqual(len({x['id'] for x in options}),4);self.assertIn('1',{x['id'] for x in options})
 def test_too_few_distinct_options_do_not_crash(self):
  song=self.track('1','A','One');_,options=c.round_choices(song,[song,self.track('2','B','Two')]);self.assertEqual(len(options),2)
 def test_daily_preserves_snapshot_and_avoids_overweighting_large_discography(self):
  from collections import Counter
  pool=[]
  for i in range(10):
   for j in range(100 if i==0 else 1):pool.append(self.track(f'{i}-{j}',f'Artist {i}',f'Song {j}'))
  counts=Counter()
  with tempfile.TemporaryDirectory() as tmp,patch.object(lb,'DB_PATH',Path(tmp)/'scores.sqlite3'):
   for day in range(100):
    _,ids=lb.daily_snapshot(f'2026-{day:03}',pool)
    counts['large']+=sum(i.startswith('0-') for i in ids)
   self.assertGreater(counts['large'],30);self.assertLess(counts['large'],70)

class UploadedCatalogTests(unittest.TestCase):
 def test_existing_cache_is_readable_by_app(self):
  source=Path(os.environ.get('NEEDLE_TEST_DATABASES','__no_uploaded_files__'))/'catalog-cache.sqlite'
  if not source.exists():self.skipTest('No uploaded database')
  with tempfile.TemporaryDirectory() as tmp:
   dst=Path(tmp)/'catalog-cache.sqlite'
   with sqlite3.connect(f'file:{source}?mode=ro',uri=True) as src,sqlite3.connect(dst) as out:src.backup(out)
   with sqlite3.connect(dst) as db:path,saved,body=db.execute('select path,saved,body from responses order by saved desc limit 1').fetchone()
   with patch.object(server,'DATA',Path(tmp)),patch.object(server.time,'time',return_value=saved+1),patch.object(server.urllib.request,'urlopen',side_effect=AssertionError('network unnecessary')):
    server.cache.pop(path,None)
    self.assertEqual(server._fetch(path),json.loads(body))
    server.cache.pop(path,None)

class ClearHistoryHTTPTests(HTTPGameTests):
 def test_clear_only_requested_history_and_preserves_scores(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(lb,'DB_PATH',Path(tmp)/'scores.sqlite3'):
   lb.record_played(['Alice'],'11','song:a|b');lb.record_played(['Bob'],'12')
   lb.record_match(dict(match_id='x',players={'t':dict(name='Alice',score=1)},score_max=1,rounds=1,mode='guess',base_difficulty='Easy'))
   result=self.post('clear-history',{'name':'  ALICE  '});self.assertEqual(result['cleared'],2)
   self.assertEqual(lb.played_song_ids(['Alice']),set());self.assertEqual(lb.played_song_ids(['Bob']),{'12'});self.assertEqual(lb.profile('Alice')['games'],1)
   with self.assertRaises(urllib.error.HTTPError):self.post('clear-history',{'name':' '})
 def test_uploaded_database_copy_preserves_scores_and_daily(self):
  source=Path(os.environ.get('NEEDLE_TEST_DATABASES','__no_uploaded_files__'))/'needle-scores.sqlite3'
  if not source.exists():self.skipTest('No uploaded database')
  with tempfile.TemporaryDirectory() as tmp:
   dst=Path(tmp)/'copy.sqlite3'
   with sqlite3.connect(f'file:{source}?mode=ro',uri=True) as src,sqlite3.connect(dst) as out:src.backup(out)
   with patch.object(lb,'DB_PATH',dst):
    with lb.connection() as db:before=(db.execute('select count(*) from scores').fetchone()[0],db.execute('select count(*) from daily_challenges').fetchone()[0])
    lb.record_played(['temporary test account'],'test');self.assertEqual(lb.clear_played('TEMPORARY TEST ACCOUNT'),1)
    with lb.connection() as db:after=(db.execute('select count(*) from scores').fetchone()[0],db.execute('select count(*) from daily_challenges').fetchone()[0]);self.assertEqual(db.execute('pragma integrity_check').fetchone()[0],'ok')
    self.assertEqual(before,after)

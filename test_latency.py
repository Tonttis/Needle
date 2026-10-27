import time,unittest
from unittest.mock import patch
import server as s
from test_variety import fixture_tracks,HTTPGameTests
class LatencyTests(HTTPGameTests):
 def test_slow_provider_cannot_block_search_or_start_round(self):
  with patch.object(s,'pool',return_value=fixture_tracks()),patch.object(s,'credit',side_effect=lambda t:(time.sleep(.3),t)[1]):
   start=time.monotonic();host=self.post('create',dict(mode='guess',multi=False,region='Europe',rounds=10));elapsed=time.monotonic()-start
   self.assertLess(elapsed,.25)
   import urllib.request,json
   start=time.monotonic()
   with urllib.request.urlopen(self.url+'search?room='+host['room']+'&token='+host['token']+'&q=Track') as r:result=json.load(r)
   self.assertLess(time.monotonic()-start,.25);self.assertLessEqual(len(result['results']),25)
   room=s.rooms[host['room']]
   self.post('guess',dict(**host,id=room['song']['id'],round=1,stage=0))
   start=time.monotonic();view=self.post('next',host)
   self.assertLess(time.monotonic()-start,.25);self.assertEqual(view['round'],2)
   # Drain the controlled worker tasks before releasing the mock.
   while s.credit_pending:time.sleep(.02)
   del s.rooms[host['room']]

class AudioCacheTests(unittest.TestCase):
 def test_parallel_listeners_share_download(self):
  from audio_cache import AudioCache
  from concurrent.futures import ThreadPoolExecutor
  calls=[]
  def load(song):calls.append(song);time.sleep(.03);return (b'audio','audio/mpeg')
  cache=AudioCache(load)
  with ThreadPoolExecutor(max_workers=8) as workers:
   results=list(workers.map(lambda _:cache.get('track',{}),range(8)))
  self.assertEqual(len(calls),1);self.assertTrue(all(r[0]==b'audio' for r in results));cache.workers.shutdown()
 def test_cache_bounds_and_failure_recovery(self):
  from audio_cache import AudioCache
  def load(song):
   if song=='bad':raise ValueError('fail')
   return (b'12345','audio/mpeg')
  cache=AudioCache(load,max_bytes=5)
  with self.assertRaises(ValueError):cache.get('bad','bad')
  cache.get('a','ok');cache.get('b','ok');self.assertEqual(cache.bytes,5);self.assertEqual(list(cache.items),['b']);cache.workers.shutdown()

class FullCatalogCacheTests(unittest.TestCase):
 def test_full_catalog_reused_and_persisted_without_trimming(self):
  import tempfile,pathlib
  rows=fixture_tracks();key=('Rock','Europe','Normal')
  with tempfile.TemporaryDirectory() as folder,patch.object(s,'DATA',pathlib.Path(folder)),patch.object(s,'build_pool',return_value=rows) as builder:
   s.catalog_jobs.clear();s.catalog_started.clear()
   first=s.prepare_catalog(*key);second=s.prepare_catalog(*key)
   self.assertIs(first,second);self.assertEqual(len(first.result(timeout=5)),len(rows))
   self.assertEqual(len(s.pool(*key)),len(rows));self.assertEqual(builder.call_count,1)
   s.catalog_jobs.clear();s.catalog_started.clear()
   self.assertEqual(len(s.pool(*key)),len(rows));self.assertEqual(builder.call_count,1)
   s.catalog_jobs.clear();s.catalog_started.clear()

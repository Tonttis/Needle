import json,tempfile,threading,unittest,time
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import patch
import server as s
from test_variety import fixture_tracks

class CatalogRotationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=patch.object(s,'DATA',Path(self.tmp.name));self.data.start()
  s.catalog_jobs.clear();s.catalog_started.clear();s.catalog_status.clear();s.catalog_tokens.clear();s.catalog_accessed.clear()
  self.key=('Mixed','Europe','Easy','All')
 def tearDown(self):
  s.catalog_jobs.clear();s.catalog_started.clear();s.catalog_status.clear();s.catalog_tokens.clear();s.catalog_accessed.clear();self.data.stop();self.tmp.cleanup()
 def test_startup_discards_only_known_mix_files(self):
  path=s.catalog_cache_path(self.key);path.write_text('old');legacy=s.DATA/'pool-full-12345678901234567890.json';legacy.write_text('old');temp=path.with_name(path.name+'.abcdef123456.tmp');temp.write_text('partial');oldv=s.DATA/'pool-v8-hits-1-12345678901234567890.json';oldv.write_text('old')
  protected=['needle-scores.sqlite3','catalog-cache.sqlite','pool-my-custom.json'];[ (s.DATA/p).write_text('keep') for p in protected ]
  self.assertEqual(s.discard_saved_mixes(),4);self.assertFalse(oldv.exists());self.assertFalse(path.exists());self.assertFalse(legacy.exists());self.assertFalse(temp.exists())
  for name in protected:self.assertEqual((s.DATA/name).read_text(),'keep')
 def test_refresh_serves_old_until_replacement_ready(self):
  old=fixture_tracks()[:8];new=fixture_tracks()[8:20];started=threading.Event();release=threading.Event()
  ready=Future();ready.set_result(old);s.catalog_jobs[self.key]=ready;s.catalog_started[self.key]=1
  def build(*args,**kwargs):started.set();release.wait(5);return new
  with patch.object(s,'build_pool',side_effect=build):
   thread=threading.Thread(target=s.refresh_catalog,args=(self.key,));thread.start();self.assertTrue(started.wait(2))
   self.assertEqual(s.pool(*self.key),old);release.set();thread.join(5);self.assertFalse(thread.is_alive())
   self.assertEqual(s.pool(*self.key),new);self.assertEqual(json.loads(s.catalog_cache_path(self.key).read_text()),new)
 def test_failure_keeps_old_available(self):
  old=fixture_tracks()[:8];ready=Future();ready.set_result(old);s.catalog_jobs[self.key]=ready
  with patch.object(s,'build_pool',side_effect=ValueError('offline')):
   with self.assertRaises(ValueError):s.refresh_catalog(self.key)
   self.assertIs(s.catalog_jobs[self.key],ready);self.assertEqual(s.pool(*self.key),old)
 def test_refresh_does_not_override_newer_generation(self):
  old=Future();old.set_result([{'id':'old'}]);s.catalog_jobs[self.key]=old
  newer=Future();newer.set_result([{'id':'newer'}])
  def build(*args,**kwargs):s.catalog_jobs[self.key]=newer;return [{'id':'obsolete'}]
  with patch.object(s,'build_pool',side_effect=build):self.assertFalse(s.refresh_catalog(self.key))
  self.assertIs(s.catalog_jobs[self.key],newer);self.assertFalse(s.catalog_cache_path(self.key).exists())
 def test_scheduled_refresh_and_stale_retirement(self):
  class OneTick:
   def __init__(self):self.count=0
   def is_set(self):return False
   def wait(self,_):self.count+=1;return self.count>1
  old=Future();old.set_result([{'id':'old'}]);s.catalog_jobs[self.key]=old;s.catalog_started[self.key]=time.time()-s.CATALOG_ROTATE_SECONDS-1;s.catalog_accessed[self.key]=time.time()
  idle=('Rock','Worldwide','Medium','All');idlejob=Future();idlejob.set_result([{'id':'idle'}]);s.catalog_jobs[idle]=idlejob;s.catalog_started[idle]=time.time()-90000;s.catalog_accessed[idle]=time.time()-90000;s.catalog_cache_path(idle).write_text('old')
  with patch.object(s,'build_pool',return_value=[{'id':'fresh'}]),patch.object(s,'CATALOG_BOOTSTRAP',()):s.catalog_rotation_loop(OneTick())
  self.assertEqual(s.catalog_jobs[self.key].result(),[{'id':'fresh'}]);self.assertNotIn(idle,s.catalog_jobs);self.assertFalse(s.catalog_cache_path(idle).exists())
 def test_bootstrap_warms_sequentially_and_continues_on_error(self):
  event=threading.Event();keys=[]
  def prepare(*key):
   keys.append(key);f=Future()
   if len(keys)==1:f.set_exception(ValueError('offline'))
   else:f.set_result([])
   if len(keys)==len(s.CATALOG_BOOTSTRAP):event.set()
   return f
  with patch.object(s,'prepare_catalog',side_effect=prepare):s.catalog_rotation_loop(event)
  self.assertEqual(keys,list(s.CATALOG_BOOTSTRAP))

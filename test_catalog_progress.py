import json,tempfile,pathlib,threading,unittest,urllib.request
from unittest.mock import patch
import server as s
import test_variety as fixture
class CatalogProgressTests(fixture.HTTPGameTests):
 def test_discovery_is_shared_and_reports_progress(self):
  start=threading.Event();finish=threading.Event()
  def build(fetch,clean,genre,region,difficulty,progress=None):
   progress('artists',7,80);start.set();finish.wait(4);return fixture.fixture_tracks()
  with tempfile.TemporaryDirectory() as folder,patch.object(s,'DATA',pathlib.Path(folder)),patch.object(s,'build_pool',side_effect=build):
   s.catalog_jobs.clear();s.catalog_started.clear();s.catalog_status.clear();s.catalog_tokens.clear()
   try:
    token=self.post('catalog-prepare',dict(genre='Mixed',region='Europe',difficulty='Easy',decade='All'))['job'];self.assertTrue(start.wait(2))
    with urllib.request.urlopen(self.url+'catalog-status?job='+token) as response:status=json.load(response)
    self.assertEqual((status['phase'],status['completed'],status['total']),('artists',7,80))
    self.assertEqual(self.post('catalog-prepare',dict(genre='Mixed',region='Europe',difficulty='Easy',decade='All'))['job'],token)
    finish.set()
    with s.catalog_guard:job=s.catalog_jobs[('Mixed','Europe','Easy','All')]
    job.result(timeout=4)
    with urllib.request.urlopen(self.url+'catalog-status?job='+token) as response:status=json.load(response)
    self.assertEqual(status['phase'],'ready')
   finally:finish.set();s.catalog_jobs.clear();s.catalog_started.clear();s.catalog_status.clear();s.catalog_tokens.clear()

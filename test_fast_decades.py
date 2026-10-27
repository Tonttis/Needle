import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import server as s

class FastDecadeTests(unittest.TestCase):
 def rows(self):
  return [dict(id=f't{i}',artist_id=f'{i//20}',album_id=f'a{i}',language='English',recognition=90) for i in range(100)]
 def test_artist_album_batches_cover_full_pool_and_fallback(self):
  calls=[]
  def fake_fetch(path):
   calls.append(path)
   if path.startswith('artist/'):
    artist=int(path.split('/')[1]);return {'data':[dict(id=f'a{i}',release_date='2014-03-01') for i in range(artist*20,artist*20+19)]}
   return {'release_date':'2018-02-01'}
  progress=[]
  with patch.object(s,'fetch',side_effect=fake_fetch):result=s.filter_decade(self.rows(),'2010s',lambda *x:progress.append(x))
  self.assertEqual(len(result),100)
  self.assertEqual(len(calls),10) # five artist pages and five exact fallbacks
  self.assertEqual(progress[-1],('dates',100,100))
 def test_errors_and_unknown_dates_do_not_guess(self):
  calls=[]
  def fake_fetch(path):
   calls.append(path)
   if path.startswith('artist/'):raise ValueError('provider unavailable')
   return {'release_date':'2017-01-01'} if path in {'album/a0','album/a1','album/a2','album/a3'} else {}
  with patch.object(s,'fetch',side_effect=fake_fetch):result=s.filter_decade(self.rows(),'2010s')
  self.assertEqual({t['id'] for t in result},{'t0','t1','t2','t3'})
 def test_prefetched_album_date_avoids_network(self):
  rows=[dict(t,album_release_date='2013-01-01') for t in self.rows()]
  with patch.object(s,'fetch',side_effect=AssertionError('unnecessary request')):self.assertEqual(len(s.filter_decade(rows,'2010s')),100)
 def test_dated_pool_reuses_completed_base_catalog(self):
  rows=self.rows()
  with tempfile.TemporaryDirectory() as tmp,patch.object(s,'DATA',Path(tmp)),patch.object(s,'build_pool',return_value=rows) as build,patch.object(s,'filter_decade',return_value=[dict(t,release_year=2014) for t in rows]):
   s.catalog_jobs.clear();s.catalog_started.clear();s.catalog_status.clear();s.catalog_tokens.clear()
   try:
    s.prepare_catalog('Mixed','Europe','Easy','All').result(timeout=3)
    s.prepare_catalog('Mixed','Europe','Easy','2010s').result(timeout=3)
    self.assertEqual(build.call_count,1)
   finally:s.catalog_jobs.clear();s.catalog_started.clear();s.catalog_status.clear();s.catalog_tokens.clear()

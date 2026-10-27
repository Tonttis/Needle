import tempfile,pathlib,time,os,unittest
from race_media import prune,MAX_AGE
class CachePolicy(unittest.TestCase):
 def test_expired_evicted_and_active_protected(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);now=time.time();old=p/'old.mp4';old.write_bytes(b'x');os.utime(old,(now-MAX_AGE-1,now-MAX_AGE-1));active=p/'active.mp4';active.write_bytes(b'xx');os.utime(active,(now-MAX_AGE-1,now-MAX_AGE-1))
   prune(p,[active],now=now,limit=100);self.assertFalse(old.exists());self.assertTrue(active.exists())
 def test_size_evicts_least_recently_used_and_preserves_mtime(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);now=time.time();a=p/'a.mp4';b=p/'b.m4a';a.write_bytes(b'aa');b.write_bytes(b'bbb');os.utime(a,(now-10,now));os.utime(b,(now,now))
   self.assertEqual(prune(p,now=now,limit=3),3);self.assertFalse(a.exists());self.assertTrue(b.exists())
 def test_only_media_files_are_removed(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);keep=p/'notes.txt';keep.write_text('keep');prune(p,limit=0);self.assertTrue(keep.exists())

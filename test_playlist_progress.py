import unittest,threading,json,urllib.request
from unittest.mock import patch
import server as s
import test_variety as fixture
class ProgressTests(fixture.HTTPGameTests):
 def test_background_progress_and_ready(self):
  started=threading.Event();finish=threading.Event();tracks=fixture.fixture_tracks();url='https://youtube.com/playlist?list=PLprogress0123'
  def build(url,fetch,clean,progress):
   progress('matching',2,10);started.set();finish.wait(4);progress('matching',10,10)
   return tracks,{'matched':10,'total':10}
  with patch.object(s,'match_playlist',side_effect=build):
   try:
    token=self.post('playlist-prepare',{'url':url})['job'];self.assertTrue(started.wait(2))
    with urllib.request.urlopen(self.url+'playlist-status?job='+token) as response:status=json.load(response)
    self.assertEqual((status['phase'],status['completed'],status['total']),('matching',2,10))
    finish.set()
    with s.playlist_guard:job=s.playlist_jobs[(url,'All')]
    job.result(timeout=4)
    with urllib.request.urlopen(self.url+'playlist-status?job='+token) as response:status=json.load(response)
    self.assertEqual((status['phase'],status['matched']),('ready',10))
    reused,other=s.prepare_playlist(url);self.assertIs(job,other);self.assertEqual(reused,token)
   finally:finish.set()
 def test_failure_is_reported_without_waiting_forever(self):
  url='https://youtube.com/playlist?list=PLfailure0123'
  with patch.object(s,'match_playlist',side_effect=ValueError('Provider unavailable')):
   token=self.post('playlist-prepare',{'url':url})['job']
   with s.playlist_guard:job=s.playlist_jobs[(url,'All')]
   with self.assertRaises(ValueError):job.result(timeout=4)
   with urllib.request.urlopen(self.url+'playlist-status?job='+token) as response:status=json.load(response)
   self.assertEqual(status['phase'],'error');self.assertEqual(status['error'],'Provider unavailable')

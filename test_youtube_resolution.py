import unittest, subprocess
from unittest.mock import patch
import server
class YoutubeResolutionTest(unittest.TestCase):
 def test_search_invokes_subprocess_without_conflicting_capture_options(self):
  server.youtube_mem.clear()
  def run(*args,**kwargs):
   self.assertNotIn('stdout',kwargs);self.assertNotIn('stderr',kwargs)
   self.assertIn('--js-runtimes',args[0]);return subprocess.CompletedProcess(args[0],0,'abcdefghijk\nTitle\n','')
  with patch.object(server.subprocess,'run',side_effect=run):
   self.assertEqual(server.resolve_youtube('Unique Test Artist','Unique Test Song'),('abcdefghijk','Title'))

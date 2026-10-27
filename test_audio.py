import unittest
from unittest.mock import patch, MagicMock
import server as s

class PreviewRecoveryTests(unittest.TestCase):
 def test_expired_url_refreshes_same_track(self):
  with patch.dict(s.os.environ,{'AUDIO_SOURCE':'preview'}),patch.object(s,'read_preview',side_effect=[OSError('403'),(b'mp3','audio/mpeg')]) as read,patch.object(s,'fetch',return_value={'preview':'https://fresh'}) as fetch:
   self.assertEqual(s.load_audio({'id':'123','preview':'https://expired'}),(b'mp3','audio/mpeg'))
   fetch.assert_called_once_with('track/123',fresh=True)
   self.assertEqual(read.call_args.args,('https://fresh',))
 def test_healthy_preview_does_not_fetch_metadata(self):
  with patch.dict(s.os.environ,{'AUDIO_SOURCE':'preview'}),patch.object(s,'read_preview',return_value=(b'mp3','audio/mpeg')),patch.object(s,'fetch') as fetch:
   s.load_audio({'id':'123','preview':'https://valid'});fetch.assert_not_called()
 def test_failed_recovery_has_actionable_error(self):
  with patch.dict(s.os.environ,{'AUDIO_SOURCE':'preview'}),patch.object(s,'read_preview',side_effect=OSError('403')),patch.object(s,'fetch',return_value={'preview':''}):
   with self.assertRaisesRegex(ValueError,'unavailable from the music provider'):
    s.load_audio({'id':'123','preview':'https://expired'})
 def test_rejects_html_and_empty_audio(self):
  for content,data in [('text/html',b'<html>'),('audio/mpeg',b'')]:
   response=MagicMock();response.headers={'Content-Type':content};response.read.return_value=data
   with patch.object(s.urllib.request,'urlopen') as op:
    op.return_value.__enter__.return_value=response
    with self.assertRaisesRegex(ValueError,'invalid audio'):s.read_preview('https://example.com/preview')

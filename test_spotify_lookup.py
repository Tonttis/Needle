import io,json,unittest,urllib.parse
from unittest.mock import patch
import spotify_lookup as sp
class Response(io.BytesIO):
 def __enter__(self):return self
 def __exit__(self,*args):self.close()
class SpotifyTests(unittest.TestCase):
 def setUp(self):sp._matches.clear();sp._token.update(value='',expires=0)
 def test_client_credentials_search_and_exact_match(self):
  good='0123456789ABCDEFGHIJKL';bad='ZYXWVUTSRQPONMLKJIHGFE'
  payload={'tracks':{'items':[{'id':bad,'name':'Song','artists':[{'name':'Different'}]},{'id':good,'name':'Song','artists':[{'name':'Artist'}]}]}}
  with patch.dict(sp.os.environ,{'SPOTIFY_CLIENT_ID':'client','SPOTIFY_CLIENT_SECRET':'secret'},clear=True),patch.object(sp.urllib.request,'urlopen',side_effect=[Response(b'{"access_token":"token","expires_in":3600}'),Response(json.dumps(payload).encode())]) as fetch:
   result=sp.resolve('Artist','Song');self.assertEqual(result['spotify_id'],good);self.assertEqual(result['spotify_url'],'https://open.spotify.com/track/'+good)
   self.assertEqual(sp.resolve('Artist','Song'),result);self.assertEqual(fetch.call_count,2)
   request=fetch.call_args.args[0];self.assertTrue(request.full_url.startswith('https://api.spotify.com/v1/search?'));self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)['market'],['FI'])
 def test_wrong_artist_or_title_is_never_used(self):
  for title,artist in [('Wrong','Artist'),('Song','Not Artist')]:
   payload={'tracks':{'items':[{'id':'0123456789ABCDEFGHIJKL','name':title,'artists':[{'name':artist}]}]}}
   with patch.object(sp,'search_token',return_value='token'),patch.object(sp.urllib.request,'urlopen',return_value=Response(json.dumps(payload).encode())):
    with self.assertRaisesRegex(ValueError,'No matching Spotify'):sp.resolve('Artist','Song')
 def test_missing_credentials_and_network_failure_are_explicit(self):
  with patch.dict(sp.os.environ,{},clear=True):
   with self.assertRaisesRegex(ValueError,'SPOTIFY_CLIENT_ID'):sp.resolve('Artist','Song')
  with patch.object(sp,'search_token',return_value='token'),patch.object(sp.urllib.request,'urlopen',side_effect=OSError('blocked')):
   with self.assertRaisesRegex(ValueError,'Spotify search is unavailable'):sp.resolve('Artist','Song')

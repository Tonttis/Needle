import json,time,unittest,urllib.error
from unittest.mock import patch
import playlists as pl
import server as s
import test_variety as fixture

class PlaylistTests(unittest.TestCase):
 def test_allowed_domains_and_injection(self):
  for url in ['http://youtube.com/playlist?list=PL1234567890','https://youtube.com.evil.test/playlist?list=PL1234567890','https://youtube.com/playlist?list=PL1234567890;rm']:
   with self.assertRaises(ValueError):pl.identify(url)
  self.assertEqual(pl.identify('https://music.youtube.com/playlist?list=PL1234567890')[0],'youtube')
 def test_youtube_playlist_matched_without_substituting_wrong_song(self):
  class P:stdout=json.dumps({'entries':[dict(id='abcdefghijk',title=f'Artist {i} - Title {i}',channel='Artist') for i in range(5)]})
  def fetch(path):
   from urllib.parse import unquote
   query=unquote(path.split('q=')[1]);i=int(query.split()[-1]);return {'data':[dict(id=i,title=f'Title {i}',artist={'id':i,'name':f'Artist {i}'},preview='https://audio.test',album={'id':i})]}
  with patch.object(pl.subprocess,'run',return_value=P()):
   tracks,report=pl.match_playlist('https://youtube.com/playlist?list=PL1234567890',fetch,s.clean)
  self.assertEqual(report['matched'],5);self.assertTrue(all(t['youtube_id']=='abcdefghijk' for t in tracks))
 def test_spotify_requires_token(self):
  with patch.dict(pl.os.environ,{},clear=True):
   with self.assertRaisesRegex(ValueError,'access token'):pl.source_tracks('https://open.spotify.com/playlist/1234567890123456789012')
 def test_spotify_pagination(self):
  import io
  pages=[{'total':3,'items':[{'item':{'type':'track','name':'A','artists':[{'name':'B'}]}},{'item':{'type':'track','name':'C','artists':[{'name':'D'}]}}]}, {'total':3,'items':[{'item':{'type':'track','name':'E','artists':[{'name':'F'}]}}]}]
  class R(io.BytesIO):
   def __enter__(self):return self
   def __exit__(self,*args):self.close()
  with patch.dict(pl.os.environ,{'SPOTIFY_ACCESS_TOKEN':'test'}),patch.object(pl.urllib.request,'urlopen',side_effect=[R(json.dumps(p).encode()) for p in pages]):
   entries,total,provider=pl.source_tracks('https://open.spotify.com/playlist/1234567890123456789012')
  self.assertEqual((len(entries),total,provider),(3,3,'spotify'))
 def test_refresh_token_is_reused_until_near_expiry(self):
  import io
  class R(io.BytesIO):
   def __enter__(self):return self
   def __exit__(self,*args):self.close()
  pl._token_cache.update(value='',expires=0)
  with patch.dict(pl.os.environ,{'SPOTIFY_CLIENT_ID':'id','SPOTIFY_CLIENT_SECRET':'secret','SPOTIFY_REFRESH_TOKEN':'refresh'},clear=True),patch.object(pl.urllib.request,'urlopen',return_value=R(b'{"access_token":"renewed","expires_in":3600}')) as request:
   self.assertEqual(pl.spotify_token(),'renewed');self.assertEqual(pl.spotify_token(),'renewed');self.assertEqual(request.call_count,1)
  pl._token_cache.update(value='',expires=0)
 def test_decade_uses_provider_dates_only(self):
  rows=[dict(id=str(i),album_id=str(i)) for i in range(5)]
  def fetch(path):return {'release_date':{'0':'1985-01-01','1':'1989-01-01','2':'1981-01-01','3':'1980-01-01','4':'1990-01-01'}[path.split('/')[-1]]}
  with patch.object(s,'fetch',side_effect=fetch):filtered=s.filter_decade(rows,'1980s')
  self.assertEqual({t['id'] for t in filtered},{'0','1','2','3'})

class PartyTests(fixture.HTTPGameTests):
 def test_mixed_rounds_and_complete_recap(self):
  tracks=fixture.fixture_tracks()
  for t in tracks:t['hot_hit']=True
  with patch.object(s,'pool',return_value=tracks),patch.object(s,'queue_youtube'),patch.object(s,'queue_prefetch'),patch.object(s,'credit',side_effect=lambda t:t):
   host=self.post('create',dict(mode='party',party_modes=['guess','choice','race','hits'],multi=False,rounds=4,name='DJ'))
   room=s.rooms[host['room']];modes=[]
   for i in range(4):
    modes.append(room['mode'])
    if room['mode']=='race':room.update(race_started=time.time()-3,race_duration=200,deadline=time.time()+197,race_status='playing')
    view=self.post('guess',dict(**host,round=i+1,stage=0,id=room['song']['id']))
    self.assertEqual(view['phase'],'reveal');view=self.post('next',host)
   self.assertEqual(set(modes),{'guess','choice','race','hits'});self.assertEqual(view['phase'],'finished')
   self.assertEqual(len(view['recap']),4);self.assertTrue(all(x['winners'][0]['name']=='DJ' for x in view['recap']))
   self.assertTrue(all('title' in x and 'link' in x for x in view['recap']))
   del s.rooms[host['room']]
 def test_playlist_bypasses_regular_catalog(self):
  tracks=fixture.fixture_tracks();report={'provider':'youtube','matched':len(tracks),'total':len(tracks),'unmatched':0}
  with patch.object(s,'pool',side_effect=AssertionError('unneeded')),patch.object(s,'playlist_pool',return_value=(tracks,report)),patch.object(s,'credit',side_effect=lambda t:t):
   host=self.post('create',dict(mode='guess',playlist_url='https://youtube.com/playlist?list=PL1234567890',multi=False));room=s.rooms[host['room']]
   self.assertEqual(s.state(room,host['token'])['playlist_report'],report);del s.rooms[host['room']]

"""Deterministic catalog simulations + real HTTP multiplayer lifecycle checks."""
import collections,json,random,threading,unittest,urllib.request,tempfile,pathlib
import leaderboard as boards
from unittest.mock import patch
import catalog as c
import server as s

def fixture_tracks(region='Europe'):
    countries=['FI'] if region=='Finland' else ['FI','GB','DE','FR','SE','NO','NL','IT','ES','IE','BE','DK']
    rows=[]
    for country in countries:
        for artist in range(24):
            # Finnish artists deliberately have much more material than others.
            for song in range(35 if country=='FI' else 5):
                rows.append(dict(id=f'{country}-{artist}-{song}',artist_id=f'{country}-{artist}',artist=f'{country} Artist {artist}',title=f'Track {song}',country=country,region=region,language='Finnish' if country=='FI' else 'English',genre='Rock',rank=10000-song,preview='fixture',art='',link=''))
    return rows

class VarietyTests(unittest.TestCase):
 def setUp(self):self.saved=random.getstate();random.seed(501)
 def tearDown(self):random.setstate(self.saved)
 def game(self,region,rounds):
    r=dict(pool=fixture_tracks(region),used=[],round=0,rounds=rounds,region=region)
    sequence=[]
    for _ in range(rounds):
        t=c.choose_song(r);r['used'].append(t['id']);r['round']+=1;sequence.append(t)
    return sequence
 def test_europe_1000_complete_ten_song_matches(self):
    for _ in range(1000):
        tracks=self.game('Europe',10)
        self.assertLessEqual(sum(t['country']=='FI' for t in tracks),1)
        self.assertEqual(len({t['artist_id'] for t in tracks}),10)
        # Familiarity now takes priority over forced one-country-per-round quotas.
        self.assertGreaterEqual(len({t['country'] for t in tracks}),2)
 def test_finnish_rounds_never_repeat_artist_before_exhaustion(self):
    for rounds in [3,10,20,30]:
        tracks=self.game('Finland',rounds)
        self.assertEqual(len({t['artist_id'] for t in tracks[:24]}),min(rounds,24))
        self.assertTrue(all(a['artist_id']!=b['artist_id'] for a,b in zip(tracks,tracks[1:])))
 def test_europe_cap_thirty_rounds(self):
    tracks=self.game('Europe',30)
    self.assertLessEqual(sum(t['country']=='FI' for t in tracks),3)
    self.assertEqual(len({t['artist_id'] for t in tracks}),30)
 def test_discovery_countries_balanced_even_with_many_finnish_seeds(self):
    seeds=c.eligible('Mixed','Europe');order=c.discovery_order(seeds)[:80]
    counts=collections.Counter(x['country'] for x in order)
    self.assertGreaterEqual(len(counts),12);self.assertLessEqual(counts['FI'],8)
    self.assertGreater(len({x['name'] for x in c.SEEDS}),500)
 def test_sparse_language_is_not_deleted_for_having_under_25_tracks(self):
    song=dict(id='1',artist='A',language='French',genre='Rock',rank=100)
    rows=[song]+[dict(id=str(i),artist=str(i),language='French',genre='Pop',rank=90) for i in range(2,5)]
    board,choices=c.round_choices(song,rows);self.assertEqual(len(choices),4)

 def test_provider_partial_failure_cannot_start_two_artist_match(self):
    seeds=[dict(name=f'Anchor {i}',country='FI',region='Finland',language='Finnish',genre='Rock') for i in range(20)]
    def fetch(path):
        from urllib.parse import unquote
        if path.startswith('search/artist'):
            name=unquote(path.split('q=')[1]);aid=int(name.split()[-1])
            return {'data':[{'id':aid,'name':name}]} if aid<2 else {'data':[]}
        aid=int(path.split('/')[1]);return {'data':[dict(id=aid*100+i,title=f'Song {i}',preview='fixture',rank=100-i,artist={'id':aid,'name':f'Anchor {aid}'}) for i in range(10)]}
    with patch.object(c,'SEEDS',seeds):
        with self.assertRaisesRegex(ValueError,'distinct artists'):
            c.build_pool(fetch,s.clean,'Rock','Finland','Easy')

class HTTPGameTests(unittest.TestCase):
 def setUp(self):
    self._score_dir=tempfile.TemporaryDirectory()
    self._score_patch=patch.object(boards,'DB_PATH',pathlib.Path(self._score_dir.name)/'scores.sqlite3')
    self._score_patch.start()
 def tearDown(self):
    self._score_patch.stop();self._score_dir.cleanup()
 @classmethod
 def setUpClass(cls):
    class Quiet(s.Handler):
        def log_message(self,*args):pass
    cls.http=s.ThreadingHTTPServer(('127.0.0.1',0),Quiet)
    cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    cls.url='http://127.0.0.1:'+str(cls.http.server_address[1])+'/api/'
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close()
 def post(self,path,data):
    req=urllib.request.Request(self.url+path,json.dumps(data).encode(),{'Content-Type':'application/json'})
    with urllib.request.urlopen(req) as r:return json.load(r)
 def test_both_modes_multiplayer_finished_and_lobby(self):
    for mode in ['guess','choice']:
      with patch.object(s,'pool',return_value=fixture_tracks()),patch.object(s,'credit',side_effect=lambda t:t):
        host=self.post('create',dict(mode=mode,multi=True,rounds=10,region='Europe',genre='Rock',name='Host'))
        guest=self.post('join',dict(room=host['room'],name='Guest'))
        view=self.post('next',host);artists=[];countries=[]
        for i in range(10):
            room=s.rooms[host['room']];track=room['song'];artists.append(track['artist_id']);countries.append(track['country'])
            self.post('guess',dict(**host,id=track['id'],round=i+1,stage=0))
            view=self.post('guess',dict(**guest,id='',round=i+1,stage=0))
            self.assertEqual(view['phase'],'reveal');self.assertFalse(view['correct'])
            view=self.post('next',host)
        self.assertEqual(view['phase'],'finished');self.assertNotIn('answer',view)
        self.assertEqual([p['score'] for p in view['players']],[10,0])
        self.assertEqual(len(set(artists)),10);self.assertLessEqual(countries.count('FI'),1)
        view=self.post('lobby',host)
        self.assertEqual(view['phase'],'lobby');self.assertEqual(view['round'],0)
        self.assertEqual(len(view['players']),2);self.assertEqual([p['score'] for p in view['players']],[0,0])
        view=self.post('next',host);self.assertEqual(view['round'],1)
        del s.rooms[host['room']]
if __name__=='__main__':unittest.main()

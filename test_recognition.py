"""Recognition calibration and full-catalog integration, without external requests."""
import random,unittest
from unittest.mock import patch
from urllib.parse import unquote
import catalog as c
import recognition as rec
import server as s

class RecognitionTests(unittest.TestCase):
 def seed(self,name):return next(x for x in c.SEEDS if rec.text_key(x['name'])==rec.text_key(name))
 def test_unknown_artist_top_song_cannot_be_easy(self):
  tracks=[dict(id='1',title='Unknown Track',rank=999999)]
  c.classify_tracks(tracks,dict(name='Unknown Artist'),'Europe','Mixed')
  self.assertFalse(c.band(tracks,'Easy'))
 def test_big_artist_unknown_song_cannot_be_easy(self):
  rows=[dict(id='1',title='Invented Deep Cut',rank=999999),dict(id='2',title='One Dance',rank=1)]
  rec.classify_tracks(rows,self.seed('Drake'),'Europe','Mixed')
  self.assertEqual([t['id'] for t in c.band(rows,'Easy')],['2'])
 def test_local_fame_is_not_pan_european_fame(self):
  seed=self.seed('Mirella')
  self.assertEqual(rec.recognition(seed,'Timanttei','Europe','Mixed'),0)
  self.assertEqual(rec.recognition(seed,'Timanttei','Europe','Pop'),0)
  self.assertGreaterEqual(rec.recognition(seed,'Timanttei','Finland','Mixed'),85)
 def test_europe_includes_international_crossovers(self):
  seeds={x['name']:x for x in c.eligible('Mixed','Europe')}
  for artist,title in [('Drake','One Dance'),('The Weeknd','Blinding Lights'),('Benson Boone','Beautiful Things'),('Avicii','Wake Me Up')]:
   self.assertIn(artist,seeds);self.assertGreaterEqual(rec.recognition(seeds[artist],title,'Europe','Mixed'),85)
 def test_specialist_standard_does_not_become_mixed_easy(self):
  seed=self.seed('Miles Davis')
  self.assertLess(rec.recognition(seed,'So What','Worldwide','Mixed'),85)
  self.assertGreaterEqual(rec.recognition(seed,'So What','Worldwide','Jazz'),85)
 def test_title_match_preserves_identity(self):
  self.assertEqual(rec.song_key('One Dance (feat. Wizkid & Kyla)'),rec.song_key('One Dance'))
  self.assertEqual(rec.song_key('Numb - 2003 Remaster'),rec.song_key('Numb'))
  self.assertNotEqual(rec.song_key('Somebody Else'),rec.song_key('Somebody'))
  self.assertNotEqual(rec.song_key('One Dance - Acoustic'),rec.song_key('One Dance'))
 def test_supported_countries_genres_and_thresholds(self):
  config=c.filter_options()
  self.assertGreaterEqual(len(rec.COUNTRIES),28);self.assertGreaterEqual(len(c.GENRES),19)
  self.assertGreaterEqual(len(c.SEEDS),800);self.assertGreaterEqual(sum(len(p['titles']) for p in rec.PROFILES.values()),900)
  for country in rec.COUNTRIES:
   self.assertIn('Easy',config['support'][country]['Mixed'])
   self.assertTrue(all(s['country']==rec.COUNTRIES[country] for s in c.eligible('Mixed',country)))
  self.assertNotIn('Jazz',config['support']['Finland'])
 def test_song_scores_are_unchanged_by_gameplay_mode(self):
  rows=[]
  for index,(key,p) in enumerate(rec.PROFILES.items()):
   seed=self.seed(p['name'])
   for j,title in enumerate(p['examples']):
    score=rec.recognition(seed,title,'Europe','Mixed')
    rows.append(dict(id=f'{index}-{j}',title=title,artist=p['name'],artist_id=str(index),country=p['country'],recognition=score))
  previous=random.getstate()
  try:
   for mode in ['guess','choice']:
    random.seed(132)
    for _ in range(250):
     room=dict(pool=rows,used=[],round=0,rounds=10,region='Europe',difficulty='Easy',mode=mode)
     picked=[]
     for i in range(10):
      t=c.choose_song(room);room['used'].append(t['id']);room['round']+=1;picked.append(t)
     self.assertTrue(all(t['recognition']>=85 for t in picked))
     self.assertEqual(len({t['artist_id'] for t in picked}),10)
     self.assertLessEqual(sum(t['country']=='FI' for t in picked),1)
  finally:random.setstate(previous)
 def test_full_catalog_kept_for_distractors_and_harder_games(self):
  seeds=[self.seed(a) for a in ['Queen','Coldplay','Drake','Avicii','Adele','Eminem','ABBA','Metallica','Dua Lipa','Nirvana','The Weeknd','Rihanna']]
  names={x['name']:i for i,x in enumerate(seeds)}
  def fetch(path):
   if path.startswith('search/artist'):
    name=unquote(path.split('q=')[1]);return {'data':[dict(id=names[name],name=name)]}
   i=int(path.split('/')[1]);seed=seeds[i];title=rec.profile(seed)['examples'][0]
   return {'data':[dict(id=i*100+j,title=title if j==0 else f'Album cut {j}',artist=dict(id=i,name=seed['name']),preview='fixture',rank=900000-j*10000) for j in range(50)]}
  with patch.object(c,'SEEDS',seeds):
   pool=c.build_pool(fetch,s.clean,'Mixed','Europe','Easy')
  self.assertEqual(len(pool),600);self.assertEqual(len(c.band(pool,'Easy')),12)
  self.assertTrue(c.band(pool,'Impossible'))
  room=dict(pool=pool,used=[],round=0,rounds=10,region='Europe',difficulty='Easy')
  for _ in range(10):
   t=c.choose_song(room);room['used'].append(t['id']);self.assertGreaterEqual(t['recognition'],85)
 def test_choice_distractors_have_similar_familiarity(self):
  song=dict(id='hit',artist='Hit',genre='Rock',language='English',recognition=90,rank=100)
  similar=[dict(id=str(i),artist=f'Known {i}',genre='Rock',language='English',recognition=90,rank=1) for i in range(4)]
  obscure=[dict(id=f'x{i}',artist=f'Unknown {i}',genre='Rock',language='English',recognition=16,rank=100) for i in range(80)]
  _,options=c.round_choices(song,[song]+similar+obscure)
  self.assertTrue(all(t['recognition']==90 for t in options))
 def test_no_easier_fallback_in_sparse_impossible_pool(self):
  with self.assertRaisesRegex(ValueError,'No tracks meet'):
   c.choose_song(dict(pool=[dict(id='1',recognition=94)],used=[],difficulty='Impossible'))
if __name__=='__main__':unittest.main()

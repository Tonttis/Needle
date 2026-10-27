import unittest
from unittest.mock import patch
import catalog as c
class CatalogTests(unittest.TestCase):
 def rows(self):
  return [dict(id=str(i),title='Song '+str(i),artist='Artist '+str(i%8),genre='Rock',language='Finnish' if i<40 else 'English',rank=1000-i) for i in range(80)]
 def test_board_count_and_language(self):
  for _ in range(30):
   rows=self.rows();board,options=c.round_choices(rows[0],rows)
   self.assertEqual(len(board),25);self.assertEqual(len({t['id'] for t in board}),25)
   self.assertTrue(all(t['language']=='Finnish' for t in board+options))
   self.assertIn(rows[0],board);self.assertIn(rows[0],options);self.assertEqual(len(options),4)
 def test_filters_intersect(self):
  seeds=c.eligible('Rock','Finland');self.assertTrue(seeds)
  self.assertTrue(all(s['region']=='Finland' and s['genre']=='Rock' for s in seeds))
  self.assertIn('Drake',{s['name'] for s in c.eligible('Mixed','Europe')})
 def test_difficulty(self):
  rows=[dict(recognition=x) for x in [94,78,65,48,32,16]]
  self.assertEqual([t['recognition'] for t in c.band(rows,'Easy')],[94])
  self.assertEqual([t['recognition'] for t in c.band(rows,'Hard')],[78,65,48])
 def test_normalization(self):
  self.assertEqual(c.norm('KÄÄRIJÄ'),c.norm('kaarija'))
  self.assertEqual(c.title_key(dict(title='Song (2011 Remastered)',artist='Queen')),c.title_key(dict(title='Song',artist='Queen')))
 def test_pool_filters_deduplicates(self):
  seeds=[dict(name='Artist '+str(i),genre='Rock',region='Finland',language='Finnish') for i in range(8)]
  def fetch(path):
   if path.startswith('search/artist'):
    from urllib.parse import unquote
    name=unquote(path.split('q=')[1]);return {'data':[{'id':int(name.split()[-1]),'name':name}]}
   aid=int(path.split('/')[1]);return {'data':[dict(id=aid*100+i,title='Song '+str(i),artist={'id':aid,'name':'Artist '+str(aid)},preview='https://example.test',rank=100-i) for i in range(50)]}
  def clean(t):return dict(id=str(t['id']),title=t['title'],artist=t['artist']['name'])
  with patch.object(c,'SEEDS',seeds):
   rows=c.build_pool(fetch,clean,'Rock','Finland','Hard');self.assertEqual(len(rows),400)
   self.assertTrue(all(t['language']=='Finnish' for t in rows))
if __name__=='__main__':unittest.main()

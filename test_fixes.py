import unittest
from unittest.mock import patch
import server as s
class FixTests(unittest.TestCase):
 def room(self):
  rows=[dict(id=str(i),title='Track '+str(i),artist='Artist',genre='Rock',language='English',rank=1000-i,art='',link='') for i in range(80)]
  r=dict(pool=rows,used=[],players={'p':dict(name='Player',score=0)},mode='choice',multi=False,round=0,rounds=10,code='TEST',genre='Rock',host='p')
  s.advance(r);return r
 def test_each_choice_scores_only_actual_answer(self):
  for index in range(4):
   r=self.room();picked=r['options'][index]['id'];r['guesses']={'p':picked};s.settle(r)
   expected=picked==r['song']['id'];self.assertEqual(r['players']['p']['score'],int(expected))
   view=s.state(r,'p');self.assertEqual(view['correct'],expected);self.assertEqual(view['result'],'correct' if expected else 'incorrect')
   s.settle(r);self.assertEqual(r['players']['p']['score'],int(expected))
 def test_no_search_hints_or_answer_leak(self):
  r=self.room();r['mode']='guess';view=s.state(r,'p')
  self.assertNotIn('board',view);self.assertNotIn('answer',view)
  self.assertEqual(s.suggestions(r,''),[]);self.assertEqual(s.suggestions(r,'t'),[])
 def test_query_changes_results_outside_fixed_board(self):
  r=self.room();self.assertLessEqual(len(s.suggestions(r,'Track')),25)
  self.assertEqual(s.suggestions(r,'Track 79')[0]['id'],'79')
  self.assertNotEqual(s.suggestions(r,'Track 79'),s.suggestions(r,'Track 22'))
 def test_contributors(self):
  t={'id':1,'title':'Song','artist':{'name':'Main'},'contributors':[{'name':'Main'},{'name':'Guest'},{'name':'Another'}]}
  self.assertEqual(s.clean(t)['artist'],'Main, Guest, Another')
 def test_credit_detail(self):
  with patch.object(s,'fetch',return_value={'id':1,'title':'Song','artist':{'name':'Main'},'contributors':[{'name':'Guest'}]}):
   self.assertEqual(s.credit({'id':'1','artist':'Main'})['artist'],'Main, Guest')
if __name__=='__main__':unittest.main()

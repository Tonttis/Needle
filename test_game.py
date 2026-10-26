import unittest,time
import server as s
class GameTests(unittest.TestCase):
 def room(self):
  r={'pool':[{'id':str(i),'title':str(i),'artist':'Artist','preview':'x'} for i in range(6)],'used':[],'players':{'a':{'score':0},'b':{'score':0}},'mode':'guess','multi':True,'round':0}
  s.advance(r);return r
 def test_simultaneous_winners(self):
  r=self.room();r['guesses']={'a':r['song']['id'],'b':r['song']['id']};s.settle(r);self.assertEqual(r['phase'],'reveal');self.assertEqual([p['score'] for p in r['players'].values()],[1,1]);s.settle(r);self.assertEqual(r['players']['a']['score'],1)
 def test_wrong_unlocks(self):
  r=self.room();r['guesses']={'a':'wrong','b':''};s.settle(r);self.assertEqual(r['stage'],1);self.assertEqual(r['guesses'],{})
 def test_wait_for_both(self):
  r=self.room();r['guesses']={'a':r['song']['id']};s.settle(r);self.assertEqual(r['phase'],'playing')
 def test_timeout(self):
  r=self.room();r['deadline']=time.time()-1;s.settle(r);self.assertEqual(r['stage'],1)
 def test_final_miss(self):
  r=self.room();r['stage']=4;r['guesses']={'a':'','b':''};s.settle(r);self.assertEqual(r['phase'],'reveal')
 def test_no_repeat(self):
  r=self.room();first=r['song']['id'];s.advance(r);self.assertNotEqual(first,r['song']['id'])
if __name__=='__main__':unittest.main()

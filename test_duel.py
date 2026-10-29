"""Song Duel lifecycle, private audio, deadlines, persistence and real clip slicing."""
import json,pathlib,shutil,subprocess,tempfile,time,unittest,urllib.error,urllib.request
from concurrent.futures import Future
from unittest.mock import patch
import duel as d,server as s,leaderboard as lb
from test_variety import HTTPGameTests

class Immediate:
 def submit(self,fn,*args):
  result=Future()
  try:result.set_result(fn(*args))
  except Exception as error:result.set_exception(error)
  return result

class DuelHTTPTests(HTTPGameTests):
 def setUp(self):
  super().setUp();self.clock=10000.;self.created=[];self.folder=tempfile.TemporaryDirectory()
  self.paths={i:pathlib.Path(self.folder.name)/f'song-{i}.m4a' for i in ('A','B')}
  for key,path in self.paths.items():path.write_bytes(key.encode())
  def fetch(path):
   self.assertTrue(path.startswith('search?limit=12&q='))
   return {'data':[dict(id=i,title='Song '+name,artist=dict(id=i,name='Artist '+name),preview='',album={}) for i,name in enumerate(('A','B'),1)]}
  def load(song,audio):
   self.assertTrue(audio);name=song['title'][-1]
   return 'abcdefghij'+name,song['title'],str(self.paths[name]),120. if name=='A' else 180.,'audio/mp4'
  def clip(path,start):return ('clip:'+pathlib.Path(path).name+':'+str(start)).encode()
  self.patches=[patch.object(d.time,'time',side_effect=lambda:self.clock),patch.object(s.DUEL,'workers',Immediate()),patch.object(s.DUEL,'fetch',side_effect=fetch),patch.object(s.DUEL,'load_media',side_effect=load),patch.object(d,'cut_clip',side_effect=clip),patch.object(s,'pool',side_effect=AssertionError('Duel must not build a catalog'))]
  for item in self.patches:item.start()
 def tearDown(self):
  for code in self.created:s.rooms.pop(code,None)
  for item in reversed(self.patches):item.stop()
  self.folder.cleanup();super().tearDown()
 def get(self,path):
  with urllib.request.urlopen(self.url+path) as response:return json.load(response)
 def room(self,rounds=1):
  host=self.post('create',dict(mode='duel',multi=True,name='Alice',rounds=rounds));self.created.append(host['room'])
  guest=self.post('join',dict(room=host['room'],name='Bob'))
  view=self.post('duel-next',host);return host,guest,view
 def state(self,who):return self.get('state?room='+who['room']+'&token='+who['token'])
 def act(self,who,action,**data):
  view=self.state(who)
  return self.post('duel-'+action,dict(**who,round=view['round'],generation=view['duel']['generation'],**data))
 def pick(self,who,index):
  view=self.state(who)
  query=urllib.parse.urlencode(dict(**who,round=view['round'],generation=view['duel']['generation'],q='any song'))
  results=self.get('duel-search?'+query)['results']
  return self.act(who,'pick',selection=results[index]['selection'])
 def clips(self,who,positions):return self.act(who,'clips',positions=positions,revision=1,locked=True)
 def ready_game(self):
  a,b,_=self.room();self.pick(a,0);self.pick(b,1)
  self.clips(a,[0,10,20,30,40]);self.clips(b,[5,15,25,35,45]);self.act(a,'ready');self.act(b,'ready');self.clock+=2
  return a,b
 def assert_http_error(self,fn):
  with self.assertRaises(urllib.error.HTTPError):fn()
 def test_online_only_two_to_eight_and_host_controls(self):
  self.assert_http_error(lambda:self.post('create',dict(mode='duel',multi=False,name='Alice')))
  a=self.post('create',dict(mode='duel',multi=True,name='Alice',rounds=3));self.created.append(a['room'])
  self.assert_http_error(lambda:self.post('duel-next',a))
  invite=self.get('invite?room='+a['room']);self.assertTrue(invite['joinable']);self.assertEqual(invite['max_players'],8)
  b=self.post('join',dict(room=a['room'],name='Bob'))
  self.assertTrue(self.get('invite?room='+a['room'])['joinable'])
  for i in range(6):self.post('join',dict(room=a['room'],name='Extra '+str(i)))
  self.assertFalse(self.get('invite?room='+a['room'])['joinable'])
  self.assert_http_error(lambda:self.post('join',dict(room=a['room'],name='Ninth')))
  self.assert_http_error(lambda:self.post('duel-next',b))
  self.assertEqual(self.post('duel-settings',dict(**a,rounds=5))['rounds'],5)
  self.assert_http_error(lambda:self.post('duel-settings',dict(**b,rounds=1)))
  self.assert_http_error(lambda:self.post('next',a))
 def test_guess_suggestions_and_private_reveal_previews(self):
  a,b,v=self.room();generation=v['duel']['generation']
  query=urllib.parse.urlencode(dict(**a,round=1,generation=generation,q='anything'))
  self.assert_http_error(lambda:self.get('duel-guess-search?'+query))
  self.assertRaises(ValueError,lambda:s.DUEL.preview_song(a['room'],a['token'],0,1,generation))
  self.pick(a,0);self.pick(b,1);self.clips(a,[0,10,20,30,40]);self.clips(b,[0,10,20,30,40]);self.act(a,'ready');self.act(b,'ready');self.clock+=2
  result=self.get('duel-guess-search?'+query)
  self.assertEqual(result,{'results':[{'title':'Song A','artist':'Artist A'},{'title':'Song B','artist':'Artist B'}]})
  self.assertRaises(ValueError,lambda:s.DUEL.preview_song(a['room'],a['token'],0,1,generation))
  self.act(a,'guess',guess='Song B');self.act(b,'guess',guess='Song A')
  self.assertEqual(s.DUEL.preview_song(a['room'],a['token'],0,1,generation)['title'],'Song A')
  self.assert_http_error(lambda:self.get('duel-guess-search?'+query))
  self.assertRaises(ValueError,lambda:s.DUEL.preview_song(a['room'],'invalid',0,1,generation))
  self.assertRaises(ValueError,lambda:s.DUEL.preview_song(a['room'],a['token'],0,1,'stale'))
  self.assertRaises(ValueError,lambda:s.DUEL.preview_song(a['room'],a['token'],2,1,generation))
  url=self.url.replace('/api/','/')+'duel-preview?'+urllib.parse.urlencode(dict(**a,round=1,generation=generation,song=0))
  with patch.object(s.deezer_reveal_cache,'get',return_value=(b'deezer-preview','audio/mpeg')) as preview:
   with urllib.request.urlopen(url) as response:self.assertEqual(response.read(),b'deezer-preview')
   self.assertEqual(preview.call_args.args[1]['title'],'Song A')
  with patch.object(s.deezer_reveal_cache,'get',side_effect=ValueError('Unavailable')),patch.object(d,'cut_clip',return_value=b'fallback') as clip:
   with urllib.request.urlopen(url) as response:self.assertEqual(response.read(),b'fallback')
   self.assertEqual(clip.call_args.args[-1],10)
  self.post('duel-next',a);self.post('duel-lobby',a)
  self.assertRaises(ValueError,lambda:s.DUEL.preview_song(a['room'],a['token'],0,1,generation))
 def test_clip_numbers_are_chronological_in_saved_state_and_encoded_audio(self):
  a,b,_=self.room();self.pick(a,0);self.pick(b,1)
  first=self.act(a,'clips',positions=[80,10,40],revision=1,locked=False)
  self.assertEqual(first['duel']['positions'],[10,40,80])
  self.act(a,'clips',positions=[100,0,20,80,40],revision=2,locked=True)
  self.clips(b,[75,5,55,25,95]);av=self.state(a);bv=self.state(b)
  self.assertEqual(av['duel']['positions'],[0,20,40,80,100]);self.assertEqual(bv['duel']['positions'],[5,25,55,75,95])
  room=s.rooms[a['room']];dstate=room['duel']
  for player in (a,b):
   token=player['token']
   for index,start in enumerate(dstate['positions'][token]):self.assertTrue(dstate['clips'][token][index].endswith((':'+str(start)).encode()))
 def group(self,count,rounds=2):
  host=self.post('create',dict(mode='duel',multi=True,name='Player 1',rounds=rounds));self.created.append(host['room'])
  players=[host]+[self.post('join',dict(room=host['room'],name='Player '+str(i+1))) for i in range(1,count)]
  self.post('duel-next',host);return players
 def test_assignments_rotate_without_self_picks_for_every_group_size(self):
  for count in range(2,9):
   players=self.group(count,count-1);host=players[0];seen={p['token']:set() for p in players}
   for round_number in range(1,count):
    room=s.rooms[host['room']];assignment=room['duel']['outgoing'];self.assertEqual(len(set(assignment.values())),count)
    for owner,receiver in assignment.items():self.assertNotEqual(owner,receiver);self.assertNotIn(receiver,seen[owner]);seen[owner].add(receiver)
    before=dict(assignment);self.clock+=31;self.assertEqual(self.state(host)['phase'],'reveal')
    if round_number<count-1:self.post('duel-next',host)
   self.assertTrue(all(len(value)==count-1 for value in seen.values()))
 def test_group_lifecycle_private_history_ready_gate_and_persistent_scores(self):
  for count in (3,4,8):
   players=self.group(count);host=players[0]
   for index,player in enumerate(players):
    self.pick(player,index%2)
    if index<count-1:self.assertEqual(self.state(host)['phase'],'picking')
   room=s.rooms[host['room']];incoming=dict(room['duel']['incoming'])
   for player in players:
    self.assertEqual(self.state(player)['duel']['supplier'],room['players'][incoming[player['token']]]['name'])
    self.clips(player,[90,10,70,30,50])
   for player in players[:-1]:self.assertEqual(self.act(player,'ready')['phase'],'loading')
   self.assertEqual(self.act(players[-1],'ready')['phase'],'playing');self.clock+=2
   for index,player in enumerate(players):
    token=player['token'];target=room['duel']['songs'][incoming[token]]
    own_key=room['duel']['clip_keys'][token]
    with self.assertRaises(ValueError):s.DUEL.clip(host['room'],players[(index+1)%count]['token'],own_key,0,1)
    self.assertIn(target['id'],lb.played_song_ids([room['players'][token]['name']]))
    view=self.act(player,'guess',guess=target['title'])
    self.assertEqual(view['phase'],'reveal' if index==count-1 else 'playing')
   self.assertEqual(len(view['duel']['answers']),count);self.assertTrue(all(p['score']==1 for p in view['players']))
   self.post('duel-next',host);self.assertNotEqual(s.rooms[host['room']]['duel']['incoming'],incoming)
   self.clock+=31;self.state(host);self.assertEqual(self.post('duel-next',host)['phase'],'finished')
   self.assertEqual(len(lb.leaderboard('duel','Duel',True)),count)
 def test_partial_group_missing_pick_awards_only_recipient_and_others_continue(self):
  players=self.group(4);a,b,c,missing=players
  self.pick(a,0);self.pick(b,1);self.pick(c,0);self.clock+=31
  view=self.state(a);self.assertEqual(view['phase'],'clips');self.assertEqual(view['duel']['done'],'forfeit-win')
  self.assertEqual(self.state(missing)['duel']['done'],'no-pick')
  self.clips(b,[0,10,20,30,40]);self.clips(c,[0,10,20,30,40]);self.act(b,'ready');self.act(c,'ready');self.clock+=2
  self.act(b,'guess',guess='Song A');view=self.act(c,'skip')
  self.assertEqual(view['phase'],'reveal');self.assertEqual([p['score'] for p in view['players']],[1,1,0,0])
  self.assertEqual([p['score'] for p in self.state(a)['players']],[1,1,0,0])
  self.assertFalse(lb.played_song_ids(['Player 1','Player 4']))
 def test_complete_duel_private_clips_unlimited_guesses_scores_history_rematch(self):
  a,b,initial=self.room();generation=initial['duel']['generation']
  self.pick(a,0)
  self.assertNotIn('Song A',json.dumps(self.state(b)))
  self.pick(b,1);av,bv=self.state(a),self.state(b)
  self.assertEqual(av['phase'],'clips');self.assertEqual(av['duel']['duration'],180);self.assertEqual(bv['duel']['duration'],120)
  self.assertNotIn('Song B',json.dumps(av));self.assertNotIn('Song A',json.dumps(bv))
  self.clips(a,[0,10,20,30,40]);bv=self.clips(b,[5,15,25,35,45]);av=self.state(a)
  self.assertEqual(av['phase'],'loading')
  def audio(who,key):
   url=self.url.replace('/api/','/')+'duel-clip/'+key+'?'+urllib.parse.urlencode(dict(**who,round=1,clip=0))
   with urllib.request.urlopen(url) as response:return response.read()
  self.assertIn(b'song-B.m4a',audio(a,av['duel']['clip_key']));self.assertIn(b'song-A.m4a',audio(b,bv['duel']['clip_key']))
  self.assert_http_error(lambda:audio(b,av['duel']['clip_key']))
  self.assertEqual(self.act(a,'ready')['phase'],'loading');playing=self.act(b,'ready');self.assertEqual(playing['phase'],'playing')
  self.assertEqual(playing['deadline']-playing['duel']['starts_at'],45)
  self.assert_http_error(lambda:self.act(a,'guess',guess='Song B'))
  self.clock+=2
  for _ in range(15):
   wrong=self.act(a,'guess',guess='incorrect');self.assertFalse(wrong['duel']['done'])
  self.assertEqual(wrong['duel']['attempts'],15)
  self.act(a,'guess',guess='Artist B - Song B')
  self.assertNotIn('Song A',json.dumps(self.state(b)))
  reveal=self.act(b,'guess',guess='Song A');self.assertEqual(reveal['phase'],'reveal')
  self.assertEqual([p['score'] for p in reveal['players']],[1,1]);self.assertEqual(len(reveal['duel']['answers']),2)
  self.assertIn('2',lb.played_song_ids(['Alice']));self.assertNotIn('1',lb.played_song_ids(['Alice']))
  self.assertIn('1',lb.played_song_ids(['Bob']));self.assertNotIn('2',lb.played_song_ids(['Bob']))
  old_key=av['duel']['clip_key'];finished=self.post('duel-next',a);self.assertEqual(finished['phase'],'finished')
  self.state(a);self.state(b);self.assertEqual(len(lb.leaderboard('duel','Duel',True)),2)
  self.assertEqual(lb.profile('Alice')['games'],1)
  self.post('duel-lobby',a);new=self.post('duel-next',a)
  self.assertNotEqual(new['duel']['generation'],generation);self.assertEqual([p['score'] for p in new['players']],[0,0])
  self.assert_http_error(lambda:audio(a,old_key))
  self.assert_http_error(lambda:self.post('duel-guess',dict(**a,round=1,generation=generation,guess='Song B')))
 def test_partial_clip_choices_autofill_and_timeout_finishes_both(self):
  a,b,_=self.room();self.pick(a,0);self.pick(b,1)
  self.act(a,'clips',positions=[12.5],revision=1,locked=False)
  self.clock+=31;av=self.state(a);bv=self.state(b)
  self.assertEqual(av['phase'],'loading');self.assertEqual(len(av['duel']['positions']),5);self.assertIn(12.5,av['duel']['positions']);self.assertEqual(av['duel']['positions'],sorted(av['duel']['positions']))
  self.assertTrue(all(0<=x<=175 for x in av['duel']['positions']));self.assertTrue(all(0<=x<=115 for x in bv['duel']['positions']))
  self.act(a,'ready');self.act(b,'ready');self.clock+=47
  final=self.state(a);self.assertEqual(final['phase'],'reveal');self.assertTrue(all(not x['correct'] for x in final['duel']['answers']))
  self.assert_http_error(lambda:self.act(a,'guess',guess='Song B'))
 def test_missing_pick_forfeits_and_no_picks_do_not_hang(self):
  a,b,_=self.room();self.clock+=31;self.assertEqual(self.state(a)['phase'],'reveal')
  self.post('duel-next',a);self.post('duel-lobby',a);self.post('duel-next',a)
  self.pick(a,0);self.clock+=31;view=self.state(a)
  self.assertEqual(view['phase'],'reveal');self.assertEqual([p['score'] for p in view['players']],[1,0]);self.assertIn('forfeit',view['duel']['notice'])
  self.assertFalse(lb.played_song_ids(['Alice','Bob']))
  self.state(a);self.assertEqual([p['score'] for p in self.state(a)['players']],[1,0])
 def test_skip_waits_for_opponent_and_wrong_answers_do_not_score(self):
  a,b=self.ready_game();self.assertEqual(self.act(a,'skip')['phase'],'playing')
  self.act(b,'guess',guess='Song B');self.assertEqual([p['score'] for p in self.state(b)['players']],[0,0])
  self.assertEqual(self.act(b,'skip')['phase'],'reveal')
  self.assert_http_error(lambda:self.act(a,'guess',guess='Song B'))
 def test_clip_validation_revisions_and_no_metadata_leak(self):
  a,b,_=self.room();self.pick(a,0);self.pick(b,1)
  for positions in ([-1],[176],[float('nan')],[float('inf')],[True],list(range(6))):
   self.assert_http_error(lambda positions=positions:self.act(a,'clips',positions=positions,revision=1,locked=False))
  self.act(a,'clips',positions=[10],revision=4,locked=False)
  self.act(a,'clips',positions=[20],revision=3,locked=False)
  self.assertEqual(self.state(a)['duel']['positions'],[10])
  self.assert_http_error(lambda:self.act(a,'clips',positions=[10],revision=5,locked=True))
  public=json.dumps(self.state(b));self.assertNotIn(self.paths['A'].name,public);self.assertNotIn('Song A',public);self.assertNotIn(a['token'],public)
 def test_unavailable_media_retries_without_changing_round_or_scoring(self):
  a,b,_=self.room()
  with patch.object(s.DUEL,'load_media',side_effect=ValueError('download blocked')):self.pick(a,0)
  self.pick(b,1);failed=self.state(a);self.assertEqual(failed['phase'],'duel-error');old=failed['duel']['generation']
  again=self.post('duel-retry',a);self.assertEqual(again['round'],1);self.assertEqual(again['score_max'],1);self.assertNotEqual(again['duel']['generation'],old)
  self.assertEqual(again['phase'],'picking')
 def test_only_server_search_results_can_be_selected_and_urls_are_checked(self):
  a,b,_=self.room()
  self.assert_http_error(lambda:self.act(a,'pick',selection='made-up'))
  view=self.state(a);params=dict(**a,round=1,generation=view['duel']['generation'],q='https://evil.example/video')
  self.assert_http_error(lambda:self.get('duel-search?'+urllib.parse.urlencode(params)))
  with patch.object(s.DUEL,'inspect_youtube',return_value=dict(id='yt:abcdefghijk',youtube_id='abcdefghijk',title='Video Title',artist='Channel',seed_artist='Channel',art='',link='https://www.youtube.com/watch?v=abcdefghijk',custom=True,preview='')):
   params['q']='https://youtu.be/abcdefghijk';result=self.get('duel-search?'+urllib.parse.urlencode(params))['results'][0]
  with patch.object(s.DUEL,'load_media',side_effect=ValueError('fixture')):
   self.act(a,'pick',selection=result['selection'],title='Song A',artist='Artist A')
  self.assertEqual(self.state(a)['duel']['picked']['title'],'Song A');self.assertNotIn('Song A',json.dumps(self.state(b)))

 def test_audio_barrier_timeout_never_uses_the_guessing_clock_or_records_history(self):
  a,b,_=self.room();self.pick(a,0);self.pick(b,1)
  self.clips(a,[0,10,20,30,40]);self.clips(b,[0,10,20,30,40]);self.act(a,'ready')
  self.assertEqual(self.state(a)['phase'],'loading');self.assertFalse(lb.played_song_ids(['Alice','Bob']))
  self.clock+=41;self.assertEqual(self.state(b)['phase'],'duel-error')
  self.assertEqual([p['score'] for p in self.state(a)['players']],[0,0])
 def test_replaced_or_expired_download_jobs_do_not_run_or_change_the_next_round(self):
  class Deferred:
   def __init__(self):self.jobs=[]
   def submit(self,fn):self.jobs.append(fn);return Future()
  a,b,_=self.room();queue=Deferred()
  with patch.object(s.DUEL,'workers',queue),patch.object(s.DUEL,'load_media',return_value=('abcdefghijk','title',str(self.paths['A']),120,'audio/mp4')) as loader:
   self.pick(a,0);self.pick(a,1)
   queue.jobs[0]();loader.assert_not_called();self.assertEqual(self.state(a)['duel']['picked']['status'],'loading')
   queue.jobs[1]();self.assertEqual(loader.call_count,1);self.assertEqual(self.state(a)['duel']['picked']['title'],'Song B')
   self.pick(b,0);self.clock+=176;self.assertEqual(self.state(a)['phase'],'duel-error')
   self.post('duel-retry',a);queue.jobs[2]();self.assertEqual(loader.call_count,1);self.assertNotIn('picked',self.state(b)['duel'])
 def test_search_result_arriving_after_pick_deadline_cannot_be_selected(self):
  a,b,_=self.room();view=self.state(a)
  def slow(_):self.clock+=31;return {'data':[dict(id=1,title='Late',artist=dict(id=1,name='Late Artist'))]}
  with patch.object(s.DUEL,'fetch',side_effect=slow):
   params=urllib.parse.urlencode(dict(**a,round=1,generation=view['duel']['generation'],q='late search'))
   self.assert_http_error(lambda:self.get('duel-search?'+params))
  self.assertEqual(self.state(a)['phase'],'reveal')

 def test_history_write_failure_pauses_instead_of_starting_untracked_play(self):
  a,b,_=self.room();self.pick(a,0);self.pick(b,1)
  self.clips(a,[0,10,20,30,40]);self.clips(b,[0,10,20,30,40]);self.act(a,'ready')
  with patch.object(lb,'record_played',side_effect=OSError('storage unavailable')):view=self.act(b,'ready')
  self.assertEqual(view['phase'],'duel-error');self.assertEqual(view['deadline'],0);self.assertIn('history',view['duel']['error'])
  self.assertEqual([p['score'] for p in view['players']],[0,0])

class DuelPureTests(unittest.TestCase):
 def test_video_links_only_allow_known_hosts_and_video_ids(self):
  for url in ('https://youtu.be/abcdefghijk?t=5','https://www.youtube.com/watch?v=abcdefghijk&list=PL1','https://music.youtube.com/watch?v=abcdefghijk','https://youtube.com/shorts/abcdefghijk'):
   self.assertEqual(d.youtube_id(url),'abcdefghijk')
  for url in ('https://youtube.com.evil/watch?v=abcdefghijk','https://evil@youtube.com/watch?v=abcdefghijk','file:///tmp/x','https://youtube.com/playlist?list=PL1','https://youtu.be/bad','javascript:alert(1)'):
   self.assertIsNone(d.youtube_id(url))
 def test_guesses_require_title_and_support_case_punctuation_and_known_aliases(self):
  song=dict(title='God’s Plan',artist='Drake')
  for guess in ("god's plan","Drake - God's Plan",'GODS PLAN DRAKE'):self.assertTrue(d.correct_guess(song,guess))
  for guess in ('Drake','plan','random song',''):self.assertFalse(d.correct_guess(song,guess))
  self.assertTrue(d.correct_guess(dict(title='アイドル',artist='YOASOBI'),'Idol'))
 def test_autofill_keeps_manual_positions_and_stays_within_song(self):
  for duration in (5,5.1,30,201.4):
   for selected in ([],[0],[max(0,duration-5)],[0,0,0,0,0]):
    filled=d.fill_positions(selected,duration);self.assertEqual(len(filled),5);self.assertTrue(all(value in filled for value in selected));self.assertEqual(filled,sorted(filled));self.assertTrue(all(0<=x<=duration-5+.001 for x in filled))
 @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'ffmpeg required for real media slicing')
 def test_actual_five_second_clips_strip_source_metadata(self):
  with tempfile.TemporaryDirectory() as tmp:
   original=pathlib.Path(tmp)/'full.m4a';snippet=pathlib.Path(tmp)/'clip.mp3'
   subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=12','-metadata','title=Secret Song Title','-metadata','artist=Secret Artist','-c:a','aac',str(original)],check=True,capture_output=True)
   snippet.write_bytes(d.cut_clip(original,7))
   info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(snippet)]))['format']
   self.assertAlmostEqual(float(info['duration']),5,delta=.12);self.assertNotIn('title',info.get('tags',{}));self.assertNotIn('artist',info.get('tags',{}))

if __name__=='__main__':unittest.main()

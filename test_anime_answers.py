"""Multilingual anime-title answers across the catalog and HTTP lifecycle."""
import json,random,time,unicodedata,unittest,urllib.error,urllib.parse,urllib.request
from unittest.mock import patch
import anime_answers as a,recognition as recognition,server as s,leaderboard as lb
from test_variety import HTTPGameTests


def tracks():
 rows=[];seen=set()
 for lane in recognition.ANIME_SONGS.values():
  for theme in lane.values():
   key=(theme['artist'],theme['canonical'])
   if key in seen:continue
   seen.add(key)
   rows.append(dict(id=str(len(rows)+1),artist=theme['artist'],seed_artist=theme['artist'],artist_id=theme['artist'],title=theme['canonical'],genre='Anime',language='Japanese',region='Japan',country='JP',rank=1000,preview='fixture',art='',link=''))
 return rows

class AnimeAnswerTests(unittest.TestCase):
 def test_every_theme_has_english_romaji_and_japanese_answers(self):
  rows=tracks();self.assertGreater(len(rows),240)
  series=set()
  for song in rows:
   answer=a.entry(song);self.assertIsNotNone(answer,song);series.add(recognition.anime_song(song['artist'],song['title'])['series'])
   for alias in answer['aliases']:
    self.assertTrue(a.matches(song,alias),(song,alias))
    self.assertTrue(a.matches(song,unicodedata.normalize('NFD',alias)),alias)
  self.assertEqual(len(series),166)
 def test_normalization_preserves_kanji_and_dakuten(self):
  self.assertEqual(a.title_key('ＳＰＹ × ＦＡＭＩＬＹ'),a.title_key('Spy x Family'))
  self.assertEqual(a.title_key(' 【推しの子】 '),a.title_key('推しの子'))
  self.assertEqual(a.title_key('ﾁｪﾝｿｰﾏﾝ'),a.title_key('チェンソーマン'))
  self.assertEqual(a.title_key('ポケモン'),a.title_key('ぽけもん'))
  self.assertNotEqual(a.title_key('ガ'),a.title_key('カ'))
  self.assertNotEqual(a.title_key('進撃の巨人'),a.title_key('進撃の巨犬'))
 def test_wrong_song_artist_and_unrelated_titles_are_rejected(self):
  song=dict(artist='YOASOBI',title='アイドル')
  for bad in ['YOASOBI','Idol','アイドル','Naruto','推し','',None,123,'x'*201]:self.assertFalse(a.matches(song,bad),bad)
  for good in ['Oshi no Ko','推しの子','【推しの子】','Ｏｓｈｉ　ｎｏ　Ｋｏ']:self.assertTrue(a.matches(song,good))
 def test_suggestions_deduplicate_and_search_all_scripts(self):
  for query in ['進撃','Shingeki','Attack on Titan','ｱｲ','チェンソー','Kusuriya']:
   rows=a.suggestions(tracks(),query);self.assertTrue(rows,query)
   self.assertEqual(len(rows),len({r['id'] for r in rows}))
   self.assertTrue(all(set(row)=={'id','title','japanese','romaji'} for row in rows))
 def test_choices_never_contain_equivalent_anime_answers(self):
  rows=tracks()
  for song in rows:
   options=a.choices(song,rows);self.assertEqual(len(options),4)
   self.assertIn(a.entry(song)['id'],[r['id'] for r in options])
   for i,item in enumerate(options):
    for other in options[i+1:]:self.assertFalse(item['keys']&other['keys'])
 def test_shared_parent_alias_does_not_accept_a_different_specific_title(self):
  original=next(t for t in tracks() if a.entry(t)['title']=='Fullmetal Alchemist')
  sequel=next(t for t in tracks() if a.entry(t)['title']=='Fullmetal Alchemist Brotherhood')
  self.assertTrue(a.matches(sequel,'Fullmetal Alchemist'))
  self.assertFalse(a.matches(original,'Fullmetal Alchemist Brotherhood'))
 def test_settings_do_not_leak_to_other_rotations(self):
  self.assertEqual(a.setting('anime','Anime'),'anime')
  self.assertEqual(a.setting('anime','J-pop'),'song')
  self.assertEqual(a.setting('anime','Anime',True),'song')
  with self.assertRaises(ValueError):a.setting('invalid','Anime')

class AnimeHTTPTests(HTTPGameTests):
 def setUp(self):
  super().setUp();self.created=[]
  self.patches=[patch.object(s,'pool',return_value=tracks()),patch.object(s,'queue_credit'),patch.object(s.credit_workers,'submit'),patch.object(s,'queue_youtube')]
  for item in self.patches:item.start()
 def tearDown(self):
  for key in self.created:s.rooms.pop(key,None)
  for item in reversed(self.patches):item.stop()
  super().tearDown()
 def room(self,mode='guess',multi=False,**extra):
  p=self.post('create',dict(mode=mode,multi=multi,genre='Anime',region='Worldwide',difficulty='Easy',anime_answer='anime',rounds=1,name='Anime Player',**extra));self.created.append(p['room']);return p
 def state(self,p):
  with urllib.request.urlopen(self.url+'state?'+urllib.parse.urlencode(p)) as response:return json.load(response)
 def answer(self,p,**extra):
  v=self.state(p);return self.post('guess',dict(**p,round=v['round'],stage=v['stage'],**extra))
 def test_typed_kanji_correct_reveal_history_score_and_rematch(self):
  p=self.room();room=s.rooms[p['room']];song=room['song'];v=self.state(p)
  self.assertEqual(v['anime_answer'],'anime');self.assertNotIn('answer',v)
  answer=a.entry(song);reveal=self.answer(p,answer=answer['japanese'])
  self.assertEqual(reveal['phase'],'reveal');self.assertTrue(reveal['correct']);self.assertEqual(reveal['answer']['anime']['japanese'],answer['japanese'])
  self.assertEqual(reveal['players'][0]['score'],5)
  self.assertIn(song['id'],lb.played_song_ids(['Anime Player']))
  finished=self.post('next',p);self.assertEqual(finished['phase'],'finished');self.assertEqual(finished['recap'][0]['anime']['id'],answer['id'])
  self.assertEqual(lb.profile('Anime Player')['games'],1)
  lobby=self.post('lobby',p);self.assertEqual(lobby['anime_answer'],'anime')
  settings=dict(mode='guess',genre='Anime',region='Worldwide',difficulty='Easy',decade='All',rounds=1,anime_answer='song')
  self.assertEqual(self.post('settings',dict(**p,**settings))['anime_answer'],'song')
  self.assertEqual(self.post('next',p)['anime_answer'],'song')
 def test_english_romaji_and_fullwidth_guesses(self):
  for field in ['title','romaji']:
   p=self.room();value=a.entry(s.rooms[p['room']]['song'])[field]
   self.assertTrue(self.answer(p,answer=value)['correct'])
 def test_wrong_typed_answer_advances_stage_and_rejects_stale_round(self):
  p=self.room();v=self.answer(p,answer='definitely not an anime');self.assertEqual(v['stage'],1)
  with self.assertRaises(urllib.error.HTTPError):self.post('guess',dict(**p,round=1,stage=0,answer='anything'))
  with self.assertRaises(urllib.error.HTTPError):self.answer(p,answer='x'*201)
  with self.assertRaises(urllib.error.HTTPError):self.answer(p,answer=['Naruto'])
  with self.assertRaises(urllib.error.HTTPError):self.answer(p,id=s.rooms[p['room']]['song']['id'])
 def test_search_and_suggestion_submission_are_anime_only(self):
  p=self.room();song=s.rooms[p['room']]['song'];answer=a.entry(song)
  with urllib.request.urlopen(self.url+'search?'+urllib.parse.urlencode(dict(**p,q=answer['japanese']))) as response:results=json.load(response)['results']
  self.assertTrue(results);self.assertTrue(all(row['id'].startswith('anime:') for row in results));self.assertNotIn('seed_artist',json.dumps(results))
  self.assertTrue(self.answer(p,id=answer['id'])['correct'])
 def test_multiple_choice_uses_titles_and_disallows_song_ids_or_free_text(self):
  p=self.room('choice');v=self.state(p);song=s.rooms[p['room']]['song']
  self.assertEqual(len(v['options']),4);self.assertTrue(all(o['id'].startswith('anime:') for o in v['options']))
  with self.assertRaises(urllib.error.HTTPError):self.answer(p,id=song['id'])
  with self.assertRaises(urllib.error.HTTPError):self.answer(p,answer=a.entry(song)['title'])
  self.assertTrue(self.answer(p,id=a.entry(song)['id'])['correct'])
 def test_multiplayer_host_settings_and_both_answer_languages(self):
  host=self.room(multi=True);guest=self.post('join',dict(room=host['room'],name='Friend'))
  settings=dict(mode='guess',genre='Anime',region='Worldwide',difficulty='Easy',decade='All',rounds=1,anime_answer='anime')
  with self.assertRaises(urllib.error.HTTPError):self.post('settings',dict(**guest,**settings))
  self.post('settings',dict(**host,**settings));self.post('next',host)
  answer=a.entry(s.rooms[host['room']]['song'])
  self.assertTrue(self.answer(host,answer=answer['title'])['submitted'])
  v=self.answer(guest,answer=answer['japanese']);self.assertEqual(v['phase'],'reveal');self.assertEqual([p['score'] for p in v['players']],[1,1])
 def test_video_race_uses_same_anime_matcher_and_cooldown(self):
  p=self.room('race');room=s.rooms[p['room']];room.update(race_started=time.time()-3,race_duration=120,race_status='playing',deadline=time.time()+117)
  v=self.answer(p,answer='wrong');self.assertTrue(v['race_wrong']);self.assertFalse(v['submitted'])
  with self.assertRaises(urllib.error.HTTPError):self.answer(p,answer=a.entry(room['song'])['title'])
  room['race_cooldowns'][p['token']]=0
  self.assertTrue(self.answer(p,answer=a.entry(room['song'])['romaji'])['correct'])
 def test_party_rounds_keep_the_anime_answer_setting(self):
  for mode in ('guess','choice','race'):
   p=self.room('party',party_modes=[mode]);v=self.state(p);room=s.rooms[p['room']]
   self.assertEqual((v['game_mode'],v['mode'],v['anime_answer']),('party',mode,'anime'))
   if mode=='race':room.update(race_started=time.time()-3,race_duration=120,race_status='playing',deadline=time.time()+117)
   answer=a.entry(room['song'])
   result=self.answer(p,id=answer['id']) if mode=='choice' else self.answer(p,answer=answer['japanese'])
   self.assertTrue(result['correct'])
 def test_default_still_accepts_only_song_selection(self):
  p=self.post('create',dict(mode='guess',multi=False,genre='Anime',region='Worldwide',difficulty='Easy',rounds=1));self.created.append(p['room'])
  self.assertEqual(self.state(p)['anime_answer'],'song')
  self.assertTrue(self.answer(p,id=s.rooms[p['room']]['song']['id'])['correct'])

if __name__=='__main__':unittest.main()

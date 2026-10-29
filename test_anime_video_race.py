"""Anime opening selection, strict video resolution, caching and title guesses."""
import hashlib,json,pathlib,subprocess,tempfile,time,unittest,urllib.parse,urllib.request,urllib.error
from contextlib import closing
from concurrent.futures import Future
from unittest.mock import patch
import anime_openings as op,anime_answers as aa,recognition as rec,race_media,server as s
from test_anime_answers import tracks
from test_variety import HTTPGameTests

class OpeningTests(unittest.TestCase):
 def test_opening_registry_has_all_tiers_and_excludes_endings_and_films(self):
  self.assertEqual(len(op.OPENINGS),183)
  for tier in ('Easy','Medium','Hard','Expert','Impossible'):
   rows=[v for v in op.OPENINGS.values() if rec.in_difficulty({'recognition':v['score']},tier)]
   self.assertGreaterEqual(len({t['artist'] for t in rows}),4,tier)
  for artist,title in [('YOASOBI','UNDEAD'),('Aimer','Deep down'),('LiSA','Homura'),('RADWIMPS','Zenzenzense'),('Vaundy','CHAINSAW BLOOD')]:self.assertIsNone(op.opening(dict(artist=artist,title=title)))
  self.assertIsNotNone(op.opening(dict(artist='米津玄師',title='KICK BACK')))
 def test_candidate_validation_rejects_wrong_song_ed_mv_and_long_versions(self):
  theme=op.opening(dict(artist='FLOW',title='COLORS'))
  row=dict(id='abcdefghijk',title='Code Geass Opening COLORS by FLOW',duration=90,channel='Crunchyroll')
  self.assertIsNotNone(op.candidate_score(row,theme))
  for changes in [dict(title='FLOW COLORS Official Music Video'),dict(title='Code Geass ending COLORS'),dict(title='Code Geass opening WORLD END'),dict(title='Code Geass opening COLORS cover'),dict(title='Code Geass opening COLORS full'),dict(duration=240),dict(duration=None),dict(is_live=True),dict(id='../badpath')]:self.assertIsNone(op.candidate_score(dict(row,**changes),theme),changes)
  japanese=dict(row,title='コードギアス ノンクレジットOP「COLORS」FLOW');self.assertIsNotNone(op.candidate_score(japanese,theme))
 def test_official_candidate_preferred_and_cache_survives_memory_reset(self):
  song=dict(artist='FLOW',title='COLORS')
  rows=[dict(id='unofficial1',title='Code Geass Opening COLORS FLOW',duration=90,channel='Fan'),dict(id='official123',title='Code Geass Creditless Opening COLORS FLOW',duration=90,channel='Crunchyroll')]
  with tempfile.TemporaryDirectory() as folder,patch.object(op.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps({'entries':rows}),'')) as run:
   data=pathlib.Path(folder);op._cache.clear()
   with closing(op.candidates(song,data)) as candidates:self.assertEqual(next(candidates)[0],'official123')
   self.assertEqual(run.call_count,1);self.assertIn('--flat-playlist',run.call_args.args[0]);self.assertEqual(run.call_args.kwargs['timeout'],25)
   op._cache.clear()
   with patch.object(op.subprocess,'run',side_effect=AssertionError('Must use SQLite cache')),closing(op.candidates(song,data)) as candidates:self.assertEqual(next(candidates)[0],'official123')
 def test_pinned_opening_needs_no_search_and_regular_youtube_cache_is_ignored(self):
  song=dict(artist='Kenshi Yonezu',title='KICK BACK',_anime_opening=True)
  with tempfile.TemporaryDirectory() as folder,patch.object(s,'DATA',pathlib.Path(folder)),patch.object(s,'resolve_youtube',side_effect=AssertionError('No music-video lookup')),patch.object(op.subprocess,'run',side_effect=AssertionError('Pinned video')),patch.object(s,'prepare_race_media',return_value=('fixture.mp4',90,'video/mp4')) as prepare:
   op._cache.clear();value=s.fetch_race_media(song);self.assertEqual(value[0],'dFlDRhvM4L0');self.assertTrue(prepare.call_args.kwargs['video_required'])
   with self.assertRaises(ValueError):s.fetch_race_media(song,True)
 def test_resolver_rejects_long_or_audio_sources_and_tries_another_video(self):
  song=dict(artist='FLOW',title='COLORS',_anime_opening=True)
  with tempfile.TemporaryDirectory() as folder,patch.object(s,'DATA',pathlib.Path(folder)),patch.object(op,'candidates',return_value=iter([('badfirst123','wrong'),('goodsecond1','opening')])),patch.object(s,'prepare_race_media',side_effect=[('long.mp4',240,'video/mp4'),('opening.mp4',90,'video/mp4')]):
   self.assertEqual(s.fetch_race_media(song)[0],'goodsecond1')
  with patch.object(op,'candidates',return_value=iter([('badfirst123','wrong')])),patch.object(s,'prepare_race_media',return_value=('audio.m4a',90,'audio/mp4')):
   with self.assertRaisesRegex(ValueError,'opening video'):s.fetch_race_media(song)
 def test_strict_video_does_not_fall_back_to_audio_only(self):
  with tempfile.TemporaryDirectory() as folder:
   data=pathlib.Path(folder);media=data/'race-media';media.mkdir();cached=media/(hashlib.sha256(b'abcdefghijk').hexdigest()+'.mp4');cached.write_bytes(b'fixture')
   info={'format':{'duration':90},'streams':[{'codec_type':'audio'}]}
   with patch.object(race_media.subprocess,'check_output',return_value=json.dumps(info).encode()),patch.object(race_media.subprocess,'run') as download:
    with self.assertRaisesRegex(ValueError,'opening video'):race_media.prepare(data,'abcdefghijk',video_required=True)
    download.assert_not_called()
   self.assertFalse(list(media.glob('*.m4a')))

class OpeningHTTPTests(HTTPGameTests):
 def setUp(self):
  super().setUp();self.created=[];self.rows=[dict(t,recognition=rec.anime_song(t['artist'],t['title'])['score']) for t in tracks()]
  self.patches=[patch.object(s,'pool',return_value=self.rows),patch.object(s,'queue_youtube'),patch.object(s,'queue_prefetch',side_effect=lambda song:Future()),patch.object(s,'queue_credit'),patch.object(s.credit_workers,'submit')]
  for item in self.patches:item.start()
 def tearDown(self):
  for code in self.created:s.rooms.pop(code,None)
  for item in reversed(self.patches):item.stop()
  super().tearDown()
 def room(self,tier='Easy',**extra):
  p=self.post('create',dict(mode='race',genre='Anime',region='Worldwide',difficulty=tier,anime_answer='song',multi=False,rounds=2,**extra));self.created.append(p['room']);return p
 def state(self,p):return s.state(s.rooms[p['room']],p['token'])
 def test_each_tier_plays_only_openings_and_prefetch_keeps_that_source(self):
  for tier in ('Easy','Medium','Hard','Expert','Impossible'):
   p=self.room(tier);r=s.rooms[p['room']];v=self.state(p)
   self.assertEqual(v['anime_answer'],'anime');self.assertTrue(v['anime_opening']);self.assertTrue(r['song']['_anime_opening']);self.assertIsNotNone(op.opening(r['song']));self.assertTrue(rec.in_difficulty(r['song'],tier))
   self.assertTrue(r['_next_round']['song']['_anime_opening']);self.assertIsNotNone(op.opening(r['_next_round']['song']))
   with self.assertRaises(urllib.error.HTTPError):self.post('race-audio',dict(**p,round=1))
 def test_anime_search_and_kanji_guess_are_automatic_even_if_song_was_requested(self):
  p=self.room();r=s.rooms[p['room']];answer=aa.entry(r['song']);r.update(race_status='playing',race_duration=90,race_started=time.time()-3,deadline=time.time()+87)
  with urllib.request.urlopen(self.url+'search?'+urllib.parse.urlencode(dict(**p,q=answer['japanese']))) as response:rows=json.load(response)['results']
  self.assertTrue(any(row['id']==answer['id'] for row in rows));self.assertTrue(all(row['id'].startswith('anime:') for row in rows))
  with self.assertRaises(urllib.error.HTTPError):self.post('guess',dict(**p,round=1,id=r['song']['id']))
  v=self.post('guess',dict(**p,round=1,answer=answer['japanese']));self.assertTrue(v['correct']);self.assertEqual(v['answer']['anime']['id'],answer['id']);self.assertIn(r['song']['id'],s.boards.played_song_ids(['Test Player']))
 def test_party_video_round_forces_anime_titles_without_changing_other_rounds(self):
  room=dict(game_mode='party',mode='party',party_modes=['race'],base_difficulty='Easy',genre='Anime',region='Worldwide',difficulty='Easy',pool=self.rows,used=[],rounds=5,anime_answer='song')
  picked=s.choose_round(room);self.assertTrue(picked['_anime_opening']);self.assertTrue(aa.active(room))
  room['mode']='guess';room['game_mode']='guess';self.assertFalse(aa.active(room));self.assertNotIn('_anime_opening',s.choose_round(room))

if __name__=='__main__':unittest.main()

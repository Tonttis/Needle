"""Japanese genre coverage, strict theme admission, tiers and history contracts."""
import random,unittest,tempfile
from pathlib import Path
import leaderboard as lb
from unittest.mock import patch
from urllib.parse import unquote
import catalog as c,recognition as r,server as s

class JapaneseCatalogTests(unittest.TestCase):
 def test_expanded_coverage_and_all_tiers(self):
  self.assertGreaterEqual(len(c.eligible('J-pop','Worldwide')),50)
  self.assertGreaterEqual(len(r.ANIME_SONGS),40)
  self.assertGreaterEqual(sum(len({e['canonical'] for e in lane.values()}) for lane in r.ANIME_SONGS.values()),200)
  config=c.filter_options()
  for scene in ('Worldwide','Europe','Japan','Asia'):
   for genre in ('J-pop','Anime'):
    self.assertEqual(config['support'][scene][genre],c.DIFFICULTIES)
  self.assertNotIn('Anime',config['support']['Finland'])
 def test_ordinary_jpop_song_cannot_enter_anime(self):
  seed=next(x for x in c.SEEDS if x['name']=='Kenshi Yonezu')
  self.assertEqual(r.recognition(seed,'Lemon','Worldwide','Anime'),0)
  self.assertEqual(r.recognition(seed,'KICK BACK','Worldwide','Anime'),90)
  self.assertGreaterEqual(r.recognition(seed,'Lemon','Worldwide','J-pop'),85)
 def test_each_anime_tier_has_distinct_editorial_songs(self):
  for tier in c.DIFFICULTIES:
   artists=set();themes=set()
   for artist,lane in r.ANIME_SONGS.items():
    for entry in lane.values():
     if r.in_difficulty({'recognition':entry['score']},tier):artists.add(artist);themes.add((artist,entry['canonical']))
   self.assertGreaterEqual(len(artists),12,tier)
   self.assertGreaterEqual(len(themes),12,tier)
 def test_japanese_artist_and_theme_aliases_share_history_identity(self):
  for roman,japanese in [('Kenshi Yonezu','米津玄師'),('Hikaru Utada','宇多田ヒカル'),('Eir Aoi','藍井エイル')]:
   self.assertEqual(r.canonical_artist_key(roman),r.canonical_artist_key(japanese))
  original=dict(id='old',artist='YOASOBI',title='アイドル')
  duplicate=dict(id='new',artist='YOASOBI',title='Idol - 2024 Remaster')
  self.assertTrue(c.song_was_played(duplicate,c.song_history_keys(original)))
  self.assertEqual(c.history_identity('Kenshi Yonezu','KICK BACK'),c.history_identity('米津玄師','KICK BACK'))
 def test_jpop_middle_tiers_do_not_collapse_outside_japan(self):
  seed=next(x for x in c.SEEDS if x['name']=='YOASOBI')
  rows=[dict(id=str(i),title=f'Other Song {i}',rank=100) for i in range(60)]
  for region in ('Worldwide','Europe','Japan'):
   result=r.classify_tracks([dict(t) for t in rows],seed,region,'J-pop')
   for tier in ('Medium','Hard','Expert','Impossible'):self.assertTrue(c.band(result,tier),(region,tier))
   self.assertFalse(c.band(result,'Easy'))
  result=r.classify_tracks([dict(t) for t in rows],seed,'Europe','Mixed')
  self.assertTrue(all(t['recognition']==16 for t in result))

 def provider(self,genre):
  seeds=c.eligible(genre,'Worldwide');names={x['name']:i for i,x in enumerate(seeds)}
  calls=[]
  def fetch(path):
   calls.append(path)
   if path.startswith('search/artist'):
    name=unquote(path.split('q=')[1]);i=names[name]
    provider_name=r.artist_names(name)[-1]
    return {'data':[dict(id=i,name=provider_name,nb_fan=100)]}
   i=int(path.split('/')[1]);seed=seeds[i];name=seed['name']
   if genre=='Anime':
    entries={entry['canonical']:entry for entry in r.ANIME_SONGS[r.canonical_artist_key(name)].values()}
    titles=[e['titles'][-1] for e in entries.values()]+['Unrelated Album Track']
   else:titles=list(r.profile(seed)['examples'])+[f'Album Cut {j}' for j in range(70)]
   rows=[dict(id=i*1000+j,title=title,rank=900000-j*1000,artist=dict(id=i,name=r.artist_names(name)[-1]),preview='fixture') for j,title in enumerate(titles)]
   return {'data':rows[50:] if 'index=50' in path else rows[:100]}
  return fetch,calls
 def test_anime_provider_import_is_theme_only_in_all_tiers(self):
  for tier in c.DIFFICULTIES:
   fetch,calls=self.provider('Anime');random.seed(42)
   pool=c.build_pool(fetch,s.clean,'Anime','Worldwide',tier)
   answers=c.band(pool,tier)
   self.assertGreaterEqual(len({c.artist_key(t) for t in answers}),12,tier)
   self.assertTrue(all(r.anime_song(t['seed_artist'],t['title']) for t in pool))
   self.assertNotIn('Unrelated Album Track',{t['title'] for t in pool})
   room=dict(pool=pool,used=[],difficulty=tier,genre='Anime',region='Worldwide',rounds=10,_played_song_ids=set())
   for _ in range(10):
    track=c.choose_song(room);self.assertFalse(c.song_history_keys(track)&room['_played_song_ids'])
    room['used'].append(track['id']);room['_played_song_ids'].update(c.song_history_keys(track))
   self.assertEqual(len(room['artist_counts']),10)
 def test_jpop_provider_import_supports_all_tiers(self):
  for tier in c.DIFFICULTIES:
   fetch,calls=self.provider('J-pop');random.seed(42)
   pool=c.build_pool(fetch,s.clean,'J-pop','Worldwide',tier)
   self.assertGreaterEqual(len({c.artist_key(t) for t in c.band(pool,tier)}),12,tier)

class JapaneseImportHistoryTests(unittest.TestCase):
 def test_native_lookup_fallback_is_bounded_and_keeps_original_artist(self):
  names=['Hironobu Kageyama','Koji Wada','Maaya Sakamoto','Megumi Hayashibara']
  seeds=[next(s for s in c.SEEDS if s['name']==name) for name in names]
  calls=[]
  def fetch(path):
   calls.append(path)
   if path.startswith('search/'):
    query=unquote(path.split('q=')[1])
    for i,name in enumerate(names):
     if query==r.artist_names(name)[1]:return {'data':[dict(id=i,name=query)]}
    return {'data':[]}
   i=int(path.split('/')[1]);name=names[i]
   entries={e['canonical']:e for e in r.ANIME_SONGS[r.canonical_artist_key(name)].values()}
   return {'data':[dict(id=i*100+j,title=e['titles'][-1],artist=dict(id=i,name=r.artist_names(name)[1]),preview='fixture',rank=999999-j) for j,e in enumerate(entries.values())]}
  with patch.object(c,'SEEDS',seeds):pool=c.build_pool(fetch,s.clean,'Anime','Worldwide','Easy')
  self.assertEqual(len({c.artist_key(t) for t in c.band(pool,'Easy')}),4)
  self.assertEqual(sum(path.startswith('search/') for path in calls),8)
  self.assertEqual({t['seed_artist'] for t in pool},set(names))
 def test_legacy_japanese_and_translated_titles_stay_excluded(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(lb,'DB_PATH',Path(tmp)/'db'):
   lb.record_played(['Alice'],'old','song:米津玄師|kickback')
   lb.record_played(['Alice'],'old-idol','song:yoasobi|idol')
   seen,artists,stats=lb.selection_history(['Alice'])
   self.assertTrue(c.song_was_played(dict(id='new',artist='Kenshi Yonezu',title='KICK BACK'),seen))
   self.assertTrue(c.song_was_played(dict(id='new-idol',artist='YOASOBI',title='アイドル'),seen))
   self.assertEqual(artists['kenshiyonezu'],1)

if __name__=='__main__':unittest.main()

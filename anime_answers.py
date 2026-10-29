"""Offline multilingual anime answers; no provider lookups on the guessing path."""
import pathlib, random, unicodedata
from recognition import anime_song


def title_key(value):
    value=unicodedata.normalize('NFKC',str(value)).casefold().replace('&','and').replace('×','x')
    value=''.join(chr(ord(c)-0x60) if '\u30a1'<=c<='\u30f6' else c for c in value)
    # Latin macrons/accents are optional; Japanese combining dakuten are retained.
    value=''.join(''.join(c for c in unicodedata.normalize('NFKD',ch) if not unicodedata.combining(c)) if 'LATIN' in unicodedata.name(ch,'') else ch for ch in value)
    return ''.join(c for c in value if c.isalnum() or c=='ー')


SERIES={}
for line in pathlib.Path(__file__).with_name('anime_series.tsv').read_text(encoding='utf-8').splitlines():
    if not line or line.startswith('#'):continue
    catalog,english,romaji,native,extra=line.split('|')
    names=catalog.split(';')
    aliases=list(dict.fromkeys(names+[english,romaji,native]+[a for a in extra.split(';') if a]))
    entry=dict(id='anime:'+title_key(english),title=english,japanese=native,romaji=romaji,aliases=aliases,keys={title_key(a) for a in aliases})
    for name in names:
        if name in SERIES:raise ValueError('Duplicate anime series mapping: '+name)
        SERIES[name]=entry


def active(room):return room.get('genre')=='Anime' and (room.get('anime_answer')=='anime' or room.get('mode')=='race') and not room.get('playlist_report')

def setting(value,genre,playlist=False):
    if value not in ('song','anime'):raise ValueError('Choose song/artist or anime title.')
    return value if genre=='Anime' and not playlist else 'song'

def entry(song):
    theme=anime_song(song.get('seed_artist') or song.get('artist',''),song.get('title',''))
    return SERIES.get(theme['series']) if theme else None

def matches(song,text):
    answer=entry(song)
    return bool(answer and isinstance(text,str) and 0<len(text)<=200 and title_key(text) in answer['keys'])

def public(answer):return {k:answer[k] for k in ('id','title','japanese','romaji')}

def suggestions(tracks,text):
    query=title_key(text)
    if len(query)<1:return []
    unique={}
    for song in tracks:
        answer=entry(song)
        if not answer or answer['id'] in unique:continue
        ranks=[0 if query==key else 1 if key.startswith(query) else 2 for key in answer['keys'] if query in key]
        if ranks:unique[answer['id']]=(min(ranks),answer)
    return [public(a) for _,a in sorted(unique.values(),key=lambda row:(row[0],row[1]['title']))[:25]]

def choices(song,tracks):
    answer=entry(song)
    if not answer:raise ValueError('This song has no catalog anime title mapping.')
    # Shared parent titles (e.g. SAO seasons) must never be separate options.
    others={}
    for track in tracks:
        item=entry(track)
        if item and item['id']!=answer['id'] and not (item['keys']&answer['keys']):others[item['id']]=item
    selected=[answer]
    for item in random.sample(list(others.values()),len(others)):
        if all(not(item['keys']&old['keys']) for old in selected):selected.append(item)
        if len(selected)==4:break
    if len(selected)<2:raise ValueError('This mix needs at least two different anime titles. Broaden the difficulty or decade.')
    random.shuffle(selected)
    return selected

"""Spotify track identification for the official Spotify Embed (no audio proxy)."""
import base64,json,os,re,threading,time,urllib.parse,urllib.request
from catalog import norm
from recognition import song_key
from playlists import spotify_token as user_token

_token_lock=threading.Lock();_token={'value':'','expires':0};_matches={}

def search_token():
    if os.getenv('SPOTIFY_ACCESS_TOKEN','').strip() or os.getenv('SPOTIFY_REFRESH_TOKEN','').strip():return user_token()
    client=os.getenv('SPOTIFY_CLIENT_ID','').strip();secret=os.getenv('SPOTIFY_CLIENT_SECRET','').strip()
    if not client or not secret:raise ValueError('Configure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET on the server to find Spotify tracks.')
    with _token_lock:
        if _token['value'] and time.time()<_token['expires']:return _token['value']
        basic=base64.b64encode((client+':'+secret).encode()).decode()
        req=urllib.request.Request('https://accounts.spotify.com/api/token',data=urllib.parse.urlencode({'grant_type':'client_credentials'}).encode(),headers={'Authorization':'Basic '+basic,'Content-Type':'application/x-www-form-urlencoded'})
        try:
            with urllib.request.urlopen(req,timeout=12) as response:data=json.load(response)
            token=data['access_token'];expiry=int(data.get('expires_in',3600))
        except Exception as e:raise ValueError('Spotify authorization failed. Check the server credentials.') from e
        _token.update(value=token,expires=time.time()+max(1,expiry-60));return token

def resolve(artist,title):
    key=(norm(artist),song_key(title));cached=_matches.get(key)
    if cached and time.time()-cached[0]<86400:return dict(cached[1])
    token=search_token();market=os.getenv('SPOTIFY_MARKET','FI').upper()
    if not re.fullmatch('[A-Z]{2}',market):market='FI'
    query=urllib.parse.urlencode({'q':artist+' '+title,'type':'track','market':market,'limit':10})
    req=urllib.request.Request('https://api.spotify.com/v1/search?'+query,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=12) as response:data=json.load(response)
    except Exception as e:raise ValueError('Spotify search is unavailable or refused access. Check the server credentials and app permissions.') from e
    want_artist=norm(artist);want_title=song_key(title)
    for item in (data.get('tracks') or {}).get('items',[]):
        track_id=str(item.get('id',''));artists=item.get('artists') or []
        if not re.fullmatch(r'[A-Za-z0-9]{22}',track_id):continue
        if song_key(str(item.get('name','')))!=want_title:continue
        if not any(norm(str(a.get('name','')))==want_artist for a in artists):continue
        match={'spotify_id':track_id,'spotify_url':'https://open.spotify.com/track/'+track_id}
        _matches[key]=(time.time(),match);return dict(match)
    raise ValueError('No matching Spotify track was found for this song.')

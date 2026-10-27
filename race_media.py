import subprocess,json,pathlib,tempfile,hashlib,threading,os,time
_locks={}
_guard=threading.Lock()
_cache_guard=threading.RLock()
MAX_BYTES=2*1024**3
MAX_AGE=30*86400

def prune(folder,protected=(),now=None,limit=MAX_BYTES):
 now=time.time() if now is None else now
 protected={str(pathlib.Path(p)) for p in protected if p}
 with _cache_guard:
  files=[p for p in folder.iterdir() if p.is_file() and p.suffix in ('.mp4','.m4a')]
  for p in list(files):
   if str(p) not in protected and now-p.stat().st_mtime>MAX_AGE:
    p.unlink(missing_ok=True);files.remove(p)
  total=sum(p.stat().st_size for p in files)
  for p in sorted(files,key=lambda p:p.stat().st_atime):
   if total<=limit:break
   if str(p) in protected:continue
   total-=p.stat().st_size;p.unlink(missing_ok=True)
  return total

def start_janitor(data,protected=lambda:()):
 def run():
  folder=data/'race-media';folder.mkdir(exist_ok=True)
  while True:
   try:prune(folder,protected())
   except OSError:pass
   threading.Event().wait(3600)
 threading.Thread(target=run,daemon=True,name='race-cache-cleanup').start()

def prepare(data,video_id,audio_only=False,protected=lambda:()):
 with _guard:mutex=_locks.setdefault(video_id,threading.Lock())
 with mutex:
  folder=data/'race-media';folder.mkdir(exist_ok=True)
  prune(folder,protected())
  for audio_only in ((True,) if audio_only else (False,True)):
   target=folder/(hashlib.sha256(video_id.encode()).hexdigest()+('.m4a' if audio_only else '.mp4'))
   try:
    if not target.exists():
     with tempfile.TemporaryDirectory(dir=folder) as temp:
      output=pathlib.Path(temp)/('media'+target.suffix)
      fmt='bestaudio[ext=m4a]/bestaudio' if audio_only else 'bestvideo[height<=480][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]'
      subprocess.run(['yt-dlp','--js-runtimes','node','--no-playlist','--max-filesize','80M','-f',fmt,'--merge-output-format','mp4','-o',str(output),'https://www.youtube.com/watch?v='+video_id],check=True,timeout=150,capture_output=True)
      if not output.exists() or output.stat().st_size>80*1024*1024:raise ValueError('Media unavailable')
      output.replace(target)
    with _cache_guard:
     st=target.stat();os.utime(target,ns=(time.time_ns(),st.st_mtime_ns))
     if prune(folder,(*protected(),str(target)))>MAX_BYTES:
      target.unlink(missing_ok=True);raise ValueError('Media cache is full; finish another active game first.')
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(target)],timeout=15))
    duration=float(info['format']['duration'])
    if duration<=0 or not any(x['codec_type']=='audio' for x in info['streams']):raise ValueError('No audio stream')
    return str(target),duration,'audio/mp4' if audio_only else 'video/mp4'
   except Exception:
    target.unlink(missing_ok=True)
  raise ValueError('Full video and audio could not be downloaded. Retry or skip this song.')

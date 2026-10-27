import subprocess,json,pathlib,tempfile,hashlib,threading
_locks={}
_guard=threading.Lock()
def prepare(data,video_id,audio_only=False):
 with _guard:mutex=_locks.setdefault(video_id,threading.Lock())
 with mutex:
  folder=data/'race-media';folder.mkdir(exist_ok=True)
  for audio_only in ((True,) if audio_only else (False,True)):
   target=folder/(hashlib.sha256(video_id.encode()).hexdigest()+('.m4a' if audio_only else '.mp4'))
   try:
    if not target.exists():
     with tempfile.TemporaryDirectory(dir=folder) as temp:
      output=pathlib.Path(temp)/('media'+target.suffix)
      fmt='bestaudio[ext=m4a]/bestaudio' if audio_only else 'bestvideo[height<=480][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]'
      subprocess.run(['yt-dlp','--no-playlist','--max-filesize','80M','-f',fmt,'--merge-output-format','mp4','-o',str(output),'https://www.youtube.com/watch?v='+video_id],check=True,timeout=150,capture_output=True)
      if not output.exists() or output.stat().st_size>80*1024*1024:raise ValueError('Media unavailable')
      output.replace(target)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(target)],timeout=15))
    duration=float(info['format']['duration'])
    if duration<=0 or not any(x['codec_type']=='audio' for x in info['streams']):raise ValueError('No audio stream')
    return str(target),duration,'audio/mp4' if audio_only else 'video/mp4'
   except Exception:
    target.unlink(missing_ok=True)
  raise ValueError('Full video and audio could not be downloaded. Retry or skip this song.')

"""Local-only anime UI fixture with generated audio; never imported in production."""
import json,pathlib,subprocess,tempfile
import server as s
from test_anime_answers import tracks

def main():
 temporary=tempfile.TemporaryDirectory();root=pathlib.Path(temporary.name);s.boards.DB_PATH=root/'scores.sqlite3'
 path=root/'preview.mp3';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=2','-c:a','libmp3lame',str(path)],check=True,capture_output=True)
 audio=(path.read_bytes(),'audio/mpeg');rows=tracks()
 s.pool=lambda *args:rows;s.choose_round=lambda r:rows[0];s.queue_credit=lambda *args:None
 s.credit_workers.submit=lambda *args,**kwargs:None
 s.audio_cache.get=lambda *args:audio;s.deezer_reveal_cache.get=lambda *args:audio
 class Handler(s.Handler):
  def log_message(self,*args):pass
  def do_GET(self):
   if self.path.startswith('/api/warm'):return self.reply({'ready':True})
   if self.path.startswith('/api/catalog-status'):return self.reply({'phase':'ready'})
   return super().do_GET()
  def do_POST(self):
   if self.path=='/api/catalog-prepare':
    self.rfile.read(int(self.headers.get('Content-Length',0)));return self.reply({'job':'fixture'})
   return super().do_POST()
 http=s.ThreadingHTTPServer(('127.0.0.1',0),Handler);print(json.dumps({'port':http.server_address[1]}),flush=True)
 try:http.serve_forever()
 finally:http.server_close();temporary.cleanup()

if __name__=='__main__':main()

"""Local-only browser-test server. No test routes are added to production."""
import json,pathlib,subprocess,tempfile,time
import server as s
import duel

def main():
    temporary=tempfile.TemporaryDirectory();root=pathlib.Path(temporary.name)
    s.boards.DB_PATH=root/'scores.sqlite3'
    audio={}
    for name,freq,length in (('A',440,120),('B',660,180)):
        path=root/(name+'.m4a')
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'sine=frequency={freq}:duration={length}','-c:a','aac',str(path)],check=True,capture_output=True)
        audio[name]=(str(path),length)
    def search(path):
        if not path.startswith('search?'):raise ValueError('Fixture only supports song search')
        return {'data':[dict(id=i,title='Song '+name,artist=dict(id=i,name='Artist '+name),album={},preview='') for i,name in enumerate(('A','B'),1)]}
    def load(song,audio_only):
        name=song['title'][-1];path,length=audio[name]
        return 'abcdefghij'+name,song['title'],path,length,'audio/mp4'
    s.DUEL.fetch=search;s.DUEL.load_media=load
    original_time=time.time;offset=[0.]
    duel.time.time=lambda:original_time()+offset[0]
    class Handler(s.Handler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path.startswith('/api/warm'):return self.reply({'ready':True})
            return super().do_GET()
        def do_POST(self):
            if self.path=='/__test/advance':
                count=int(self.headers.get('Content-Length',0))
                value=json.loads(self.rfile.read(count));offset[0]+=float(value['seconds'])
                with s.lock:
                    for room in s.rooms.values():
                        if room.get('mode')=='duel':s.DUEL.tick(room)
                return self.reply({'advanced':offset[0]})
            return super().do_POST()
    http=s.ThreadingHTTPServer(('127.0.0.1',0),Handler);s.DUEL.start_clock()
    print(json.dumps({'port':http.server_address[1]}),flush=True)
    try:http.serve_forever()
    finally:http.server_close();temporary.cleanup()

if __name__=='__main__':main()

/* Private per-player Song Duel UI. The server owns all phases, clocks and answers. */
window.NeedleDuel=(()=>{
 let view,bridge,panel,key='',received=0,candidate=null,searchVersion=0,positions=[],revision=0;
 let audioContext,gain,analyser,audioSource,buffers=[],bufferKey='',loadingKey='',loadingAbort,playVersion=0,animation,playing=-1,guessBusy=false,readyBusy=false;
 const el=id=>document.getElementById(id),escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const format=seconds=>{seconds=Math.max(0,Math.floor(Number(seconds)||0));return Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')};
 const now=()=>view?view.serverTime+(performance.now()-received)/1000:0;
 const phaseKey=v=>v.code+':'+v.round+':'+(v.duel?.generation||'lobby')+':'+v.phase;
 const status=message=>{if(el('duel-feedback'))el('duel-feedback').textContent=message};
 const stale=(active,identity)=>!view||bridge.getSession()!==active||key!==identity;
 function keyboardLayout(){
  const focus=document.activeElement,id=focus?.id||'',viewport=window.visualViewport;
  const typing=!!view&&['duel-query','duel-song-title','duel-song-artist','duel-guess'].includes(id);
  const visible=viewport?.height||innerHeight,open=typing&&visible<innerHeight-100;
  document.body.classList.toggle('duel-keyboard',open);
  document.body.dataset.duelFocus=id==='duel-query'?'search':id==='duel-guess'?'guess':'selection';
  document.body.style.height=open?visible+'px':'';
 }
 window.visualViewport?.addEventListener('resize',keyboardLayout);
 document.addEventListener('focusin',keyboardLayout);
 document.addEventListener('focusout',()=>queueMicrotask(keyboardLayout));
 async function send(action,data={}){
  const active=bridge.getSession(),identity=key,round=view.round,generation=view.duel?.generation;
  bridge.before();
  try{const result=await bridge.api(action,{...active,round,generation,...data});if(bridge.getSession()===active)bridge.apply(result);return result}
  catch(error){if(!stale(active,identity))bridge.error(error);return null}
 }
 function stop(){
  playVersion++;cancelAnimationFrame(animation);playing=-1;
  if(audioSource){audioSource.onended=null;try{audioSource.stop()}catch{}audioSource=null}
  document.body.classList.remove('is-playing');window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:false}}));
  panel?.querySelectorAll('.duel-clip-play').forEach(button=>{button.classList.remove('playing');button.style.setProperty('--played','0%')});
 }
 function hide(){
  stop();loadingAbort?.abort();loadingAbort=null;loadingKey='';buffers=[];bufferKey='';key='';searchVersion++;guessBusy=false;readyBusy=false;
  if(panel)panel.hidden=true;view=null;keyboardLayout();
 }
 async function acknowledgeAudio(){
  if(readyBusy||view?.phase!=='loading'||view.duel?.ready)return;
  readyBusy=true;
  try{const result=await send('duel-ready');if(!result&&el('duel-audio-retry'))el('duel-audio-retry').hidden=false}
  finally{readyBusy=false}
 }
 async function prepareAudio(){
  const clipKey=view?.duel?.clip_key;if(!clipKey||loadingKey===clipKey)return;
  if(bufferKey===clipKey){await acknowledgeAudio();return}
  loadingAbort?.abort();loadingAbort=new AbortController();const abort=loadingAbort;
  const active=bridge.getSession(),identity=key;loadingKey=clipKey;
  const timeout=setTimeout(()=>abort.abort(),25000);
  try{
   audioContext ||= new AudioContext();
   const query=new URLSearchParams({...active,round:String(view.round)});
   const loaded=await Promise.all(Array.from({length:5},async(_,i)=>{
    const response=await fetch('/duel-clip/'+encodeURIComponent(clipKey)+'?'+query+'&clip='+i,{signal:abort.signal,cache:'no-store'});
    if(!response.ok)throw Error('Your clips could not load. Retry audio.');
    const data=await response.arrayBuffer();return audioContext.decodeAudioData(data);
   }));
   if(stale(active,identity)||view.duel?.clip_key!==clipKey)return;
   buffers=loaded;bufferKey=clipKey;status('Your five clips are ready. Waiting for your opponent…');
   await acknowledgeAudio();
  }catch(error){if(!stale(active,identity)){status('Audio did not load. Check your connection and retry.');if(el('duel-audio-retry'))el('duel-audio-retry').hidden=false}}
  finally{clearTimeout(timeout);if(loadingKey===clipKey)loadingKey=''}
 }
 async function play(index){
  if(view?.phase!=='playing'||view.duel?.done||now()<view.duel.starts_at)return;
  if(bufferKey!==view.duel.clip_key||!buffers[index]){status('Loading your audio. Please wait.');await prepareAudio();return}
  stop();const version=playVersion,clipKey=view.duel.clip_key;
  try{
   audioContext ||= new AudioContext();await audioContext.resume();
   if(version!==playVersion||view?.phase!=='playing'||view.duel.done||view.duel.clip_key!==clipKey)return;
   gain ||= audioContext.createGain();analyser ||= audioContext.createAnalyser();analyser.fftSize=128;
   gain.gain.setValueAtTime(Number(el('duel-volume')?.value??localStorage.getItem('needle-volume')??.7),audioContext.currentTime);
   const source=audioContext.createBufferSource();source.buffer=buffers[index];source.connect(gain);gain.disconnect();gain.connect(analyser);analyser.disconnect();analyser.connect(audioContext.destination);
   audioSource=source;playing=index;const started=audioContext.currentTime;
   source.onended=()=>{if(audioSource===source)stop()};source.start(0,0,Math.min(5,source.buffer.duration));
   const button=panel.querySelector('[data-play="'+index+'"]');button?.classList.add('playing');
   document.body.classList.add('is-playing');window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:true,analyser,duration:5}}));
   const frequency=new Uint8Array(analyser.frequencyBinCount);
   function frame(){if(audioSource!==source)return;button?.style.setProperty('--played',Math.min(100,(audioContext.currentTime-started)*20)+'%');analyser.getByteFrequencyData(frequency);panel.querySelectorAll('.duel-visual i').forEach((bar,i)=>bar.style.transform='scaleY('+(0.12+frequency[3+i*3]/255*.88)+')');animation=requestAnimationFrame(frame)}frame();
  }catch(error){stop();bridge.error(error)}
 }
 function steps(){const phase=view.phase,stage=['picking','preparing'].includes(phase)?0:['clips','preparing-clips'].includes(phase)?1:['loading','playing'].includes(phase)?2:3;return '<nav class="duel-stages" aria-label="Round stages">'+['Pick a song · 30s','Choose 5 clips · 30s','Guess · 45s'].map((text,i)=>'<span class="'+(i===stage?'active':i<stage?'complete':'')+'">'+(i<stage?'✓':i+1)+' '+text+'</span>').join('')+'</nav>'}
 function heading(title,copy){return '<div class="duel-heading"><div><div class="eyebrow">SONG DUEL / SIDE A ↔ SIDE B</div><h1>'+title+'</h1><p>'+copy+'</p></div><div id="duel-time" class="duel-time" aria-label="Time remaining"></div></div>'}
 function controls(){return '<div class="duel-controls"><label>VOLUME <input id="duel-volume" type="range" min="0" max="1" step=".05" value="'+escape(localStorage.getItem('needle-volume')||'.7')+'"></label><button id="duel-stop" type="button">Stop audio ■</button></div>'}
 function mount(){
  panel.innerHTML=steps();const phase=view.phase;
  if(phase==='lobby'){
   panel.innerHTML+=heading('A song for your rival.','Two players. Two secret songs. Five chances to find the hook.')+'<div class="duel-lobby-layout"><div class="duel-records" aria-hidden="true"><span>A</span><b>↔</b><span>B</span></div><div class="duel-lobby-copy"><h2>Make them guess.</h2><p>Choose any song for your opponent. They choose five five-second moments blindly, then listen and guess in any order.</p><p>Unlimited replays and guesses. One point per correct song; a missed song pick forfeits the round.</p><div class="duel-lobby-actions"><label>Rounds <select id="duel-rounds">'+[1,3,5,10,20,30].map(n=>'<option '+(n===view.rounds?'selected':'')+'>'+n+'</option>').join('')+'</select></label><button class="primary" id="duel-start" type="button">Start Song Duel ↗</button></div><p id="duel-lobby-note" class="muted"></p></div></div>';
   el('duel-rounds').onchange=()=>send('duel-settings',{rounds:Number(el('duel-rounds').value)});
   el('duel-start').onclick=()=>send('duel-next');
  }else if(phase==='picking'){
   candidate=null;searchVersion++;
   panel.innerHTML+=heading('Choose their mystery song.','Search any song or paste a public YouTube video link. Your opponent cannot see your choice.')+'<div class="duel-pick-grid"><section class="duel-search-side"><form id="duel-search-form" class="duel-search-form"><label class="sr-only" for="duel-query">Song, artist, or YouTube link</label><input id="duel-query" maxlength="200" placeholder="Song, artist, or YouTube link…" autocomplete="off"><button id="duel-find" type="submit">Find ↗</button></form><p id="duel-search-status" class="muted" aria-live="polite">A song they know—or a deep cut. Your call.</p><div id="duel-search-results" class="duel-search-results"></div></section><section class="duel-selection"><div class="eyebrow">YOUR SECRET PICK</div><div id="duel-picked" aria-live="polite"></div><form id="duel-pick-form" hidden><label for="duel-song-title">Song title used for guessing</label><input id="duel-song-title" maxlength="160" required><label for="duel-song-artist">Artist</label><input id="duel-song-artist" maxlength="120" required><p id="duel-title-hint" class="muted"></p><button id="duel-pick-confirm" class="primary" type="submit">Send to opponent ↗</button></form></section></div>';
   el('duel-search-form').onsubmit=search;
   el('duel-pick-form').onsubmit=async event=>{event.preventDefault();if(!candidate)return;el('duel-pick-confirm').disabled=true;await send('duel-pick',{selection:candidate.selection,title:el('duel-song-title').value.trim(),artist:el('duel-song-artist').value.trim()});if(el('duel-pick-confirm'))el('duel-pick-confirm').disabled=false};
  }else if(phase==='clips'){
   positions=[...(view.duel.positions||[])];revision=view.duel.revision||0;
   panel.innerHTML+=heading('Find five moments.','This is your opponent’s song. You will hear only the five parts you choose—after this stage.')+'<div id="duel-clip-picker"><div class="duel-timeline-labels"><span>0:00</span><span id="duel-seek-label">0:00 → 0:05</span><span>'+format(view.duel.duration)+'</span></div><div class="duel-timeline"><div class="duel-timeline-texture" aria-hidden="true"></div><div id="duel-markers" aria-hidden="true"></div><input id="duel-seek" aria-label="Choose the start of a five-second clip" type="range" min="0" max="'+Math.max(0,(view.duel.duration||5)-5)+'" step=".1" value="0"></div><div class="duel-pick-controls"><button id="duel-add" type="button">+ Add this 5-second part</button><span id="duel-slot-count"></span></div><div id="duel-slots" class="duel-slots"></div><div class="duel-confirm-row"><p id="duel-selection-note" class="muted">Change your choices until you lock them. Missing choices fill automatically when time ends.</p><button id="duel-lock" class="primary" type="button">Lock my five clips ✓</button></div></div><p id="duel-no-song" class="muted" hidden>Your opponent did not choose a song. Waiting for their guessing round.</p>';
   el('duel-seek').oninput=()=>{const start=Number(el('duel-seek').value);el('duel-seek-label').textContent=format(start)+' → '+format(start+5)};
   el('duel-add').onclick=()=>{if(positions.length>=5||view.duel.locked)return;positions.push(Number(el('duel-seek').value));savePositions(false)};
   el('duel-lock').onclick=()=>savePositions(true);
  }else if(['preparing','preparing-clips','loading'].includes(phase)){
   panel.innerHTML+=heading(phase==='preparing'?'Getting the records ready.':phase==='preparing-clips'?'Cutting your five moments.':'Ready on both sides.','Your guessing timer stays paused while audio loads.')+'<div class="duel-wait"><div class="duel-orbit" aria-hidden="true">↔</div><h2 id="duel-wait-label">'+(phase==='loading'?'Loading your private clips…':'Preparing audio…')+'</h2><p class="muted">Both players get their own five clips. No titles. No artwork. Just sound.</p><p id="duel-feedback" aria-live="polite"></p><button id="duel-audio-retry" type="button" hidden>Retry audio ↻</button></div>';
   el('duel-audio-retry').onclick=()=>{el('duel-audio-retry').hidden=true;prepareAudio()};
  }else if(phase==='playing'){
   panel.innerHTML+=heading('Five parts. One song.','Play any clip, in any order. Unlimited replays and guesses until the clock runs out.')+'<div class="duel-play-layout"><section class="duel-listen"><div class="duel-visual" aria-hidden="true">'+Array.from({length:12},()=>'<i></i>').join('')+'</div><div id="duel-play-clips" class="duel-play-clips">'+Array.from({length:5},(_,i)=>'<button class="duel-clip-play" type="button" data-play="'+i+'"><span class="duel-clip-number">'+(i+1)+'</span><span>▶ Play clip<small>'+format(view.duel.positions[i])+' · 5 seconds</small></span><span class="duel-clip-progress"></span></button>').join('')+'</div>'+controls()+'</section><section class="duel-answer-side"><div class="eyebrow">TRUST YOUR EARS</div><h2>Name that song.</h2><form id="duel-guess-form"><label class="sr-only" for="duel-guess">Song title or artist and title</label><input id="duel-guess" maxlength="200" autocomplete="off" placeholder="Song title (artist optional)…" required><button class="primary" id="duel-guess-submit" type="submit">Guess ↗</button></form><p id="duel-feedback" role="status" aria-live="polite"></p><button id="duel-skip" type="button">I give up—skip my song →</button><p id="duel-opponent-status" class="muted"></p><button id="duel-audio-retry" type="button" hidden>Retry audio ↻</button></section></div>';
   panel.querySelectorAll('[data-play]').forEach(button=>button.onclick=()=>play(Number(button.dataset.play)));
   el('duel-stop').onclick=stop;el('duel-volume').oninput=()=>{const volume=Number(el('duel-volume').value);localStorage.setItem('needle-volume',String(volume));document.getElementById('volume').value=String(volume);if(gain&&audioContext)gain.gain.setTargetAtTime(volume,audioContext.currentTime,.015)};
   el('duel-guess-form').onsubmit=async event=>{event.preventDefault();const input=el('duel-guess');const guess=input.value.trim();if(!guess||guessBusy)return;guessBusy=true;el('duel-guess-submit').disabled=true;try{await send('duel-guess',{guess})}finally{guessBusy=false;if(el('duel-guess-submit')){el('duel-guess-submit').disabled=!!view.duel.done;if(!view.duel.done){input.select();input.focus()}}}};
   el('duel-skip').onclick=()=>send('duel-skip');el('duel-audio-retry').onclick=()=>prepareAudio();
  }else if(phase==='reveal'){
   const answers=view.duel.answers||[];
   panel.innerHTML+=heading('The records revealed.',escape(view.duel.notice||'A point for each correct song. Both players can score.'))+'<div class="duel-reveal-grid">'+(answers.length?answers.map(answer=>'<article class="duel-result"><div class="eyebrow">'+escape(answer.owner)+'’S PICK FOR '+escape(answer.guesser)+'</div><span class="duel-result-mark">'+(answer.correct?'✓':'○')+'</span><h2>'+escape(answer.title)+'</h2><p>'+escape(answer.artist)+'</p><strong>'+(answer.correct?escape(answer.guesser)+' guessed it · +1 point':escape(answer.guesser)+(answer.result==='no-song'?' had no song':' did not guess it'))+'</strong>'+(answer.link&&/^https:\/\/www\.youtube\.com\/watch\?v=[\w-]{11}$/.test(answer.link)?'<a href="'+escape(answer.link)+'" target="_blank" rel="noopener">Watch on YouTube ↗</a>':'')+'</article>').join(''):'<p class="muted">Neither player chose a song before the timer ended.</p>')+'</div><div class="duel-bottom"><p class="muted">'+(view.host?'Ready for another pair of mystery songs?':'Waiting for the host to continue.')+'</p><button class="primary" id="duel-next" type="button">'+(view.round>=view.rounds?'See final scores →':'Next round →')+'</button></div>';
   el('duel-next').hidden=!view.host;el('duel-next').onclick=()=>send('duel-next');
  }else if(phase==='finished'){
   const players=[...view.players].sort((a,b)=>b.score-a.score),winner=players[0],tie=players.every(p=>p.score===winner.score);
   panel.innerHTML+=heading(tie?'An even match.':escape(winner.name)+' wins!','Your Song Duel is complete. Same room, new songs?')+'<div class="duel-finish-scores">'+players.map(p=>'<div><span>'+escape(p.name)+(p.me?' · you':'')+'</span><strong>'+p.score+'<small> / '+view.rounds+'</small></strong></div>').join('')+'</div><div class="duel-bottom"><button id="duel-home" type="button">Home</button><button id="duel-rematch" class="primary" type="button">Back to lobby ↻</button></div>';
   el('duel-home').onclick=()=>bridge.goHome();el('duel-rematch').hidden=!view.host;el('duel-rematch').onclick=()=>send('duel-lobby');
  }else if(phase==='duel-error'){
   panel.innerHTML+=heading('A record couldn’t load.','The guessing clock never started. You can retry with different songs.')+'<div class="duel-wait"><p role="alert">'+escape(view.duel.error)+'</p><div class="duel-bottom"><button id="duel-abandon-round" type="button">Skip this round →</button><button class="primary" id="duel-retry-round" type="button">Pick songs again ↻</button></div><p class="muted">'+(view.host?'You control the retry.':'Waiting for the host to retry or skip this round.')+'</p></div>';
   el('duel-abandon-round').hidden=el('duel-retry-round').hidden=!view.host;el('duel-retry-round').onclick=()=>send('duel-retry');el('duel-abandon-round').onclick=()=>send('duel-next');
  }
 }
 async function search(event){
  event.preventDefault();const query=el('duel-query').value.trim();if(query.length<2)return;
  const version=++searchVersion,identity=key,active=bridge.getSession();el('duel-find').disabled=true;el('duel-search-status').textContent='Searching…';
  try{
   const result=await bridge.api('duel-search?'+new URLSearchParams({...active,round:String(view.round),generation:view.duel.generation,q:query}));
   if(stale(active,identity)||version!==searchVersion)return;
   el('duel-search-status').textContent=result.results.length?'Choose the song you want them to guess.':'No songs found. Try another search or paste a YouTube link.';
   let page=0;
   function showResults(){
    const pages=Math.ceil(result.results.length/3);page=Math.max(0,Math.min(page,pages-1));
    el('duel-search-results').innerHTML=result.results.slice(page*3,page*3+3).map((song,i)=>'<button type="button" data-candidate="'+(page*3+i)+'"><span>'+escape(song.title)+'</span><small>'+escape(song.artist)+'</small><b>↗</b></button>').join('')+(pages>1?'<div class="list-pages"><button data-duel-page="prev" type="button" '+(page===0?'disabled':'')+'>← Previous</button><span>'+(page+1)+' / '+pages+'</span><button data-duel-page="next" type="button" '+(page===pages-1?'disabled':'')+'>Next →</button></div>':'');
    panel.querySelectorAll('[data-duel-page]').forEach(button=>button.onclick=()=>{page+=button.dataset.duelPage==='next'?1:-1;showResults()});
    panel.querySelectorAll('[data-candidate]').forEach(button=>button.onclick=()=>{candidate=result.results[Number(button.dataset.candidate)];el('duel-pick-form').hidden=false;el('duel-song-title').value=candidate.title;el('duel-song-artist').value=candidate.artist;el('duel-song-title').readOnly=el('duel-song-artist').readOnly=!candidate.custom;el('duel-title-hint').textContent=candidate.custom?'Check the title and artist: these are the answers accepted for this YouTube pick.':'Your opponent must name this song. Artist and punctuation are optional.';panel.querySelectorAll('[data-candidate]').forEach(b=>b.classList.toggle('selected',b===button))});
   }showResults();
  }catch(error){if(!stale(active,identity)&&version===searchVersion)el('duel-search-status').textContent=error.message}
  finally{if(!stale(active,identity)&&el('duel-find'))el('duel-find').disabled=false}
 }
 function savePositions(locked){revision++;paintSlots();send('duel-clips',{positions:[...positions],revision,locked})}
 function paintSlots(){
  if(!el('duel-slots'))return;const locked=!!view.duel.locked,end=view.duel.duration||5;
  el('duel-slot-count').textContent=positions.length+' / 5 selected';
  el('duel-slots').innerHTML=Array.from({length:5},(_,i)=>'<button type="button" data-remove="'+i+'" '+(locked||i>=positions.length?'disabled':'')+'><span>'+String(i+1).padStart(2,'0')+'</span><b>'+ (i<positions.length?format(positions[i])+' → '+format(positions[i]+5):'Choose a part')+'</b><small>'+(i<positions.length?'× Remove':'5 seconds')+'</small></button>').join('');
  el('duel-markers').innerHTML=positions.map((start,i)=>'<i style="left:'+(start/end*100)+'%;width:'+Math.min(100,5/end*100)+'%"><span>'+(i+1)+'</span></i>').join('');
  panel.querySelectorAll('[data-remove]').forEach(button=>button.onclick=()=>{if(locked)return;positions.splice(Number(button.dataset.remove),1);savePositions(false)});
  el('duel-add').disabled=locked||positions.length>=5;el('duel-lock').disabled=locked||positions.length!==5;el('duel-seek').disabled=locked;
  el('duel-lock').textContent=locked?'Clips locked ✓':'Lock my five clips ✓';
 }
 function update(){
  const d=view.duel||{},opponent=view.players.find(p=>!p.me);
  if(view.phase==='lobby'){
   el('duel-start').hidden=!view.host;el('duel-start').disabled=view.players.length!==2;el('duel-rounds').disabled=!view.host;
   if(document.activeElement!==el('duel-rounds'))el('duel-rounds').value=String(view.rounds);
   el('duel-lobby-note').textContent=view.players.length===2?(view.host?'Both players are here. Start when you’re ready.':'Waiting for the host to start.'):'Copy the invite above. Song Duel needs exactly two players.';
  }
  if(view.phase==='picking')el('duel-picked').textContent=d.picked?d.picked.title+' — '+d.picked.artist+' · '+(d.picked.status==='error'?'Could not load—choose another song.':d.picked.status==='ready'?'Ready for your opponent.':'Loading audio…'):'No song chosen yet.';
  if(view.phase==='clips'){
   if((d.revision||0)>=revision){positions=[...(d.positions||[])];revision=d.revision||0}
   el('duel-clip-picker').hidden=!!d.done;el('duel-no-song').hidden=!d.done;paintSlots();
  }
  if(view.phase==='loading'){if(d.done){status('Your opponent did not pick a song. Waiting for their audio.')}else prepareAudio()}
  if(view.phase==='playing'){
   if(d.done)stop();
   const disabled=!!d.done||now()<d.starts_at;
   panel.querySelector('.duel-listen').hidden=d.done==='no-song';panel.querySelector('.duel-play-layout').classList.toggle('duel-without-song',d.done==='no-song');
   el('duel-guess-form').hidden=el('duel-skip').hidden=d.done==='no-song';
   panel.querySelectorAll('[data-play],#duel-guess,#duel-guess-submit,#duel-skip').forEach(node=>node.disabled=disabled||(node.id==='duel-guess-submit'&&guessBusy));
   status(d.done==='no-song'?'Your opponent did not pick a song for you. Waiting for their guess…':d.done==='correct'?'Correct! Waiting for your opponent…':d.done?'Your song is skipped. Waiting for your opponent…':d.feedback||'Song title is enough. Artist + title works too.');
   el('duel-opponent-status').textContent=opponent?.submitted?opponent.name+' has finished guessing.':(opponent?.name||'Your opponent')+' is still listening.';
   if(!d.done&&bufferKey!==d.clip_key)prepareAudio();
  }
  tick();
 }
 function tick(){
  if(!view)return;const timer=el('duel-time');if(!timer)return;
  const timed=['picking','clips','playing'].includes(view.phase),remaining=Math.max(0,Math.ceil(view.deadline-now()));
  timer.textContent=timed?(view.phase==='playing'&&now()<view.duel.starts_at?'Get ready':remaining+'s'):['preparing','preparing-clips','loading'].includes(view.phase)?'◌':'';
  timer.classList.toggle('urgent',timed&&remaining<=10);
  if(view.phase==='playing'&&!view.duel.done){const disabled=now()<view.duel.starts_at||remaining===0;panel.querySelectorAll('[data-play],#duel-guess,#duel-guess-submit,#duel-skip').forEach(node=>node.disabled=disabled||(node.id==='duel-guess-submit'&&guessBusy))}
  if(timed&&remaining===0&&audioSource)stop();
 }
 setInterval(tick,100);
 function render(value,apiBridge){
  bridge=apiBridge;view=value;received=performance.now();panel=el('duel-panel');panel.hidden=false;
  const identity=phaseKey(view);
  if(identity!==key){stop();loadingAbort?.abort();loadingKey='';key=identity;guessBusy=false;mount()}
  if(view.duel?.clip_key&&bufferKey!==view.duel.clip_key&&view.phase==='loading'){buffers=[];bufferKey=''}
  update();keyboardLayout();
 }
 return {render,hide,stop,format};
})();

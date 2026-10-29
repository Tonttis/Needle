/* Private per-player Song Duel UI. The server owns all phases, clocks and answers. */
window.NeedleDuel=(()=>{
 let view,bridge,panel,key='',received=0,candidate=null,searchVersion=0,positions=[],revision=0;
 let guessTimer,guessVersion=0,previewAbort,previewRun=0,revealPage=0,clipSaves=Promise.resolve(),clipLockBusy=false;
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
  playVersion++;previewRun++;previewAbort?.abort();previewAbort=null;cancelAnimationFrame(animation);playing=-1;
  if(audioSource){audioSource.onended=null;try{audioSource.stop()}catch{}audioSource=null}
  document.body.classList.remove('is-playing');window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:false}}));
  clearVisual();panel?.querySelectorAll('.duel-result').forEach(node=>node.classList.remove('preview-playing'));
  panel?.querySelectorAll('.duel-clip-play').forEach(button=>{button.classList.remove('playing');button.style.setProperty('--played','0%')});
 }
 function hide(){
  clearTimeout(guessTimer);guessVersion++;stop();loadingAbort?.abort();loadingAbort=null;loadingKey='';buffers=[];bufferKey='';key='';searchVersion++;guessBusy=false;readyBusy=false;
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
   buffers=loaded;bufferKey=clipKey;status('Your five clips are ready. Waiting for the room…');
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
   gain ||= audioContext.createGain();analyser ||= audioContext.createAnalyser();analyser.fftSize=1024;analyser.smoothingTimeConstant=.75;
   gain.gain.setValueAtTime(volume(),audioContext.currentTime);
   const source=audioContext.createBufferSource();source.buffer=buffers[index];source.connect(gain);gain.disconnect();gain.connect(analyser);analyser.disconnect();analyser.connect(audioContext.destination);
   audioSource=source;playing=index;const started=audioContext.currentTime;
   source.onended=()=>{if(audioSource===source)stop()};source.start(0,0,Math.min(5,source.buffer.duration));
   const button=panel.querySelector('[data-play="'+index+'"]');button?.classList.add('playing');
   document.body.classList.add('is-playing');window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:true,analyser,duration:5}}));
   animateVisual(source,Math.min(5,source.buffer.duration),'Clip '+(index+1),button);
  }catch(error){stop();bridge.error(error)}
 }
 function steps(){const phase=view.phase,stage=['picking','preparing'].includes(phase)?0:['clips','preparing-clips'].includes(phase)?1:['loading','playing'].includes(phase)?2:3;return '<nav class="duel-stages" aria-label="Round stages">'+['Pick a song · 30s','Choose 5 clips · 30s','Guess · 45s'].map((text,i)=>'<span class="'+(i===stage?'active':i<stage?'complete':'')+'">'+(i<stage?'✓':i+1)+' '+text+'</span>').join('')+'</nav>'}
 function heading(title,copy){return '<div class="duel-heading"><div><div class="eyebrow">SONG DUEL / SIDE A ↔ SIDE B</div><h1>'+title+'</h1><p>'+copy+'</p></div><div id="duel-time" class="duel-time" aria-label="Time remaining"></div></div>'}
 function volume(){const stored=Number(localStorage.getItem('needle-volume')??.7);return Number.isFinite(stored)?Math.max(0,Math.min(1,stored)):.7}
 function controls(){return '<div class="duel-controls" aria-label="Song Duel audio controls"><label for="duel-volume">VOLUME</label><input id="duel-volume" aria-label="Song Duel volume" type="range" min="0" max="1" step=".01" value="'+volume()+'"><output id="duel-volume-value" for="duel-volume">'+(volume()===0?'Muted':Math.round(volume()*100)+'%')+'</output><button id="duel-stop" type="button" disabled>Stop ■</button></div>'}
 function visual(){return '<div class="duel-visual"><canvas id="duel-spectrum" aria-hidden="true"></canvas><span id="duel-visual-label">Ready to listen</span></div>'}
 function sizeVisual(){
  const canvas=el('duel-spectrum');if(!canvas)return null;
  const bounds=canvas.getBoundingClientRect();if(!bounds.width||!bounds.height)return null;
  const ratio=Math.min(2,devicePixelRatio||1),width=Math.round(bounds.width*ratio),height=Math.round(bounds.height*ratio);
  if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height}
  return {canvas,context:canvas.getContext('2d'),width,height};
 }
 function clearVisual(){
  cancelAnimationFrame(animation);const visual=sizeVisual();
  if(visual){const {canvas,context:c,width:w,height:h}=visual;canvas.dataset.level='0';c.clearRect(0,0,w,h);c.strokeStyle='#b7a2e944';c.lineWidth=1;c.beginPath();c.moveTo(0,h*.48);c.lineTo(w,h*.48);c.stroke()}
  if(el('duel-visual-label'))el('duel-visual-label').textContent='Ready to listen';
  if(el('duel-stop'))el('duel-stop').disabled=true;
 }
 function animateVisual(source,duration,label,button){
  cancelAnimationFrame(animation);const started=audioContext.currentTime,frequency=new Uint8Array(analyser.frequencyBinCount),wave=new Uint8Array(analyser.fftSize);let previous=-Infinity;
  if(el('duel-stop'))el('duel-stop').disabled=false;
  function frame(timestamp){
   if(audioSource!==source)return;
   if(timestamp-previous>=1000/30){
    previous=timestamp;const elapsed=Math.min(duration,audioContext.currentTime-started),visual=sizeVisual();
    button?.style.setProperty('--played',Math.min(100,elapsed/duration*100)+'%');
    if(el('duel-visual-label'))el('duel-visual-label').textContent=label+' · '+elapsed.toFixed(1)+' / '+duration.toFixed(0)+'s';
    if(visual){
     const {canvas,context:c,width:w,height:h}=visual;analyser.getByteFrequencyData(frequency);analyser.getByteTimeDomainData(wave);
     c.clearRect(0,0,w,h);const gradient=c.createLinearGradient(0,h,0,0);gradient.addColorStop(0,'#b59ae9');gradient.addColorStop(1,'#e5ff87');c.fillStyle=gradient;
     let peak=0;const bars=40,gap=w/200,barWidth=w/bars-gap;
     for(let i=0;i<bars;i++){const low=Math.floor((Math.pow(frequency.length,i/bars)-1)),high=Math.max(low+1,Math.floor(Math.pow(frequency.length,(i+1)/bars)-1));let power=0;for(let j=low;j<Math.min(high,frequency.length);j++)power=Math.max(power,frequency[j]);peak=Math.max(peak,power);const size=Math.max(1,power/255*h*.7);c.globalAlpha=.65;c.fillRect(i*w/bars,h-size,barWidth,size)}
     c.globalAlpha=1;c.strokeStyle='#e6f5d5';c.lineWidth=Math.max(1,h/65);c.beginPath();for(let i=0;i<wave.length;i++){const x=i/(wave.length-1)*w,y=h*.4+(wave[i]-128)/128*h*.32;if(i)c.lineTo(x,y);else c.moveTo(x,y)}c.stroke();canvas.dataset.level=String(peak);
    }
   }
   animation=requestAnimationFrame(frame);
  }
  animation=requestAnimationFrame(frame);
 }
 window.addEventListener('resize',()=>{if(!audioSource)clearVisual()});

 function mount(){
  panel.innerHTML=steps();const phase=view.phase;
  if(phase==='lobby'){
   panel.innerHTML+=heading('A song for your rival.','2–8 players. Secret songs. Five moments to find the hook.')+'<div class="duel-lobby-layout"><div class="duel-records" aria-hidden="true"><span>A</span><b>↔</b><span>B</span></div><div class="duel-lobby-copy"><h2>Make them guess.</h2><p>Choose a song for your assigned player. Everyone receives one mystery song and chooses five moments blindly. Assignments rotate between rounds.</p><p>Unlimited replays and guesses. One point per correct song. Submit a song to play; a missing incoming pick awards a forfeit point.</p><div class="duel-lobby-actions"><label>Rounds <select id="duel-rounds">'+[1,3,5,10,20,30].map(n=>'<option '+(n===view.rounds?'selected':'')+'>'+n+'</option>').join('')+'</select></label><button class="primary" id="duel-start" type="button">Start Song Duel ↗</button></div><p id="duel-lobby-note" class="muted"></p></div></div>';
   el('duel-rounds').onchange=()=>send('duel-settings',{rounds:Number(el('duel-rounds').value)});
   el('duel-start').onclick=()=>send('duel-next');
  }else if(phase==='picking'){
   candidate=null;searchVersion++;
   panel.innerHTML+=heading('Pick a song for '+escape(view.duel.recipient)+'.','Search any song or paste a public YouTube video link. Your opponent cannot see your choice.')+'<div class="duel-pick-grid"><section class="duel-search-side"><form id="duel-search-form" class="duel-search-form"><label class="sr-only" for="duel-query">Song, artist, or YouTube link</label><input id="duel-query" maxlength="200" placeholder="Song, artist, or YouTube link…" autocomplete="off"><button id="duel-find" type="submit">Find ↗</button></form><p id="duel-search-status" class="muted" aria-live="polite">A song they know—or a deep cut. Your call.</p><div id="duel-search-results" class="duel-search-results"></div></section><section class="duel-selection"><div class="eyebrow">YOUR SECRET PICK</div><div id="duel-picked" aria-live="polite"></div><form id="duel-pick-form" hidden><label for="duel-song-title">Song title used for guessing</label><input id="duel-song-title" maxlength="160" required><label for="duel-song-artist">Artist</label><input id="duel-song-artist" maxlength="120" required><p id="duel-title-hint" class="muted"></p><button id="duel-pick-confirm" class="primary" type="submit">Send to opponent ↗</button></form></section></div>';
   el('duel-search-form').onsubmit=search;
   el('duel-pick-form').onsubmit=async event=>{event.preventDefault();if(!candidate)return;el('duel-pick-confirm').disabled=true;await send('duel-pick',{selection:candidate.selection,title:el('duel-song-title').value.trim(),artist:el('duel-song-artist').value.trim()});if(el('duel-pick-confirm'))el('duel-pick-confirm').disabled=false};
  }else if(phase==='clips'){
   positions=[...(view.duel.positions||[])].sort((a,b)=>a-b);revision=view.duel.revision||0;
   panel.innerHTML+=heading('Find five moments.','Your song is from '+escape(view.duel.supplier)+'. You will hear only the five parts you choose—after this stage.')+'<div id="duel-clip-picker"><div class="duel-timeline-labels"><span>0:00</span><span id="duel-seek-label">0:00 → 0:05</span><span>'+format(view.duel.duration)+'</span></div><div class="duel-timeline"><div class="duel-timeline-texture" aria-hidden="true"></div><div id="duel-markers" aria-hidden="true"></div><input id="duel-seek" aria-label="Choose the start of a five-second clip" type="range" min="0" max="'+Math.max(0,(view.duel.duration||5)-5)+'" step=".1" value="0"></div><div class="duel-pick-controls"><button id="duel-add" type="button">+ Add this 5-second part</button><span id="duel-slot-count"></span></div><div id="duel-slots" class="duel-slots"></div><div class="duel-confirm-row"><p id="duel-selection-note" class="muted">Change your choices until you lock them. Missing choices fill automatically when time ends.</p><button id="duel-lock" class="primary" type="button">Lock my five clips ✓</button></div></div><p id="duel-no-song" class="muted" hidden>Your opponent did not choose a song. Waiting for their guessing round.</p>';
   el('duel-seek').oninput=()=>{const start=Number(el('duel-seek').value);el('duel-seek-label').textContent=format(start)+' → '+format(start+5)};
   el('duel-add').onclick=()=>{if(positions.length>=5||view.duel.locked)return;positions.push(Number(el('duel-seek').value));savePositions(false)};
   el('duel-lock').onclick=()=>savePositions(true);
  }else if(['preparing','preparing-clips','loading'].includes(phase)){
   panel.innerHTML+=heading(phase==='preparing'?'Getting the records ready.':phase==='preparing-clips'?'Cutting your five moments.':'Ready around the room.','Your guessing timer stays paused while audio loads.')+'<div class="duel-wait"><div class="duel-orbit" aria-hidden="true">↔</div><h2 id="duel-wait-label">'+(phase==='loading'?'Loading your private clips…':'Preparing audio…')+'</h2><p class="muted">Everyone gets their own five clips. No titles. No artwork. Just sound.</p><p id="duel-feedback" aria-live="polite"></p><button id="duel-audio-retry" type="button" hidden>Retry audio ↻</button></div>';
   el('duel-audio-retry').onclick=()=>{el('duel-audio-retry').hidden=true;prepareAudio()};
  }else if(phase==='playing'){
   panel.innerHTML+=heading('Five parts. One song.','Play any clip, in any order. Unlimited replays and guesses until the clock runs out.')+'<div class="duel-play-layout"><section class="duel-listen">'+visual()+'<div id="duel-play-clips" class="duel-play-clips">'+Array.from({length:5},(_,i)=>'<button class="duel-clip-play" type="button" data-play="'+i+'"><span class="duel-clip-number">'+(i+1)+'</span><span>▶ Play clip<small>'+format(view.duel.positions[i])+' · 5 seconds</small></span><span class="duel-clip-progress"></span></button>').join('')+'</div></section><section class="duel-answer-side"><div class="eyebrow">TRUST YOUR EARS</div><h2>Name that song.</h2><form id="duel-guess-form"><label class="sr-only" for="duel-guess">Song title or artist and title</label><input id="duel-guess" maxlength="200" autocomplete="off" placeholder="Search a song or artist…" aria-controls="duel-suggestions" required><button class="primary" id="duel-guess-submit" type="submit">Guess ↗</button></form><div id="duel-suggestions" class="duel-suggestions" aria-label="Song suggestions"></div><p id="duel-suggestion-status" class="muted" aria-live="polite"></p><p id="duel-feedback" role="status" aria-live="polite"></p><button id="duel-skip" type="button">I give up—skip my song →</button><p id="duel-opponent-status" class="muted"></p><button id="duel-audio-retry" type="button" hidden>Retry audio ↻</button></section></div>';
   panel.querySelectorAll('[data-play]').forEach(button=>button.onclick=()=>play(Number(button.dataset.play)));
   el('duel-guess').oninput=()=>{clearTimeout(guessTimer);guessVersion++;el('duel-suggestions').replaceChildren();el('duel-suggestion-status').textContent='';if(el('duel-guess').value.trim().length>=2)guessTimer=setTimeout(guessSuggestions,250)};
   el('duel-guess-form').onsubmit=async event=>{event.preventDefault();const input=el('duel-guess');const guess=input.value.trim();if(!guess||guessBusy)return;clearTimeout(guessTimer);guessVersion++;el('duel-suggestions').replaceChildren();guessBusy=true;el('duel-guess-submit').disabled=true;try{await send('duel-guess',{guess})}finally{guessBusy=false;if(el('duel-guess-submit')){el('duel-guess-submit').disabled=!!view.duel.done;if(!view.duel.done){input.select();input.focus()}}}};
   el('duel-skip').onclick=()=>send('duel-skip');el('duel-audio-retry').onclick=()=>prepareAudio();
  }else if(phase==='reveal'){
   const answers=view.duel.answers||[];
   panel.innerHTML+=heading('The records revealed.',escape(view.duel.notice||'A point for each correct song. Everyone can score.'))+visual()+'<div class="duel-reveal-grid">'+(answers.length?answers.map(answer=>'<article class="duel-result"><div class="eyebrow">'+escape(answer.owner)+'’S PICK FOR '+escape(answer.guesser)+'</div><span class="duel-result-mark">'+(answer.correct?'✓':'○')+'</span><h2>'+escape(answer.title)+'</h2><p>'+escape(answer.artist)+'</p><strong>'+(answer.correct?escape(answer.guesser)+' guessed it · +1 point':escape(answer.guesser)+(answer.result==='no-song'?' had no song':' did not guess it'))+'</strong>'+(answer.link&&/^https:\/\/www\.youtube\.com\/watch\?v=[\w-]{11}$/.test(answer.link)?'<a href="'+escape(answer.link)+'" target="_blank" rel="noopener">Watch on YouTube ↗</a>':'')+'</article>').join(''):'<p class="muted">Nobody chose a song before the timer ended.</p>')+'</div><div class="duel-preview-controls"><button id="duel-preview-play" type="button">▶ Replay all previews</button>'+(answers.length>2?'<div class="duel-reveal-pages"><button type="button" id="duel-reveal-prev" aria-label="Previous songs">←</button><span id="duel-reveal-page"></span><button type="button" id="duel-reveal-next" aria-label="Next songs">→</button></div>':'')+'<span id="duel-preview-status" role="status"></span></div><div class="duel-bottom"><p class="muted">'+(view.host?'Ready for another round of mystery songs?':'Waiting for the host to continue.')+'</p><button class="primary" id="duel-next" type="button">'+(view.round>=view.rounds?'See final scores →':'Next round →')+'</button></div>';
   el('duel-preview-play').onclick=()=>playPreviews();revealPage=0;showRevealPage();if(el('duel-reveal-prev')){el('duel-reveal-prev').onclick=()=>{revealPage--;showRevealPage()};el('duel-reveal-next').onclick=()=>{revealPage++;showRevealPage()}};
   queueMicrotask(()=>{if(view?.phase==='reveal')playPreviews()});
   el('duel-next').hidden=!view.host;el('duel-next').onclick=()=>send('duel-next');
  }else if(phase==='finished'){
   const players=[...view.players].sort((a,b)=>b.score-a.score),winner=players[0],leaders=players.filter(p=>p.score===winner.score),tie=leaders.length>1;
   panel.innerHTML+=heading(tie?(players.length>2?'Shared first place.':'An even match.'):escape(winner.name)+' wins!',(tie&&players.length>2?leaders.length+' players tied for first place. ':'')+'Your Song Duel is complete. Same room, new songs?')+'<div class="duel-finish-scores '+(players.length>2?'duel-group-scores':'')+'">'+players.map(p=>'<div class="'+(p.score===winner.score?'duel-finish-leader':'')+'"><span>'+escape(p.name)+(p.me?' · you':'')+'</span><strong>'+p.score+'<small> / '+view.rounds+'</small></strong></div>').join('')+'</div><div class="duel-bottom"><button id="duel-home" type="button">Home</button><button id="duel-rematch" class="primary" type="button">Back to lobby ↻</button></div>';
   el('duel-home').onclick=()=>bridge.goHome();el('duel-rematch').hidden=!view.host;el('duel-rematch').onclick=()=>send('duel-lobby');
  }else if(phase==='duel-error'){
   panel.innerHTML+=heading('A record couldn’t load.','The guessing clock never started. You can retry with different songs.')+'<div class="duel-wait"><p role="alert">'+escape(view.duel.error)+'</p><div class="duel-bottom"><button id="duel-abandon-round" type="button">Skip this round →</button><button class="primary" id="duel-retry-round" type="button">Pick songs again ↻</button></div><p class="muted">'+(view.host?'You control the retry.':'Waiting for the host to retry or skip this round.')+'</p></div>';
   el('duel-abandon-round').hidden=el('duel-retry-round').hidden=!view.host;el('duel-retry-round').onclick=()=>send('duel-retry');el('duel-abandon-round').onclick=()=>send('duel-next');
  }
  panel.insertAdjacentHTML('beforeend',controls());
  el('duel-volume').oninput=()=>{const value=Number(el('duel-volume').value);localStorage.setItem('needle-volume',String(value));el('volume').value=String(value);el('duel-volume-value').textContent=value===0?'Muted':Math.round(value*100)+'%';el('duel-volume').setAttribute('aria-valuetext',value===0?'Muted':Math.round(value*100)+' percent');if(gain&&audioContext)gain.gain.setTargetAtTime(value,audioContext.currentTime,.015)};
  el('duel-stop').onclick=()=>{stop();if(view.phase==='reveal')previewStatus('Previews stopped.')};clearVisual();
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
 async function guessSuggestions(){
  const input=el('duel-guess'),query=input?.value.trim();if(!query||view?.phase!=='playing'||view.duel.done)return;
  const version=++guessVersion,identity=key,active=bridge.getSession();el('duel-suggestion-status').textContent='Searching…';
  try{
   const result=await bridge.api('duel-guess-search?'+new URLSearchParams({...active,round:String(view.round),generation:view.duel.generation,q:query}));
   if(stale(active,identity)||version!==guessVersion||view.duel.done)return;
   el('duel-suggestion-status').textContent=result.results.length?'Choose a suggestion to guess, or type your own title.':'No suggestions. You can still submit your own title.';
   el('duel-suggestions').innerHTML=result.results.map((song,i)=>'<button type="button" data-suggestion="'+i+'"><span>'+escape(song.title)+'</span><small>'+escape(song.artist)+'</small></button>').join('');
   panel.querySelectorAll('[data-suggestion]').forEach(button=>button.onclick=()=>{if(view.duel.done||guessBusy||now()<view.duel.starts_at||now()>=view.deadline)return;const song=result.results[Number(button.dataset.suggestion)];input.value=song.artist+' - '+song.title;el('duel-guess-form').requestSubmit()});
  }catch(error){if(!stale(active,identity)&&version===guessVersion)el('duel-suggestion-status').textContent='Suggestions unavailable. Type a title and press Guess.'}
 }
 function showRevealPage(){
  const count=view?.duel?.answers?.length||0,pages=Math.max(1,Math.ceil(count/2));revealPage=Math.max(0,Math.min(revealPage,pages-1));
  panel.querySelectorAll('.duel-result').forEach((node,index)=>node.hidden=Math.floor(index/2)!==revealPage);
  if(el('duel-reveal-page')){el('duel-reveal-page').textContent=(revealPage+1)+' / '+pages;el('duel-reveal-prev').disabled=revealPage===0;el('duel-reveal-next').disabled=revealPage===pages-1}
 }
 function previewStatus(message){if(el('duel-preview-status'))el('duel-preview-status').textContent=message}
 async function playPreviews(){
  stop();const run=previewRun,identity=key,active=bridge.getSession(),answers=[...(view.duel.answers||[])];
  const current=()=>run===previewRun&&!stale(active,identity)&&view.phase==='reveal';
  audioContext ||= new AudioContext();
  try{await audioContext.resume()}catch{}
  for(let i=0;i<answers.length&&current();i++){
   revealPage=Math.floor(i/2);showRevealPage();
   previewStatus('Loading '+(i+1)+' / '+answers.length+'…');
   const abort=new AbortController();previewAbort=abort;const timeout=setTimeout(()=>abort.abort(),20000);
   try{
    const query=new URLSearchParams({...active,round:String(view.round),generation:view.duel.generation,song:String(i)});
    const response=await fetch('/duel-preview?'+query,{signal:abort.signal,cache:'no-store'});if(!response.ok)throw Error('Preview unavailable');
    const buffer=await audioContext.decodeAudioData(await response.arrayBuffer());clearTimeout(timeout);if(!current())return;
    if(audioContext.state!=='running'){previewStatus('Press Replay to hear the previews.');return}
    gain ||= audioContext.createGain();analyser ||= audioContext.createAnalyser();analyser.fftSize=1024;analyser.smoothingTimeConstant=.75;
    gain.gain.setValueAtTime(volume(),audioContext.currentTime);
    const source=audioContext.createBufferSource();source.buffer=buffer;source.connect(gain);gain.disconnect();gain.connect(analyser);analyser.disconnect();analyser.connect(audioContext.destination);audioSource=source;
    panel.querySelectorAll('.duel-result').forEach((n,j)=>n.classList.toggle('preview-playing',i===j));
    previewStatus((i+1)+' / '+answers.length+' · '+answers[i].artist+' — '+answers[i].title);
    const duration=Math.min(10,buffer.duration);animateVisual(source,duration,'Song '+(i+1)+' of '+answers.length);document.body.classList.add('is-playing');window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:true,analyser,duration}}));
    await new Promise(resolve=>{source.onended=resolve;abort.signal.addEventListener('abort',resolve,{once:true});source.start(0,0,duration)});
    if(audioSource===source){audioSource=null;clearVisual();document.body.classList.remove('is-playing');window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:false}}))}
   }catch(error){if(current())previewStatus('Preview unavailable. Trying the next song…')}
   finally{clearTimeout(timeout);if(previewAbort===abort)previewAbort=null}
  }
  if(current()){stop();panel.querySelectorAll('.duel-result').forEach(n=>n.classList.remove('preview-playing'));previewStatus('Previews complete · 10 seconds per song.')}
 }
 function savePositions(locked){
  if(clipLockBusy)return;positions.sort((a,b)=>a-b);revision++;if(locked)clipLockBusy=true;
  const data={positions:[...positions],revision,locked},identity=key;paintSlots();
  clipSaves=clipSaves.catch(()=>{}).then(()=>{if(identity!==key||view?.phase!=='clips'||(!locked&&data.revision<revision))return;return send('duel-clips',data)}).finally(()=>{if(identity===key&&locked){clipLockBusy=false;paintSlots()}});
 }
 function paintSlots(){
  if(!el('duel-slots'))return;const locked=!!view.duel.locked||clipLockBusy,end=view.duel.duration||5;
  el('duel-slot-count').textContent=positions.length+' / 5 selected';
  el('duel-slots').innerHTML=Array.from({length:5},(_,i)=>'<button type="button" data-remove="'+i+'" '+(locked||i>=positions.length?'disabled':'')+'><span>'+String(i+1).padStart(2,'0')+'</span><b>'+ (i<positions.length?format(positions[i])+' → '+format(positions[i]+5):'Choose a part')+'</b><small>'+(i<positions.length?'× Remove':'5 seconds')+'</small></button>').join('');
  el('duel-markers').innerHTML=positions.map((start,i)=>'<i style="left:'+(start/end*100)+'%;width:'+Math.min(100,5/end*100)+'%"><span>'+(i+1)+'</span></i>').join('');
  panel.querySelectorAll('[data-remove]').forEach(button=>button.onclick=()=>{if(locked)return;positions.splice(Number(button.dataset.remove),1);savePositions(false)});
  el('duel-add').disabled=locked||positions.length>=5;el('duel-lock').disabled=locked||positions.length!==5;el('duel-seek').disabled=locked;
  el('duel-lock').textContent=locked?'Clips locked ✓':'Lock my five clips ✓';
 }
 function update(){
  const d=view.duel||{},others=view.players.filter(p=>!p.me),remaining=others.filter(p=>!p.submitted).length;
  if(view.phase==='lobby'){
   el('duel-start').hidden=!view.host;el('duel-start').disabled=view.players.length<2;el('duel-rounds').disabled=!view.host;
   if(document.activeElement!==el('duel-rounds'))el('duel-rounds').value=String(view.rounds);
   el('duel-lobby-note').textContent=view.players.length>=2?(view.host?view.players.length+' / 8 players joined. Invite more friends or start when ready.':'Waiting for the host to start. Up to 8 players can join.'):'Copy the invite above. Song Duel needs at least two players.';
  }
  if(view.phase==='picking')el('duel-picked').textContent=d.picked?d.picked.title+' — '+d.picked.artist+' · '+(d.picked.status==='error'?'Could not load—choose another song.':d.picked.status==='ready'?'Ready for your opponent.':'Loading audio…'):'No song chosen yet.';
  if(view.phase==='clips'){
   if((d.revision||0)>=revision){positions=[...(d.positions||[])].sort((a,b)=>a-b);revision=d.revision||0}
   el('duel-clip-picker').hidden=!!d.done;el('duel-no-song').hidden=!d.done;el('duel-no-song').textContent=d.done==='forfeit-win'?'No incoming song. You receive +1 by forfeit. Waiting for the room.':'You did not submit a song. This round is skipped for you.';paintSlots();
  }
  if(view.phase==='loading'){if(d.done){status(d.done==='forfeit-win'?'You receive +1 by forfeit. Waiting for the room to load audio.':'You did not submit a song. Waiting for the room.')}else prepareAudio()}
  if(view.phase==='playing'){
   if(d.done){stop();clearTimeout(guessTimer);guessVersion++;el('duel-suggestions').replaceChildren();el('duel-suggestion-status').textContent=''}
   const disabled=!!d.done||now()<d.starts_at,withoutSong=['no-song','no-pick','forfeit-win'].includes(d.done);
   panel.querySelector('.duel-listen').hidden=withoutSong;panel.querySelector('.duel-play-layout').classList.toggle('duel-without-song',withoutSong);
   el('duel-guess-form').hidden=el('duel-skip').hidden=withoutSong;
   panel.querySelectorAll('[data-play],#duel-guess,#duel-guess-submit,#duel-skip').forEach(node=>node.disabled=disabled||(node.id==='duel-guess-submit'&&guessBusy));
   status(d.done==='forfeit-win'?'You supplied a song but received none: +1 by forfeit. Waiting for the room.':d.done==='no-pick'?'You did not submit a song. Waiting for the room.':d.done==='no-song'?'Your opponent did not pick a song for you. Waiting for their guess…':d.done==='correct'?'Correct! Waiting for the room…':d.done?'Your song is skipped. Waiting for the room…':d.feedback||'Song title is enough. Artist + title works too.');
   el('duel-opponent-status').textContent=remaining?remaining+' of '+others.length+' other players still listening.':'Everyone else has finished guessing.';
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
  if(identity!==key){clearTimeout(guessTimer);guessVersion++;stop();loadingAbort?.abort();loadingKey='';key=identity;guessBusy=false;clipLockBusy=false;clipSaves=Promise.resolve();mount()}
  if(view.duel?.clip_key&&bufferKey!==view.duel.clip_key&&view.phase==='loading'){buffers=[];bufferKey=''}
  update();keyboardLayout();
 }
 return {render,hide,stop,format};
})();

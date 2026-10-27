const $=s=>document.querySelector(s),esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let mode='guess',session=JSON.parse(sessionStorage.getItem('needle')||'null'),state,last='',ctx,source,buffer,audioUrl='',polling=false,searchSeq=0,analyser,frequency,playGeneration=0,submitting=false,mutationEpoch=0,playbackGain;
const STEPS_DISPLAY={guess:[.1,.5,2,8,15],choice:[5],hits:[.1,.5,2,8,15],race:[30]};
function stepsFor(m){return STEPS_DISPLAY[m]||STEPS_DISPLAY.guess}
const audioDownloads=new Map();
function downloadAudio(url){if(!audioDownloads.has(url)){const task=fetch(url).then(async r=>{if(!r.ok){const detail=await r.json().catch(()=>({}));throw Error(detail.error||'Audio could not load. Retry playback.')}const bytes=await r.arrayBuffer();if(!bytes.byteLength)throw Error('Empty audio preview. Retry playback.');return bytes}).catch(e=>{audioDownloads.delete(url);throw e});audioDownloads.set(url,task);if(audioDownloads.size>3)audioDownloads.delete(audioDownloads.keys().next().value)}return audioDownloads.get(url)}
$('#volume').value=localStorage.getItem('needle-volume')||'.7';
$('#volume').oninput=()=>{const volume=Number($('#volume').value);if($('#race-video video'))$('#race-video video').volume=volume;localStorage.setItem('needle-volume',String(volume));const sa=$('#spotify-audio');if(sa)sa.volume=volume;if(playbackGain&&ctx)playbackGain.gain.setTargetAtTime(volume,ctx.currentTime,.015)};

async function api(path,data){const r=await fetch('/api/'+path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const v=await r.json();if(!r.ok)throw Error(v.error||'Request failed');return v}
function error(e){$('#error').textContent=e.message}
async function action(a,extra={}){mutationEpoch++;try{$('#error').textContent='';if(a==='create'){try{const prev=JSON.parse(localStorage.getItem('needle-prev')||'null');if(prev)extra={previous_artists:prev.artists,previous_songs:prev.songs,...extra}}catch{}}const v=await api(a,{...session,...extra});if(v.token){session=v;sessionStorage.setItem('needle',JSON.stringify(v));await refresh()}else if(v.phase){state=v;render();if(state.phase==='reveal'&&state.answer)renderRevealExtras(state.answer)}else await refresh()}catch(e){error(e)}}
function youtubeLink(answer){const url=answer.videoId?'https://www.youtube.com/watch?v='+encodeURIComponent(answer.videoId):(answer.artist&&answer.title?'https://www.youtube.com/results?search_query='+encodeURIComponent(answer.artist+' '+answer.title+' official video'):'');return url?'<a class="yt-open" target="_blank" rel="noopener" href="'+esc(url)+'">Watch on YouTube</a>':''}
function renderRevealExtras(answer){
 try{
  stop();
  let box=$('#reveal-extras');
  if(!box){
   box=document.createElement('div');box.id='reveal-extras';box.className='reveal-extras';
   const anchor=$('#answer');
   (anchor&&anchor.parentElement?anchor.parentElement:document.body).appendChild(box);
  }
  const hasPreview=!!answer.spotify_preview;
  box.innerHTML=
   (answer.race_points!=null?'<span class="muted">'+(state.correct?'You earned +'+answer.race_points+' pts':answer.race_points?'Winning guess: '+answer.race_points+' pts':'No points awarded')+' · '+(answer.race_elapsed||0)+'s</span>':'')+
   (hasPreview?'<audio id="spotify-audio" preload="auto"></audio>':answer.preview_pending?'<span class="muted">Finding an Apple Music preview…</span>':'<span class="muted">Apple Music preview unavailable; trying the game preview.</span>');
  const audio=$('#spotify-audio');
  if(audio){
   try{audio.volume=+($('#volume').value||.7)}catch{}
   audio.src='/spotify-audio/'+(state.audio||'').split('/').pop();
   // Route the reveal preview through the same analyser used by snippets.
   // Keep element volume separate from snippet gain, and retain the audio node
   // until the element is replaced on the next reveal.
   try{
    ctx ||= new AudioContext();
    analyser ||= ctx.createAnalyser();analyser.fftSize=128;
    const mediaSource=ctx.createMediaElementSource(audio);
    mediaSource.connect(analyser);analyser.disconnect();analyser.connect(ctx.destination);
    audio.onplaying=()=>{if($('#spotify-audio')!==audio)return;document.body.classList.add('is-playing');$('#play').textContent='■';window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:true,analyser,duration:Number.isFinite(audio.duration)&&audio.duration>0?audio.duration:30}}))};
    const onStopped=()=>{if($('#spotify-audio')!==audio)return;document.body.classList.remove('is-playing');$('#play').textContent='▶';window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:false}}))};
    audio.onpause=onStopped;audio.onended=onStopped;
    ctx.resume().catch(()=>{});
   }catch{}
   audio.play().catch(()=>{});
   audio.onerror=()=>{try{$('#play').click()}catch(e){error(e)}};
  }else if(!answer.preview_pending){
   try{if(ctx){const revealAudio=state.audio;queueMicrotask(()=>{if(state&&state.phase==='reveal'&&state.audio===revealAudio)$('#play').click()})}}catch{}
  }
 }catch{}
}
function selectedGameMode(){return mode==='playlist'?$('#playlist-mode').value:mode}
function updateModeSelection(){const custom=mode==='playlist';$('#decade').parentElement.hidden=custom;$('#playlist-field').hidden=!custom;$('#playlist-mode-field').hidden=!custom;$('#playlist-hint').hidden=!custom;$('#party-settings').hidden=selectedGameMode()!=='party';syncMix()}
document.querySelectorAll('.mode').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;document.querySelectorAll('.mode').forEach(x=>x.classList.toggle('selected',x===b));updateModeSelection()});
$('#playlist-mode').addEventListener('change',updateModeSelection);
let importGeneration=0;
$('#playlist-cancel').onclick=()=>{importGeneration++;$('#playlist-progress').hidden=true;$('#solo').disabled=$('#create').disabled=false;$('#solo').textContent='Start listening ↗';$('#error').textContent='Preparation cancelled.'};
async function waitForPreparation(kind,parameters,generation){
 const job=await api(kind+'-prepare',parameters);
 while(generation===importGeneration){
  const progress=await api(kind+'-status?job='+encodeURIComponent(job.job));
  if(generation!==importGeneration)throw Error('Cancelled');
  if(progress.phase==='error')throw Error(progress.error||'Playlist preparation failed.');
  const bar=$('#playlist-progress-bar'),label=$('#playlist-progress-label'),count=$('#playlist-progress-count');
  if(progress.phase==='ready'){$('#playlist-cancel').hidden=true;bar.value=100;label.textContent=kind==='playlist'?'Playlist ready':'Mix ready';count.textContent=kind==='playlist'?progress.matched+'/'+progress.total+' matched':'';return}
  if(progress.phase==='matching'&&progress.total>0){bar.value=Math.round(100*progress.completed/progress.total);label.textContent='Matching songs to playable previews…';count.textContent=progress.completed+'/'+progress.total+' checked'}
  else if(progress.phase==='artists'&&progress.total>0){bar.value=Math.min(95,Math.round(100*progress.completed/progress.total));label.textContent='Finding artists and songs…';count.textContent=progress.completed+' artists checked'}
  else if(progress.phase==='dates'&&progress.total>0){bar.value=Math.min(95,Math.round(100*progress.completed/progress.total));label.textContent='Checking release dates…';count.textContent=progress.completed+'/'+progress.total+' albums checked'}
  else{bar.removeAttribute('value');label.textContent=progress.phase==='filtering'?'Preparing tracks…':kind==='playlist'?'Reading playlist…':'Preparing your mix…';count.textContent='This can take a little while'}
  await new Promise(resolve=>setTimeout(resolve,1000));
 }
 throw Error('Cancelled');
}
async function create(multi){
 const chosenMode=selectedGameMode(),custom=mode==='playlist',playlist=custom?$('#playlist-url').value.trim():'';
 if(custom&&!playlist){$('#error').textContent='Paste a playlist link to start.';$('#playlist-url').focus();return}
 const party_modes=[...document.querySelectorAll('#party-settings input:checked')].map(x=>x.value);
 if(chosenMode==='party'&&!party_modes.length){$('#error').textContent='Choose at least one Party mode.';return}
 const generation=++importGeneration;
 $('#solo').disabled=$('#create').disabled=true;$('#solo').textContent=custom?'Preparing playlist…':'Preparing full mix…';
 $('#error').textContent=custom?'':'Building a broad mix of artists… Cached mixes start immediately; new mixes load in the background.';
 try{
  const payload={mode:chosenMode,party_modes,playlist_url:playlist,multi,name:$('#name').value,genre:$('#genre').value,region:$('#region').value,difficulty:$('#difficulty').value,decade:custom?'All':$('#decade').value,rounds:+$('#rounds').value};
  const settings=chosenMode==='hits'?{genre:'Mixed',region:'Worldwide',difficulty:'Hits',decade:payload.decade}:{genre:payload.genre,region:payload.region,difficulty:payload.difficulty,decade:payload.decade};
  $('#playlist-progress').hidden=false;$('#playlist-cancel').hidden=false;$('#playlist-progress-bar').removeAttribute('value');$('#playlist-progress-label').textContent=custom?'Reading playlist…':'Preparing your mix…';$('#playlist-progress-count').textContent='This can take a little while';
  await waitForPreparation(custom?'playlist':'catalog',custom?{url:playlist}:settings,generation);
  if(generation!==importGeneration)return;
  await action('create',payload);
 }catch(e){if(generation===importGeneration)error(e)}
 finally{if(generation===importGeneration){$('#playlist-progress').hidden=true;$('#solo').disabled=$('#create').disabled=false;$('#solo').textContent='Start listening ↗'}}
}
$('#solo').onclick=()=>create(false);$('#create').onclick=()=>create(true);$('#join').onclick=()=>action('join',{room:$('#code').value.trim().toUpperCase(),name:$('#name').value});function goHome(){if(!$('#playlist-progress').hidden)$('#playlist-cancel').click();$('#race-video video')?.pause();stop();session=null;state=null;last='';searchSeq++;sessionStorage.removeItem('needle');$('#error').textContent='';renderHome()}
$('#leave').onclick=goHome;$('.brand').onclick=e=>{e.preventDefault();goHome()};
if(!history.state?.needle){history.replaceState({needle:'home'},'',location.href);history.pushState({needle:'app'},'',location.href)}
window.addEventListener('popstate',()=>{goHome();history.pushState({needle:'app'},'',location.href)});
function clearInviteURL(){const u=new URL(location.href);u.searchParams.delete('room');history.replaceState(history.state,'',u)}
function renderHome(){document.body.classList.remove('in-game');renderRaceVideo();clearInviteURL();$('#invite').hidden=true;$('#home').hidden=false;$('#game').hidden=true;window.dispatchEvent(new CustomEvent('needle:screen',{detail:{home:true}}))}
$('#share').onclick=async()=>{try{await navigator.clipboard.writeText(location.origin+'/?room='+session.room);$('#share').textContent='Invite copied ✓'}catch(e){$('#error').textContent='Room code: '+session.room}};
$('#next').onclick=()=>action('next');$('#return-lobby').onclick=()=>action('lobby');$('#finish-home').onclick=goHome;$('#skip').onclick=()=>guess('');async function guess(id){if(submitting||!state||state.submitted||state.phase!=='playing'||(state.mode==='race'&&state.serverTime<(state.race_cooldown_until||0)))return;submitting=true;try{ctx ||= new AudioContext();await ctx.resume()}catch{}stop();document.querySelectorAll('#choices button,#results button,#skip').forEach(b=>b.disabled=true);await action('guess',{id,round:state.round,stage:state.stage});if(state?.mode==='race'&&state?.phase==='playing'){searchSeq++;$('#search').value='';$('#results').innerHTML='';}submitting=false;if(state?.phase==='playing'&&!state.submitted)document.querySelectorAll('#choices button,#results button,#skip').forEach(b=>b.disabled=false)}
function stop(){try{const sa=document.querySelector('#spotify-audio');if(sa){sa.pause()}}catch{}playGeneration++;document.body.classList.remove('is-playing');window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:false}}));if(source){const old=source;source=null;old.onended=null;try{old.stop()}catch{}}$('#play').textContent='▶'}
$('#play').onclick=async()=>{
 if(source||$('#play').textContent==='…'||($('#spotify-audio')&&$('#spotify-audio').paused===false)){stop();return}
 const generation=++playGeneration, current=state; if(!current)return;
 try{
 ctx ||= new AudioContext();await ctx.resume();$('#error').textContent='';$('#play').textContent='…';
 if(audioUrl!==current.audio){const bytes=await downloadAudio(current.audio);const b=await ctx.decodeAudioData(bytes.slice(0));if(generation!==playGeneration||state!==current&&state?.audio!==current.audio)return;buffer=b;audioUrl=current.audio}
 if(generation!==playGeneration||!state)return;
 source=ctx.createBufferSource();source.buffer=buffer;playbackGain ||= ctx.createGain();playbackGain.gain.setValueAtTime(+$('#volume').value,ctx.currentTime);
 analyser ||= ctx.createAnalyser();analyser.fftSize=128;frequency=new Uint8Array(analyser.frequencyBinCount);
 source.connect(playbackGain);playbackGain.disconnect();playbackGain.connect(analyser);analyser.disconnect();analyser.connect(ctx.destination);
 const playing=source;source.onended=()=>{if(source===playing){source=null;document.body.classList.remove('is-playing');window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:false}}));$('#play').textContent='▶'}};
 source.start(0,0,Math.min(current.phase==='reveal'?buffer.duration:current.seconds,buffer.duration));document.body.classList.add('is-playing');window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:true,analyser,duration:current.phase==='reveal'?buffer.duration:current.seconds}}));$('#play').textContent='■';
 }catch(e){audioDownloads.delete(current.audio);if(generation===playGeneration){stop();error(e)}}
};
async function refresh(){if(!session||polling)return;polling=true;try{const active=session,epoch=mutationEpoch;const v=await api('state?room='+active.room+'&token='+active.token);if(session!==active||epoch!==mutationEpoch)return;const wasReveal=state&&state.phase==='reveal'&&state.round===v.round&&state.stage===v.stage;const previousPreview=state?.answer?.spotify_preview,previousPending=state?.answer?.preview_pending;state=v;render();if(state.phase==='reveal'&&state.answer&&(!wasReveal||previousPreview!==state.answer.spotify_preview||previousPending!==state.answer.preview_pending))renderRevealExtras(state.answer)}catch(e){error(e)}finally{polling=false}}
function correctPlayersMessage(){if(!state.multi||state.phase!=='reveal')return '';const names=state.correct_players||[];return names.length?names.join(' & ')+' got it right!':'Nobody got it right.'}
function render(){$('#invite').hidden=true;document.body.classList.add('in-game');$('#game').dataset.phase=state.phase;$('#game').dataset.mode=state.mode;$('#game').classList.toggle('finished',state.phase==='finished');$('#wrapup').hidden=state.phase!=='finished';if(state.phase==='finished')renderFinal();
renderRaceVideo();if(state.phase!=='reveal')$('#reveal-extras')?.remove();$('#catalog-info').textContent=state.catalog?(state.catalog.answers??state.catalog.tracks)+' eligible songs · '+state.catalog.artists+' artists · '+state.catalog.tracks+' searchable tracks'+(state.playlist_report?' · playlist: '+state.playlist_report.matched+'/'+state.playlist_report.total+' matched':''):'';$('#home').hidden=true;$('#game').hidden=false;window.dispatchEvent(new CustomEvent('needle:screen',{detail:{home:false}}));const key=state.round+':'+state.stage+':'+state.phase;if(key!==last){stop();$('#search').value='';$('#results').innerHTML='';last=key; if(state.audio&&state.phase==='playing'&&state.mode!=='race')downloadAudio(state.audio).catch(()=>{}); searchSeq++; $('.answer-hint').textContent='Type at least 2 characters · up to 25 matching suggestions'; $('#skip').disabled=false; /* reveal autoplay handled by renderRevealExtras: Spotify default, Deezer fallback */}$('#roundLabel').textContent=state.multi?'ROOM '+state.code+' / '+state.round+' OF '+state.rounds:'TRACK '+state.round+' / '+state.rounds;$('#scores').innerHTML=state.players.map(p=>'<span class="score">'+esc(p.name)+(p.me?' · you':'')+(p.submitted?' ✓':'')+'<b>'+p.score+'</b></span>').join('');$('#status').textContent=state.region.toUpperCase()+' · '+state.genre.toUpperCase()+' · '+state.difficulty.toUpperCase()+' / '+raceLabel();$('#headline').textContent=state.phase==='lobby'?'Your listening room.':state.phase==='finished'?'That’s a wrap.':state.phase==='reveal'?(state.correct?'You got it!':state.result==='skipped'?'No guess this time.':'Not this one.'):state.submitted?'Guess locked in.':'Sounds familiar?';$('.disc').hidden=['lobby','finished'].includes(state.phase)||state.mode==='race';$('#steps').innerHTML=state.phase==='lobby'?'Share your room code. Friends can join before you start.':(state.mode==='race'?[]:stepsFor(state.mode)).map((n,i)=>'<span class="step '+(i===state.stage?'active':'')+'">'+n+'s</span>').join('');$('#skip').hidden=state.phase!=='playing'||state.mode==='race'||state.mode==='choice'||state.submitted;const cooling=state.mode==='race'&&state.serverTime<(state.race_cooldown_until||0);$('#search').disabled=cooling;if(cooling){$('#results').innerHTML='';$('.answer-hint').textContent='Not quite — try again in '+Math.ceil(state.race_cooldown_until-state.serverTime)+'s';}else if(state.mode==='race'&&state.race_wrong&&!$('#search').value){$('.answer-hint').textContent='Try another guess.';}$('#guessbox').hidden=state.phase!=='playing'||state.mode==='choice'||state.submitted||(state.mode==='race'&&(!state.race_started||state.serverTime<state.race_started));$('#choices').hidden=state.phase!=='playing'||state.mode!=='choice'||state.submitted;const optionKey=JSON.stringify(state.options||[])+':'+state.round;if($('#choices').dataset.key!==optionKey){$('#choices').dataset.key=optionKey;$('#choices').innerHTML=(state.options||[]).map(o=>'<button data-id="'+esc(o.id)+'">'+esc(o.title)+'<br><small>'+esc(o.artist)+'</small></button>').join('');$('#choices').querySelectorAll('button').forEach(b=>b.onclick=()=>guess(b.dataset.id));}$('#answer').innerHTML=state.answer?'<p class="result-label '+(state.correct?'result-correct':'result-wrong')+'">'+(state.correct?'✓ Correct answer':'✕ '+(state.result==='skipped'?'Skipped or timed out':'Incorrect answer'))+'</p>'+(correctPlayersMessage()?'<p class="correct-players">'+esc(correctPlayersMessage())+'</p>':'')+'<img alt="Album artwork" src="'+esc(state.answer.art)+'"><h2>'+esc(state.answer.title)+'</h2><p>'+esc(state.answer.artist)+'</p><div class="listen-row">'+(state.answer.link?'<a class="deezer-open" target="_blank" rel="noopener" href="'+esc(state.answer.link)+'">Listen on Deezer</a>':'')+(state.answer.spotify_url?'<a class="spotify-open" target="_blank" rel="noopener" href="'+esc(state.answer.spotify_url)+'">Open in Spotify</a>':'')+youtubeLink(state.answer)+'</div>':'';$('#next').hidden=!state.host||!['lobby','reveal'].includes(state.phase);$('#next').textContent=state.phase==='lobby'?'Everyone here? Start →':state.round>=state.rounds?'See final scores →':'Next song →';$('#clock').textContent=state.mode==='race'&&!state.race_started?'Preparing media — clock paused':state.phase==='playing'?(state.submitted?'Waiting for the other listeners · ':'')+Math.max(0,Math.ceil(state.deadline-state.serverTime))+' seconds to guess':state.phase==='finished'?state.players.slice().sort((a,b)=>b.score-a.score).map(p=>p.name+' · '+p.score).join(' / '):''}
let searchTimer;
$('#search').oninput=()=>{
 clearTimeout(searchTimer);const sequence=++searchSeq,term=$('#search').value.trim(),active=session,round=state.round,stage=state.stage;
 $('#results').innerHTML='';$('.answer-hint').textContent=term.length<2?'Type at least 2 characters · up to 25 matching suggestions':'Searching…';
 if(term.length<2)return;
 searchTimer=setTimeout(async()=>{try{
 const data=await api('search?room='+active.room+'&token='+active.token+'&q='+encodeURIComponent(term));
 if(sequence!==searchSeq||session!==active||!state||state.round!==round||state.stage!==stage||state.phase!=='playing'||state.submitted)return;
 const rows=data.results;let page=0;
 function showPage(){
  const size=3,pages=Math.ceil(rows.length/size);page=Math.max(0,Math.min(page,pages-1));
  $('.answer-hint').textContent=rows.length?rows.length+' matches · page '+(page+1)+' of '+pages:'No matches. Try another title or artist.';
  $('#results').innerHTML=rows.slice(page*size,(page+1)*size).map(t=>'<button data-id="'+esc(t.id)+'"><span>'+esc(t.title)+'</span><small>'+esc(t.artist)+'</small><span class="answer-arrow">↗</span></button>').join('')+(pages>1?'<div class="list-pages"><button type="button" data-page="prev" '+(page===0?'disabled':'')+'>← Previous</button><span>'+(page+1)+' / '+pages+'</span><button type="button" data-page="next" '+(page===pages-1?'disabled':'')+'>Next →</button></div>':'');
  $('#results').querySelectorAll('button[data-id]').forEach(b=>b.onclick=()=>guess(b.dataset.id));
  $('#results').querySelectorAll('button[data-page]').forEach(b=>b.onclick=()=>{page+=b.dataset.page==='next'?1:-1;showPage()});
 } showPage();
  }catch(e){if(sequence===searchSeq)error(e)}},250);
};

function raceLabel(){return state&&state.mode==='race'?'VIDEO RACE':state.mode==='choice'?'PICK THE SONG':state.mode==='hits'?'HOTTEST HITS':state.mode==='party'?'PARTY MODE':'NAME THE SONG'}
let raceKey='',raceObjectURL='',raceLoading=false;
function renderRaceVideo(){
 let box=$('#race-video');
 if(!state||state.mode!=='race'||state.phase!=='playing'){
  if(box){box.querySelector('video')?.pause();box.remove()}
  if(raceObjectURL)URL.revokeObjectURL(raceObjectURL);raceObjectURL='';raceKey='';return;
 }
 if(!box){box=document.createElement('div');box.id='race-video';$('.player').appendChild(box)}
 const key=state.audio;
 if(raceKey!==key){box.querySelector('video')?.pause();if(raceObjectURL)URL.revokeObjectURL(raceObjectURL);raceObjectURL='';raceKey=key;raceLoading=false;box.innerHTML='<p class="race-message">Preparing full-length video or audio… No guessing time is running.</p><button class="race-start" hidden>Start playback</button><button class="race-skip">Skip song</button><video playsinline preload="auto" style="width:100%;max-height:420px"></video>';
 box.querySelector('.race-skip').onclick=()=>action('race-skip',{round:state.round});
 box.querySelector('.race-start').onclick=async()=>{if(state.race_status==='error'){await action('race-retry',{round:state.round});return}const v=box.querySelector('video');try{await v.play()}catch{box.querySelector('.race-message').textContent='Press Start playback once media has loaded.'}};
 }
 const v=box.querySelector('video');v.volume=Number($('#volume').value);
 const message=box.querySelector('.race-message');
 if(state.race_status==='error'){message.textContent=state.race_error;box.querySelector('.race-start').hidden=false;box.querySelector('.race-start').textContent='Retry media';return}
 if(state.race_url&&!raceLoading&&!raceObjectURL){
  raceLoading=true;const round=state.round;
  fetch(state.race_url).then(r=>{if(!r.ok)throw Error('Media download failed');return r.blob()}).then(blob=>{
   if(raceKey!==key)return;
   raceObjectURL=URL.createObjectURL(blob);v.src=raceObjectURL;
   v.onplaying=async()=>{if(raceKey!==key)return;if(!state.race_started){box.querySelector('.race-start').hidden=true;v.dataset.unlocked='1';v.pause();v.currentTime=0;message.textContent='Ready. Waiting for the other listeners…';await action('race-ready',{round})}};
   v.onerror=()=>{if(raceKey!==key)return;if(state.race_type==='video/mp4'&&!state.race_started){message.textContent='Trying full-length audio instead…';action('race-audio',{round})}else message.textContent='Browser could not decode this media. Skip this song or retry the download.'};
   v.oncanplay=()=>{if(v.dataset.unlocked)return;v.play().catch(()=>{box.querySelector('.race-start').hidden=false;message.textContent='Media ready. Press Start playback to enable sound.'})};
  }).catch(e=>{if(raceKey===key){raceLoading=false;message.textContent=e.message+' — retrying.'}});
 }
 if(state.race_started&&raceObjectURL){const delay=state.race_started-state.serverTime;
  if(delay>0)message.textContent='Everyone ready. Starting…';
  else {const points=Math.max(1,20-Math.floor(20*Math.max(0,state.elapsed||0)/state.race_duration));message.textContent=Math.max(0,Math.ceil(state.deadline-state.serverTime))+' seconds remaining · '+points+' points available';if(v.paused){v.currentTime=Math.min(state.elapsed||0,v.duration||0);v.play().catch(()=>{box.querySelector('.race-start').hidden=false;message.textContent='Press Start playback to resume sound.'})}}
 }
}
const inviteCode=(new URLSearchParams(location.search).get('room')||'').trim().toUpperCase();
$('#code').value=inviteCode;
async function showInvite(code){
 $('#home').hidden=true;$('#game').hidden=true;$('#invite').hidden=false;$('#invite-error').textContent='';$('#invite-join').disabled=true;
 try{
  const data=await api('invite?room='+encodeURIComponent(code));
  if($('#invite').hidden)return;
  $('#invite-description').textContent=data.host+' invited you to play.';
  $('#invite-mode').textContent=({guess:'Name the song',choice:'Pick the song',hits:'Hottest Hits',race:'Video race',party:'Party mode'})[data.mode]||'Music game';
  $('#invite-mix').textContent=data.region+' · '+data.genre+' · '+data.difficulty+(data.decade&&data.decade!=='All'?' · '+data.decade:'')+' · '+data.rounds+' rounds';
  $('#invite-players').textContent=data.players+'/8 players';$('#invite-details').hidden=false;
  if(!data.joinable){$('#invite-error').textContent=data.reason;return}
  $('#invite-join').disabled=false;$('#invite-name').focus();
 }catch(e){$('#invite-description').textContent='This invite is unavailable.';$('#invite-error').textContent=e.message}
}
$('#invite-home').onclick=goHome;
$('#invite-form').onsubmit=async e=>{e.preventDefault();const button=$('#invite-join');if(button.disabled)return;button.disabled=true;$('#invite-error').textContent='';try{
 const v=await api('join',{room:inviteCode,name:$('#invite-name').value.trim()});
 session=v;state=null;last='';mutationEpoch++;sessionStorage.setItem('needle',JSON.stringify(v));clearInviteURL();await refresh();
 }catch(error){$('#invite-error').textContent=error.message;button.disabled=false}};
if(inviteCode&&(!session||session.room!==inviteCode)){session=null;sessionStorage.removeItem('needle');showInvite(inviteCode)}else if(inviteCode&&session)clearInviteURL();
setInterval(refresh,1000);refresh();


let recapPage=0,recapMatch='';
function renderFinal(){
 const players=state.players.slice().sort((a,b)=>b.score-a.score||a.name.localeCompare(b.name));
 const best=players[0]?.score||0,winners=players.filter(p=>p.score===best);
 $('#winner-title').textContent=best===0?'A tough set.':winners.length>1?'It’s a tie!':winners[0].name+' wins!';
 $('#match-summary').textContent=state.rounds+' songs · '+state.region+' · '+state.genre+' · '+(state.game_mode==='party'?state.base_difficulty:state.difficulty)+(state.decade&&state.decade!=='All'?' · '+state.decade:'');
 let rank=0,lastScore=null;
 $('#final-scores').innerHTML=players.map((p,i)=>{if(p.score!==lastScore)rank=i+1;lastScore=p.score;return '<li class="'+(p.score===best&&best>0?'top-score':'')+'"><span class="rank">'+rank+'</span><span class="final-name">'+esc(p.name)+(p.me?'<small>You</small>':'')+'</span><strong>'+p.score+'<small>POINTS</small></strong></li>'}).join('');
 const recap=state.recap||[];const matchKey=session?.room+':'+state.rounds;if(recapMatch!==matchKey){recapPage=0;recapMatch=matchKey}recapPage=Math.max(0,Math.min(recapPage,recap.length-1));
 const allowedLink=value=>/^https:\/\//i.test(value||'')?esc(value):'';
 $('#recap-list').innerHTML=recap.slice(recapPage,recapPage+1).map(item=>{
  const winners=(item.winners||[]).map(w=>esc(w.name)+' · '+Number(w.seconds).toFixed(1)+'s').join(' / ')||'Nobody guessed it';
  const deezer=allowedLink(item.link),spotify=allowedLink(item.spotify_url);
  const links=(deezer?'<a href="'+deezer+'" target="_blank" rel="noopener">Deezer ↗</a>':'')+(spotify?'<a href="'+spotify+'" target="_blank" rel="noopener">Spotify ↗</a>':'');
  const label=({guess:'Name the song',choice:'Pick the song',race:'Video race',hits:'Hottest Hits'})[item.mode]||item.mode;
  return '<li><span class="recap-number">'+Number(item.round)+'</span><div><strong>'+esc(item.title)+'</strong><span>'+esc(item.artist)+' · '+esc(label)+'</span><small>'+winners+'</small></div><div class="recap-links">'+links+'</div></li>';
 }).join('')+(recap.length>1?'<li class="list-pages"><button type="button" data-recap="prev" '+(recapPage===0?'disabled':'')+'>← Previous</button><span>'+(recapPage+1)+' / '+recap.length+'</span><button type="button" data-recap="next" '+(recapPage===recap.length-1?'disabled':'')+'>Next →</button></li>':'');
 $('#recap-list').querySelectorAll('[data-recap]').forEach(b=>b.onclick=()=>{recapPage+=b.dataset.recap==='next'?1:-1;renderFinal()});
  $('#return-lobby').hidden=!state.host||!state.multi;$('#finish-home').hidden=false;$('#host-wait').textContent=!state.multi?'Solo run finished. Head home to start a new mix.':state.host?'Start another match with the same room and players.':'Waiting for the host to return everyone to the lobby.';
 try{
  const artists=[...new Set((state.history||[]).map(h=>h.artist).filter(Boolean))].slice(-12);
  const songs=(state.history||[]).map(h=>h.song).filter(Boolean).slice(-20);
  if(artists.length||songs.length)localStorage.setItem('needle-prev',JSON.stringify({artists,songs}));
 }catch{}
}

let warmTimer,mixConfig;
const difficultyHelp={Easy:'Recognisable hits only. Europe Easy favours cross-border anthems. Obscure tracks never fill an Easy pool.',Medium:'Known hits plus strong catalogue favourites. Worldwide and Europe Medium include crossover hits.',Hard:'Mid-catalogue singles and fan favourites. No Easy anthems here.',Expert:'Album cuts and deeper catalogue. For collectors.',Impossible:'The deepest end of the available catalogue. Expect obscurity.'};
function syncMix(){
  if(!mixConfig)return;
  $('#decade').parentElement.hidden=mode==='playlist';
  ['#genre','#region','#difficulty'].forEach(id=>$(id).parentElement.hidden=(mode==='hits'||mode==='race'||mode==='playlist'));
  if(mode==='playlist'){$('#mix-help').textContent='Play your playlist with the game type you choose.';return}
  if(mode==='hits'){$('#mix-help').textContent='Hottest Hits: all-time singalong favourites, iconic hooks and international anthems. Five snippets, solo or with friends. A stricter song selection than Easy — no deep cuts.';warmCatalog();return}
  if(mode==='race'){$('#mix-help').textContent='Video race: the music video (or audio + artwork) loads completely before guessing, then plays for its full length. Type to guess — fastest correct wins. Correct answers earn 20 to 1 points, spread evenly across the whole song. Skip scores 0.';warmCatalog();return}
 const supported=mixConfig.support[$('#region').value]||{};
 const previousGenre=$('#genre').value,previousDifficulty=$('#difficulty').value;
 $('#genre').innerHTML=mixConfig.genres.map(g=>'<option'+(!supported[g]?' disabled':'')+'>'+esc(g)+'</option>').join('');
 $('#genre').value=supported[previousGenre]?previousGenre:Object.keys(supported)[0]||'Mixed';
 const difficulties=supported[$('#genre').value]||[];
 $('#difficulty').innerHTML=mixConfig.difficulties.map(d=>'<option'+(!difficulties.includes(d)?' disabled':'')+'>'+esc(d)+'</option>').join('');
 $('#difficulty').value=difficulties.includes(previousDifficulty)?previousDifficulty:difficulties[0]||'Medium';
 const scene=$('#region').value;
 $('#mix-help').textContent=difficultyHelp[$('#difficulty').value]+' '+(scene==='Europe'?'Europe mixes European and international crossover hits; it does not force a different country every song.':scene==='Worldwide'?'Worldwide favours international recognition on Easy.':'This scene focuses on its own artists; familiarity is relative to that scene.')+' Greyed-out combinations lack enough calibrated artists.';
 warmCatalog();
}
function warmCatalog(){clearTimeout(warmTimer);if(!mixConfig||mode==='playlist')return;warmTimer=setTimeout(()=>api('warm?'+new URLSearchParams(mode==='hits'?{genre:'Mixed',region:'Worldwide',difficulty:'Hits',decade:$('#decade').value}:{genre:$('#genre').value,region:$('#region').value,difficulty:$('#difficulty').value,decade:$('#decade').value})).catch(()=>{}),400)}
['#region','#genre','#difficulty','#decade'].forEach(id=>$(id).addEventListener('change',syncMix));
$('#solo').disabled=$('#create').disabled=true;
api('config').then(config=>{mixConfig=config;$('#region').innerHTML=config.regions.map(x=>'<option>'+esc(x)+'</option>').join('');syncMix();$('#solo').disabled=$('#create').disabled=false}).catch(error);

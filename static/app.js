const $=s=>document.querySelector(s),esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let mode='guess',session=JSON.parse(sessionStorage.getItem('needle')||'null'),state,last='',ctx,source,buffer,audioUrl='',polling=false,searchSeq=0,analyser,frequency,playGeneration=0,submitting=false,mutationEpoch=0,playbackGain;
const audioDownloads=new Map();
function downloadAudio(url){if(!audioDownloads.has(url)){const task=fetch(url).then(async r=>{if(!r.ok){const detail=await r.json().catch(()=>({}));throw Error(detail.error||'Audio could not load. Retry playback.')}const bytes=await r.arrayBuffer();if(!bytes.byteLength)throw Error('Empty audio preview. Retry playback.');return bytes}).catch(e=>{audioDownloads.delete(url);throw e});audioDownloads.set(url,task);if(audioDownloads.size>3)audioDownloads.delete(audioDownloads.keys().next().value)}return audioDownloads.get(url)}
$('#volume').value=localStorage.getItem('needle-volume')||'.7';
$('#volume').oninput=()=>{const volume=Number($('#volume').value);localStorage.setItem('needle-volume',String(volume));if(playbackGain&&ctx)playbackGain.gain.setTargetAtTime(volume,ctx.currentTime,.015)};

async function api(path,data){const r=await fetch('/api/'+path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const v=await r.json();if(!r.ok)throw Error(v.error||'Request failed');return v}
function error(e){$('#error').textContent=e.message}
async function action(a,extra={}){mutationEpoch++;try{$('#error').textContent='';const v=await api(a,{...session,...extra});if(v.token){session=v;sessionStorage.setItem('needle',JSON.stringify(v));await refresh()}else if(v.phase){state=v;render()}else await refresh()}catch(e){error(e)}}
document.querySelectorAll('.mode').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;document.querySelectorAll('.mode').forEach(x=>x.classList.toggle('selected',x===b))});
async function create(multi){$('#solo').disabled=$('#create').disabled=true;$('#solo').textContent='Preparing full mix…';$('#error').textContent='Building a broad mix of artists… Cached mixes start immediately; new mixes load in the background.';await action('create',{mode,multi,name:$('#name').value,genre:$('#genre').value,region:$('#region').value,difficulty:$('#difficulty').value,rounds:+$('#rounds').value});$('#solo').disabled=$('#create').disabled=false;$('#solo').textContent='Start listening ↗'}
$('#solo').onclick=()=>create(false);$('#create').onclick=()=>create(true);$('#join').onclick=()=>action('join',{room:$('#code').value.trim().toUpperCase(),name:$('#name').value});function goHome(){stop();session=null;state=null;last='';searchSeq++;sessionStorage.removeItem('needle');$('#error').textContent='';renderHome()}
$('#leave').onclick=goHome;$('.brand').onclick=e=>{e.preventDefault();goHome()};
if(!history.state?.needle){history.replaceState({needle:'home'},'',location.href);history.pushState({needle:'app'},'',location.href)}
window.addEventListener('popstate',()=>{goHome();history.pushState({needle:'app'},'',location.href)});
function renderHome(){$('#home').hidden=false;$('#game').hidden=true;window.dispatchEvent(new CustomEvent('needle:screen',{detail:{home:true}}))}
$('#share').onclick=async()=>{try{await navigator.clipboard.writeText(location.origin+'/?room='+session.room);$('#share').textContent='Invite copied ✓'}catch(e){$('#error').textContent='Room code: '+session.room}};
$('#next').onclick=()=>action('next');$('#return-lobby').onclick=()=>action('lobby');$('#finish-home').onclick=goHome;$('#skip').onclick=()=>guess('');async function guess(id){if(submitting||!state||state.submitted||state.phase!=='playing')return;submitting=true;try{ctx ||= new AudioContext();await ctx.resume()}catch{}stop();document.querySelectorAll('#choices button,#results button,#skip').forEach(b=>b.disabled=true);await action('guess',{id,round:state.round,stage:state.stage});submitting=false;if(state?.phase==='playing'&&!state.submitted)document.querySelectorAll('#choices button,#results button,#skip').forEach(b=>b.disabled=false)}
function stop(){playGeneration++;document.body.classList.remove('is-playing');window.dispatchEvent(new CustomEvent('needle:audio',{detail:{playing:false}}));if(source){const old=source;source=null;old.onended=null;try{old.stop()}catch{}}$('#play').textContent='▶'}
$('#play').onclick=async()=>{
 if(source||$('#play').textContent==='…'){stop();return}
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
async function refresh(){if(!session||polling)return;polling=true;try{const active=session,epoch=mutationEpoch;const v=await api('state?room='+active.room+'&token='+active.token);if(session!==active||epoch!==mutationEpoch)return;state=v;render()}catch(e){error(e)}finally{polling=false}}
function render(){$('#game').classList.toggle('finished',state.phase==='finished');$('#wrapup').hidden=state.phase!=='finished';if(state.phase==='finished')renderFinal();$('#catalog-info').textContent=state.catalog?(state.catalog.answers??state.catalog.tracks)+' eligible songs · '+state.catalog.artists+' artists · '+state.catalog.tracks+' searchable tracks':'';$('#home').hidden=true;$('#game').hidden=false;window.dispatchEvent(new CustomEvent('needle:screen',{detail:{home:false}}));const key=state.round+':'+state.stage+':'+state.phase;if(key!==last){stop();$('#search').value='';$('#results').innerHTML='';last=key; if(state.audio&&state.phase==='playing')downloadAudio(state.audio).catch(()=>{}); searchSeq++; $('.answer-hint').textContent='Type at least 2 characters · up to 25 matching suggestions'; $('#skip').disabled=false; if(state.phase==='reveal'&&ctx){const revealAudio=state.audio;queueMicrotask(()=>{if(state?.phase==='reveal'&&state.audio===revealAudio)$('#play').click()})}}$('#roundLabel').textContent=state.multi?'ROOM '+state.code+' / '+state.round+' OF '+state.rounds:'TRACK '+state.round+' / '+state.rounds;$('#scores').innerHTML=state.players.map(p=>'<span class="score">'+esc(p.name)+(p.me?' · you':'')+(p.submitted?' ✓':'')+'<b>'+p.score+'</b></span>').join('');$('#status').textContent=state.region.toUpperCase()+' · '+state.genre.toUpperCase()+' · '+state.difficulty.toUpperCase()+' / '+(state.mode==='choice'?'PICK THE SONG':'NAME THE SONG');$('#headline').textContent=state.phase==='lobby'?'Your listening room.':state.phase==='finished'?'That’s a wrap.':state.phase==='reveal'?(state.correct?'You got it!':state.result==='skipped'?'No guess this time.':'Not this one.'):state.submitted?'Guess locked in.':'Sounds familiar?';$('.disc').hidden=['lobby','finished'].includes(state.phase);$('#steps').innerHTML=state.phase==='lobby'?'Share your room code. Friends can join before you start.':(state.mode==='choice'?[5]:[.1,.5,2,8,15]).map((n,i)=>'<span class="step '+(i===state.stage?'active':'')+'">'+n+'s</span>').join('');$('#guessbox').hidden=state.phase!=='playing'||state.mode!=='guess'||state.submitted;$('#choices').hidden=state.phase!=='playing'||state.mode!=='choice'||state.submitted;const optionKey=JSON.stringify(state.options||[])+':'+state.round;if($('#choices').dataset.key!==optionKey){$('#choices').dataset.key=optionKey;$('#choices').innerHTML=(state.options||[]).map(o=>'<button data-id="'+esc(o.id)+'">'+esc(o.title)+'<br><small>'+esc(o.artist)+'</small></button>').join('');$('#choices').querySelectorAll('button').forEach(b=>b.onclick=()=>guess(b.dataset.id));}$('#answer').innerHTML=state.answer?'<p class="result-label '+(state.correct?'result-correct':'result-wrong')+'">'+(state.correct?'✓ Correct answer':'✕ '+(state.result==='skipped'?'Skipped or timed out':'Incorrect answer'))+'</p><img alt="Album artwork" src="'+esc(state.answer.art)+'"><h2>'+esc(state.answer.title)+'</h2><p>'+esc(state.answer.artist)+'</p><a target="_blank" rel="noopener" href="'+esc(state.answer.link)+'">Listen to the song ↗</a>':'';$('#next').hidden=!state.host||!['lobby','reveal'].includes(state.phase);$('#next').textContent=state.phase==='lobby'?'Everyone here? Start →':state.round>=state.rounds?'See final scores →':'Next song →';$('#clock').textContent=state.phase==='playing'?(state.submitted?'Waiting for the other listeners · ':'')+Math.max(0,Math.ceil(state.deadline-state.serverTime))+' seconds to guess':state.phase==='finished'?state.players.slice().sort((a,b)=>b.score-a.score).map(p=>p.name+' · '+p.score).join(' / '):''}
let searchTimer;
$('#search').oninput=()=>{
 clearTimeout(searchTimer);const sequence=++searchSeq,term=$('#search').value.trim(),active=session,round=state.round,stage=state.stage;
 $('#results').innerHTML='';$('.answer-hint').textContent=term.length<2?'Type at least 2 characters · up to 25 matching suggestions':'Searching…';
 if(term.length<2)return;
 searchTimer=setTimeout(async()=>{try{
 const data=await api('search?room='+active.room+'&token='+active.token+'&q='+encodeURIComponent(term));
 if(sequence!==searchSeq||session!==active||!state||state.round!==round||state.stage!==stage||state.phase!=='playing'||state.submitted)return;
 const rows=data.results;$('.answer-hint').textContent=rows.length+' matching suggestions · click to lock your guess';
 $('#results').innerHTML=rows.map(t=>'<button data-id="'+esc(t.id)+'"><span>'+esc(t.title)+'</span><small>'+esc(t.artist)+'</small><span class="answer-arrow">↗</span></button>').join('')||'<p class="muted">No matches. Try a different title or artist.</p>';
 $('#results').querySelectorAll('button').forEach(b=>b.onclick=()=>guess(b.dataset.id));
 }catch(e){if(sequence===searchSeq)error(e)}},250);
};
$('#code').value=new URLSearchParams(location.search).get('room')||'';setInterval(refresh,1000);refresh();


function renderFinal(){
 const players=state.players.slice().sort((a,b)=>b.score-a.score||a.name.localeCompare(b.name));
 const best=players[0]?.score||0,winners=players.filter(p=>p.score===best);
 $('#winner-title').textContent=best===0?'A tough set.':winners.length>1?'It’s a tie!':winners[0].name+' wins!';
 $('#match-summary').textContent=state.rounds+' songs · '+state.region+' · '+state.genre+' · '+state.difficulty;
 let rank=0,lastScore=null;
 $('#final-scores').innerHTML=players.map((p,i)=>{if(p.score!==lastScore)rank=i+1;lastScore=p.score;return '<li class="'+(p.score===best&&best>0?'top-score':'')+'"><span class="rank">'+rank+'</span><span class="final-name">'+esc(p.name)+(p.me?'<small>You</small>':'')+'</span><strong>'+p.score+'<small>POINTS</small></strong></li>'}).join('');
 $('#return-lobby').hidden=!state.host;$('#host-wait').textContent=state.host?'Start another match with the same room and players.':'Waiting for the host to return everyone to the lobby.';
}

let warmTimer,mixConfig;
const difficultyHelp={Easy:'Recognisable hits only. Obscure tracks never fill an Easy pool.',Medium:'Known hits plus popular favourites.',Hard:'Less obvious singles and catalogue favourites.',Expert:'Album cuts and less familiar songs.',Impossible:'The deeper end of the available catalogue.'};
function syncMix(){
 if(!mixConfig)return;
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
function warmCatalog(){clearTimeout(warmTimer);if(!mixConfig)return;warmTimer=setTimeout(()=>api('warm?'+new URLSearchParams({genre:$('#genre').value,region:$('#region').value,difficulty:$('#difficulty').value})).catch(()=>{}),400)}
['#region','#genre','#difficulty'].forEach(id=>$(id).addEventListener('change',syncMix));
$('#solo').disabled=$('#create').disabled=true;
api('config').then(config=>{mixConfig=config;$('#region').innerHTML=config.regions.map(x=>'<option>'+esc(x)+'</option>').join('');syncMix();$('#solo').disabled=$('#create').disabled=false}).catch(error);

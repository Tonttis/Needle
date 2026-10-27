/* Independent visual engine: keeps moving even when catalog/audio requests fail. */
(()=>{
 const body=document.body,toggle=document.getElementById('motion-toggle');
 let motion='full';try{motion=localStorage.getItem('needle-motion')||'full'}catch{}
 if(!['full','calm','off'].includes(motion))motion='full';
 function apply(){body.dataset.motion=motion;toggle.textContent='Motion: '+motion[0].toUpperCase()+motion.slice(1);toggle.setAttribute('aria-pressed',String(motion!=='off'));try{localStorage.setItem('needle-motion',motion)}catch{}}
 toggle.onclick=()=>{motion=['full','calm','off'][(['full','calm','off'].indexOf(motion)+1)%3];apply()};apply();
 const canvas=document.createElement('canvas');canvas.id='ambient';canvas.setAttribute('aria-hidden','true');body.prepend(canvas);
 const panel=document.querySelector('.player'),local=document.createElement('canvas');local.className='player-atmosphere';local.setAttribute('aria-hidden','true');panel.prepend(local);
 for(const side of ['left','right']){const meter=document.createElement('div');meter.className='side-analyzer '+side;meter.setAttribute('aria-hidden','true');meter.innerHTML='<i></i>'.repeat(28);panel.append(meter)}
 const sideBars=[...document.querySelectorAll('.side-analyzer i')];
 const bg=canvas.getContext('2d'),fg=local.getContext('2d');if(!bg||!fg)return;
 const bars=[...document.querySelectorAll('.equalizer i')],progress=document.querySelector('.playback-progress span');
 const dust=Array.from({length:85},()=>({x:Math.random(),y:Math.random(),r:.7+Math.random()*2,v:.3+Math.random()*.8,phase:Math.random()*6.28}));
 let width=0,height=0,pw=0,ph=0,last=0,energy=0,playing=false,analyser=null,data=null,start=0,duration=15;
 function fit(c,g,w,h){const d=Math.min(devicePixelRatio||1,2);c.width=Math.round(w*d);c.height=Math.round(h*d);c.style.width=w+'px';c.style.height=h+'px';g.setTransform(d,0,0,d,0,0)}
 function resize(){width=innerWidth;height=innerHeight;fit(canvas,bg,width,height);pw=panel.clientWidth;ph=panel.clientHeight;if(pw&&ph)fit(local,fg,pw,ph)}
 addEventListener('resize',resize);new ResizeObserver(resize).observe(panel);resize();
 addEventListener('needle:audio',e=>{playing=e.detail.playing;if(playing){analyser=e.detail.analyser;data=new Uint8Array(analyser.frequencyBinCount);start=performance.now();duration=e.detail.duration||15}else{analyser=null;data=null;progress.style.width='0%'}});
 function drawField(g,w,h,now,inside){
  g.clearRect(0,0,w,h);if(motion==='off')return;
  const t=now*.00014;
  for(let n=0;n<2;n++){
   const x=w*(.5+Math.sin(t+n*2)*.32),y=h*(.5+Math.cos(t*.8+n)*.25);
   const glow=g.createRadialGradient(x,y,0,x,y,Math.max(w,h)*.55);
   glow.addColorStop(0,n?`rgba(180,150,255,${.12+energy*.18})`:`rgba(180,225,105,${.06+energy*.12})`);glow.addColorStop(1,'transparent');g.fillStyle=glow;g.fillRect(0,0,w,h);
  }
  for(const p of dust){g.beginPath();g.fillStyle=`rgba(${playing?220:174},${playing?245:189},${playing?157:225},${(inside?.28:.36)+energy*.4})`;g.arc(p.x*w,p.y*h,p.r*(1+energy*1.5),0,Math.PI*2);g.fill()}
  if(energy>.015){for(let j=0;j<3;j++){g.beginPath();g.strokeStyle=`rgba(216,249,149,${energy*.65})`;for(let x=0;x<=w;x+=8){const y=h*(.5+j*.08)+Math.sin(x*.012+now*.002+j)*energy*h*.17;x?g.lineTo(x,y):g.moveTo(x,y)}g.stroke()}}
 }
 function frame(now){requestAnimationFrame(frame);if(!playing&&now-last<32)return;if(document.hidden){last=now;return}const dt=Math.min((now-last)/1000,.05);last=now;
  let level=0;if(playing&&analyser){analyser.getByteFrequencyData(data);level=data.reduce((a,b)=>a+b,0)/data.length/255}energy+=(level-energy)*.16;
  const amount=motion==='full'?1:motion==='calm'?.25:0;
  body.style.setProperty('--audio-energy',(energy*amount).toFixed(3));
  for(const p of dust){p.y=(p.y-dt*.017*p.v*(1+energy*6)*amount+1)%1;p.x=(p.x+Math.sin(now*.0003+p.phase)*dt*.005*amount+1)%1}
  drawField(bg,width,height,now,false);if(pw&&ph&&!document.getElementById('game').hidden)drawField(fg,pw,ph,now,true);
  bars.forEach((b,i)=>{const sample=data?data[Math.floor(i*data.length/bars.length)]/255:0;const idle=.08+.06*(1+Math.sin(now*.0015+i*.65));b.style.transform=`scaleY(${motion==='off'?.12:Math.max(.08,playing?sample:idle)})`;b.style.opacity=playing?'.9':'.35'});
  sideBars.forEach((b,i)=>{const n=i%28;const sample=data?data[Math.floor(n*data.length/28)]/255:0;const idle=.08+.04*Math.sin(now*.001+n*.4);b.style.transform=`scaleX(${motion==='off'?.08:Math.max(.06,playing?sample:idle)})`;b.style.opacity=playing?'.85':'.22'});
  if(playing)progress.style.width=Math.min(100,(now-start)/(duration*1000)*100)+'%';
 }
 requestAnimationFrame(frame);
})();
// Original synthesized menu ambience: a soft, slowly breathing suspended chord.
(()=>{
 const button=document.getElementById('ambience-toggle'),slider=document.getElementById('ambience-volume');
 let context,master,enabled=false,home=!document.getElementById('home').hidden,voices=[];
 function level(){if(!context||!master)return;const now=context.currentTime;master.gain.cancelScheduledValues(now);master.gain.setTargetAtTime(enabled&&home&&!document.hidden?Number(slider.value)*.10:0,now,.7);button.textContent=enabled?(home?'Ambience: On':'Ambience: Paused'):'Ambience: Off';button.setAttribute('aria-pressed',String(enabled))}
 async function setup(){if(context){await context.resume();return}context=new AudioContext();master=context.createGain();master.gain.value=0;master.connect(context.destination);
  const filter=context.createBiquadFilter();filter.type='lowpass';filter.frequency.value=650;filter.Q.value=.3;filter.connect(master);
  // A D-suspended voicing with slow independent amplitude modulation, no external media.
  [146.832,220,293.665,329.628,440].forEach((hz,i)=>{
   const osc=context.createOscillator(),gain=context.createGain(),lfo=context.createOscillator(),depth=context.createGain();osc.type='sine';osc.frequency.value=hz;osc.detune.value=(i-2)*2;gain.gain.value=.16;lfo.frequency.value=.045+i*.012;depth.gain.value=.045;lfo.connect(depth);depth.connect(gain.gain);osc.connect(gain);gain.connect(filter);osc.start();lfo.start();voices.push(osc,lfo)
  });
 }
 button.onclick=async()=>{try{if(!enabled)await setup();enabled=!enabled;level()}catch{button.textContent='Ambience unavailable'}};
 slider.oninput=level;addEventListener('needle:screen',e=>{const next=e.detail.home;if(home!==next){home=next;level()}});document.addEventListener('visibilitychange',level);
 addEventListener('pagehide',()=>{context?.close();voices=[];context=null;master=null;enabled=false});
})();

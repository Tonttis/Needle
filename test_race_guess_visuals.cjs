const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync('static/app.js','utf8');let stops=0,actions=0;const nodes={'#search':{value:'answer'},'#results':{innerHTML:'old'}};
const context={state:{mode:'race',phase:'playing',submitted:false,serverTime:10,race_cooldown_until:0,round:1,stage:0},submitting:false,ctx:{resume:async()=>{}},stop(){stops++},document:{querySelectorAll(){return[]}},action:async()=>{actions++},searchSeq:0,$:s=>nodes[s]};
vm.createContext(context);vm.runInContext(code.slice(code.indexOf('async function guess(id,answer)'),code.indexOf('function stop(){')),context);
(async()=>{await context.guess('wrong');assert.equal(actions,1);assert.equal(stops,0);assert.equal(nodes['#search'].value,'');console.log('Wrong video-race guess keeps playback and visualizer running: passed')})().catch(e=>{console.error(e);process.exitCode=1});

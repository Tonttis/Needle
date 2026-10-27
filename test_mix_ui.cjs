// Exercise the actual filter/controller code without a browser or external services.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
const config=JSON.parse(execFileSync('python',['-c','import catalog,json;print(json.dumps(catalog.filter_options()))'],{encoding:'utf8'}));
class Select{
 constructor(value){this.value=value;this.listeners={};this.disabled=false;this.options=[];this.parentElement={hidden:false};}
 set innerHTML(html){this.options=[...html.matchAll(/<option( disabled)?>(.*?)<\/option>/g)].map(m=>({value:m[2].replace(/&amp;/g,'&'),disabled:!!m[1]}));this.value=this.options.find(o=>!o.disabled)?.value||'';}
 addEventListener(event,fn){this.listeners[event]=fn;}
}
const elements={'#region':new Select('Worldwide'),'#genre':new Select('Mixed'),'#difficulty':new Select('Easy'),'#decade':new Select('All'),'#solo':{},'#create':{},'#mix-help':{}};
const scope={mode:'guess',$:id=>elements[id],esc:s=>s.replace(/&/g,'&amp;'),api:async path=>{assert.equal(path,'config');return config},setTimeout:()=>1,clearTimeout(){},URLSearchParams,error:e=>{throw e}};
vm.createContext(scope);const code=fs.readFileSync('static/app.js','utf8');vm.runInContext(code.slice(code.indexOf('let warmTimer,mixConfig;')),scope);
setImmediate(()=>{try{
 assert.equal(elements['#solo'].disabled,false);assert.equal(elements['#difficulty'].value,'Easy');
 assert.equal(elements['#region'].options.length,config.regions.length);
 for(const region of config.regions){
  elements['#region'].value=region;elements['#genre'].value='Mixed';elements['#difficulty'].value='Easy';vm.runInContext('syncMix()',scope);
  assert.equal(elements['#difficulty'].value,'Easy',region);
  for(const genre of Object.keys(config.support[region])){
   elements['#genre'].value=genre;vm.runInContext('syncMix()',scope);
   assert.equal(elements['#genre'].value,genre);
   assert.ok(config.support[region][genre].includes(elements['#difficulty'].value));
  }
 }
 elements['#region'].value='Finland';elements['#genre'].value='Jazz';vm.runInContext('syncMix()',scope);
 assert.equal(elements['#genre'].value,'Mixed');assert.ok(elements['#genre'].options.find(o=>o.value==='Jazz').disabled);
 scope.mode='hits';vm.runInContext('syncMix()',scope);assert.equal(elements['#genre'].parentElement.hidden,true);assert.match(elements['#mix-help'].textContent,/Hottest Hits/);
 scope.mode='playlist';vm.runInContext('syncMix()',scope);assert.equal(elements['#decade'].parentElement.hidden,true);scope.mode='guess';vm.runInContext('syncMix()',scope);assert.equal(elements['#genre'].parentElement.hidden,false);assert.equal(elements['#decade'].parentElement.hidden,false);
 console.log('Filter UI: every supported scene/genre, difficulty fallback, and unsupported choices passed.');
}catch(e){console.error(e);process.exitCode=1}});

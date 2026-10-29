/* Optional Party transitions with generated audio and two real browser sessions. */
if(process.env.NEEDLE_BROWSER_TESTS!=='1'){console.log('Party Duel browser test: optional (set NEEDLE_BROWSER_TESTS=1).');process.exit(0)}
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const fixture=spawn('python3',['-u','duel_browser_fixture.py'],{cwd:__dirname,stdio:['ignore','pipe','pipe']});
let browser,base,logs='';const errors=[];fixture.stderr.on('data',d=>logs+=d.toString());
const port=new Promise((resolve,reject)=>{let data='';const timer=setTimeout(()=>reject(Error(logs||'Fixture timeout')),30000);fixture.stdout.on('data',d=>{data+=d;try{const result=JSON.parse(data.split('\n')[0]);clearTimeout(timer);resolve(result.port)}catch{}})});
const phase=(page,value)=>page.waitForFunction(value=>document.querySelector('#game').dataset.phase===value,value,{timeout:25000});
const mode=(page,value)=>page.waitForFunction(value=>document.querySelector('#game').dataset.mode===value,value);
const state=page=>page.evaluate(async()=>{const session=JSON.parse(sessionStorage.getItem('needle'));return(await fetch('/api/state?'+new URLSearchParams(session))).json()});
async function pick(page,index){await page.locator('#duel-query').fill('any song');await page.locator('#duel-find').click();await page.locator('[data-candidate="'+index+'"]').click();await page.locator('#duel-pick-confirm').click()}
async function advance(page,seconds){await page.request.post(base+'/__test/advance',{data:{seconds}})}
async function bounds(page){const result=await page.evaluate(()=>({scroll:document.documentElement.scrollHeight,height:innerHeight,panels:[...document.querySelectorAll('#lobby-settings,#duel-panel,#next,#duel-next,#wrapup')].filter(n=>n.getBoundingClientRect().height>0).map(n=>({id:n.id,top:n.getBoundingClientRect().top,bottom:n.getBoundingClientRect().bottom}))}));assert.ok(result.scroll<=result.height+1,JSON.stringify(result));assert.ok(result.panels.every(p=>p.top>=0&&p.bottom<=result.height+1),JSON.stringify(result))}
(async()=>{try{
 base='http://127.0.0.1:'+await port;
 browser=await chromium.launch({headless:true,executablePath:process.env.NEEDLE_CHROME||undefined,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--autoplay-policy=no-user-gesture-required']});
 const contexts=await Promise.all([{width:1280,height:800},{width:390,height:844}].map(async viewport=>{const c=await browser.newContext({viewport});await c.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('data:')?r.continue():r.abort());return c}));
 const a=await contexts[0].newPage(),b=await contexts[1].newPage();for(const p of [a,b])p.on('pageerror',e=>errors.push(e.message));
 await a.goto(base);await a.locator('.mode[data-mode=party]').click();await a.locator('#name').fill('Alice');
 for(const value of ['guess','race','hits'])await a.locator('#party-settings input[value='+value+']').uncheck();
 await a.locator('#party-settings input[value=duel]').check();await a.locator('#create').click();await phase(a,'lobby');
 const initial=await state(a);await b.goto(base+'/?room='+initial.code);await b.locator('#invite-name').fill('Bob');await b.locator('#invite-join').click();await phase(b,'lobby');
 await a.locator('#lobby-rounds').selectOption('3');await a.locator('#lobby-save').click();await a.waitForFunction(()=>!document.querySelector('#lobby-save').disabled);
 assert.equal(await b.locator('#lobby-party input[value=duel]').isDisabled(),true);await bounds(a);await bounds(b);
 await a.locator('#next').click();await phase(a,'picking');await phase(b,'picking');assert.equal((await state(a)).game_mode,'party');assert.match(await a.locator('#roundLabel').textContent(),/PARTY/);
 await pick(a,0);await pick(b,1);await phase(a,'clips');await phase(b,'clips');
 // Let the real server fill missing selections, then browser-decode the actual clips.
 await advance(a,31);await phase(a,'playing');await phase(b,'playing');await advance(a,2);
 await a.locator('#duel-guess').fill('Song B');await a.locator('#duel-guess-submit').click();await b.locator('#duel-guess').fill('Song A');await b.locator('#duel-guess-submit').click();await phase(a,'reveal');await phase(b,'reveal');await bounds(a);await bounds(b);
 assert.deepEqual((await state(a)).players.map(p=>p.score),[1,1]);await a.locator('#duel-next').click();await mode(a,'choice');await mode(b,'choice');
 assert.equal(await a.locator('#duel-panel').isVisible(),false);await bounds(a);await bounds(b);
 for(const page of [a,b])await page.locator('#choices button').first().click();await phase(a,'reveal');await a.locator('#next').click();
 // New cycle starts with Duel again, then one shared Party final and rematch.
 await phase(a,'picking');await phase(b,'picking');await advance(a,31);await phase(a,'reveal');await a.locator('#duel-next').click();await phase(a,'finished');await phase(b,'finished');
 const done=await state(a);assert.equal(done.game_mode,'party');assert.equal(done.score_max,3);assert.deepEqual(done.recap.map(r=>r.mode),['duel','choice','duel']);
 assert.match(await a.locator('#recap-list').textContent(),/Song Duel/);await bounds(a);await bounds(b);
 const boards=await a.evaluate(async()=>({party:await(await fetch('/api/leaderboard?mode=party&difficulty=Easy&multi=1')).json(),duel:await(await fetch('/api/leaderboard?mode=duel&difficulty=Duel&multi=1')).json()}));assert.equal(boards.party.entries.length,2);assert.equal(boards.duel.entries.length,0);
 await a.locator('#return-lobby').click();await phase(a,'lobby');await phase(b,'lobby');assert.equal((await state(a)).code,initial.code);assert.equal(await a.locator('#lobby-party input[value=duel]').isChecked(),true);
 for(const page of [a,b])assert.equal(await page.locator('#error').textContent(),'');assert.deepEqual(errors,[]);
 console.log('Party Duel browser passed: desktop/mobile selection, private picks, real clips, Duel → choice → Duel, shared scores/recap/leaderboard, same-room rematch, no overflow.');
}finally{if(browser)await browser.close();fixture.kill('SIGTERM')}})().catch(e=>{console.error(e,logs);process.exitCode=1});

/* Optional real two-browser test with fixture media, not live providers.
 * NEEDLE_BROWSER_TESTS=1 NEEDLE_CHROME=/path/to/chrome node test_duel_browser.cjs
 * Requires Playwright, Python, and ffmpeg. The production server has no test routes.
 */
if(process.env.NEEDLE_BROWSER_TESTS!=='1'){console.log('Song Duel browser test: optional (set NEEDLE_BROWSER_TESTS=1).');process.exit(0)}
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const shots=process.env.NEEDLE_DUEL_SHOTS||fs.mkdtempSync(path.join(os.tmpdir(),'needle-duel-shots-'));
const fixture=spawn('python3',['-u','duel_browser_fixture.py'],{cwd:__dirname,stdio:['ignore','pipe','pipe']});
let browser,base;const errors=[];let logs='';fixture.stderr.on('data',data=>logs+=data.toString());
const waitPort=new Promise((resolve,reject)=>{let data='';const timer=setTimeout(()=>reject(Error('Fixture start timed out: '+logs)),30000);fixture.stdout.on('data',part=>{data+=part;const line=data.split('\n')[0];try{const value=JSON.parse(line);clearTimeout(timer);resolve(value.port)}catch{}});fixture.on('exit',code=>reject(Error('Fixture exited '+code+': '+logs)))});
async function state(page){return page.evaluate(async()=>{const session=JSON.parse(sessionStorage.getItem('needle'));return(await fetch('/api/state?'+new URLSearchParams(session))).json()})}
async function phase(page,value){await page.waitForFunction(value=>document.querySelector('#game').dataset.phase===value,value,{timeout:25000})}
async function bounds(page,label){
 const value=await page.evaluate(()=>({height:Math.min(innerHeight,window.visualViewport?.height||innerHeight),scroll:document.documentElement.scrollHeight,panel:document.querySelector('#duel-panel').getBoundingClientRect().bottom,buttons:[...document.querySelectorAll('#duel-panel button:not([hidden]),#duel-panel input:not([hidden])')].filter(x=>x.getBoundingClientRect().height>0).map(x=>({label:x.id||x.textContent.slice(0,30),top:x.getBoundingClientRect().top,bottom:x.getBoundingClientRect().bottom}))}));
 assert.ok(value.scroll<=Math.max(value.height,await page.evaluate(()=>innerHeight))+1,label+' page overflow: '+JSON.stringify(value));
 assert.ok(value.buttons.every(x=>x.top>=0&&x.bottom<=Math.min(value.height,value.panel)+1),label+' controls overflow: '+JSON.stringify(value));
}
async function pick(page,index){
 await page.locator('#duel-query').fill('any song');await page.locator('#duel-find').click();await page.locator('[data-candidate="'+index+'"]').click();await bounds(page,'pick');await page.locator('#duel-pick-confirm').click();
}
async function positions(page,values){
 for(const value of values){await page.locator('#duel-seek').evaluate((node,value)=>{node.value=String(value);node.dispatchEvent(new Event('input',{bubbles:true}))},value);await page.locator('#duel-add').click()}
 await page.waitForFunction(()=>document.querySelector('#duel-slot-count').textContent==='5 / 5 selected');
}
(async()=>{
 try{
  const port=await waitPort;base='http://127.0.0.1:'+port;
  browser=await chromium.launch({headless:true,...(process.env.NEEDLE_CHROME?{executablePath:process.env.NEEDLE_CHROME,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{} )});
  const aContext=await browser.newContext({viewport:{width:1280,height:800}}),bContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  for(const context of [aContext,bContext]){await context.route('**/*',route=>route.request().url().startsWith(base)||route.request().url().startsWith('data:')?route.continue():route.abort());context.on('page',page=>page.on('pageerror',error=>errors.push(error.message)))}
  const a=await aContext.newPage(),b=await bContext.newPage();
  await a.goto(base);await a.locator('[data-mode="duel"]').click();assert.equal(await a.locator('#solo').isVisible(),false);assert.equal(await a.locator('#genre').isVisible(),false);
  const art=await a.locator('.duel-card-art img').boundingBox();assert.ok(Math.abs(art.width/art.height-260/160)<.02);await a.screenshot({path:path.join(shots,'home-duel.png')});
  await a.locator('#name').fill('Alice');await a.locator('#create').click();await phase(a,'lobby');await bounds(a,'lobby desktop');assert.equal(await a.locator('#duel-volume').isVisible(),true);await a.locator('#duel-volume').fill('0.35');assert.equal(await a.locator('#duel-volume-value').textContent(),'35%');
  const av=await state(a);await a.locator('#duel-rounds').selectOption('1');
  await b.goto(base+'/?room='+av.code);await b.locator('#invite-name').fill('Bob');await b.locator('#invite-join').click();await phase(b,'lobby');await bounds(b,'lobby phone');
  await a.locator('#duel-start').click();await phase(a,'picking');await phase(b,'picking');
  await pick(a,0);await pick(b,1);await phase(a,'clips');await phase(b,'clips');
  assert.ok(!(await a.locator('#duel-panel').textContent()).includes('Song B'));assert.ok(!(await b.locator('#duel-panel').textContent()).includes('Song A'));
  await positions(a,[80,20,60,0,40]);await positions(b,[45,15,35,5,25]);assert.deepEqual((await state(a)).duel.positions,[0,20,40,60,80]);assert.deepEqual((await state(b)).duel.positions,[5,15,25,35,45]);assert.deepEqual(await a.locator('#duel-markers span').allTextContents(),['1','2','3','4','5']);await bounds(a,'clips desktop');await bounds(b,'clips phone');for(const viewport of [{width:360,height:640},{width:844,height:390}]){await b.setViewportSize(viewport);await bounds(b,'clips '+viewport.width+'x'+viewport.height)}await b.setViewportSize({width:390,height:844});
  await a.screenshot({path:path.join(shots,'clips-desktop.png')});await b.screenshot({path:path.join(shots,'clips-phone.png')});
  await b.reload();await phase(b,'clips');assert.deepEqual((await state(b)).duel.positions,[5,15,25,35,45]);assert.equal(await b.locator('#duel-slot-count').textContent(),'5 / 5 selected');
  await a.locator('#duel-lock').click();await b.locator('#duel-lock').click();await phase(a,'playing');await phase(b,'playing');
  await bounds(a,'guess desktop');await bounds(b,'guess phone');for(const viewport of [{width:360,height:640},{width:844,height:390}]){await b.setViewportSize(viewport);await bounds(b,'guess '+viewport.width+'x'+viewport.height)}await b.setViewportSize({width:390,height:844});
  await b.waitForFunction(()=>!document.getElementById('duel-guess').disabled);await b.locator('#duel-guess').focus();
  await b.evaluate(()=>{Object.defineProperty(window.visualViewport,'height',{value:430,configurable:true});window.visualViewport.dispatchEvent(new Event('resize'))});
  await bounds(b,'guess with phone keyboard');assert.equal(await b.locator('.duel-listen').isVisible(),false);
  await b.evaluate(()=>{document.activeElement.blur();delete window.visualViewport.height;window.visualViewport.dispatchEvent(new Event('resize'))});
  const as=await state(a),bs=await state(b);assert.equal(as.deadline-as.duel.starts_at,45);
  await b.reload();await phase(b,'playing');assert.equal((await state(b)).deadline,bs.deadline);await b.locator('[data-play="0"]').click();await b.waitForTimeout(500);await b.locator('[data-play="0"]').click();await b.waitForFunction(()=>document.body.classList.contains('is-playing'));
  assert.equal(await b.evaluate(async({key,room})=>{const session=JSON.parse(sessionStorage.getItem('needle'));return(await fetch('/duel-clip/'+key+'?'+new URLSearchParams({...session,round:'1',clip:'0'}))).status},{key:as.duel.clip_key,room:av.code}),400);
  await a.locator('[data-play="2"]').click();await a.waitForFunction(()=>document.body.classList.contains('is-playing'));await a.waitForTimeout(350);await a.waitForFunction(()=>Number(document.querySelector('#duel-spectrum').dataset.level)>0);assert.ok((await a.locator('#duel-visual-label').textContent()).includes('Clip 3'));const firstWave=await a.locator('#duel-spectrum').evaluate(c=>c.toDataURL());await a.waitForTimeout(120);assert.notEqual(await a.locator('#duel-spectrum').evaluate(c=>c.toDataURL()),firstWave);
  assert.ok(await a.locator('[data-play="2"]').evaluate(node=>parseFloat(node.style.getPropertyValue('--played'))>0));
  await a.locator('[data-play="2"]').click();await a.locator('[data-play="0"]').click();
  await a.locator('#duel-volume').evaluate(node=>{node.value='0.2';node.dispatchEvent(new Event('input',{bubbles:true}))});assert.equal(await a.evaluate(()=>localStorage.getItem('needle-volume')),'0.2');assert.equal(await a.locator('#duel-volume-value').textContent(),'20%');await a.locator('#duel-volume').fill('0');assert.equal(await a.locator('#duel-volume-value').textContent(),'Muted');await a.locator('#duel-stop').click();assert.equal(await a.locator('#duel-spectrum').getAttribute('data-level'),'0');await a.locator('#duel-volume').fill('0.2');
  await a.screenshot({path:path.join(shots,'guess-desktop.png')});await b.screenshot({path:path.join(shots,'guess-phone.png')});
  for(let i=0;i<3;i++){await a.locator('#duel-guess').fill('Wrong title '+i);await a.locator('#duel-guess-submit').click();await a.waitForFunction(count=>document.querySelector('#duel-feedback').textContent.includes('Not that song'),i)}
  assert.ok((await state(a)).duel.attempts>=3);
  await a.locator('#duel-guess').fill('Song B');await a.locator('[data-suggestion="1"]').waitFor();await bounds(a,'desktop suggestions');await a.locator('[data-suggestion="1"]').click();await a.waitForFunction(()=>document.querySelector('#duel-feedback').textContent.startsWith('Correct'));
  await b.locator('#duel-guess').fill('Artist A Song A');await b.locator('[data-suggestion="0"]').waitFor();await bounds(b,'phone suggestions');await b.locator('[data-suggestion="0"]').click();await phase(a,'reveal');await phase(b,'reveal');await bounds(a,'reveal desktop');await bounds(b,'reveal phone');
  assert.deepEqual((await state(a)).players.map(p=>p.score),[1,1]);
  await a.locator('#duel-preview-play').click();await a.waitForFunction(()=>document.querySelector('#duel-preview-status').textContent.includes('1 / 2 ·'),{},{timeout:25000});await a.waitForFunction(()=>document.querySelector('#duel-preview-status').textContent.includes('2 / 2 ·'),{},{timeout:15000});await a.waitForFunction(()=>Number(document.querySelector('#duel-spectrum').dataset.level)>0);assert.equal(await a.locator('#duel-volume').inputValue(),'0.2');await a.locator('#duel-volume').fill('0.4');assert.equal(await a.locator('#duel-volume-value').textContent(),'40%');await a.waitForFunction(()=>document.querySelector('#duel-preview-status').textContent.includes('Previews complete'),{},{timeout:15000});
  await a.locator('#duel-preview-play').click();await a.waitForFunction(()=>document.body.classList.contains('is-playing'));await a.locator('#duel-stop').click();assert.equal(await a.evaluate(()=>document.body.classList.contains('is-playing')),false);
  await a.screenshot({path:path.join(shots,'reveal-desktop.png')});await b.screenshot({path:path.join(shots,'reveal-phone.png')});
  await a.locator('#duel-next').click();await phase(a,'finished');await phase(b,'finished');await bounds(a,'finished desktop');await bounds(b,'finished phone');
  const board=await a.evaluate(async()=> (await fetch('/api/leaderboard?mode=duel&difficulty=Duel&multi=1')).json());assert.equal(board.entries.length,2);
  await a.locator('#duel-rematch').click();await phase(a,'lobby');await phase(b,'lobby');await a.locator('#duel-start').click();await phase(b,'picking');
  await pick(a,0);await a.request.post(base+'/__test/advance',{data:{seconds:31}});await phase(a,'reveal');await phase(b,'reveal');
  assert.deepEqual((await state(a)).players.map(p=>p.score),[1,0]);assert.ok((await a.locator('#duel-panel').textContent()).includes('forfeit'));
  assert.equal(await a.locator('#error').textContent(),'');assert.equal(await b.locator('#error').textContent(),'');assert.deepEqual(errors,[],'browser errors');
  console.log('Song Duel real browsers: desktop + phone; private songs/clips, five selections, real audio, unlimited guesses/replays, scoring, leaderboards, rematch, timeouts, no page overflow. Passed.');console.log('Internal screenshots:',shots);
 }finally{if(browser)await browser.close();fixture.kill('SIGTERM')}
})().catch(error=>{console.error(error);if(logs)console.error(logs);process.exitCode=1});

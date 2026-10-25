const fs = require('fs');
const http = require('http');
const path = require('path');
const os = require('os');
const {spawn} = require('child_process');
const assert = require('assert');
const root = path.resolve(__dirname, '..');
const pause = ms => new Promise(r=>setTimeout(r,ms));
const results=[];
async function main() {
 const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost');
  const rel=decodeURIComponent(url.pathname).slice(1);
  if (!/^(design\/ui-preview\.html|web\/[\w.-]+)$/.test(rel)){res.writeHead(404);res.end();return;}
  const file=path.join(root,rel);
  const type={'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon'}[path.extname(file)];
  try {res.setHeader('Content-Type',type||'application/octet-stream');res.end(fs.readFileSync(file));}catch(e){res.writeHead(404);res.end();}
 });
 await new Promise(r=>server.listen(8011,'127.0.0.1',r));
 const profile=fs.mkdtempSync(path.join(os.tmpdir(),'course-ui-t06-'));
 const browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu','--no-sandbox','--disable-software-rasterizer','--disable-background-networking','--disable-component-update','--disable-sync','--disable-extensions','--no-first-run','--no-default-browser-check','--remote-debugging-port=9226','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
 browser.stderr.on("data",d=>process.stderr.write(d));
 let ws;
 try {
  let tabs;
  for(let i=0;i<250;i++){try{tabs=await (await fetch('http://127.0.0.1:9226/json')).json();break;}catch(e){await pause(100);}}
  assert(tabs,'Edge CDP unavailable');
  ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
  let seq=0;const pending=new Map();
  ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);if(m.error)p.reject(Error(JSON.stringify(m.error)));else p.resolve(m.result);}};
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  await call('Page.enable');
  for(const width of [360,390,768,1280])for(const theme of ['light','dark'])for(const mode of ['today','week']){
   await call('Emulation.setDeviceMetricsOverride',{width,height:width<600?640:900,deviceScaleFactor:1,mobile:false});
   await call('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme},{name:'prefers-reduced-motion',value:'reduce'}]});
   await call('Page.navigate',{url:'http://127.0.0.1:8011/design/ui-preview.html?mode='+mode});
   await pause(650);
   const item=await evaluate(`({width:innerWidth,scroll:document.documentElement.scrollWidth,checks:JSON.parse(document.documentElement.getAttribute('data-preview-results')),metrics:JSON.parse(document.documentElement.getAttribute('data-preview-metrics'))})`);
   assert.equal(item.width,width);assert(item.scroll<=width);assert(item.checks&&item.checks.every(c=>c.pass),JSON.stringify(item));
   const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
   fs.writeFileSync('design/screenshots/'+mode+'-'+width+'-'+theme+'.png',Buffer.from(shot.data,'base64'));
   results.push({mode,theme,...item});
  }
  for(const mode of ['weekend','empty','gate','expired','lock','no-data','network','sheet','bounds','periods','unconfigured','xss']){
   await call('Emulation.setDeviceMetricsOverride',{width:360,height:640,deviceScaleFactor:1,mobile:false});
   await call('Page.navigate',{url:'http://127.0.0.1:8011/design/ui-preview.html?mode='+mode});await pause(700);
   const checks=await evaluate(`JSON.parse(document.documentElement.getAttribute('data-preview-results'))`);
   assert(checks&&checks.every(c=>c.pass),mode+JSON.stringify(checks));results.push({mode,checks});
  }
  await call('Page.navigate',{url:'http://127.0.0.1:8011/design/ui-preview.html?mode=weekend'});await pause(650);
  for(const count of [6,7]) {
   if(count===7) await evaluate("fixture.courses.push({name:'Sunday example',day:6,units:[2,3],weeks:[8],room:'D404',teachers:''});document.getElementById('week-next').click()");
   await pause(100);
   const dims=await evaluate("({width:document.getElementById('grid').getBoundingClientRect().width,col:document.querySelector('#grid thead th:nth-child(2)').getBoundingClientRect().width,page:document.documentElement.scrollWidth})");
   assert(dims.col>=56,JSON.stringify({count,...dims,debug:await evaluate("({style:document.getElementById('grid').getAttribute('style'),cols:document.querySelectorAll('#grid col').length,heads:document.querySelectorAll('#grid thead th').length})")}));assert(dims.page<=360);
   results.push({mode:'columns-'+count,...dims});
  }
  const label=await evaluate("document.getElementById('week-label').textContent");
  await evaluate("document.getElementById('grid-scroll').focus()");
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
  await call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});await pause(200);
  assert.equal(await evaluate("document.getElementById('week-label').textContent"),label);
  assert(await evaluate("document.getElementById('grid-scroll').scrollLeft>0"));
  await evaluate("document.getElementById('week-label').focus()");
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
  assert.notEqual(await evaluate("document.getElementById('week-label').textContent"),label);
  await call('Emulation.setEmulatedMedia',{media:'print'});
  assert(await evaluate("getComputedStyle(document.getElementById('week-label')).display!=='none'&&getComputedStyle(document.getElementById('pane-today')).display!=='none'&&getComputedStyle(document.getElementById('pane-week')).display!=='none'"));
  results.push({mode:'keyboard-and-print',pass:true});
  await call('Emulation.setEmulatedMedia',{media:''});
  for(const mode of ['render-error','login-render-error','login-network']){
   await call('Page.navigate',{url:'http://127.0.0.1:8011/design/ui-preview.html?mode='+mode});await pause(650);
   if(mode!=='render-error') {await evaluate("document.getElementById('gate-input').value='example';document.getElementById('gate-form').dispatchEvent(new Event('submit',{cancelable:true}))");await pause(400);}
   const text=await evaluate("document.getElementById('"+(mode==='login-network'?'gate-error':'fatal-text')+"').textContent");
   assert(text.includes(mode==='login-network'?'网络连接失败':'页面出错了，请刷新'),mode+text);
   results.push({mode,text});
  }
  fs.writeFileSync('design/screenshots/browser-results.json',JSON.stringify(results,null,2));
  console.log('16 viewport/theme screenshots, 12 states, column widths, keyboard, print and error checks passed');
 } finally {
  if(ws)ws.close();browser.kill();server.close();
  await pause(500);
  fs.rmSync(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
 }
}
main().catch(e=>{fs.writeFileSync('design/screenshots/browser-results.json',JSON.stringify({results,error:String(e)},null,2));console.error(e);process.exitCode=1});

const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync('web/app.js', 'utf8');
const context = {state: {data: {courses: []}}, WEEKDAYS: ['一','二','三','四','五','六','日']};
vm.createContext(context);
['parseDate','dayNumber','weekdayIndex','weekOf','weekDates','unitText','weekText','coursesOn','meetingsOf','hueOf'].forEach(name => {
  const match = source.match(new RegExp('^  function ' + name + '\\([\\s\\S]*?^  }', 'm'));
  assert(match, name);
  vm.runInContext(match[0], context);
});
assert.equal(context.weekOf(new Date(2026,9,24), '2026-08-31'), 8);
assert.equal(context.weekOf(new Date(2026,7,1), '2026-08-31'), 1);
assert.equal(context.weekDates(8, '2026-08-31')[0], '10/19');
assert.equal(context.weekDates(1, null), null);
assert.equal(context.unitText({units:[0,1]}).replace(/[—–]/g,'-'), '1-2');
assert.equal(context.weekText([1,2,3,5]).replace(/[—–]/g,'-'), '1-3，5');
context.state.data.courses = [
 {name:'机械',day:0,units:[2,3],weeks:[8]},
 {name:'机械',day:2,units:[0,1],weeks:[9]},
 {name:'汽车',day:0,units:[0,1],weeks:[8]}
];
assert.equal(context.coursesOn(0,8)[0].name, '汽车');
assert.equal(context.meetingsOf({name:'机械'},8).length, 1);
assert.equal(context.hueOf('机械'), context.hueOf('机械'));
console.log('既有日历、过滤、排序、课程哈希基线通过');
const extraNames = ['boundedWeek','totalWeeks','nextCourse','validPeriods','todayDate','effectiveWeek'];
extraNames.forEach(name => {
 const match = source.match(new RegExp('^  function ' + name + '\\([\\s\\S]*?^  }', 'm'));
 assert(match, name); vm.runInContext(match[0], context);
});
assert.equal(context.hueOf('机械'), 6);
for (const name of ['', '汽车构造', '机械设计', '<img src=x onerror=alert(1)>', '😀']) {
 let hash = 0; for (let i=0;i<name.length;i++) hash=(hash*31+name.charCodeAt(i))>>>0;
 assert.equal(context.hueOf(name), hash%8);
}
assert.equal(context.totalWeeks(), 9);
assert.equal(context.boundedWeek(-20,17),1);
assert.equal(context.boundedWeek(18,17),17);
assert.equal(context.boundedWeek(8,17),8);
context.state.data.courses = [
 {name:'本周一不应选中',day:0,units:[0,1],weeks:[8]},
 {name:'下周一第一门',day:0,units:[0,1],weeks:[9]},
 {name:'下周一第二门',day:0,units:[2,3],weeks:[9]}
];
for (const day of [5,6]) {
 const result = context.nextCourse(day,8);
 assert.equal(result.course.name,'下周一第一门'); assert.equal(result.week,9);
 assert.equal(result.offset,7-day);
}
assert.equal(context.nextCourse(0,8).course.name,'下周一第一门');
assert.equal(context.nextCourse(0,8).offset,7);
assert.equal(context.nextCourse(0,9),null);
context.state.data.courses=[];
assert.equal(context.totalWeeks(),17);
assert.equal(context.nextCourse(5,8),null);
assert.equal(context.validPeriods(null,11),false);
assert.equal(context.validPeriods([['08:00','08:45']],11),false);
assert.equal(context.validPeriods([['25:00','26:00']],1),false);
assert.equal(context.validPeriods([['8:00','08:45']],1),false);
assert.equal(context.validPeriods([['08:00','08:45']],1),true);
assert.equal(context.validPeriods([['08:00','08:45'],null],1),false);
assert.equal(context.weekDates(19,'2026-08-31')[0],'1/4');
assert.equal(context.weekText([]),''); assert.equal(context.unitText({units:[]}), '—');
assert.equal(context.unitText({units:[10]}),'11');
assert.equal(context.weekOf(new Date(2026,7,31),'2026-08-31'),1);
assert.equal(context.weekOf(new Date(2026,8,6),'2026-08-31'),1);
assert.equal(context.weekOf(new Date(2026,8,7),'2026-08-31'),2);
const RealDate = Date;
context.Date = class extends RealDate {constructor(...args) {super(...(args.length ? args : [2026,9,25,12]));}};
context.state.todayIso='2026-10-24'; context.state.localDay=context.dayNumber(new Date(2026,9,24));
context.state.anchorDate=new Date(2026,9,24);context.state.currentWeek=8;
assert.equal(context.todayDate().getDate(),25); assert.equal(context.effectiveWeek(),8);
context.Date = class extends RealDate {constructor(...args) {super(...(args.length ? args : [2026,9,26,12]));}};
assert.equal(context.effectiveWeek(),9);
assert(!source.includes('innerHTML'));assert(!/\?\.|\?\?/.test(source));
const html=fs.readFileSync('web/index.html','utf8');
assert.equal((html.match(/content="\{OG_BASE\}/g)||[]).length,3);
assert(html.includes('/static/style.css?v=20261024.1'));
assert(html.includes('/static/app.js?v=20261024.1'));
const oldSource = require('child_process').execFileSync('git',['show','HEAD:web/app.js'],{encoding:'utf8'});
const poem = text => text.match(/  var POEMS = \[[\s\S]*?\n  \];/)[0].replace(/\r/g,'');
assert.equal(poem(source),poem(oldSource));
console.log('跨周、首末周、8 色哈希、时间字段、跨零点、资源约定与完整诗句数组自测通过');

function extract(name, target) {
 const match=source.match(new RegExp('^  function '+name+'\\([\\s\\S]*?^  }','m'));
 assert(match,name); vm.runInContext(match[0],target);
}
const fixes={}; vm.createContext(fixes);
extract('gridMinWidth',fixes);
assert.equal(fixes.gridMinWidth(6),374);
assert.equal(fixes.gridMinWidth(7),432);
assert.equal(fixes.gridMinWidth(6)+2,376);
assert.equal(fixes.gridMinWidth(7)+2,434);
assert(/id="week-label"[^>]*title="回到本周"/.test(html));
assert(!/id="week-label"[^>]*aria-label=/.test(html));
const labels={WEEKDAYS:['一','二','三','四','五','六','日'],
 node:()=>({setAttribute(k,v){this[k]=v},addEventListener(){}}),hueOf:()=>0,unitText:()=> '1–2'};
vm.createContext(labels);extract('courseButton',labels);
assert(labels.courseButton({name:'Test',day:0,room:'A101'},'next-course',8)['aria-label'].startsWith('下一次上课，'));
async function checkBoot() {
 for (const kind of ['network','render','ok']) {
  const seen=[];
  const ctx={state:{},TOKEN_KEY:'token',setPage:()=>{},readStored:()=>null,
   requestSnapshot:()=>kind==='network'?Promise.reject(Error('offline')):Promise.resolve({status:200}),
   handleSnapshot:()=>{if(kind==='render')throw Error('render broken')},
   showFatal:r=>seen.push(r?'server':'network'),showPageError:e=>seen.push('render')};
  vm.createContext(ctx); extract('receiveSnapshot',ctx); extract('boot',ctx); await ctx.boot();
  assert.deepEqual(seen,kind==='ok'?[]:[kind]);
 }
 console.log('Six/seven-column minimum widths and boot error classification passed');
}
checkBoot().catch(error=>{console.error(error);process.exitCode=1});

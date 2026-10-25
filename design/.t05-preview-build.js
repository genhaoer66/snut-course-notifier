const fs=require('fs');
const fixture={updated_at:'2026-10-22 07:00',updated_ts:1792623600,semester_start:'2026-08-31',current_week:8,server_today:'2026-10-22',unit_count:11,periods:null,courses:[
{name:'汽车构造',teachers:'示例教师甲',room:'7号楼 7203',day:3,units:[0,1],weeks:[8,9,10,17]},
{name:'机械设计基础',teachers:'示例教师乙',room:'7号楼 7105',day:3,units:[2,3],weeks:[8,9,10,17]},
{name:'工程力学',teachers:'示例教师丙',room:'8号楼 8201',day:0,units:[0,1],weeks:[9,17]},
{name:'高等数学',teachers:'示例教师丁',room:'A101',day:1,units:[4,5],weeks:[8,9,17]},
{name:'大学英语',teachers:'示例教师戊',room:'B202',day:2,units:[6,7],weeks:[8,9,17]},
{name:'材料成型',teachers:'',room:'',day:4,units:[8,9],weeks:[8,9,17]}
]};
fs.writeFileSync('design/t05-synthetic.json',JSON.stringify(fixture,null,2));
const setup=`
var previewMode=new URLSearchParams(location.search).get('mode')||'today';
var fixture=${JSON.stringify(fixture)};
window.previewRequests=[];
window.previewErrors=[];
window.addEventListener('error',function(e){previewErrors.push(e.message)});
var store={};
Object.defineProperty(window,'localStorage',{value:{getItem:function(k){return store[k]||null},setItem:function(k,v){store[k]=v},removeItem:function(k){delete store[k]}}});
if(previewMode==='render-error')fixture.courses=[null];
if(previewMode==='expired')store['snut.token']='invalid';
if(['week','weekend','bounds'].indexOf(previewMode)!==-1)store['snut.view']='week';
if(previewMode==='weekend')fixture.courses.push({name:'周末示例课',room:'C303',teachers:'示例教师',day:5,units:[0,1],weeks:[8,9]});
if(previewMode==='empty')fixture.server_today='2026-10-24';
if(previewMode==='unconfigured'){fixture.current_week=null;fixture.semester_start=null}
if(previewMode==='periods')fixture.periods=Array.from({length:11},function(){return ['08:00','08:45']});
if(previewMode==='xss')fixture.courses[0].name='<img src=x onerror=alert(1)>';
window.fetch=function(path,opts){
 previewRequests.push({path:path,options:opts});
 var status=200,body=fixture;
 if(previewMode==='login-render-error'||previewMode==='login-network'){if(!window.previewLoggedIn){status=401;body={}}else if(previewMode==='login-render-error'){fixture.courses=[null]}else return Promise.reject(Error('offline'));if(path==='/api/login')window.previewLoggedIn=true;}
 if(['gate','expired','lock'].indexOf(previewMode)!==-1){status=401;body={error:'需要访问口令'}}
 if(path==='/api/login'){status=previewMode==='lock'?429:200;body=status===429?{code:'locked',error:'口令错误次数过多，请 3 秒后再试'}:{ok:true,token:null}}
 if(previewMode==='no-data'){status=503;body={code:'no_data',error:'课表数据还没生成',hint:'合成提示：请等待更新'}}
 if(previewMode==='network')return Promise.reject(new Error('合成断网'));
 return Promise.resolve({status:status,json:function(){return Promise.resolve(body)}});
};
window.addEventListener('DOMContentLoaded',function(){setTimeout(function(){
 if(['sheet'].indexOf(previewMode)!==-1)document.querySelector('.course').click();
 if(previewMode==='lock'){document.getElementById('gate-input').value='wrong';document.getElementById('gate-form').dispatchEvent(new Event('submit',{cancelable:true}))}
 var results=[];
 function check(name,pass){results.push({name:name,pass:!!pass})}
 var app=document.getElementById('app');
 check('无脚本错误',previewErrors.length===0);
 check('只请求合成接口',previewRequests.every(function(r){return r.path==='/api/timetable'||r.path==='/api/login'}));
 if(!app.hidden){
 check('页面无横向溢出',document.documentElement.scrollWidth<=innerWidth);
 check('今日日期',document.getElementById('today-date').textContent.indexOf('第 8 周')!==-1||previewMode==='unconfigured');
 var first=document.querySelector('.course');
 if(first&&!document.getElementById('pane-today').hidden)check('首卡教室在首屏',first.querySelector('.course-room').getBoundingClientRect().bottom<=innerHeight);
 if(!document.getElementById('pane-week').hidden){
  check('十一节',document.querySelectorAll('#grid tbody tr').length===11);
  check('工作日不横滑',previewMode==='weekend'||document.getElementById('grid-scroll').scrollWidth<=document.getElementById('grid-scroll').clientWidth+1);
 }
 if(previewMode==='empty')check('下周课匹配',document.querySelector('.next-course').textContent.indexOf('工程力学')!==-1);
 if(previewMode==='xss')check('外部字符串无HTML执行',document.querySelectorAll('#today-list img').length===0&&document.querySelector('.course-name').textContent.indexOf('<img')===0);
 if(previewMode==='bounds'){
 var prev=document.getElementById('week-prev'),next=document.getElementById('week-next');
 for(var i=0;i<25;i++)prev.click();check('第一周禁用',prev.disabled);
 for(var j=0;j<25;j++)next.click();check('最大周禁用',next.disabled);
 document.getElementById('week-reset').click();check('回本周',document.getElementById('week-label').textContent.indexOf('第 8 周')!==-1);
 }
}
if(previewMode==='render-error')fixture.courses=[null];
if(previewMode==='expired')check('过期提示',document.getElementById('gate-error').textContent.indexOf('已过期')!==-1);
if(previewMode==='no-data')check('503提示',document.getElementById('fatal-hint').textContent.indexOf('合成提示')!==-1);
if(previewMode==='network')check('断网提示',document.getElementById('fatal-text').textContent.indexOf('连不上')!==-1);

if(previewMode==='sheet'){
 check('详情初始焦点',document.activeElement.id==='sheet-close');
 document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));
 check('详情Tab不逃逸',document.activeElement.id==='sheet-close');
 document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));
 setTimeout(function(){check('关闭回原卡',document.getElementById('sheet').hidden&&document.activeElement.classList.contains('course'));document.documentElement.setAttribute('data-preview-results',JSON.stringify(results))},220);
}
if(previewMode==='periods')check('有效periods才显示时间',document.querySelector('.course-time').textContent.indexOf('08:00')!==-1);
if(previewMode==='unconfigured')check('缺开学日期提示',document.querySelector('.notice').textContent.indexOf('尚未配置')!==-1);
if(previewMode==='weekend')check('周末仅溢出时提示',!document.getElementById('grid-hint').hidden===(document.getElementById('grid-scroll').scrollWidth>document.getElementById('grid-scroll').clientWidth+1));
check('桌面双栏或移动切换',innerWidth>=1024?!document.getElementById('pane-today').hidden&&!document.getElementById('pane-week').hidden&&document.getElementById('view-tabs').hidden:true);
document.documentElement.setAttribute('data-preview-metrics',JSON.stringify({width:innerWidth,height:innerHeight,bg:getComputedStyle(document.documentElement).backgroundColor}));
document.documentElement.setAttribute('data-preview-results',JSON.stringify(results));
},300)});
`;
let html=fs.readFileSync('web/index.html','utf8').replace(/\/static\//g,'../web/').replace('<script defer', '<script>'+setup+'</script><script defer');
fs.writeFileSync('design/ui-preview.html',html);

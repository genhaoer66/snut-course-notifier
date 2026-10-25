(function () {
  "use strict";
  var TOKEN_KEY = "snut.token";
  var VIEW_KEY = "snut.view";
  var WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
  var state = {data: null, currentWeek: null, week: 1, view: "today", token: null, todayIso: "", lockUntil: 0, lockTimer: null, trigger: null, closing: null};
  var POEMS = [
    ["白日依山尽，黄河入海流。", "王之涣《登鹳雀楼》"],
    ["欲穷千里目，更上一层楼。", "王之涣《登鹳雀楼》"],
    ["会当凌绝顶，一览众山小。", "杜甫《望岳》"],
    ["读书破万卷，下笔如有神。", "杜甫《奉赠韦左丞丈二十二韵》"],
    ["星垂平野阔，月涌大江流。", "杜甫《旅夜书怀》"],
    ["随风潜入夜，润物细无声。", "杜甫《春夜喜雨》"],
    ["海内存知己，天涯若比邻。", "王勃《送杜少府之任蜀州》"],
    ["落霞与孤鹜齐飞，秋水共长天一色。", "王勃《滕王阁序》"],
    ["穷且益坚，不坠青云之志。", "王勃《滕王阁序》"],
    ["路漫漫其修远兮，吾将上下而求索。", "屈原《离骚》"],
    ["亦余心之所善兮，虽九死其犹未悔。", "屈原《离骚》"],
    ["山重水复疑无路，柳暗花明又一村。", "陆游《游山西村》"],
    ["纸上得来终觉浅，绝知此事要躬行。", "陆游《冬夜读书示子聿》"],
    ["长风破浪会有时，直挂云帆济沧海。", "李白《行路难》"],
    ["天生我材必有用，千金散尽还复来。", "李白《将进酒》"],
    ["两岸猿声啼不住，轻舟已过万重山。", "李白《早发白帝城》"],
    ["桃花潭水深千尺，不及汪伦送我情。", "李白《赠汪伦》"],
    ["举头望明月，低头思故乡。", "李白《静夜思》"],
    ["春蚕到死丝方尽，蜡炬成灰泪始干。", "李商隐《无题》"],
    ["身无彩凤双飞翼，心有灵犀一点通。", "李商隐《无题》"],
    ["夕阳无限好，只是近黄昏。", "李商隐《乐游原》"],
    ["采菊东篱下，悠然见南山。", "陶渊明《饮酒》"],
    ["行到水穷处，坐看云起时。", "王维《终南别业》"],
    ["明月松间照，清泉石上流。", "王维《山居秋暝》"],
    ["大漠孤烟直，长河落日圆。", "王维《使至塞上》"],
    ["春眠不觉晓，处处闻啼鸟。", "孟浩然《春晓》"],
    ["绿树村边合，青山郭外斜。", "孟浩然《过故人庄》"],
    ["野火烧不尽，春风吹又生。", "白居易《赋得古原草送别》"],
    ["日出江花红胜火，春来江水绿如蓝。", "白居易《忆江南》"],
    ["同是天涯沦落人，相逢何必曾相识。", "白居易《琵琶行》"],
    ["沉舟侧畔千帆过，病树前头万木春。", "刘禹锡《酬乐天扬州初逢席上见赠》"],
    ["千淘万漉虽辛苦，吹尽狂沙始到金。", "刘禹锡《浪淘沙》"],
    ["晴空一鹤排云上，便引诗情到碧霄。", "刘禹锡《秋词》"],
    ["山不在高，有仙则名。", "刘禹锡《陋室铭》"],
    ["问渠那得清如许，为有源头活水来。", "朱熹《观书有感》"],
    ["等闲识得东风面，万紫千红总是春。", "朱熹《春日》"],
    ["少年易老学难成，一寸光阴不可轻。", "朱熹《偶成》"],
    ["不识庐山真面目，只缘身在此山中。", "苏轼《题西林壁》"],
    ["竹外桃花三两枝，春江水暖鸭先知。", "苏轼《惠崇春江晚景》"],
    ["欲把西湖比西子，淡妆浓抹总相宜。", "苏轼《饮湖上初晴后雨》"],
    ["但愿人长久，千里共婵娟。", "苏轼《水调歌头》"],
    ["莫听穿林打叶声，何妨吟啸且徐行。", "苏轼《定风波》"],
    ["博观而约取，厚积而薄发。", "苏轼《稼说送张琥》"],
    ["山高月小，水落石出。", "苏轼《后赤壁赋》"],
    ["春风又绿江南岸，明月何时照我还。", "王安石《泊船瓜洲》"],
    ["不畏浮云遮望眼，自缘身在最高层。", "王安石《登飞来峰》"],
    ["墙角数枝梅，凌寒独自开。", "王安石《梅花》"],
    ["落红不是无情物，化作春泥更护花。", "龚自珍《己亥杂诗》"],
    ["千磨万击还坚劲，任尔东西南北风。", "郑燮《竹石》"],
    ["接天莲叶无穷碧，映日荷花别样红。", "杨万里《晓出净慈寺送林子方》"],
    ["小荷才露尖尖角，早有蜻蜓立上头。", "杨万里《小池》"],
    ["稻花香里说丰年，听取蛙声一片。", "辛弃疾《西江月》"],
    ["明月别枝惊鹊，清风半夜鸣蝉。", "辛弃疾《西江月》"],
    ["醉里挑灯看剑，梦回吹角连营。", "辛弃疾《破阵子》"],
    ["黑发不知勤学早，白首方悔读书迟。", "颜真卿《劝学》"],
    ["少壮不努力，老大徒伤悲。", "汉乐府《长歌行》"],
    ["春风得意马蹄疾，一日看尽长安花。", "孟郊《登科后》"],
    ["谁言寸草心，报得三春晖。", "孟郊《游子吟》"],
    ["天街小雨润如酥，草色遥看近却无。", "韩愈《早春呈水部张十八员外》"],
    ["业精于勤，荒于嬉。", "韩愈《进学解》"],
    ["学而不思则罔，思而不学则殆。", "《论语》"],
    ["三人行，必有我师焉。", "《论语》"],
    ["敏而好学，不耻下问。", "《论语》"],
    ["士不可以不弘毅，任重而道远。", "《论语》"],
    ["天行健，君子以自强不息。", "《周易》"],
    ["不积跬步，无以至千里。", "荀子《劝学》"],
    ["锲而不舍，金石可镂。", "荀子《劝学》"],
    ["宝剑锋从磨砺出，梅花香自苦寒来。", "《警世贤文》"],
    ["粉骨碎身浑不怕，要留清白在人间。", "于谦《石灰吟》"],
    ["江山代有才人出，各领风骚数百年。", "赵翼《论诗》"]
  ];
  function $(id) { return document.getElementById(id); }
  function node(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function icon(name) {
    var el = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    el.setAttribute("class", "icon"); el.setAttribute("aria-hidden", "true");
    use.setAttribute("href", "#i-" + name); el.appendChild(use);
    return el;
  }
  function readStored(key, fallback) {
    try { return localStorage.getItem(key) || fallback; } catch (error) { return fallback; }
  }
  function writeStored(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch (error) { /* 隐私模式写入失败不影响本次会话。 */ }
  }
  function parseDate(iso) {
    var parts = iso.split("-");
    return new Date(+parts[0], +parts[1] - 1, +parts[2]);
  }
  function dayNumber(date) {
    return Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86400000);
  }
  function weekdayIndex(date) {
    return (date.getDay() + 6) % 7;
  }
  function weekOf(date, startIso) {
    var delta = dayNumber(date) - dayNumber(parseDate(startIso));
    return delta < 0 ? 1 : Math.floor(delta / 7) + 1;
  }
  function weekDates(week, startIso) {
    if (!startIso) return null;
    var monday = parseDate(startIso);
    var out = [];
    for (var i = 0; i < 7; i++) {
      var d = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + (week - 1) * 7 + i);
      out.push((d.getMonth() + 1) + "/" + d.getDate());
    }
    return out;
  }
  function hueOf(name) {
    var hash = 0;
    for (var i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    return hash % 8;
  }
  function unitText(course) {
    if (!course.units || !course.units.length) return "—";
    var first = Math.min.apply(null, course.units) + 1;
    var last = Math.max.apply(null, course.units) + 1;
    return first === last ? String(first) : first + "–" + last;
  }
  function weekText(weeks) {
    if (!weeks || !weeks.length) return "";
    var sorted = weeks.slice().sort(function (a, b) { return a - b; });
    var output = [], start = sorted[0], previous = sorted[0];
    for (var i = 1; i <= sorted.length; i++) {
      var current = sorted[i];
      if (current === previous + 1) { previous = current; continue; }
      output.push(start === previous ? String(start) : start + "–" + previous);
      start = previous = current;
    }
    return output.join("，");
  }
  function coursesOn(day, week) {
    return state.data.courses.filter(function (course) {
      return course.day === day && course.weeks.indexOf(week) !== -1;
    }).sort(function (a, b) { return Math.min.apply(null, a.units) - Math.min.apply(null, b.units); });
  }
  function coursesInWeek(week) {
    return state.data.courses.filter(function (course) { return course.weeks.indexOf(week) !== -1; });
  }
  function meetingsOf(course, week) {
    return state.data.courses.filter(function (other) {
      return other.name === course.name && other.weeks.indexOf(week) !== -1;
    }).sort(function (a, b) { return a.day - b.day || Math.min.apply(null, a.units) - Math.min.apply(null, b.units); });
  }
  function totalWeeks() {
    var weeks = [];
    state.data.courses.forEach(function (course) { weeks = weeks.concat(course.weeks); });
    return weeks.length ? Math.max.apply(null, weeks) : 17;
  }
  function boundedWeek(week, max) {
    return Math.max(1, Math.min(max, week));
  }
  function nextCourse(day, week) {
    for (var offset = 1; offset <= 7; offset++) {
      var target = day + offset;
      var targetWeek = week + Math.floor(target / 7);
      var courses = coursesOn(target % 7, targetWeek);
      if (courses.length) return {course: courses[0], offset: offset, week: targetWeek};
    }
    return null;
  }
  function validPeriods(periods, count) {
    return Array.isArray(periods) && periods.length >= count && periods.every(function (p) {
      return Array.isArray(p) && p.length === 2 && p.every(function (t) {
        return typeof t === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(t);
      });
    });
  }
  function todayDate() {
    if (!state.todayIso) return new Date();
    // 沿用服务端日期；回到前台时补上页面打开后经过的日历天数。
    var elapsed = dayNumber(new Date()) - state.localDay;
    var date = parseDate(state.todayIso);
    date.setDate(date.getDate() + elapsed);
    return date;
  }
  function effectiveWeek() {
    if (state.currentWeek === null) return null;
    var elapsed = dayNumber(todayDate()) - dayNumber(state.anchorDate);
    return state.currentWeek + Math.floor((weekdayIndex(state.anchorDate) + elapsed) / 7);
  }
  function request(path, options) {
    return fetch(path, options).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (body) {
        return {status: response.status, body: body};
      });
    });
  }
  function requestSnapshot() {
    var headers = {};
    if (state.token) headers.Authorization = "Bearer " + state.token;
    return request("/api/timetable", {headers: headers, cache: "no-store"});
  }
  function setPage(mode) {
    ["boot", "gate", "fatal", "app"].forEach(function (id) { $(id).hidden = id !== mode; });
    $("boot").setAttribute("aria-busy", mode === "boot" ? "true" : "false");
  }
  function gateError(message, warning) {
    $("gate-error").textContent = message || "";
    $("gate-error").hidden = !message;
    $("gate-error").classList.toggle("warning", !!warning);
    $("gate-input").setAttribute("aria-invalid", message && !warning ? "true" : "false");
  }
  function showGate(message, warning) {
    setPage("gate");
    $("gate-input").value = "";
    gateError(message, warning);
    updateLock();
    if (!$("gate-input").disabled) $("gate-input").focus();
  }
  function updateLock() {
    var seconds = Math.max(0, Math.ceil((state.lockUntil - Date.now()) / 1000));
    $("gate-input").disabled = seconds > 0;
    $("gate-button").disabled = seconds > 0;
    $("gate-button").textContent = seconds ? "请 " + seconds + " 秒后再试" : "进入课表";
    $("gate-button").setAttribute("aria-busy", "false");
    if (!seconds && state.lockTimer) {
      clearInterval(state.lockTimer); state.lockTimer = null; gateError("");
    }
  }
  function lockGate(message) {
    var match = /(\d+)\s*秒/.exec(message || "");
    state.lockUntil = Date.now() + (match ? +match[1] : 300) * 1000;
    if (state.lockTimer) clearInterval(state.lockTimer);
    showGate(message || "口令错误次数过多，请稍后再试");
    state.lockTimer = setInterval(updateLock, 1000);
  }
  function showFatal(result) {
    setPage("fatal");
    $("fatal-text").textContent = result ? result.body.error || "服务器返回了 " + result.status : "暂时连不上服务器，请检查网络后重试。";
    $("fatal-hint").textContent = result && result.body.hint || "";
    $("fatal-hint").hidden = !$("fatal-hint").textContent;
  }
  function handleSnapshot(result) {
    if (result.status === 200) { start(result.body); return; }
    if (result.status === 401) {
      var expired = !!state.token;
      state.token = null; writeStored(TOKEN_KEY, null);
      showGate(expired ? "口令已更新或登录已过期，请重新输入" : "", expired);
    } else showFatal(result);
  }
  function showPageError(error) {
    console.error(error);
    showFatal({body: {error: "页面出错了，请刷新"}});
  }
  function receiveSnapshot(result) {
    try { handleSnapshot(result); } catch (error) { showPageError(error); }
  }
  function boot() {
    state.data = null; setPage("boot");
    state.token = readStored(TOKEN_KEY, state.token);
    return requestSnapshot().then(receiveSnapshot, function () { showFatal(null); });
  }
  function start(data) {
    state.data = data;
    state.data.courses = data.courses || [];
    state.data.unit_count = data.unit_count || 11;
    state.currentWeek = typeof data.current_week === "number" ? data.current_week :
      (data.semester_start ? weekOf(data.server_today ? parseDate(data.server_today) : new Date(), data.semester_start) : null);
    state.todayIso = data.server_today || "";
    state.localDay = dayNumber(new Date());
    state.anchorDate = todayDate();
    state.week = boundedWeek(state.currentWeek || 1, totalWeeks());
    state.renderedWeek = state.currentWeek;
    state.view = readStored(VIEW_KEY, "today") === "week" ? "week" : "today";
    var poem = POEMS[Math.floor(Math.random() * POEMS.length)];
    $("poem").textContent = "今日一句：" + poem[0] + " —— " + poem[1];
    setPage("app"); render();
  }
  function courseButton(course, cls, week) {
    var button = node("button", cls);
    button.type = "button";
    button.setAttribute("data-tone", String(hueOf(course.name)));
    button.setAttribute("aria-label", (cls === "next-course" ? "下一次上课，" : "") + "周" + WEEKDAYS[course.day] + " 第" + unitText(course) + "节 " + course.name + "，" + (course.room || "教室待定"));
    button.addEventListener("click", function () { openSheet(course, week, button); });
    return button;
  }
  function renderToday() {
    var date = todayDate(), day = weekdayIndex(date), week = effectiveWeek();
    var courses = week !== null ? coursesOn(day, week) : [];
    $("today-date").textContent = (date.getMonth() + 1) + "月" + date.getDate() + "日 星期" + WEEKDAYS[day] + (week !== null ? " · 第 " + week + " 周" : "");
    $("today-title").textContent = week === null ? "本学期课表已准备好" : courses.length ? "今天 " + courses.length + " 门课" : day >= 5 ? "周末，好好休息" : "今天没有课";
    var list = $("today-list"); list.textContent = "";
    if (week === null) {
      list.appendChild(node("p", "notice", "尚未配置本学期第一周日期，暂时无法按教学周过滤。")); return;
    }
    if (!courses.length) {
      var empty = node("div", "empty-card");
      empty.appendChild(node("p", "empty-title", !coursesInWeek(week).length ? "第 " + week + " 周整周无常规课，多为集中实践周或假期" : day >= 5 ? "周末没有安排课程" : "这一天没有排课"));
      var next = nextCourse(day, week);
      var block = next ? courseButton(next.course, "next-course", next.week) : node("div", "next-course");
      block.appendChild(node("span", "next-label", "下一次上课"));
      block.appendChild(node("span", null, next ? (next.offset === 1 ? "明天" : "周" + WEEKDAYS[next.course.day]) + " · 第 " + unitText(next.course) + " 节 · " + next.course.name + " · " + (next.course.room || "教室待定") : "接下来一周无课，集中实践周，不上常规课"));
      empty.appendChild(block); list.appendChild(empty); return;
    }
    courses.forEach(function (course) {
      var card = courseButton(course, "course", week);
      var time = node("span", "course-time");
      time.appendChild(node("strong", null, unitText(course) + "节"));
      if (validPeriods(state.data.periods, state.data.unit_count)) time.appendChild(node("span", null, state.data.periods[Math.min.apply(null, course.units)][0]));
      var body = node("span", "course-body");
      body.appendChild(node("span", "course-name", course.name));
      var room = node("span", "course-room"); room.appendChild(icon("pin")); room.appendChild(node("span", null, course.room || "教室待定")); body.appendChild(room);
      body.appendChild(node("span", "course-teacher", course.teachers || "教师待定"));
      card.appendChild(time); card.appendChild(body); list.appendChild(card);
    });
  }
  function gridMinWidth(dayCount) {
    return 24 + dayCount * 56 + (dayCount + 1) * 2;
  }
  function renderWeek() {
    var week = state.week, current = effectiveWeek();
    var dates = weekDates(week, state.data.semester_start);
    $("week-prev").disabled = week <= 1;
    $("week-next").disabled = week >= totalWeeks();
    $("week-label").textContent = "";
    $("week-label").appendChild(node("span", "week-number", "第 " + week + " 周"));
    if (dates) $("week-label").appendChild(node("span", "week-range", " " + dates[0] + "–" + dates[6]));
    if (week === current) $("week-label").appendChild(node("span", "week-badge", "本周"));
    $("week-reset").hidden = week === current || current === null;
    $("week-label").disabled = current === null;
    var courses = coursesInWeek(week), days = {}, rooms = Object.create(null), loads = [0,0,0,0,0,0,0];
    courses.forEach(function (c) { days[c.day] = true; loads[c.day] += c.units.length; if (c.room) rooms[c.room] = (rooms[c.room] || 0) + 1; });
    var common = Object.keys(rooms).sort(function (a,b) { return rooms[b] - rooms[a]; })[0] || "—";
    $("week-summary").textContent = courses.length ? courses.length + " 次课 · " + Object.keys(days).length + " 天 · 常在 " + common : "这周没有常规课";
    var dayCount = Math.max(5, state.data.courses.reduce(function (max, c) { return Math.max(max, c.day + 1); }, 5));
    var table = $("grid"); table.textContent = "";
    table.classList.toggle("has-weekend", dayCount > 5);
    // 节次列也占一个间隙，补足 table 两侧的 border-spacing。
    table.style.minWidth = dayCount > 5 ? (gridMinWidth(dayCount) + 2) + "px" : "";
    table.appendChild(node("caption", "sr-only", "第 " + week + " 周课表"));
    var colgroup = node("colgroup"); colgroup.appendChild(node("col", "unit-col"));
    for (var c = 0; c < dayCount; c++) colgroup.appendChild(node("col"));
    table.appendChild(colgroup);
    var head = node("thead"), header = node("tr"), corner = node("th", null, "节");
    corner.setAttribute("scope", "col"); header.appendChild(corner);
    var today = weekdayIndex(todayDate());
    for (var day = 0; day < dayCount; day++) {
      var th = node("th", week === current && day === today ? "is-today" : ""); th.setAttribute("scope", "col");
      th.appendChild(node("span", null, "周" + WEEKDAYS[day]));
      if (dates) th.appendChild(node("span", "grid-date", dates[day]));
      th.appendChild(node("span", "grid-load", loads[day] ? loads[day] + "节" : "—")); header.appendChild(th);
    }
    head.appendChild(header); table.appendChild(head);
    var matrix = [];
    for (day = 0; day < dayCount; day++) matrix[day] = [];
    courses.forEach(function (course) { course.units.forEach(function (unit) { matrix[course.day][unit] = course; }); });
    var tbody = node("tbody");
    for (var unit = 0; unit < state.data.unit_count; unit++) {
      var tr = node("tr", [1,3,5,7].indexOf(unit) !== -1 ? "unit-divider" : "");
      var rowhead = node("th", null, String(unit + 1)); rowhead.setAttribute("scope", "row");
      if (validPeriods(state.data.periods, state.data.unit_count)) {
        var label = "第" + (unit + 1) + "节 " + state.data.periods[unit].join("–"); rowhead.title = label; rowhead.setAttribute("aria-label", label);
      }
      tr.appendChild(rowhead);
      for (day = 0; day < dayCount; day++) {
        var course = matrix[day][unit];
        if (course && unit > 0 && matrix[day][unit - 1] === course) continue;
        var td = node("td", week === current && day === today ? "is-today" : "");
        if (course) {
          var span = 1;
          while (unit + span < state.data.unit_count && matrix[day][unit + span] === course) span++;
          td.rowSpan = span;
          var block = courseButton(course, "grid-course" + (span === 1 ? " single" : ""), week);
          block.style.height = "calc(var(--row-h) * " + span + " + " + ((span - 1) * 2) + "px)";
          block.appendChild(node("span", "grid-name", course.name)); block.appendChild(node("span", "grid-room", course.room || "教室待定")); td.appendChild(block);
        }
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody); renderGridHint();
  }
  function renderGridHint() {
    var box = $("grid-scroll");
    $("grid-hint").hidden = !$("grid").classList.contains("has-weekend") || box.scrollWidth <= box.clientWidth + 1;
  }
  function renderFooter() {
    var footer = $("footer"); footer.textContent = "";
    var stamp = state.data.updated_ts;
    var updated = stamp ? new Date(stamp * 1000) : null;
    var stale = updated && dayNumber(updated) !== dayNumber(todayDate());
    footer.appendChild(node("span", stale ? "warning" : "", "数据更新于 " + (state.data.updated_at || "未知") + (stale ? "（不是今天）" : "")));
    var week = effectiveWeek(); footer.appendChild(node("span", null, week !== null ? "本学期第 " + week + " 周" : "未配置开学日期"));
    if (state.todayIso && dayNumber(new Date()) !== dayNumber(todayDate())) {
      var date = todayDate();
      var iso = date.getFullYear() + "-" + ("0" + (date.getMonth() + 1)).slice(-2) + "-" + ("0" + date.getDate()).slice(-2);
      footer.appendChild(node("span", "warning", "本机日期与服务器不一致（服务器 " + iso + "）"));
    }
    footer.appendChild(node("span", "footer-update", "每日 07:00 自动更新"));
  }
  function renderTabs() {
    var desktop = window.matchMedia("(min-width: 1024px)").matches;
    $("view-tabs").hidden = desktop; $("bar-update").hidden = !desktop;
    ["today", "week"].forEach(function (view) {
      var selected = state.view === view;
      $("tab-" + view).setAttribute("aria-selected", selected ? "true" : "false");
      $("tab-" + view).tabIndex = selected ? 0 : -1;
      $("pane-" + view).hidden = !desktop && !selected;
      $("pane-" + view).setAttribute("role", desktop ? "region" : "tabpanel");
    });
    renderGridHint();
  }
  function render() {
    renderToday(); renderWeek(); renderFooter(); renderTabs();
  }
  function changeView(view, focus) {
    state.view = view; writeStored(VIEW_KEY, view); renderTabs();
    if (focus) $("tab-" + view).focus();
  }
  function changeWeek(week) {
    state.week = boundedWeek(week, totalWeeks()); renderWeek();
  }
  function resetWeek() {
    if (effectiveWeek() !== null) changeWeek(effectiveWeek());
  }
  function openSheet(course, week, trigger) {
    clearTimeout(state.closing); state.trigger = trigger;
    var sheet = $("sheet"); sheet.classList.remove("closing");
    $("sheet-meta").textContent = "周" + WEEKDAYS[course.day] + " · 第 " + unitText(course) + " 节";
    $("sheet-name").textContent = course.name;
    $("sheet-dialog").setAttribute("data-tone", String(hueOf(course.name)));
    var facts = $("sheet-facts"); facts.textContent = "";
    [["pin", "教室", course.room || "待定"], ["person", "教师", course.teachers || "—"], ["calendar", "周次", "第 " + weekText(course.weeks) + " 周（共 " + course.weeks.length + " 周）"]].forEach(function (fact) {
      var row = node("div", "fact"), term = node("dt"); term.appendChild(icon(fact[0])); term.appendChild(node("span", null, fact[1])); row.appendChild(term); row.appendChild(node("dd", null, fact[2])); facts.appendChild(row);
    });
    var meetings = meetingsOf(course, week), list = $("meeting-list"); list.textContent = "";
    $("sheet-meetings").hidden = !meetings.length;
    meetings.forEach(function (meeting) {
      var row = node("div", "meeting" + (meeting === course ? " selected" : ""));
      row.setAttribute("data-tone", String(hueOf(meeting.name)));
      row.appendChild(node("span", null, "周" + WEEKDAYS[meeting.day])); row.appendChild(node("span", null, "第 " + unitText(meeting) + " 节")); row.appendChild(node("span", null, meeting.room || "待定")); list.appendChild(row);
    });
    sheet.hidden = false; document.body.style.overflow = "hidden";
    $("sheet-close").focus();
    $("app").setAttribute("aria-hidden", "true");
    // inert 在旧微信中可能不可用，另有 Tab 循环和 focusin 兜底。
    $("app").inert = true;
  }
  function closeSheet() {
    if ($("sheet").hidden || $("sheet").classList.contains("closing")) return;
    $("sheet").classList.add("closing");
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    state.closing = setTimeout(function () {
      $("sheet").hidden = true; $("sheet").classList.remove("closing");
      document.body.style.overflow = ""; $("app").inert = false; $("app").removeAttribute("aria-hidden");
      if (state.trigger && document.documentElement.contains(state.trigger)) state.trigger.focus();
    }, reduced ? 0 : 160);
  }
  function bindEvents() {
    $("gate-form").addEventListener("submit", function (event) {
      event.preventDefault(); if (Date.now() < state.lockUntil) return;
      var password = $("gate-input").value; if (!password) return;
      $("gate-button").disabled = true; $("gate-input").disabled = true;
      $("gate-button").textContent = "正在验证…"; $("gate-button").setAttribute("aria-busy", "true");
      request("/api/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: password})}).then(function (result) {
        if (result.status === 429 || result.body.code === "locked") { lockGate(result.body.error); return; }
        if (result.status !== 200) { showGate(result.body.error || "服务器返回了 " + result.status); return; }
        state.token = result.body.token || null; writeStored(TOKEN_KEY, state.token);
        return requestSnapshot().then(receiveSnapshot, function () { showGate("网络连接失败，请检查网络后重试"); });
      }, function () { showGate("网络连接失败，请检查网络后重试"); }).catch(showPageError);
    });
    $("fatal-retry").addEventListener("click", boot);
    ["today", "week"].forEach(function (view) {
      $("tab-" + view).addEventListener("click", function () { changeView(view); });
      $("tab-" + view).addEventListener("keydown", function (event) {
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); event.stopPropagation(); changeView(view === "today" ? "week" : "today", true); }
      });
    });
    $("week-prev").addEventListener("click", function () { changeWeek(state.week - 1); });
    $("week-next").addEventListener("click", function () { changeWeek(state.week + 1); });
    $("week-label").addEventListener("click", resetWeek); $("week-reset").addEventListener("click", resetWeek);
    $("sheet-close").addEventListener("click", closeSheet);
    $("sheet").addEventListener("click", function (event) { if (event.target.hasAttribute("data-close")) closeSheet(); });
    document.addEventListener("focusin", function (event) {
      if (!$("sheet").hidden && !$("sheet-dialog").contains(event.target)) $("sheet-close").focus();
    });
    document.addEventListener("keydown", function (event) {
      if (!$("sheet").hidden) {
        if (event.key === "Escape") { event.preventDefault(); closeSheet(); }
        if (event.key === "Tab") { event.preventDefault(); $("sheet-close").focus(); }
        return;
      }
      if (!state.data || $("pane-week").hidden || /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName) || event.target.isContentEditable) return;
      if ($("grid-scroll").contains(event.target)) return;
      if (event.key === "ArrowLeft") { event.preventDefault(); changeWeek(state.week - 1); }
      if (event.key === "ArrowRight") { event.preventDefault(); changeWeek(state.week + 1); }
      if (event.key === "Home") { event.preventDefault(); resetWeek(); }
    });
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && state.data) {
        var old = state.renderedWeek; if (state.week === old) state.week = boundedWeek(effectiveWeek(), totalWeeks());
        render(); state.renderedWeek = effectiveWeek();
      }
    });
    window.addEventListener("resize", function () { if (state.data) renderTabs(); });
  }
  bindEvents();
  boot();
})();

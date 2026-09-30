/* 课表前端 —— 毛玻璃版
 *
 * 结构：
 * 1. api       负责口令和快照请求
 * 2. poem      页面顶端的随机诗句（本地数据，不联网）
 * 3. calendar  负责日期、周次和课程过滤
 * 4. render    负责把数据写入 DOM
 * 5. events    负责页面交互
 *
 * 配色取自本机的 dsh-whale-widget 鲸鱼挂件：
 *   深靛蓝 #203170 / 钢蓝 #536ba9 / 淡长春花蓝 #9fb0d9。
 *
 * 不使用 innerHTML：教务系统返回的课程名、教师、教室都只通过
 * textContent 写入，避免把外部字符串当成 HTML 执行。
 */
(function () {
  "use strict";

  var TOKEN_KEY = "snut.token";
  var WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

  /* 随机诗句：全部是公版古诗文，纯本地数组，不请求任何外部接口。
   * 格式与页面上的排布一致：上句，下句。 + 出处。 */
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

  var state = {
    data: null,
    week: 1,
    currentWeek: null,
    view: "today"
  };

  function $(id) { return document.getElementById(id); }

  function node(tag, className, text) {
    var item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  }

  /* ------------------------------------------------------------------
   * 1. API
   * ------------------------------------------------------------------ */

  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY) || ""; }
    catch (error) { return ""; }
  }

  function saveToken(token) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch (error) {
      // 隐私模式禁止 localStorage 时，本次会话仍然可以继续使用。
    }
  }

  function requestSnapshot(token) {
    var headers = {};
    if (token) headers.Authorization = "Bearer " + token;
    return fetch("/api/timetable", { headers: headers, cache: "no-store" })
      .then(function (response) {
        return response.json().catch(function () { return {}; })
          .then(function (body) {
            return { status: response.status, body: body };
          });
      });
  }

  function login(password) {
    return fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: password })
    }).then(function (response) {
      return response.json().catch(function () { return {}; })
        .then(function (body) {
          return { status: response.status, body: body };
        });
    });
  }

  /* ------------------------------------------------------------------
   * 2. 随机诗句
   * ------------------------------------------------------------------ */

  function pickPoem() {
    var item = POEMS[Math.floor(Math.random() * POEMS.length)];
    $("poem-text").textContent = item[0];
    $("poem-from").textContent = "—— " + item[1];
  }

  /* ------------------------------------------------------------------
   * 3. 日期与周次
   * ------------------------------------------------------------------ */

  function parseDate(iso) {
    var parts = iso.split("-");
    return new Date(+parts[0], +parts[1] - 1, +parts[2]);
  }

  function dayNumber(date) {
    return Math.floor(Date.UTC(
      date.getFullYear(), date.getMonth(), date.getDate()
    ) / 86400000);
  }

  function weekdayIndex(date) {
    return (date.getDay() + 6) % 7;
  }

  function formatDate(date) {
    return (date.getFullYear() + " 年 " + (date.getMonth() + 1) +
      " 月 " + date.getDate() + " 日　星期" + WEEKDAYS[weekdayIndex(date)]);
  }

  function weekOf(date, startIso) {
    var delta = dayNumber(date) - dayNumber(parseDate(startIso));
    return delta < 0 ? 1 : Math.floor(delta / 7) + 1;
  }

  /* 课程配色：色相锁在青蓝→紫之间（186–271），保持鲸鱼配色的整体调性。 */
  function toneOf(name) {
    var hash = 0;
    for (var i = 0; i < name.length; i++) {
      hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    }
    var hue = 186 + (hash % 86);
    return {
      line: "hsl(" + hue + " 50% 45%)",
      // 带一点透明度，让课程块也能透出背后的玻璃底色
      soft: "hsl(" + hue + " 64% 96% / .8)",
      text: "hsl(" + hue + " 44% 30%)"
    };
  }

  function unitText(course) {
    if (!course.units || !course.units.length) return "—";
    var first = Math.min.apply(null, course.units) + 1;
    var last = Math.max.apply(null, course.units) + 1;
    return first === last ? String(first) : first + "—" + last;
  }

  function weekText(weeks) {
    if (!weeks || !weeks.length) return "";
    var sorted = weeks.slice().sort(function (a, b) { return a - b; });
    var output = [];
    var start = sorted[0];
    var previous = sorted[0];

    for (var i = 1; i <= sorted.length; i++) {
      var current = sorted[i];
      if (current === previous + 1) {
        previous = current;
        continue;
      }
      output.push(start === previous ? String(start) : start + "—" + previous);
      start = previous = current;
    }
    return output.join("，");
  }

  function periodText(units) {
    var periods = state.data.periods;
    if (!periods || !periods.length || !units || !units.length) return "";
    var first = periods[Math.min.apply(null, units)];
    var last = periods[Math.max.apply(null, units)];
    if (!first || !last || !first[0] || !last[1]) return "";
    return "　" + first[0] + "—" + last[1];
  }

  function coursesOn(day, week) {
    return state.data.courses.filter(function (course) {
      return course.day === day && course.weeks.indexOf(week) !== -1;
    }).sort(function (a, b) {
      return Math.min.apply(null, a.units) - Math.min.apply(null, b.units);
    });
  }

  function coursesInWeek(week) {
    return state.data.courses.filter(function (course) {
      return course.weeks.indexOf(week) !== -1;
    });
  }

  /* ------------------------------------------------------------------
   * 4. 页面状态与渲染
   * ------------------------------------------------------------------ */

  function setPage(mode) {
    $("boot").hidden = true;
    $("gate").hidden = true;
    $("fatal").hidden = true;
    $("app").hidden = mode !== "app";
  }

  function showGate(message) {
    $("boot").hidden = true;
    $("fatal").hidden = true;
    $("app").hidden = true;
    $("gate").hidden = false;
    $("gate-input").value = "";
    $("gate-input").disabled = false;
    $("gate-button").disabled = false;
    $("gate-error").textContent = message || "";
    $("gate-error").hidden = !message;
    $("gate-input").focus();
  }

  function showFatal(message) {
    $("boot").hidden = true;
    $("gate").hidden = true;
    $("app").hidden = true;
    $("fatal").hidden = false;
    $("fatal-text").textContent = message;
  }

  function start(data) {
    state.data = data || {};
    state.data.courses = state.data.courses || [];
    state.data.unit_count = state.data.unit_count || 11;
    state.currentWeek = data.current_week ||
      (data.semester_start ? weekOf(new Date(), data.semester_start) : null);
    state.week = state.currentWeek || 1;
    setPage("app");
    render();
  }

  function boot() {
    pickPoem();
    requestSnapshot(getToken()).then(function (result) {
      if (result.status === 200) start(result.body);
      else if (result.status === 401) showGate("");
      else showFatal(result.body.error || "服务器返回了 " + result.status);
    }).catch(function () {
      showFatal("暂时连不上服务器，请检查网络后重试。");
    });
  }

  function render() {
    renderHero();
    renderTabs();
    renderToday();
    renderStats();
    renderWeek();
    renderFooter();
  }

  function renderHero() {
    var today = new Date();
    var count = state.currentWeek ? coursesOn(weekdayIndex(today), state.currentWeek).length : 0;
    var week = state.currentWeek || state.week;
    $("hero-eyebrow").textContent =
      WEEKDAYS[weekdayIndex(today)].toUpperCase() + " · " +
      (today.getMonth() + 1) + " 月 " + today.getDate() + " 日";
    $("hero-title").textContent = state.currentWeek
      ? "今天有 " + count + " 门课，安排得刚刚好。"
      : "本学期课表已准备好。";
    $("hero-date").textContent = formatDate(today) + "　·　第 " + week + " 周";
    $("hero-week").textContent = "第 " + week + " 周";
    $("week-progress").style.width = Math.min(100, Math.max(6, week / 17 * 100)) + "%";
    $("week-progress-label").textContent = "本学期第 " + week + " / 17 周";
    $("week-label").textContent = "第 " + state.week + " 周";
  }

  function renderTabs() {
    document.querySelectorAll(".view-tab").forEach(function (tab) {
      var active = tab.getAttribute("data-view") === state.view;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    $("pane-today").hidden = state.view !== "today";
    $("pane-week").hidden = state.view !== "week";
  }

  function renderToday() {
    var today = new Date();
    var day = weekdayIndex(today);
    var courses = state.currentWeek ? coursesOn(day, state.currentWeek) : [];
    $("today-heading").textContent = "今天 · 星期" + WEEKDAYS[day];
    $("today-count").textContent = courses.length + " 门课程";

    var list = $("today-list");
    list.textContent = "";

    if (!state.currentWeek) {
      list.appendChild(node("div", "notice",
        "尚未配置本学期第一周日期，暂时无法按教学周过滤。"));
      return;
    }

    if (!courses.length) {
      var empty = node("div", "empty-demo");
      empty.appendChild(node("b", null, day >= 5 ? "周末，好好休息" : "今天没有课"));
      empty.appendChild(node("span", null, "当前日期没有安排课程"));
      list.appendChild(empty);
      return;
    }

    courses.forEach(function (course) {
      list.appendChild(courseCard(course));
    });
  }

  function courseCard(course) {
    var card = node("button", "course");
    var tone = toneOf(course.name);
    card.type = "button";
    card.style.setProperty("--tone", tone.line);
    card.style.setProperty("--tone-soft", tone.soft);
    var time = node("div", "course-time");
    time.appendChild(node("strong", null, unitText(course)));
    time.appendChild(node("span", null, periodText(course.units).trim()
      || "第 " + unitText(course) + " 节"));
    var body = node("div");
    body.appendChild(node("h4", null, course.name));
    body.appendChild(node("p", null, (course.room || "教室待定") + "　·　" + (course.teachers || "教师待定")));
    card.appendChild(time);
    card.appendChild(body);
    card.addEventListener("click", function () { openSheet(course); });
    return card;
  }

  function renderStats() {
    var courses = coursesInWeek(state.week);
    var days = {};
    var rooms = {};
    courses.forEach(function (course) {
      days[course.day] = true;
      if (course.room) rooms[course.room] = (rooms[course.room] || 0) + 1;
    });
    var commonRoom = Object.keys(rooms).sort(function (a, b) {
      return rooms[b] - rooms[a];
    })[0] || "—";

    var values = [
      [courses.length, "本周课程"],
      [Object.keys(days).length, "上课日"],
      [state.data.unit_count, "节次总数"],
      [commonRoom, "常用教室"]
    ];
    var stats = $("stats");
    stats.textContent = "";
    values.forEach(function (value, index) {
      // 最后一项是教室名，长度不定，给它整行宽度免得折成两行
      var item = node("div", index === values.length - 1 ? "stat stat-wide" : "stat");
      item.appendChild(node("b", null, String(value[0])));
      item.appendChild(node("span", null, value[1]));
      stats.appendChild(item);
    });
  }

  function renderWeek() {
    $("grid-heading").textContent = "第 " + state.week + " 周课表";
    var table = $("grid");
    table.textContent = "";
    var unitCount = state.data.unit_count;
    var today = new Date();
    var todayDay = weekdayIndex(today);
    var markToday = state.week === state.currentWeek;

    var cells = {};
    var day;
    for (day = 0; day < 7; day++) {
      cells[day] = [];
      for (var unit = 0; unit < unitCount; unit++) cells[day][unit] = null;
    }
    state.data.courses.forEach(function (course) {
      if (!cells[course.day] || course.weeks.indexOf(state.week) === -1) return;
      course.units.forEach(function (unit) {
        if (unit >= 0 && unit < unitCount) cells[course.day][unit] = course;
      });
    });

    var head = node("thead");
    var headRow = node("tr");
    headRow.appendChild(node("th", "unit", ""));
    for (day = 0; day < 7; day++) {
      var mark = (day === todayDay && markToday) ? "today" : "";
      if (day >= 5) mark = (mark + " weekend").trim();
      headRow.appendChild(node("th", mark, "周" + WEEKDAYS[day]));
    }
    head.appendChild(headRow);
    table.appendChild(head);

    var body = node("tbody");
    var skip = {};
    for (var row = 0; row < unitCount; row++) {
      var tr = node("tr");
      tr.appendChild(node("th", "unit", String(row + 1)));
      for (day = 0; day < 7; day++) {
        if (skip[day] > 0) {
          skip[day]--;
          continue;
        }
        var cell = node("td");
        var course = cells[day][row];
        if (course) {
          var span = 1;
          while (row + span < unitCount && cells[day][row + span] === course) span++;
          if (span > 1) {
            cell.rowSpan = span;
            skip[day] = span - 1;
          }
          cell.appendChild(courseBlock(course));
        }
        tr.appendChild(cell);
      }
      body.appendChild(tr);
    }
    table.appendChild(body);
  }

  function courseBlock(course) {
    var block = node("button", "course-block");
    var tone = toneOf(course.name);
    block.type = "button";
    block.style.setProperty("--tone", tone.line);
    block.style.setProperty("--tone-soft", tone.soft);
    block.style.setProperty("--tone-text", tone.text);
    block.appendChild(node("span", null, course.name));
    block.appendChild(node("small", null, course.room || "教室待定"));
    block.addEventListener("click", function () { openSheet(course); });
    return block;
  }

  function renderFooter() {
    var updated = $("updated");
    updated.textContent = "数据更新于 " + (state.data.updated_at || "未知");
    updated.className = "";
    if (state.data.updated_ts) {
      var stamp = new Date(state.data.updated_ts * 1000);
      if (dayNumber(stamp) < dayNumber(new Date())) {
        updated.textContent += "（不是今天）";
        updated.className = "stale";
      }
    }
    $("semester").textContent = state.currentWeek
      ? "本学期第 " + state.currentWeek + " 周"
      : "未配置开学日期";
  }

  function openSheet(course) {
    $("sheet-name").textContent = course.name;
    $("sheet-when").textContent =
      "星期" + WEEKDAYS[course.day] + " · 第 " + unitText(course) +
      " 节" + periodText(course.units);
    $("sheet-room").textContent = course.room || "待定";
    $("sheet-teacher").textContent = course.teachers || "—";
    $("sheet-weeks").textContent = course.weeks.length
      ? "第 " + weekText(course.weeks) + " 周（共 " + course.weeks.length + " 周）"
      : "—";
    $("sheet").hidden = false;
  }

  function closeSheet() { $("sheet").hidden = true; }

  function switchWeek(delta) {
    state.week = Math.max(1, state.week + delta);
    render();
  }

  /* ------------------------------------------------------------------
   * 5. 交互
   * ------------------------------------------------------------------ */

  function bindEvents() {
    document.querySelectorAll(".view-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        state.view = tab.getAttribute("data-view");
        renderTabs();
      });
    });
    $("prev-week").addEventListener("click", function () { switchWeek(-1); });
    $("next-week").addEventListener("click", function () { switchWeek(1); });
    $("week-label").addEventListener("click", function () {
      if (state.currentWeek) {
        state.week = state.currentWeek;
        render();
      }
    });
    $("gate-form").addEventListener("submit", function (event) {
      event.preventDefault();
      var password = $("gate-input").value;
      if (!password) return;
      $("gate-button").disabled = true;
      login(password).then(function (result) {
        if (result.status !== 200) {
          showGate(result.body.error || "口令不正确");
          return;
        }
        saveToken(result.body.token);
        return requestSnapshot(result.body.token).then(function (next) {
          if (next.status === 200) start(next.body);
          else showGate(next.body.error || "口令验证失败");
        });
      }).catch(function () { showGate("网络连接失败"); });
    });
    $("fatal-retry").addEventListener("click", boot);
    $("sheet").addEventListener("click", function (event) {
      if (event.target.hasAttribute("data-close")) closeSheet();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeSheet();
    });
  }

  bindEvents();
  boot();
})();

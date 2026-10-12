/* 课表前端 —— 第四版
 *
 * 结构（与上一版一致，方便对照）：
 *   1. api       口令与快照请求
 *   2. poem      页面顶端的随机诗句（本地数据，不联网）
 *   3. calendar  日期、周次、课程过滤
 *   4. render    把数据写进 DOM
 *   5. events    交互
 *
 * 这一版在功能上新增了四件事，都是「把已有数据讲得更清楚」：
 *   · 首屏的「下一节课」——原来那句「今天有 N 门课，安排得刚刚好。」
 *     占了最大字号却没说上什么课；现在直接把下一节或明天的课摆出来。
 *   · 正在上的那节课会高亮（按节次时间段推断），扫一眼就知道现在到哪儿了。
 *   · 侧栏多了一周七天的小柱图，比四个孤立数字更快看出松紧。
 *   · 课程详情会列出这门课一周里的每一次排课——原来只显示被点的那一条，
 *     同学看不到「这门课一周上几次、在哪几天」。
 *
 * 安全约定（沿用）：不使用 innerHTML。教务系统返回的课程名、教师、教室
 * 一律经 textContent 写入，外部字符串永远不会当成 HTML 执行。
 *
 * 配色约定：课程色用 oklch() 生成，锁死感知亮度与彩度，只让色相随课程名变化。
 * 这是为了避开 HSL 的坑——它的 L 不是感知亮度，会让黄绿色系的课看起来比
 * 蓝紫色的课亮一档，同一张表里轻重不一。CSS 里的变量名与 style.css 对齐。
 */
(function () {
  "use strict";

  var TOKEN_KEY = "snut.token";
  var VIEW_KEY = "snut.view";
  var WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

  /* 这里曾经写死过一份「第 N 节 = 几点到几点」的作息表，用来把节次翻译成
   * 钟点、并推断「现在正在上哪一节」。已删——教务系统没有这个接口
   * （periods 字段实测为 null），那份时间是猜的，猜错就会让整站显示错误的
   * 上课时间。课表本身只认节次，而节次是教务系统给的，不会错。 */

  /* 随机诗句：公版古诗文，纯本地数组，不请求任何外部接口。 */
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
    view: "today",
    todayIso: ""
  };

  function $(id) { return document.getElementById(id); }

  function node(tag, className, text) {
    var item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  }

  /* 原先这里有个 icon(name) 工具，用来往 JS 建的按钮里塞内联 SVG
   * （<use> 指向 index.html 顶部的 symbol）。唯一的使用者是课程卡上的
   * 「正在上课」时钟标记，它随作息表一起删了，这个函数也就没有了调用者。
   * 将来要再塞图标，照搬 detail-list 里的写法即可（那份是写在 HTML 里的）。 */

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

  function readStored(key, fallback) {
    try { return localStorage.getItem(key) || fallback; }
    catch (error) { return fallback; }
  }

  function writeStored(key, value) {
    try { localStorage.setItem(key, value); }
    catch (error) { /* 存不下就算了，不影响使用 */ }
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
    var text = $("poem-text");
    // 每个字同时从上下交替飞入，最终排成一行；保留标点和完整读屏文本。
    var characters = Array.from(item[0]);
    text.textContent = "";
    text.style.setProperty("--poem-length", String(characters.length));
    text.appendChild(node("span", "poem-accessible", item[0]));
    characters.forEach(function (character, index) {
      var letter = node("span", "poem-char poem-char-" +
        (index % 2 ? "lower" : "upper"), character);
      letter.setAttribute("aria-hidden", "true");
      text.appendChild(letter);
    });
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
      " 月 " + date.getDate() + " 日 星期" + WEEKDAYS[weekdayIndex(date)]);
  }

  function weekOf(date, startIso) {
    var delta = dayNumber(date) - dayNumber(parseDate(startIso));
    return delta < 0 ? 1 : Math.floor(delta / 7) + 1;
  }

  /* 某一教学周里周一到周日各自的日期文本（形如 "9/28"）。
   * 开学日期就是第 1 周的周一，所以第 n 周的周一 = 开学日期 + (n-1)*7 天。
   * 没配置 SEMESTER_START 时返回 null，表头就只显示星期、不显示日期。 */
  function weekDates(week, startIso) {
    if (!startIso) return null;
    var monday = parseDate(startIso);
    var out = [];
    for (var i = 0; i < 7; i++) {
      // 用 Date 构造器做日期加减，跨月、跨年都不会出错
      var d = new Date(
        monday.getFullYear(), monday.getMonth(),
        monday.getDate() + (week - 1) * 7 + i
      );
      out.push((d.getMonth() + 1) + "/" + d.getDate());
    }
    return out;
  }

  /* 课程色相：同一个课程名永远得到同一个色相。
   * 范围 218–306（青蓝→蓝紫），落在这一段是为了和整体靛蓝调性一致，
   * 也刻意避开 320 以上的品红区——那片颜色在这套设计里会显得突兀。 */
  function hueOf(name) {
    var hash = 0;
    for (var i = 0; i < name.length; i++) {
      hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    }
    return 218 + (hash % 89);
  }

  /* 课程配色：oklch 锁死 L(感知亮度) 与 C(彩度)，只让色相随课程名变化。
   *
   * 为什么不用 HSL：HSL 的 L 不是感知亮度，同一个 L 下黄绿会比蓝紫亮一档。
   * 实测第三版那套 `hsl(h 50% 45%)` 在 186–271 色相区间里，相对亮度差 4.06 倍
   * （最亮的课看起来比最暗的重很多）；这一版锁死 L 之后只差 1.26 倍。
   *
   * 深色模式必须换一组 L：浅底上的深蓝字放到深底上就看不见了。
   * 色相从 hueOf() 来，两套严格一致，不会出现「同一门课换了颜色」。 */
  function toneOf(name) {
    var hue = hueOf(name);
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return {
        line: "oklch(72% 0.130 " + hue + ")",
        soft: "oklch(40% 0.070 " + hue + " / 0.58)",
        text: "oklch(93% 0.040 " + hue + ")"
      };
    }
    return {
      line: "oklch(56% 0.150 " + hue + ")",
      soft: "oklch(94% 0.045 " + hue + " / 0.72)",
      text: "oklch(34% 0.115 " + hue + ")"
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

  /* 同一个课程名在一周里的所有排课。用于详情弹窗的「本周排课」列表。 */
  function meetingsOf(course, week) {
    return state.data.courses.filter(function (other) {
      return other.name === course.name && other.weeks.indexOf(week) !== -1;
    }).sort(function (a, b) {
      return a.day - b.day || Math.min.apply(null, a.units) - Math.min.apply(null, b.units);
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
    // server_today 是服务器那边的日期。同学手机时间不准时，用它可以发现
    // 「本地以为今天是周三、服务器说是周四」这类偏差，页脚会提示。
    state.todayIso = data.server_today || "";
    var stored = readStored(VIEW_KEY, "today");
    state.view = (stored === "week") ? "week" : "today";
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
    renderBusy();
    renderWeek();
    renderFooter();
  }

  function renderHero() {
    var today = new Date();
    var day = weekdayIndex(today);
    var week = state.currentWeek || state.week;
    var courses = state.currentWeek ? coursesOn(day, state.currentWeek) : [];

    $("hero-eyebrow").textContent =
      "星期" + WEEKDAYS[day] + " · " +
      (today.getMonth() + 1) + " 月 " + today.getDate() + " 日";

    // 标题只说事实：有课说几门，没课就直说没课。
    // 上一版这里是「今天有 N 门课，安排得刚刚好。」——占着最大字号却没有信息量。
    if (!state.currentWeek) {
      $("hero-title").textContent = "本学期课表已准备好";
    } else if (!courses.length) {
      $("hero-title").textContent = day >= 5 ? "周末，好好休息"
        : "今天没有课";
    } else {
      $("hero-title").textContent = "今天 " + courses.length + " 门课";
    }

    $("hero-date").textContent = formatDate(today) + "　·　第 " + week + " 周";
    $("hero-week").textContent = "第 " + week + " 周";

    var total = totalWeeks();
    $("week-progress").style.width =
      Math.min(100, Math.max(4, week / total * 100)) + "%";
    $("week-progress-label").textContent =
      "本学期第 " + week + " / " + total + " 周";
    $("week-label").textContent = "第 " + state.week + " 周";

    renderHeroNext(courses, day);
  }

  /* 首屏那行提示：显示今天的第一门课；今天没有就往后找最近的一天。
   * 只说到第几节，不再翻译成钟点——那张作息表是猜的（见文件开头）。
   * 也正因为不认钟点，它无法回答「下一节是哪节」，所以标题从「下一节」
   * 改成了「今天」：说今天第一门，不会错。 */
  function renderHeroNext(courses, day) {
    var list = $("hero-next");
    list.textContent = "";
    if (!state.currentWeek) return;

    if (courses.length) {
      list.appendChild(nextChip("今天", courses[0]));
      return;
    }

    // 今天没有 → 找接下来的第一门课（往后最多看 7 天）
    var now = new Date();
    for (var offset = 1; offset <= 7; offset++) {
      var target = new Date(
        now.getFullYear(), now.getMonth(), now.getDate() + offset
      );
      var picked = coursesOn(weekdayIndex(target), state.currentWeek);
      if (picked.length) {
        list.appendChild(nextChip(
          offset === 1 ? "明天" : "周" + WEEKDAYS[weekdayIndex(target)],
          picked[0]
        ));
        return;
      }
    }
    // 往后一周都没有课：多半是实训周 / 假期，直说
    list.appendChild(nextChip("接下来一周", null));
  }

  function nextChip(label, course) {
    var item = node("li");
    item.appendChild(node("span", null, label + "　"));
    var strong = node("b");
    if (course) {
      strong.textContent = "第 " + unitText(course) + " 节";
      item.appendChild(strong);
      item.appendChild(node("span", null, "　" + course.name));
    } else {
      strong.textContent = "无课";
      item.appendChild(node("span", null, "　集中实践周，不上常规课"));
    }
    item.title = course ? (course.name + " · " + (course.room || "教室待定")) : "";
    return item;
  }

  function totalWeeks() {
    var weeks = [];
    state.data.courses.forEach(function (course) {
      weeks = weeks.concat(course.weeks);
    });
    // 快照里周次最大到 17；没有任何数据时退回 17，避免除零
    return weeks.length ? Math.max.apply(null, weeks) : 17;
  }

  function renderTabs() {
    document.querySelectorAll(".view-tab").forEach(function (tab) {
      var active = tab.getAttribute("data-view") === state.view;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    $("pane-today").hidden = state.view !== "today";
    $("pane-week").hidden = state.view !== "week";
    // 面板刚显隐过，滑动提示要跟着重算（隐藏时量不出宽度，会保持隐藏）
    renderGridHint();
  }

  /* 「手机上可以左右滑动查看完整课表」只在真的滑得动时才说。桌面端五列本来
   * 就放得下，还挂着这句话就是一条错提示。读 scrollWidth 会强制一次 reflow，
   * 但它只在切视图、翻周次时跑，代价可以忽略。 */
  function renderGridHint() {
    var grid = $("grid");
    var hint = document.querySelector(".grid-hint");
    if (!grid || !hint) return;
    var box = grid.parentNode;
    hint.hidden = box.scrollWidth <= box.clientWidth + 1;
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
      empty.appendChild(node("span", null, emptyHint(day)));
      list.appendChild(empty);
      return;
    }

    courses.forEach(function (course) {
      list.appendChild(courseCard(course, day));
    });
  }

  /* 没课时给一句有依据的解释，而不是干巴巴的「当前日期没有安排课程」。
   * 学校有几周是集中实践周（全校不上常规课），这时整周都是空的。 */
  function emptyHint(day) {
    var week = state.currentWeek;
    if (week && coursesInWeek(week).length === 0) {
      return "第 " + week + " 周整周无常规课，多为集中实践周或假期";
    }
    return day >= 5 ? "周末没有安排课程" : "这一天没有排课";
  }

  /* 「正在上课」的高亮随作息表一起删了：它靠本机时间去套那张猜出来的
   * 钟点表，作息一旦对不上就会给出一节错的课，还不如不给。 */
  function courseCard(course, day) {
    var card = node("button", "course");
    var tone = toneOf(course.name);
    card.type = "button";
    card.style.setProperty("--tone", tone.line);

    var body = node("div");
    body.appendChild(node("h4", "course-name", course.name));
    var meta = node("p", "course-meta");
    meta.appendChild(node("span", null, course.room || "教室待定"));
    meta.appendChild(node("span", "sep", "·"));
    meta.appendChild(node("span", null, course.teachers || "教师待定"));
    body.appendChild(meta);

    var time = node("div", "course-time");
    time.appendChild(node("strong", null, unitText(course)));
    time.appendChild(node("span", "unit-label",
      "第 " + unitText(course) + " 节"));

    card.appendChild(body);
    card.appendChild(time);
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

    // 上面三个数字 + 上课日/节次数已经能说明问题，教室名长度不定，单独给整行
    var values = [
      [courses.length, "本周课程"],
      [Object.keys(days).length, "上课日"],
      [state.data.unit_count, "节次总数"],
      [commonRoom, "常用教室"]
    ];
    $("stats-week").textContent = "第 " + state.week + " 周";
    var stats = $("stats");
    stats.textContent = "";
    values.forEach(function (value, index) {
      var item = node("div", index === values.length - 1 ? "stat stat-wide" : "stat");
      item.appendChild(node("b", null, String(value[0])));
      item.appendChild(node("span", null, value[1]));
      stats.appendChild(item);
    });
  }

  /* 一周七天的小柱图：比四个孤立数字更快看出这周的松紧。
   * 柱子高度按「节次数」而不是「课程数」算——连堂两节的课不该和单节等重。
   *
   * 整周无课（集中实践周）时**照样画**五条空槽：一片空白会让人以为是
   * 加载失败，而五条空槽一眼就能看出「这周确实没课」。 */
  function renderBusy() {
    var box = $("busy");
    box.textContent = "";
    var courses = coursesInWeek(state.week);

    var loads = [0, 0, 0, 0, 0, 0, 0];
    courses.forEach(function (course) {
      loads[course.day] += course.units.length;
    });
    var peak = Math.max.apply(null, loads) || 1;
    var todayDay = weekdayIndex(new Date());
    var isThisWeek = state.week === state.currentWeek;

    box.appendChild(node("p", "busy-title",
      courses.length ? "每日节次数" : "每日节次数（本周无课）"));
    for (var day = 0; day < 5; day++) {
      var row = node("div", "busy-row");
      if (loads[day] === 0) row.classList.add("is-zero");
      if (isThisWeek && day === todayDay) row.classList.add("is-today");
      row.appendChild(node("span", null, "周" + WEEKDAYS[day]));
      var bar = node("span", "busy-bar");
      var fill = node("i");
      // 先给 0 宽度，下一帧再设真实宽度，让动画能跑起来
      fill.style.width = "0%";
      bar.appendChild(fill);
      row.appendChild(bar);
      row.appendChild(node("span", "busy-count", String(loads[day])));
      box.appendChild(row);
      (function (element, ratio) {
        requestAnimationFrame(function () {
          element.style.width = (ratio * 100) + "%";
        });
      })(fill, loads[day] / peak);
    }
  }

  function renderWeek() {
    $("grid-heading").textContent = "第 " + state.week + " 周课表";
    var table = $("grid");
    table.textContent = "";
    var unitCount = state.data.unit_count;
    var today = new Date();
    var todayDay = weekdayIndex(today);
    var markToday = state.week === state.currentWeek;

    /* 星期列数按数据推导，不写死 7：周一到周五恒显（某天没课，
     * 「这天没课」本身也是信息），但整学期都没课的周六周日不画。
     * 现在 27 门课全排在工作日，多出来的两列只让手机白滑两百多像素。
     * 哪天教务排进周末的课，列会自动补回来，不用改代码。 */
    var dayCount = 5;
    state.data.courses.forEach(function (course) {
      if (course.day >= dayCount) dayCount = course.day + 1;
    });
    table.style.setProperty("--day-cols", dayCount);

    var cells = {};
    var day;
    for (day = 0; day < dayCount; day++) {
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
    var dates = weekDates(state.week, state.data.semester_start);
    for (day = 0; day < dayCount; day++) {
      var classes = [];
      if (day === todayDay && markToday) classes.push("today");
      if (day >= 5) classes.push("weekend");
      var th = node("th", classes.join(" "), "周" + WEEKDAYS[day]);
      // 表头第二行：这一天在这一周里的具体日期
      if (dates) th.appendChild(node("span", "day-date", dates[day]));
      headRow.appendChild(th);
    }
    head.appendChild(headRow);
    table.appendChild(head);

    var body = node("tbody");
    var skip = {};
    for (var row = 0; row < unitCount; row++) {
      var tr = node("tr");
      tr.appendChild(node("th", "unit", String(row + 1)));
      for (day = 0; day < dayCount; day++) {
        if (skip[day] > 0) {
          skip[day]--;
          continue;
        }
        var cell = node("td");
        if (markToday && day === todayDay) cell.classList.add("is-today");
        var course = cells[day][row];
        if (course) {
          var span = 1;
          while (row + span < unitCount && cells[day][row + span] === course) span++;
          if (span > 1) {
            cell.rowSpan = span;
            skip[day] = span - 1;
          }
          cell.appendChild(courseBlock(course, span));
        }
        tr.appendChild(cell);
      }
      body.appendChild(tr);
    }
    table.appendChild(body);

    // 表格重建过，列宽变了，滑动提示要重新判断
    renderGridHint();
  }

  function courseBlock(course, span) {
    var block = node("button", "course-block");
    var tone = toneOf(course.name);
    block.type = "button";
    block.style.setProperty("--tone", tone.line);
    block.style.setProperty("--tone-soft", tone.soft);
    block.style.setProperty("--tone-text", tone.text);
    if (span > 1) block.classList.add("span-multi");
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
    var parts = [state.currentWeek
      ? "本学期第 " + state.currentWeek + " 周"
      : "未配置开学日期"];

    // 本机日期和服务器日期不一致时提醒一句——错的是日期，看到的课表就全错
    if (state.todayIso && state.todayIso !== localIso(new Date())) {
      parts.push("本机日期与服务器不一致（服务器 " + state.todayIso + "）");
    }
    $("semester").textContent = parts.join(" · ");
  }

  function localIso(date) {
    var month = String(date.getMonth() + 1);
    var day = String(date.getDate());
    return date.getFullYear() + "-" +
      (month.length < 2 ? "0" + month : month) + "-" +
      (day.length < 2 ? "0" + day : day);
  }

  function openSheet(course) {
    $("sheet-name").textContent = course.name;
    $("sheet-tag").textContent =
      "星期" + WEEKDAYS[course.day] + " · 第 " + unitText(course) + " 节";

    // 本周排课：同名课程在这一周的所有排课。原来只显示被点的那一条，
    // 看不到「这门课一周上几次、在哪几天」。
    var meetings = $("sheet-meetings");
    meetings.textContent = "";
    var sameWeek = meetingsOf(course, state.week);
    sameWeek.forEach(function (item) {
      var li = node("li");
      li.appendChild(node("span", "day", "周" + WEEKDAYS[item.day]));
      li.appendChild(node("span", "periods", "第 " + unitText(item) + " 节"));
      li.appendChild(node("span", "room", item.room || "教室待定"));
      meetings.appendChild(li);
    });
    meetings.hidden = sameWeek.length === 0;

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
        writeStored(VIEW_KEY, state.view);
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

    // 切到后台再回来时，时间可能已经跨过了一节课的边界。
    // visibilitychange 一次就够，不做轮询——这个页面不需要秒级实时。
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && state.data) render();
    });

    // 系统在浅色 / 深色之间切换时，课程色需要跟着换一组亮度
    if (window.matchMedia) {
      var scheme = window.matchMedia("(prefers-color-scheme: dark)");
      var onScheme = function () { if (state.data) render(); };
      if (scheme.addEventListener) scheme.addEventListener("change", onScheme);
      else if (scheme.addListener) scheme.addListener(onScheme);
    }
  }

  bindEvents();
  boot();
})();

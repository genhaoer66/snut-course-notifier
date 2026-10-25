# T06：T05 新前端的审查修复与收尾

先读 tasks/COMMON.md、tasks/UI-DESIGN.md、tasks/T05-new-ui.md。范围同 T05（web/、scripts/make_brand_assets.py、design/；snut/ 与 tests/ 零改动）。

独立审查（Sonnet）确认的问题，全部要修：

1. web/style.css 里用了 `inset`（约 30、65、111、112 行）：微信 Android 旧内核不识别。全部换成 top/right/bottom/left。
2. web/style.css:70 `#grid.has-weekend` 的 min-width 固定 374px：7 列时每列约 50px，课名块内宽低于规格 56px。改为按列数计算 `min-width: calc(24px + n*56px + (n+1)*2px)`（n 为列数；在 JS 里按有无周末设置，或用 CSS 变量），使手机上周表可横滑而文字不被挤压。
3. 打印样式：`.week-nav button` 被隐藏、caption 是 sr-only，打印没有「第 N 周」标题。打印时让 `#week-label`（或等效元素）可见。
4. web/app.js 约 262、466 行：`.catch` 吞掉 start()/render() 的运行时异常，渲染出错会被显示成「网络连接失败/连不上服务器」。把网络错误和渲染异常分开处理，渲染异常 console.error 并给出通用的「页面出错了，请刷新」提示。
5. 无障碍：index.html:61 `#week-label` 的 aria-label="回到本周" 盖掉了可见周次文字，改用 title；app.js:284 `courseButton` 的 aria-label 覆盖了「下一次上课」块的文字，改为在其前拼上「下一次上课，」。
6. app.js:489-491：焦点在可横滑的 #grid-scroll 上时，←/→ 被用来翻周，键盘无法横向滚动周末列。只在焦点不在 #grid-scroll 上时才响应方向键翻周。

收尾（上一轮因环境故障没做完）：
7. 截图：360/390px 截图被裁切的原因是 headless Chrome 窗口有约 500px 最小宽度，不是 CSS 布局 bug。请换一种能真实模拟窄视口的截图方式（例如 Chrome 的 --window-size 配合 device metrics emulation，或在 playwright/CDP 里用 setDeviceMetricsOverride；先看 design/ 里上一轮用了什么），重新截 360/390/768/1280 × 浅/深 共 16 张到 design/screenshots/，确认 360 宽下没有横向溢出（除周表的内部横滑容器外），并对照 UI-DESIGN.md 逐张自查，发现问题直接修。截图时服务必须指向 design/ 下的合成快照，禁止读真实 data/、.env。
8. 重跑 `node --check web/app.js`、node design/ui-selftest.js（按需补上 #2、#4 的自测）、python -m unittest discover -s tests、compileall，全部通过。
9. 写 tasks/T05.report.md（功能对等逐条对照、与规格不一致处及理由、验证做到哪一步、未做到的事）与 tasks/T06.report.md（上述 1–7 逐条：怎么修的）。若工具再报 Windows 1909，先把已有结论写进报告再继续。

验收：git status 改动仅在范围内；`grep -n "inset" web/style.css` 无输出；`grep -nE "\?\.|\?\?" web/app.js` 无输出；无外链资源。

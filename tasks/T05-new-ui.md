# T05：按新设计规格重写网站前端

先读 `tasks/COMMON.md`（注意：其中「只改范围内文件」以本文件的范围为准；「不碰外部」仍适用，但**不要**求保持旧界面外观——旧 UI 全部废弃）和 **`tasks/UI-DESIGN.md`（本任务的唯一设计依据，逐节落实）**。

## 范围（只允许动这些）

- `web/index.html`、`web/app.js`、`web/style.css`（整体重写）
- `web/logo.svg`、`web/favicon.svg`、`web/og-cover.svg`（按规格 8.1/8.2 重绘）
- 新增 `web/favicon.ico`、`web/apple-touch-icon.png`、`web/og-cover.png`；可复用/改写 `scripts/make_brand_assets.py` 来生成 PNG/ICO（先看它现在怎么做、依赖是否可用；不能装新依赖）
- `design/logo/logo-ai-a.png` 是 AI 生成的视觉参考（只读）；矢量以规格 8.1 的几何数值手写为准

**不改** `snut/` 任何文件、`tests/`、`requirements*`、CI。后端接口（`/api/login`、`/api/timetable`、`/healthz`）与 `_render_index` 的占位约定不变；先读 `snut/webapp.py` 弄清它对 `index.html` 做了什么替换，以及静态资源的路径与缓存头，新 HTML 必须与之兼容（`tests/test_webapp_routes.py` 中关于 index/OG 的断言必须继续通过，不要改测试）。

## 硬约束（来自项目）

- 纯静态，无框架、无构建、无任何外链资源（无 CDN/Web 字体/外部图片）。
- 兼容微信内置浏览器与 iOS Safari 15+/Android Chrome；JS 用 ES2017 以内，不用可选链 `?.` 与 `??`（微信旧内核）。
- 全部文案简体中文。
- 不读取真实 `data/`、`.env`；本地预览如需数据，只能用合成 JSON（可放 `design/` 下，不要提交进 `web/`）。

## 必须做

1. 严格落实规格的 token、版面、课程配色、交互、响应式、无障碍（每一节）。规格里「功能对等清单」每一项都要实现并在报告里逐条标注位置。
2. 旧版 `web/app.js` 的所有功能必须保留（以规格第 7 节清单为准），同时修复规格第 9 节与 Opus 设计师指出的这些隐患：
   - 今天无课时查找「下一次上课」，跨到下周时必须按下周周次过滤；
   - 周次翻页要有上下限（1 ~ 学期最大周次，依数据确定）；
   - 令牌过期被服务端拒绝（401）后回到登录页时，要给出明确提示，而不是静默；
   - 503 响应里的 `hint` 要显示给用户；
   - 渲染课程名/教室/教师一律用 `textContent` 或转义，禁止拼接未转义的 `innerHTML`。
3. 资源引用写 `/static/style.css?v=YYYYMMDD.n`（用今天日期 20261024.1），按 `_render_index`/静态路由的实际路径确认写法。
4. 验证：
   - `node --check web/app.js`；
   - 为 `app.js` 里的纯逻辑（周次计算、下一次上课查找、课程名→颜色映射、翻页边界）写可在 node 下运行的自测脚本 `design/ui-selftest.js`（不进 web/，不依赖浏览器），并跑通；
   - 若本机有可用的无头浏览器（先找 `scripts/`、`logs/` 里已有预览截图的做法，如 playwright/Edge headless），用合成数据起 `python -m uvicorn snut.webapp:app --port 8011`（**注意**：webapp 会读真实 `.env`/`data`；改用环境变量或合成目录让它指向 `design/` 下的合成快照，务必不读真实数据；做不到就不起服务，只做静态检查），按规格 360/390/768/1280 四个宽度、浅/深色各截图存到 `design/screenshots/` 并逐张对照规格自查；没有浏览器就在报告里明确写「未做浏览器验证」。
5. `python -m unittest discover -s tests` 必须仍然全绿；`python -m compileall -q snut scripts tests` 通过。

## 验收

- `git status` 里改动只出现在范围内；`snut/`、`tests/` 零改动
- `grep -nE "https?://" web/index.html web/app.js web/style.css` 只允许出现在 OG/规范性 meta 的占位或注释之外的**零个外部资源引用**（`{OG_BASE}` 占位、`xmlns` 命名空间除外）
- 报告 `tasks/T05.report.md`：功能对等逐条对照、每处与规格不一致的地方及理由、未做到的事、验证做到哪一步

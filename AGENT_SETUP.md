# AGENT_SETUP.md —— 让 AI 助手帮你配置这个项目

> **如果你是刚拿到这个项目的新用户**：把下面[第一节的提示词](#一给-ai-助手的提示词复制这段)
> 整段复制给你的 AI 助手（Claude Code / Cursor / ChatGPT / DeepSeek…）就行，
> 它会带你走完配置。也可以直接把本文件丢给它。
>
> **如果你是 AI 助手**：本文件就是你的任务清单与护栏，请**逐条遵守**，
> 尤其是[第六节](#六护栏请勿违反)那几条——它们对应的是这个项目真实踩过的坑。

---

## 一、给 AI 助手的提示词（复制这段）

```text
请帮我配置并跑通这个开源项目：
https://github.com/genhaoer66/snut-course-notifier

它是「陕西理工大学课表自动推送 + 课表网站」：定时登录学校教务系统抓课表，
发邮件到手机，并生成一份脱敏快照给网页看。

请严格按仓库根目录的 AGENT_SETUP.md 执行，大致流程：
1. 克隆仓库、创建虚拟环境、安装依赖（requirements.txt）
2. 复制 .env.example 为 .env，然后逐个问我下面这些值 —— 不要自己编造：
   - SNUT_USERNAME（学号）
   - SNUT_PASSWORD（教务系统密码）
   - SEMESTER_START（本学期第 1 周的周一日期）
3. 跑 scripts/test_login.py，确认能登录学校系统
4. 跑 python -m snut.main --dry-run，把抓到的课表打给我看
5. 起本地网站（uvicorn 127.0.0.1:8000）让我预览

注意事项：学校教务系统响应很慢而且有防刷机制，不要反复重试登录、
不要把 REQUEST_INTERVAL 调小于 2；我的学号密码等敏感信息只能写进 .env
（它已被 .gitignore 忽略），不要提交到 git，也不要写进任何其他文件。
每一步做完告诉我结果，遇到要我做决定的地方先问我。
```

---

## 二、项目是什么（30 秒版）

```text
定时任务 ──> 登录学校统一认证 ──> 抓课表 ──┬──> 邮件 / 微信推送
                                          └──> data/timetable.json（脱敏快照）
                                                     │
                                    uvicorn 只读这个 JSON ──> 网页
```

**适用范围**：目前**只支持陕西理工大学**（金智统一身份认证 + 树维 EAMS 教务系统）。
其它学校需要在 `snut/auth.py` 与 `snut/course.py` 里替换实现，详见 README 的「适配其他学校」。

---

## 三、环境要求

| 项 | 要求 |
|---|---|
| Python | **3.8 或更高**（3.8.6 与 3.13 均已实测） |
| 系统 | Windows / Linux / macOS 均可 |
| 依赖 | `python -m pip install -r requirements.txt` |
| 可选 | `requirements-optional.txt`（验证码 OCR，包较大，不装也能用） |
| 网络 | 需能访问 `authserver.snut.edu.cn` 与 `jwgl.snut.edu.cn` |

---

## 四、必须问用户、不能自己编的配置

| 变量 | 必填 | 说明 |
|---|---|---|
| `SNUT_USERNAME` | ✅ | 学号 |
| `SNUT_PASSWORD` | ✅ | 教务系统密码（代码会按学校要求 AES 加密后再提交） |
| `SEMESTER_START` | ✅ 强烈建议 | 本学期**第 1 周的周一**，格式 `YYYY-MM-DD` |
| `SMTP_USER` / `SMTP_AUTH_CODE` / `MAIL_TO` | 可选 | 要发邮件才填。`SMTP_AUTH_CODE` 是邮箱**授权码**，不是登录密码 |
| `SERVERCHAN_KEY` | 可选 | Server酱 SendKey，填了才推微信 |
| `WEB_PASSWORD` | 可选 | 网站访问口令。**留空＝任何人拿到链接都能看课表** |

### ⚠️ 关于 `SEMESTER_START`，务必这样问用户

**绝对不要**用「课表里哪几周是空的」去反推开学日期。
这个学校空白的周可能是**实训周**（集中实践环节，全校不上常规课），不是假期，会算错一周。

**算错一周的后果**：邮件和网站会显示**上一周的课**，而且看起来完全正常，极难发现。

正确做法，按优先级：

1. 问用户「今天是第几周」——然后反推：`第 1 周周一 = 今天 - (周次-1)*7 - 今天是周几的偏移`；
2. 让用户翻学校的**调课通知**（通知里会写「某日补第几周星期几的课」，括号里就是周次）；
3. 实在没有，用教务系统里正在上的课核对。

拿到日期后**必须校验**：算出的第 1 周周一应该是**周一**（`weekday() == 0`）。

---

## 五、执行步骤（含验收标准）

```bash
# 1. 克隆与环境
git clone https://github.com/genhaoer66/snut-course-notifier.git
cd snut-course-notifier
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate
python -m pip install -r requirements.txt

# 2. 配置（把用户给的值填进 .env）
#    Windows: copy .env.example .env      Linux/macOS: cp .env.example .env

# 3. 登录诊断  ← 验收：输出「登录成功」，并能访问课表页
python scripts/test_login.py

# 4. 抓一次课表（不发推送，但会写网站快照）  ← 验收：打印出某一天的课程列表
python -m snut.main --dry-run

# 5. 本地预览网站（后台运行，然后让用户在浏览器打开 http://127.0.0.1:8000）
python -m uvicorn snut.webapp:app --host 127.0.0.1 --port 8000
```

**全部完成的标志**：第 3 步登录成功、第 4 步打印出了课程、第 5 步网页能打开并看到课表。

### 项目结构（方便你定位问题）

```text
snut/config.py     配置读取          ← 报「缺少配置项」看这里
snut/auth.py       登录（学校相关）   ← 登录失败的排查重点
snut/course.py     抓取与解析（学校相关）
snut/formatter.py  邮件格式化
snut/notify.py     邮件 / Server酱推送
snut/snapshot.py   脱敏快照
snut/main.py       CLI 总流程
snut/webapp.py     FastAPI 只读网站
web/               前端（纯静态，零构建）
scripts/           诊断工具（不参与日常运行）
```

---

## 六、护栏（请勿违反）

1. **不要频繁重试登录。** 学校有防刷机制，请求过密会返回「请不要过快点击」。
   日常运行靠会话复用就能免密，不要一失败就重新登录。
2. **不要调小 `REQUEST_INTERVAL`**（默认 3 秒，不要小于 2）。它是全局请求间隔，
   调小可能触发风控，甚至让用户的账号被临时限制。
3. **不要用真实推送命令反复调试**，一律用 `--dry-run`（它同样会更新网站快照）。
4. **敏感信息只进 `.env`**（已被 `.gitignore` 忽略）。**不要**把学号、密码、
   邮箱授权码写进任何 `.py`、`.md`、注释或提交信息里。
   同样绝不要提交：`.session/`（等同于登录凭证）、`data/`、`logs/`。
5. **不要破坏架构边界**：`snut/webapp.py` 不得 import `auth` / `course` / `captcha`。
   网站进程里不能出现学号密码，否则同学刷网页就会给学校增加请求。
6. **不要把自动化绕过的部分做过头**：不代他人登录、不批量抓取、不做多用户托管。
   本项目按「一次抓取 → 一份快照 → 多人查看」设计，请保持这个形态。
7. 用户没明确要求时，**不要动服务器**、不要部署、不要 `git push`。

---

## 七、常见问题排查

| 现象 | 原因 / 处理 |
|---|---|
| `缺少配置项 SNUT_USERNAME` | `.env` 没建或没填，见第四、五节 |
| 登录返回「认证失败」 | 多半不是密码错。登录页有 4 套表单且 id 重复，`cllt` 必须硬编码为 `userNameLogin`（代码里已处理，若仍失败看下一条） |
| 登录页提示「请不要过快点击」 | 被限流：等几分钟，或把 `REQUEST_INTERVAL` 调大 |
| 需要图形验证码 | 装 `requirements-optional.txt` 用 OCR；或运行 `scripts/captcha_login.py fetch` → 人工看图 → `submit <验证码>` |
| 课表为空 / 「没有权限」 | 学期 id 或 `ids` 变了，跑 `scripts/debug_course.py` 看当前值（`ids` 不是学号） |
| 课表中课程整体差一周 | `SEMESTER_START` 算错了，见第四节 |
| 网站显示「课表数据还没生成」 | 还没抓过，先跑一次 `python -m snut.main --dry-run` |
| 网页改了看不到变化 | 静态资源是长缓存，在 URL 后面加 `?v=2` 或强制刷新 |

---

## 八、可选：再往下走一步

`--dry-run` 只打印不推送。如果用户想真正收到推送：

1. 在 `.env` 填 `SMTP_USER` / `SMTP_AUTH_CODE` / `MAIL_TO`（授权码获取方式见 `.env.example` 注释）；
2. 跑一次 `python -m snut.main` 验证能收到邮件；
3. 再考虑用 cron / systemd timer 定时执行（Linux 部署见 `DEPLOY.md`，网站部署见 `DEPLOY-WEB.md`）。

> 💡 定时任务建议**避开整点**（学校服务器整点负载高，也更容易被风控注意到），
> 例如要「早上 7 点」，用 `3 7 * * *`（7:03）。

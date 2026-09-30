# 架构说明

## 1. 运行时边界

项目分为两个彼此隔离的运行时：

### 抓取任务

入口：`python -m snut.main`

职责：

1. 从配置读取学校账号和推送配置；
2. 复用 Cookie 或执行 CAS 登录；
3. 请求 EAMS 并解析 JavaScript 课表；
4. 生成邮件 / Server酱消息；
5. 通过 `snapshot.save_snapshot()` 写入脱敏快照。

这个进程可以访问学校系统，也可以读取 `.env`。

### Web 服务

入口：`uvicorn snut.webapp:app`

职责：

1. 返回 `web/index.html`；
2. 读取 `data/timetable.json`；
3. 提供 `/api/timetable`、`/api/login` 和 `/healthz`；
4. 提供静态前端资源。

这个进程不导入 `auth`、`course`、`captcha`、`notify`，也不执行学校请求。它只读快照，因此网页访问量不会影响学校教务系统。

## 2. 数据流

```text
.env
 │
 ▼
Config ──> LoginClient ──> EAMS
                         │
                         ▼
                    CourseTable
                    /         \
                   ▼           ▼
             formatter      snapshot
                │              │
                ▼              ▼
             邮件推送       timetable.json
                                  │
                                  ▼
                          FastAPI /api/timetable
                                  │
                                  ▼
                            浏览器本地渲染
```

前端一次请求全量课表，周次切换、按天过滤和表格渲染都在浏览器完成。切换周次不会增加 API 请求。

## 3. 文件职责

| 文件 | 只负责什么 |
|---|---|
| `snut/config.py` | 读取并校验环境变量、集中管理路径 |
| `snut/auth.py` | CAS 登录、AES 密码加密、Cookie 会话复用 |
| `snut/course.py` | EAMS 请求、学期/学生 ID 提取、课表 JS 解析 |
| `snut/captcha.py` | 可选验证码识别 |
| `snut/formatter.py` | 邮件正文和周次计算 |
| `snut/notify.py` | 邮件、Server酱推送 |
| `snut/snapshot.py` | 公开字段白名单、原子写入、旧快照保护 |
| `snut/main.py` | CLI 编排，不承载底层解析细节 |
| `snut/webapp.py` | 只读快照的 HTTP API 和认证 |
| `web/index.html` | DOM 骨架，不放业务数据 |
| `web/style.css` | 视觉和响应式布局 |
| `web/app.js` | API、周次过滤、渲染、交互 |
| `scripts/` | 诊断和部署工具，不参与业务运行 |

## 4. 失败策略

### 抓取失败

- 保留上一次的 `data/timetable.json`；
- cron 日志记录错误；
- 正常运行模式尝试发送告警；
- 网站继续展示旧快照，并在页脚标记更新时间。

### 邮件失败

邮件失败会返回非零状态，但不影响已经写入的网站快照。

### 快照失败

快照写入异常只记录日志，不阻止邮件推送。写入使用临时文件 + `os.replace`，避免网站读到半截 JSON。

### 网站不可用

systemd 自动重启 `course-web`；Cloudflare Tunnel 只把公网流量转发到本机 `127.0.0.1:8000`。

## 5. 安全边界

- 真实配置只放 `.env`，不进入 Git；
- Cookie 只放 `.session/`，不进入 Git；
- 快照只导出 `PUBLIC_FIELDS`；
- Web 服务不持有教务登录凭证；
- 源站服务只监听回环地址；
- Cloudflare Tunnel 隐藏源站地址并负责 HTTPS；
- 访问口令是共享口令，不是多用户账号系统；
- 口令 token 是无状态 HMAC，默认 30 天有效；
- 登录失败按客户端 IP 做内存限速；
- 所有网页响应带 `X-Robots-Tag: noindex`。

## 6. 修改顺序

### 修改解析或登录

先运行：

```bash
python -m unittest discover -s tests -v
python -m snut.main --dry-run
```

不要用真实推送命令反复调试，学校 EAMS 有请求限速。

### 修改网页

1. 修改 `web/index.html`、`web/style.css`、`web/app.js`；
2. 执行 `node --check web/app.js`；
3. 本地启动 Web 服务；
4. 生产部署时上传前端并更新资源版本号；
5. 不需要重新抓取课表。

### 修改配置

优先修改 `.env.example` 的说明，再在服务器的 `.env` 写真实值。不要把真实值反向复制回模板。


# 架构说明

## 运行时与数据流

```text
.env → Config → main
                ├─ LoginClient（auth 门面）
                │    ├─ HTTPClient / ThrottledAdapter（请求、限速、重试）
                │    ├─ login_page（HTML 纯解析）
                │    └─ session_store（Cookie 恢复与保存）
                └─ course.load_course_table → CourseTable / Activity
                                              ├─ formatter → notify → 邮件 / Server酱
                                              └─ snapshot.save_snapshot
                                                    │ 原子写入
                                              data/timetable.json
                                                    │ 只读
                              webapp ← snapshot.load_snapshot
                                ├─ web_security（访问令牌、登录限速）
                                ├─ formatter（按当前日期计算周次）
                                └─ web/ → 浏览器渲染与本地过滤
```

一次抓取，两个产物：推送内容与网站快照。快照在推送前写入，所以推送失败不影响已生成的快照。
`--dry-run` 仍登录、抓取和写快照，只跳过推送；`--no-snapshot` 才跳过快照写入。
浏览器首次取得全量数据后，切周和课程过滤在本地完成，不增加学校请求。

## 模块职责

| 模块 | 职责与边界 |
|---|---|
| `snut/config.py` | 加载环境变量，校验必填账号、数字与日期，提供目录和配置单例 |
| `snut/auth.py` | 对外登录门面 `LoginClient`；AES 密码加密；Cookie 复用、静默 SSO、完整登录与验证码重试编排 |
| `snut/auth_http.py` | `HTTPClient` 维护 requests 会话；`ThrottledAdapter` 限速、重试和认证 HTTP→HTTPS；处理 SSL 兼容降级 |
| `snut/login_page.py` | 无网络的登录表单解析、验证码标记判断、错误提取和目标主机判定 |
| `snut/session_store.py` | 保存 Cookie name/value/domain/path，兼容旧字典格式，处理缺失或损坏会话文件 |
| `snut/course.py` | 学期与内部学生 ID 提取，EAMS 抓取、JavaScript 解析、排课合并，以及 `Activity` / `CourseTable` 数据模型 |
| `snut/captcha.py` | 可选 OCR 初始化与验证码识别，不可用时提供降级原因 |
| `snut/formatter.py` | 日/周文本与 HTML 格式化、教学周计算，不请求学校 |
| `snut/notify.py` | SMTP 和 Server酱推送、启用渠道分发、告警与错误处理 |
| `snut/snapshot.py` | 字段白名单、作息表读取、快照构造、原子保存与读取，不导入课表请求模块 |
| `snut/main.py` | 参数解析、配置与日志、登录、抓取、快照、格式化和推送的顺序编排 |
| `snut/web_security.py` | HMAC 令牌签发/校验、Bearer 提取、客户端 IP 与内存失败计数；不依赖 Web 框架 |
| `snut/webapp.py` | FastAPI 路由、配置错误响应、快照读取、实时周次补充、分享标签、缓存与静态资源 |
| `web/index.html` | DOM 与元信息骨架，不内嵌真实课表 |
| `web/app.js` | 请求快照、状态管理、周次与课程过滤、渲染、键盘和弹层交互 |
| `web/style.css` | 松石绿视觉、深浅色、响应式、打印和减弱动态效果 |
| `scripts/` | 诊断和部署工具；`deploy_web.py` 收集后端模块与前端资源，`upload_frontend.py` 仅上传前端 |

## Web 边界与接口

`snut/webapp.py` **不得 import `auth` / `course` / `captcha`**，也不得调用学校接口。
Web 只能读取落地快照，浏览器刷新不会触发登录或抓取。这条请求边界必须保持。

当前实现仍导入 `config.py`，该模块加载 `.env`；路由通过 `get_config()` 创建包含必填学校账号的通用 `Config`。
因此目前隔离的是学校请求逻辑，而不是进程内凭证。不能宣称 Web 不读取 `.env` 或内存中没有账号密码。
进一步拆分网站配置属于后续工作。

| 接口 | 行为 |
|---|---|
| `GET/HEAD /` | 读取 HTML，替换分享标签 `{OG_BASE}`，`Cache-Control: no-cache` |
| `GET/HEAD /api/timetable` | 校验可选令牌、读取快照，补充实时 `current_week` 和 `server_today`；无快照返回 503 |
| `POST /api/login` | 无口令时返回空令牌；否则校验口令、记录失败或签发令牌 |
| `GET/HEAD /healthz` | 返回进程与快照概况；`ok` 不代表快照一定存在，应检查 `has_snapshot` |
| `GET/HEAD /robots.txt` | 点名拒绝 AI 爬虫，允许搜索引擎读取 noindex 指令 |
| `/static/` | 映射整个 `web/`，静态资源缓存 604800 秒，修改后需更新资源版本号 |

课表 API 有口令时缓存为 `private, max-age=300`，公开模式为 `public, max-age=600`。
所有响应添加 `X-Robots-Tag`。网站令牌为日期加 HMAC，有效期 30 天；修改共享口令使旧签名失效。
同 IP 在 300 秒窗口内累计 8 次错误后锁定至窗口结束，计数保存在进程内存，不是持久化或跨进程计数。

## 快照与失败策略

课程白名单为 `name`、`teachers`、`room`、`day`、`units`、`weeks`，排除学号、内部 ID、课程编码和学期 ID。
根字段包含更新时间、学期起始日、每天节次数、可选作息表与课程列表。教师姓名仍在白名单内，快照不是完全匿名数据。
不要改用 `vars()` 或 `__dict__` 整体导出，新字段应默认不公开。

- 快照先写临时文件，再用 `os.replace` 原子替换；失败时保留已有快照。
- 抓取或登录失败会结束流程；非 dry-run 模式尝试发告警，网站继续读取旧快照。
- 快照写入异常只记录日志，不阻止后续推送。
- `notify.push()` 默认记录各渠道错误并继续其他渠道。没有配置渠道会抛错；已配置渠道发送失败默认不抛错，因此 CLI 不保证返回非零状态。
- 快照缺失或 JSON 损坏时返回无数据提示。前端标注更新时间，旧数据不能当作抓取成功的证明。
- `data/periods.json` 由快照构造时读取；修改后必须重新生成快照。未提供时前端只显示节次，不编造作息时间。

## 六个学校系统的坑

金智 CAS 登录需要 AES-CBC/PKCS7 加密，树维 EAMS 返回的是 JavaScript，不是正方系统的接口。

| 坑 | 处理位置与原则 |
|---|---|
| 多套登录表单 ID 重复，首个 `cllt` 可能属于生物识别 | `login_page.py` 固定 `cllt=userNameLogin`、`dllt=generalLogin` |
| `startWeek=1` 只返回第 1 周 | `course.py` 传空串取整学期；不传会导致失败的 `project.id` |
| `ids` 不是学号 | 从课表页 JS 现场提取内部学生记录 ID |
| 周次位图容易偏移一周 | 下标 i 就是第 i 周，第 0 位只占位，不加 1 |
| 落格索引容易偏移一节 | 星期与节次均从 0 开始，索引为 `星期 * unitCount + 节次` |
| CAS 重定向到不通的 HTTP 80 端口 | `auth_http.ThrottledAdapter` 将学校认证主机请求提升为 HTTPS |

这些约定来自既有学校实测记录与对应代码。请求间隔、Cookie domain/path 和旧版 urllib3 重试参数兼容同样不能随意删除。
教学周起始日需按校历或调课通知维护；空白周可能是实训周，不能用来反推开学日。

## 维护与验证

运行 `python -m unittest discover -s tests -v`、`python -m compileall -q snut scripts tests`、
`node --check web/app.js` 与 `node tests/js/ui-selftest.js`。
离线测试通过后，涉及学校行为的验证应另行在授权范围内低频执行，不能把单元测试等同于学校在线可用性。

界面规格见 [DESIGN.md](DESIGN.md)，入门与配置见 [README](../README.md)，
部署见 [邮件运维](../DEPLOY.md) 和 [网站运维](../DEPLOY-WEB.md)。

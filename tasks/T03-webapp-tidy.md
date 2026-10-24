# T03：整理 snut/webapp.py（429 行）并补测试

先读 `tasks/COMMON.md`。

## 目标

`webapp.py` 里混着：令牌签发/校验、登录失败锁定、客户端 IP 解析、安全头中间件、index 渲染（OG 标签）、API 路由。理清分层、补上测试，使其行为不变但可维护。

## 范围（只允许动这些）

- `snut/webapp.py`
- 可新增 `snut/web_security.py`（令牌、锁定、IP 解析等纯逻辑）等少量模块——**这些新模块和 webapp 一样，绝不能 import `snut.auth` / `snut.course` / `snut.captcha`**（项目边界：网站进程里没有学号密码，不碰学校系统）
- 新增 `tests/test_webapp_*.py`、`tests/test_web_security.py`

不要改 `web/` 前端，不要改 `snut/` 其它文件。

## 必须做

1. 先测后改。纯逻辑部分直接单测：
   - `issue_token` / `verify_token`：正确令牌通过；篡改、过期、错误 secret 被拒；用注入的 `now` 控制时间，不真等。
   - 登录锁定：连续失败达到阈值后 `_lockout_remaining` > 0，窗口过后解除；不同 IP 互不影响。
   - `_client_ip`：直连与经反代头（以现有实现为准，写清楚被信任的头是哪个）。
2. 路由层测试：若环境已装 `fastapi` 与 `httpx`（先 `python -c "import fastapi, httpx"` 检查）就用 `fastapi.testclient.TestClient`；否则这部分测试用 `unittest.skipUnless` 跳过，并在报告说明。覆盖：`/healthz`、`/robots.txt`、`/api/...` 无令牌返回 401、错误密码登录失败与锁定、`timetable` 读取临时目录里的合成 JSON 快照、`index` 返回 200 且含 OG 标签、noindex 头存在。配置通过构造内存 `Config`/临时目录注入，**不要读真实 `.env` 与 `data/`**。
3. 重构：把纯安全逻辑从路由文件中分出；统一重复代码；确保 `webapp.py` 的 `app` 对象和 `uvicorn snut.webapp:app` 启动方式不变；所有 HTTP 路径、状态码、响应体字段、头不变。
4. 在报告里明确列出你发现的任何安全隐患（比较令牌用的是否常量时间比较、锁定表是否会无限增长、反代头是否可伪造等）——只报告，不要擅自改变安全语义；确属明显 bug 且修复不改变正常行为的（如常量时间比较）可以修，并在报告注明。

## 验收

- 全部测试 + compileall 绿
- `grep -nE "snut\.(auth|course|captcha)|from \.(auth|course|captcha)" snut/webapp.py snut/web_security.py` 无输出
- `git diff --stat` 只有范围内文件

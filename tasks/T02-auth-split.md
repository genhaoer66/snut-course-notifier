# T02：拆分 snut/auth.py（639 行，LoginClient 单类约 480 行）

先读 `tasks/COMMON.md`。

## 目标

`LoginClient` 把「HTTP 会话/限速/重试」「密码加密」「登录页解析」「CAS 提交与重定向」「会话持久化与静默 SSO」全揉在一个类里。把它拆成职责清晰的小单元，让每块可单独测试。

## 范围（只允许动这些）

- `snut/auth.py`（保留为对外门面：`AuthError`、`CaptchaRequired`、`LoginClient`、`encrypt_password`、`ThrottledAdapter` 等现有公开名字必须仍可 `from snut.auth import ...`）
- 可新增 `snut/` 下的新模块（例如 `snut/http.py`、`snut/session_store.py`、`snut/login_page.py`，命名由你定，但要少而清晰，不要为拆而拆）
- 新增 `tests/test_auth_*.py`、`tests/fixtures/` 下合成 HTML

不允许改 `snut/` 下除 auth 及新增模块以外的文件；`scripts/`、`snut/course.py`、`snut/main.py` 里对 `snut.auth` 的现有用法不能被破坏（用 grep 找出所有调用点，确保接口兼容；`compileall` 要过）。

## 必须做

1. 先为可纯函数化的部分补测试再拆，至少覆盖：
   - `encrypt_password`：固定 salt 与随机前缀被 patch 后，输出可用 AES-CBC 解回明文（若依赖库不可用，则测试中 skip，并在报告说明）。
   - 登录页解析：用**合成** HTML（虚构，含 4 套表单、重复 `id="cllt"`）验证：必须使用硬编码 `cllt="userNameLogin"`、`dllt="generalLogin"`，而不是 HTML 里第一个 `cllt`（坑 #1）。
   - `ThrottledAdapter`：authserver 的 `http://` 请求被提升为 `https://`（坑 #6）；最小请求间隔生效（patch `time.sleep`/`time.time`，不要真的睡）。
   - 会话持久化：`save_session` 连 domain 一起存，读回后 Cookie 可发出（坑：不存 domain 会失效）。用临时目录。
2. 在此保护下拆分 `LoginClient`，使三层会话策略（复用 cookie → 静默 SSO → 完整登录）在代码里一眼可见；重复的重定向跟随/错误判定逻辑去重。
3. 不改任何请求的 URL、参数、头、顺序、间隔；不改日志级别语义。

## 验收

- `python -m unittest discover -s tests -v`、`compileall` 全绿
- `git diff --stat` 里没有范围外文件
- `from snut.auth import AuthError, CaptchaRequired, LoginClient, encrypt_password` 仍然可用，且 `scripts/*.py` 里引用的名字都还在
- 测试里无真实学号/密码/姓名

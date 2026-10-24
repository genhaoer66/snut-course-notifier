# T04：config / notify / main / formatter 补测试并清理

先读 `tasks/COMMON.md`。

## 目标

这几个模块是日常 7:00 推送的主干，几乎没有测试。先补测试，再做小范围、低风险的清理。

## 范围（只允许动这些）

- `snut/config.py`、`snut/notify.py`、`snut/main.py`、`snut/formatter.py`、`snut/snapshot.py`
- 新增 `tests/test_config.py`、`tests/test_notify.py`、`tests/test_main.py`，可扩充现有 `tests/test_formatter.py`、`tests/test_snapshot.py`

不要改 `snut/auth.py`、`snut/course.py`、`snut/webapp.py`、`snut/captcha.py`（并行任务在改）。

## 必须做

1. `config`：用 `unittest.mock.patch.dict(os.environ, ..., clear=True)` 隔离环境（并确保不会读到真实 `.env`：先查看 config 如何加载 `.env`，测试里要能关掉/重定向，必要时给 `get_config` 增加一个不改变默认行为的可选参数）。覆盖：必填缺失抛 `ConfigError`；`_get_int/_get_float/_get_bool` 的合法与非法值；默认值；`SEMESTER_START` 解析。
2. `notify`：patch `smtplib` 与 `requests`，验证 `send_mail` 的收发件人、主题、SSL/端口选择；`send_serverchan` 的请求参数；`push` 在多通道中一个失败时的行为（`raise_on_error` 开/关）；`send_alert` 不泄漏密码/授权码。不发真实网络。
3. `main`：`resolve_week`（含 `--week` 覆盖、开学前、学期中），`build_parser` 的参数；`main()` 在 `--dry-run` 下用 patch 掉登录/抓取/推送的假对象跑通一遍，断言**没有**调用真实推送、**有**产出文本。
4. `formatter`：补周课表/日课表的文本与 HTML 断言（用合成 `CourseTable`，可从 `snut.course` 构造 `Activity`），以及 `current_week_from_start` 的边界（周日→周一的进位、开学前）。HTML 里课程名等字段要验证已转义。
5. `snapshot`：脱敏字段断言（不含教师以外之外的敏感字段——先看实现里"公开字段"的定义，按它断言），原子写入（写入中途失败不留下半截文件，若实现未做原子写则只报告）。
6. 清理（仅在上面测试保护下）：消除这些模块内的重复代码、无用 import、过长函数；不改文案、不改推送内容格式、不改 CLI。

## 验收

- 全部测试 + compileall 绿
- `git diff --stat` 只有范围内文件
- 推送文本/HTML 的输出对同一输入与重构前逐字相同（用重构前先固化的期望值断言）

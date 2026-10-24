# 所有任务通用约束（每份任务单都隐含包含本文件）

开始前先读 `AGENTS.md`（尤其「六个必须记住的坑」和「webapp 不得 import 碰学校系统的模块」）。

1. **行为保持**：这是重构，不是改功能。对外行为、公开函数/类名、CLI 参数、HTTP 接口、`data/timetable.json` 格式都不变。
2. **不碰外部**：不读 `.env`、`.session/`、`data/`、`logs/`；不运行 `snut.main` 和 `scripts/` 下任何脚本；不发网络请求；不 ssh。需要配置时在测试里用内存/临时目录构造。
3. 标准库 `unittest`（CI：`python -m unittest discover -s tests`）；兼容 Python 3.8（无 `match`、无 `X | Y` 类型、无 `removeprefix`）。`requirements*.txt` 与 CI 配置不改。
4. **只改本任务「范围」列出的文件**。其它文件有人并行修改，禁止触碰。禁止 git add / commit / stash / checkout / reset。
5. 每个文件被改动之前，若涉及重构，先确保有测试覆盖该行为（没有就先补测试，再重构）。
6. 默认不写注释，只在原因不显然（踩坑点）时写一行。保留现有代码中记录学校系统坑的注释。
7. 完成前跑：`python -m unittest discover -s tests -v` 与 `python -m compileall -q snut scripts tests`，必须全绿。
8. 写报告 `tasks/<任务号>.report.md`：改了哪些文件、做了什么取舍、测试覆盖了什么、发现的疑似 bug（只报告，不顺手修）、没做到的事。报告要简洁。

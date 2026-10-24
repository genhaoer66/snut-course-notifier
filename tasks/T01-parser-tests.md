# T01：为课表解析器补回归测试（只加测试，不改业务代码）

## 背景

`snut/course.py` 用正则解析教务系统返回的 JavaScript，是项目里最脆弱、踩坑最多的部分，
目前**完全没有测试**。后续要重构 `config` / `auth` / `course`，需要先有这张安全网。

开始前先读：`AGENTS.md`（尤其「六个必须记住的坑」）、`snut/course.py` 全文、
`tests/test_snapshot.py`（了解现有测试风格）。

## 范围

只允许新增：

- `tests/fixtures/course_table_sample.js` —— **合成**的接口响应样本
- `tests/test_course_parser.py`

**不允许修改** `snut/` 下任何文件、`requirements*.txt`、CI 配置。

## 硬性约束

1. 用标准库 `unittest`（CI 跑的是 `python -m unittest discover -s tests`），不要引入 pytest。
2. 兼容 Python 3.8（不要用 `match`、`X | Y` 类型写法、`str.removeprefix` 等）。
3. fixture 必须是**虚构数据**：课程名用「示例课程A」之类，教师用「教师甲」，教室用「101」。
   **不要**读取 `.env`、`.session/`、`data/`、`logs/`，不要运行 `snut.main`、`scripts/` 下任何脚本，
   不要发起任何网络请求。测试只用 fixture 和内存数据。
4. fixture 的格式照 `snut/course.py` 顶部模块文档字符串里的示例，并对照 `_ACTIVITY_RE`、
   `_INDEX_RE`、`_UNIT_COUNT_RE` 确保真的能被解析（先自己跑通再写断言）。
5. 如果发现 `course.py` 有 bug：**不要修**，把现象、复现方式写进报告，并用
   `@unittest.expectedFailure` 标出对应测试。

## 必须覆盖的用例

fixture 至少包含这些情形（可拆成多个小 fixture 字符串内联在测试里）：

1. **周次位图下标就是周次**：位图 `"0110000000000000000000"` 应解析为 `weeks == [1, 2]`，
   不是 `[2, 3]`。第 0 位即使为 `'1'` 也不算周次。
2. **落格索引**：`index = 星期*unitCount + 节次`，星期、节次均从 0 开始。
   例如 `index = 2*11+4` → `day == 2`（周三），`units == [4]`；同一课程连续两格应合并为 `units == [4, 5]`。
3. **合并**：同名、同教室、同教师、同星期、同节次、周次不同的两条记录，合并后 `weeks` 为并集。
   教室或教师不同则**不**合并。
4. **跳过**：位图全 0 的记录、没有落格语句的记录、课程名为空的记录，都不产生 `Activity`。
5. **教师**：多个教师用「、」连接；`var teachers = []` 时 `teachers == ""`。
6. **`unitCount`**：缺省为 11；fixture 里写了其它值时应读取。
7. **`CourseTable.on_day`**：按节次升序；传 `week` 时只返回该周有课的。
8. **`_compress_ranges` 与 `Activity` 展示属性**：`[5,6,7,9,10]` → `"5-7,9-10"`；
   `unit_text` 单节为 `"3"`、多节为 `"5-6"`；`room` 为空时 `room_text == "待定"`。
9. **`_pick_semester`**：给定含多个学期的文本，验证选最新学年；用 `unittest.mock.patch`
   固定 `datetime.date.today()`（注意 `course.py` 里是 `import datetime`，patch 目标要写对），
   分别验证 3 月选第二学期、10 月选第一学期。

## 验收标准（我会逐条检查）

- [ ] `python -m unittest discover -s tests -v` 全部通过（`expectedFailure` 除外）
- [ ] `git diff --stat` 显示 `snut/` 下零改动
- [ ] fixture 和测试里没有真实姓名、学号、真实课程名
- [ ] 每条「必须覆盖」都有对应测试，且断言的是具体值，不是「不报错」
- [ ] 测试之间互不依赖，能单独运行

## 完成后

在 `tasks/T01-parser-tests.report.md` 写：改了哪些文件、每条用例对应哪个测试、
发现的疑似 bug（没有就写「无」）、你没能做到的事。

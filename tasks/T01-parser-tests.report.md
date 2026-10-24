# T01 课表解析器回归测试报告

## 文件变更

本任务仅新增以下三个文件（第三个为任务要求的报告）：

- `tests/fixtures/course_table_sample.js`：虚构的 JavaScript 响应，含显式 `unitCount = 12`、连续落格、多教师、空教师列表及空教室。
- `tests/test_course_parser.py`：28 个标准库 `unittest` 测试；其余场景使用内联合成响应及内存对象。
- `tasks/T01-parser-tests.report.md`：本报告。

未修改任何业务代码、依赖或 CI 配置。已先单独解析文件 fixture，确认得到 2 条预期记录后再添加断言。

## 必须覆盖用例与测试对应关系

下表测试方法均位于 `tests/test_course_parser.py`。

| 要求 | 测试方法 | 具体断言 |
| --- | --- | --- |
| 1. 周次位图下标 | `CourseParserTests.test_week_bitmap_indices_are_week_numbers`；`test_week_zero_is_ignored_even_when_set` | 指定完整位图解析为 `[1, 2]`；第 0 位设为 1 仍为 `[1, 2]`，仅第 0 位为 1 时无排课。 |
| 2. 落格索引及连续节次 | `CourseParserTests.test_single_cell_uses_zero_based_day_and_unit`；`test_first_day_and_first_unit_are_zero`；`test_consecutive_cells_form_one_activity_in_unit_order`；`test_cells_on_different_days_form_separate_activities` | `2*unitCount+4` 得到 `(2, [4])`；首日首节为 `(0, [0])`；倒序输入连续格得到 `(2, [4, 5])`；不同星期分别生成记录。 |
| 3. 合并规则 | `CourseParserTests.test_matching_records_merge_sorted_week_union`；`test_different_rooms_do_not_merge`；`test_different_teachers_do_not_merge`；`test_other_merge_key_fields_must_match` | 相同键仅留 1 条，重叠周次取排序去重并集 `[1, 2, 3]`；教室、教师、课程名、星期、节次不同均保留 2 条，各自周次不串联。 |
| 4. 跳过无效记录 | `CourseParserTests.test_all_zero_bitmap_is_skipped`；`test_record_without_placement_is_skipped`；`test_empty_or_whitespace_course_name_is_skipped`；`test_skipped_blocks_do_not_borrow_neighbor_cells` | 各类无效块均得到空列表；与正常块混排时只留下正常块的名称、周次、星期和节次。 |
| 5. 教师 | `CourseParserTests.test_multiple_teachers_are_joined_with_separator`；`test_empty_teacher_array_produces_empty_string` | 多教师严格为 `教师甲、教师乙`；空数组严格为 `""`。 |
| 6. unitCount | `CourseParserTests.test_unit_count_defaults_to_eleven`；`test_explicit_unit_count_is_read`；`test_file_fixture_parses_exact_records` | 缺省为 11；显式为 13 时读取 13 并保留第 12 个零基节次；文件 fixture 为 12。 |
| 7. on_day | `CourseTableTests.test_on_day_sorts_by_unit_and_excludes_other_days`；`test_on_day_filters_week_and_keeps_unit_order` | 乱序添加后严格按 `[0, 1]`、`[4, 5]`、`[8, 9]` 排序；第 1、2 周分别返回对应课程名列表，排除其它星期，无课时为空列表。 |
| 8. 展示属性 | `ActivityDisplayTests.test_compress_ranges`；`test_unit_text_converts_zero_based_units`；`test_room_text_handles_empty_room`；`test_week_text_weekday_name_and_on_week` | 指定周次压缩为 `5-7,9-10`；也验证乱序去重、空列表及单值；单节为 `3`，多节为 `5-6`，空教室为 `待定`；验证周次文本、星期及周次成员判断。 |
| 9. 学期选择 | `PickSemesterTests.test_march_selects_second_term_of_latest_year`；`test_october_selects_first_term_of_latest_year`；`test_no_semester_entries_returns_none` | 最新学年放在文本中间；patch `snut.course.datetime.date` 并固定 `today()`，3 月选最新学年第二学期 ID 22，10 月选第一学期 ID 21；无条目返回 `None`。 |

`test_file_fixture_parses_exact_records` 还逐字段核对文件 fixture 的两条完整记录，包括课程代码、名称、教师、教室、周次、星期和节次。

## 验收结果

- 本地实际运行版本：Python 3.8.6。
- `python -m unittest discover -s tests -v`：32 个测试全部通过（新增 28 个、原有 4 个），无失败、跳过或 expected failure。运行时设置 `PYTHONDONTWRITEBYTECODE=1`，避免生成字节码文件。
- 将新增的 28 个测试各自在独立 Python 子进程中以完整测试 ID 运行：28/28 通过；每次重新加载模块及测试状态，不依赖其它测试先运行。
- `git diff --check` 通过。
- fixture 和新增测试仅使用 `示例课程A/B/C/D`、`教师甲/乙`、虚构代码和教室；没有真实姓名、学号或真实课程名。
- 未读取 `.env`、`.session/`、`data/`、`logs/`；未执行 `snut.main` 或 `scripts/` 中任何脚本；未发起网络请求。现有快照测试仅在临时目录使用自建数据。
- 开始和结束时比对 `snut/` 顶层所有文件的 SHA256，以及完整已有 tracked diff，均一致，本任务对 `snut/` 的增量为零。

## 疑似 bug

无。本次覆盖场景均符合预期，无需使用 `@unittest.expectedFailure`。

## 未能做到的事及工作区说明

本任务实现及测试验收无未完成项。

全工作区的 `git diff --stat` 无法显示 `snut/` 绝对零改动：开始执行前已存在 `snut/webapp.py` 的未提交修改（65 行涉及变动，60 增 5 删），以及 `web/index.html` 的既有修改和其它未跟踪文件。本任务完整保留这些既有内容，未回滚或混入本任务；前后比对证明既有 diff 和 `snut/` 文件内容均未变化。

新增文件保持未跟踪状态，没有执行 `git add` 或提交，因此普通 `git diff --stat` 不列出它们；本任务文件清单见上文。

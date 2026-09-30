# 部署说明（Linux 服务器）

下面是以 Debian / Ubuntu 系服务器为例的部署流程，其它发行版同理。

| 项目 | 值 |
|---|---|
| 服务器 | 你的 Linux 服务器 |
| 项目目录 | `/opt/course-notifier` |
| Python | `.venv/bin/python`（3.13，虚拟环境） |
| 定时任务 | 每天早上 **7:00**（crontab） |
| 日志 | `/opt/course-notifier/logs/cron.log` 与 `course.log` |
| 时区 | Asia/Shanghai（+0800），与本地一致 |

---

## 日常运维

### 查看运行日志

```bash
ssh root@<SERVER_HOST>
tail -50 /opt/course-notifier/logs/cron.log      # 定时任务输出
tail -50 /opt/course-notifier/logs/course.log    # 程序运行日志
```

### 手动跑一次（验证是否正常）

```bash
ssh root@<SERVER_HOST>
cd /opt/course-notifier
.venv/bin/python -m snut.main --dry-run    # 只打印不推送
.venv/bin/python -m snut.main              # 真推送
```

### 修改推送时间

```bash
crontab -e
```

格式是 `分 时 * * *`。`0 7 * * *` 表示每天早上 7:00。

> 💡 **建议避开整点**（如 `0 7`）。学校服务器在整点前后负载高，且容易被风控注意到。
> 想改成 7 点左右，可以用 `43 6` 或 `52 6`。

### 查看定时任务是否在跑

```bash
crontab -l
grep -i snut /var/log/syslog | tail -20
```

---

## 更新代码

改完本地代码后，从 Windows 上执行：

```bash
cd /path/to/course-notifier
SNUT_SSH_HOST='<服务器地址>' SNUT_SSH_PASS='<服务器密码>' python scripts/remote.py "!ls -la"
```

若需要重新上传，参照 `scripts/remote.py` 的写法用 paramiko 的 `sftp.put`，
**注意把 Windows 路径的 `\` 换成 `/`**（否则文件会以 `snut\auth.py` 这种
名字落在根目录，而不是进入子目录）。

上传后需要重启什么吗？**不需要**——crontab 每次都是全新执行，
下次运行自动用新代码。

---

## 排查常见问题

| 现象 | 排查方向 |
|---|---|
| 早上没收到邮件 | 看 `logs/cron.log` 有无报错；确认机器是否在运行 |
| 日志里有「请不要过快点击」 | 调大 `.env` 里的 `REQUEST_INTERVAL` |
| 日志里有「需要图形验证码」 | 看 `logs/` 下的 `debug_login_failed.html`；OCR 偶发失败会自动重试 3 次 |
| 课表为空 | 学期 id 可能变了，跑 `scripts/debug_course.py` 看当前值 |
| 想确认程序还活着 | 看 `logs/course.log` 的修改时间 |

### 手动登录（OCR 连续失败时的兜底）

```bash
cd /opt/course-notifier
.venv/bin/python scripts/captcha_login.py fetch
# 把 logs/captcha_sample.png 下载下来看图
.venv/bin/python scripts/captcha_login.py submit <验证码>
```

---

## 安全事项

1. 强烈建议使用 **SSH 密钥登录**并关闭密码登录，不要用密码登录公网服务器。
2. `/opt/course-notifier/.env` 权限设为 `600`（仅 root 可读），
   其中存有学号、教务系统密码、邮箱授权码，泄露等同于账号泄露。
3. `.session/cookies.json` 等同于登录凭证，同样只留在服务器上、不要外传。
4. 安全组只放行必要端口（22/443）；网站的 8000 端口**不要**对公网开放。

---

## 换学期要改什么

只需要改一处——`.env` 里的开学日期：

```bash
nano /opt/course-notifier/.env
# SEMESTER_START=2026-08-31   ← 改成新学期第 1 周的周一
```

推算方法：**当前周次**和**当天日期**反推。
例如 2026-09-21 是第 4 周周一，则第 1 周周一 = 09-21 往前推 21 天 = 08-31。

> 教务系统没有提供「本学期第 1 周从哪天开始」的接口
> （实测 `schoolCalendar!search.action` 返回 404），所以这一项需要手工维护，
> 但一学期只需改一次。

# 课表网站 —— 部署说明

> 邮件推送那部分的运维见 `DEPLOY.md`。本文只讲网站。

---

## 架构

```
[每天 7:00 cron]  python -m snut.main
                      │
                      ├──> 发邮件到手机     （原有功能，没变）
                      └──> 写 data/timetable.json   （新增，脱敏后的快照）
                                  │
[systemd 常驻]   uvicorn 127.0.0.1:8000  ── 只读这个 JSON
                                  │
[cloudflared]    主动出站隧道 ──> Cloudflare 边缘 ──> https://example.com
```

**一次抓取，两个产物。** 网站**完全不碰学校教务系统**——同学怎么刷新都不会
给学校增加一次请求，学校风控、改版、限流也都波及不到网站。

> 💡 **crontab 不用改。** 原来的 `python -m snut.main` 现在会顺手写快照，
> 不需要新增定时任务。

### 为什么走 Cloudflare Tunnel

服务器是**大陆**节点，域名未 ICP 备案（Cloudflare 注册的域名无法备案），
80/443 会被云厂商在网络层拦截，域名解析过去也打不开。

Tunnel 让服务器**主动往外连** Cloudflare，不需要开放任何入站端口：
绕开端口封锁、免费自动 HTTPS、还顺带隐藏了源站 IP。

---

## 一次性部署

### 第 1 步：服务器上装依赖

```bash
ssh root@<SERVER_HOST>
cd /opt/course-notifier
.venv/bin/pip install fastapi uvicorn
```

### 第 2 步：上传新代码

从 Windows 本地执行（需要服务器密码）：

```bash
cd /path/to/course-notifier
SNUT_SSH_HOST='<服务器地址>' SNUT_SSH_PASS='<服务器密码>' python scripts/remote.py "!ls -la"
```

需要上传的文件：

| 新增 | 说明 |
|---|---|
| `snut/snapshot.py` | 课表快照的脱敏与读写 |
| `snut/webapp.py` | 网站后端 |
| `web/` | 前端（index.html / app.js / style.css） |
| `deploy/course-web.service` | systemd 服务单元 |

| 修改 | 说明 |
|---|---|
| `snut/config.py` | 新增 `web_password` / `data_dir` |
| `snut/main.py` | 抓完顺手存快照 |

> ⚠️ 用 paramiko 的 `sftp.put` 上传时，**注意把 Windows 路径的 `\` 换成 `/`**，
> 否则文件会以 `snut\auth.py` 这种名字落在根目录，而不是进子目录。

### 第 3 步：起网站服务

```bash
cp /opt/course-notifier/deploy/course-web.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now course-web

systemctl status course-web          # 应为 active (running)
curl -s http://127.0.0.1:8000/healthz
```

`healthz` 返回里 `has_snapshot: false` 说明还没抓过课表——手动跑一次：

```bash
cd /opt/course-notifier && .venv/bin/python -m snut.main --dry-run
# --dry-run 只打印不发信，但同样会写快照
```

> ⚠️ **服务必须绑 `127.0.0.1`，不要改成 `0.0.0.0`。** 公网入口交给隧道，
> 源站不开放任何入站端口——别人扫到 8000 也连不上。

### 第 4 步：装 cloudflared

```bash
# 用 Cloudflare 官方 APT 源，能跟着系统自动更新
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null

echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list

sudo apt update && sudo apt install -y cloudflared
cloudflared --version
```

### 第 5 步：Cloudflare 后台建隧道（图形操作）

1. 打开 <https://one.dash.cloudflare.com>
2. 左侧 **Networks → Tunnels** → **Create a tunnel**
3. 选 **Cloudflared**，起个名字（比如 `snut-web`），保存
4. 在隧道详情页找到安装命令，**复制其中的 token**（一长串 `eyJ...`）
5. 到 **Public Hostname** 标签页，**Add a public hostname**：

   | 字段 | 填什么 |
   |---|---|
   | Subdomain | 留空（用根域名） |
   | Domain | `example.com` |
   | Type | `HTTP` |
   | URL | `127.0.0.1:8000` |

   Cloudflare 会自动建好 DNS 的 CNAME 记录，HTTPS 证书也是自动签的。

### 第 6 步：把 token 装到服务器

```bash
sudo cloudflared service install <粘贴 token>
systemctl status cloudflared         # 应为 active (running)
journalctl -u cloudflared -n 30      # 看连接日志
```

隧道状态在 Cloudflare 后台应该显示 **Healthy**。

### 第 7 步：验证

```bash
# 服务器上
curl -s http://127.0.0.1:8000/healthz

# 你自己的电脑上
curl -I https://example.com
# 应看到 server: cloudflare 和 cf-ray 头，说明流量走了 Cloudflare

curl -s https://example.com/robots.txt
```

最后用**手机浏览器**打开 <https://example.com> 实测一遍。

---

## 日常运维

```bash
systemctl status course-web                  # 网站进程
systemctl restart course-web                 # 改完代码重启
journalctl -u course-web -n 50 -f            # 实时日志

systemctl status cloudflared                 # 隧道进程
journalctl -u cloudflared -n 50              # 隧道日志

crontab -l                                   # 抓取任务（没动过）
tail -50 /opt/course-notifier/logs/course.log
```

### 手动更新一次课表数据

```bash
cd /opt/course-notifier && .venv/bin/python -m snut.main --dry-run
```

`--dry-run` 只打印不发信，但**同样会更新网站的课表快照**。

### 网站显示的还是旧数据？

页脚会显示「数据更新于 X月X日 HH:MM」。如果那不是今天，说明当天抓取失败了：

```bash
tail -50 /opt/course-notifier/logs/cron.log
```

抓取失败时**网站会继续显示旧快照**（这是有意设计——宁旧不空），
所以不会白屏，但页脚会标黄提醒。修好抓取后网站自动恢复。

---

## 换学期要改什么

和原来一样，只改 `SEMESTER_START`：

```bash
nano /opt/course-notifier/.env
# SEMESTER_START=2026-08-24   ← 改成新学期第 1 周的周一
systemctl restart course-web   # 改完重启一下，让网站拿到新值
```

> ⚠️ **这个日期算错一周，网站默认显示的就是上一周的课。**
> 推算方法见 `DEPLOY.md`，或看下面「如何验证开学日期对不对」。

### 如何验证开学日期对不对

**别靠"哪几周空着"来猜。** 课表里空白的周可能是**实训周**
（集中实践环节，全校不上常规课），不是假期。2026 秋季学期的下标 1–3
和第 7 周就是这样，很容易被误认成假期从而算错一周。

**正确做法：拿学校自己的调课通知来对。** 通知会写明「某日补某日的课」，
括号里标出那天属于第几周：

> 砺志书院 2026 通知：「9月20日（周日）上 **10月6日（第六周星期二）** 的课」

10月6日是周二且在第六周 → 第六周 = 10-05~10-11 → 第一周周一 = `2026-08-31`。

**校方口径 > 任何推算。** 找不到通知时，直接问班里同学「今天第几周」，
或者看教务系统里正在上的课对得上哪一周。

---

## 可选：显示每节课的起止时间

教务系统**不提供**作息时间表（接口实测不存在），所以默认只显示「第 5-6 节」，
不显示 `14:00-15:40`。

要显示的话，在服务器上建一个 `data/periods.json`：

```json
[
  ["08:00", "08:45"],
  ["08:50", "09:35"],
  ["10:05", "10:50"],
  ["10:55", "11:40"],
  ["14:00", "14:45"],
  ["14:50", "15:35"],
  ["16:05", "16:50"],
  ["16:55", "17:40"],
  ["19:00", "19:45"],
  ["19:50", "20:35"],
  ["20:40", "21:25"]
]
```

数组下标对应节次（0 = 第 1 节），共 11 项。改完刷新页面即可，**不用重启服务**。

> 没有这个文件时，网站的课程详情里**不显示时间**——而不是填一个编的时间。
> 同学照着错时间去了教室才是真的耽误事。

---

## 安全设计

| 风险 | 措施 |
|---|---|
| 学号 / 内部 ids 泄漏 | `snut/snapshot.py` **白名单**导出字段，从源头排除 |
| 外人查看课表 | `.env` 里的 `WEB_PASSWORD`（留空则完全公开） |
| 搜索引擎收录 | 响应头 `X-Robots-Tag: noindex` + HTML meta + robots.txt 挡 AI 爬虫 |
| 源站 IP 暴露 | Cloudflare Tunnel 出站连接，服务器零入站端口 |
| 8000 端口被扫 | 服务只监听 `127.0.0.1` |
| 快照被他人读取 | `data/timetable.json` 权限 `600` |
| 暴力猜口令 | 同 IP 连续错 8 次锁定 5 分钟 |

### 关于反收录的一个反直觉之处

`robots.txt` 里的 `Disallow` **挡不住收录**，它只挡爬取。被 disallow 的网址
照样可能出现在搜索结果里（只显示一个空壳 URL）。

真正能拒绝收录的是 `noindex`，而它**必须让爬虫抓得到页面才能读到**。
所以本站的 `robots.txt` **故意不写 `Disallow: /`**——写了反而会让爬虫
读不到我们的 `noindex` 头，两个指令打架。

同时，`robots.txt` 里点名挡掉了 GPTBot / ClaudeBot / Bytespider 等
拿数据做训练的 AI 爬虫。

### 部署后自查

```bash
cd /opt/course-notifier
grep -rn "SNUT_PASSWORD\|SMTP_AUTH_CODE\|CASTGC\|jwgl\.snut\|authserver" data/ web/ \
  && echo "!!! 有泄漏，立刻处理" || echo "OK 干净"
```

---

## 排查

| 现象 | 排查方向 |
|---|---|
| 域名打不开 | `systemctl status cloudflared`；Cloudflare 后台隧道是否 Healthy |
| 502 / 1033 | 隧道通了但源站没起：`systemctl status course-web` |
| 打开是空白页 | 看浏览器控制台；确认 `/static/app.js` 能加载 |
| 页面显示「课表数据还没生成」 | 快照没生成，跑一次 `python -m snut.main --dry-run` |
| 页脚时间是旧的且标黄 | 当天抓取失败，看 `logs/cron.log` |
| 周次显示不对 | `SEMESTER_START` 算错了，见上文 |
| 忘记口令 | 改 `.env` 里的 `WEB_PASSWORD` 后 `systemctl restart course-web` |
| 想临时关掉口令 | `.env` 里 `WEB_PASSWORD=` 留空，重启服务 |

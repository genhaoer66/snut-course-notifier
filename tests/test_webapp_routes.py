import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


HAS_WEB = all(importlib.util.find_spec(name) is not None
              for name in ("fastapi", "httpx"))
if HAS_WEB:
    from fastapi.testclient import TestClient

    with patch("dotenv.load_dotenv"):
        from snut import webapp
        from snut.config import Config, ConfigError


@unittest.skipUnless(HAS_WEB, "需要已安装 fastapi 和 httpx；不安装依赖、不访问网络")
class WebappRoutesTests(unittest.TestCase):
    def setUp(self):
        folder = self._tempdir()
        root = Path(folder)
        self.config = Config.__new__(Config)
        self.config.data_dir = root
        self.config.web_dir = root
        self.config.web_password = "shared-secret"
        self.config.semester_start = datetime.date(2026, 8, 31)
        self.snapshot = {
            "updated_at": "2026-10-24 07:00", "updated_ts": 1792796400,
            "semester_start": "2026-08-31", "unit_count": 11,
            "periods": None, "current_week": -100,
            "courses": [{"name": "测试课程", "teachers": "教师", "room": "A101",
                         "day": 0, "units": [0, 1], "weeks": [8, 9]}],
        }
        self.snapshot_path = root / "timetable.json"
        self.snapshot_path.write_text(json.dumps(self.snapshot), encoding="utf-8")
        (root / "index.html").write_text(
            '<meta property="og:url" content="{OG_BASE}/">'
            '<meta property="og:image" content="{OG_BASE}/static/share.png">'
            '<!-- {OG_BASE} -->', encoding="utf-8")
        config_patch = patch.object(webapp, "get_config", return_value=self.config)
        config_patch.start()
        self.addCleanup(config_patch.stop)
        env_patch = patch.dict("os.environ", {"SNUT_OG_BASE": "https://example.test/"})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        webapp._failures.clear()
        self.addCleanup(webapp._failures.clear)
        self.client = TestClient(webapp.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def _tempdir(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return folder.name

    def assert_noindex(self, response):
        self.assertEqual(response.headers["x-robots-tag"], webapp.NOINDEX_HEADER)

    def test_health_and_robots(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True, "has_snapshot": True, "updated_at": self.snapshot["updated_at"],
            "courses": 1, "auth": True,
        })
        self.assert_noindex(response)
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn("User-agent: GPTBot\nDisallow: /", response.text)
        self.assertIn("User-agent: *\nDisallow:\n", response.text)
        self.assert_noindex(response)

    def test_timetable_auth_and_synthetic_snapshot(self):
        for method in (self.client.get, self.client.head):
            response = method("/api/timetable")
            self.assertEqual(response.status_code, 401)
            self.assert_noindex(response)
        self.assertEqual(self.client.get("/api/timetable").json(), {
            "error": "需要访问口令", "code": "auth_required"})
        token = webapp.issue_token(self.config.web_password)
        response = self.client.get("/api/timetable", headers={"Authorization": "Bearer " + token})
        self.assertEqual(response.status_code, 200)
        expected = dict(self.snapshot)
        expected.update(current_week=webapp.current_week_from_start(self.config.semester_start),
                        server_today=datetime.date.today().isoformat())
        self.assertEqual(response.json(), expected)
        self.assertEqual(response.headers["cache-control"], "private, max-age=300")
        self.assert_noindex(response)
        self.config.web_password = None
        self.assertEqual(self.client.get("/api/timetable").headers["cache-control"],
                         "public, max-age=600")

    def test_login_failure_lockout_and_success_clears_failures(self):
        with patch("time.time", return_value=1000):
            for _ in range(webapp.MAX_LOGIN_FAILURES):
                response = self.client.post("/api/login", json={"password": "wrong"})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"error": "口令不对", "code": "bad_password"})
                self.assert_noindex(response)
            response = self.client.post("/api/login", json={"password": "shared-secret"})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.json(), {
                "error": "口令错误次数过多，请 301 秒后再试", "code": "locked"})
            self.assert_noindex(response)
            response = self.client.post("/api/login", json={"password": "shared-secret"},
                                        headers={"CF-Connecting-IP": "198.51.100.9"})
            self.assertEqual(response.status_code, 200)
        with patch("time.time", return_value=1301):
            response = self.client.post("/api/login", json={"password": "shared-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(webapp.verify_token(
            "shared-secret", response.json()["token"], now=datetime.date.fromtimestamp(1301)))
        self.assertEqual(webapp._failures, {})
        self.config.web_password = None
        self.assertEqual(self.client.post("/api/login").json(), {"ok": True, "token": None})

    def test_index_og_head_and_cache(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('property="og:image" content="https://example.test/static/share.png"', response.text)
        self.assertIn('property="og:url" content="https://example.test/"', response.text)
        self.assertIn("<!-- {OG_BASE} -->", response.text)
        self.assertEqual(response.headers["cache-control"], "no-cache")
        self.assert_noindex(response)
        head = self.client.head("/")
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b"")
        self.assertEqual(head.headers["content-length"], str(len(response.content)))
        self.assert_noindex(head)
        static = self.client.get("/static/nonexistent-t03-file")
        self.assertEqual(static.status_code, 404)
        self.assertEqual(static.headers["cache-control"], "public, max-age=604800, immutable")
        self.assert_noindex(static)

    def test_missing_snapshot_and_config_error(self):
        self.snapshot_path.unlink()
        self.assertFalse(self.client.get("/healthz").json()["has_snapshot"])
        self.config.web_password = None
        response = self.client.get("/api/timetable")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {
            "error": "课表数据还没生成", "code": "no_data",
            "hint": "服务器上的抓取任务可能尚未运行过"})
        with patch.object(webapp, "get_config", side_effect=ConfigError("synthetic")):
            for path in ("/", "/healthz", "/api/timetable"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.json(), {"error": "服务端配置缺失", "code": "config"})
                self.assert_noindex(response)

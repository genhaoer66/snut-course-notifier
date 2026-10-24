import base64
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import requests

from snut import auth


HTML = '''<html>
<form><input id="cllt" value="fidoLogin"><input id="dllt" value="fido"></form>
<form><input id="cllt" value="smsLogin"></form>
<form><input id="cllt" value="userNameLogin">
<input id="execution" value=" fake-execution ">
<input name="pwdEncryptSalt" value="0123456789abcdef">
<input name="lt" value=" fake-lt "></form>
<form><input id="cllt" value="qrLogin"></form>
<img id="captchaImg"></html>'''


def config(root):
    return SimpleNamespace(
        auth_base="https://auth.example.test/authserver",
        eams_base="https://eams.example.test/eams",
        sso_service_url="https://eams.example.test/eams/ssoLogin.action",
        username="synthetic-user", password="synthetic-password",
        http_timeout=60, request_interval=3,
        session_dir=root / "session", log_dir=root / "logs",
        debug_save_raw=False,
        ensure_dirs=lambda: (root / "logs").mkdir(exist_ok=True),
    )


def response(url="https://eams.example.test/eams/home", text="", status=200):
    return SimpleNamespace(url=url, text=text, status_code=status,
                           apparent_encoding="utf-8", encoding=None,
                           content=b"synthetic-image", raise_for_status=Mock())


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = auth.LoginClient(config(Path(self.tmp.name)))
        self.addCleanup(self.client.session.close)
        blocker = patch.object(requests.Session, "request",
                               side_effect=AssertionError("network forbidden"))
        blocker.start()
        self.addCleanup(blocker.stop)

    def test_encrypt_round_trip(self):
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
        except ImportError:
            self.skipTest("PyCryptodome unavailable")
        with patch.object(auth, "_random_string", side_effect=["A" * 64, "B" * 16]) as random:
            encrypted = auth.encrypt_password("synthetic-password", " 0123456789abcdef ")
        cipher = AES.new(b"0123456789abcdef", AES.MODE_CBC, b"B" * 16)
        self.assertEqual(unpad(cipher.decrypt(base64.b64decode(encrypted)), 16),
                         b"A" * 64 + b"synthetic-password")
        self.assertEqual(random.call_args_list, [call(64), call(16)])
        self.assertEqual(auth.encrypt_password("synthetic-password", ""), "synthetic-password")

    def test_login_page_four_forms_and_captcha(self):
        self.client._request = Mock(return_value=response(text=HTML))
        params, html, captcha = self.client._fetch_login_page("service")
        self.assertEqual(params, dict(execution="fake-execution", lt="fake-lt",
                                     pwdEncryptSalt="0123456789abcdef",
                                     cllt="userNameLogin", dllt="generalLogin"))
        self.assertEqual(html, HTML)
        self.assertFalse(captcha)
        self.client._request.assert_called_once_with(
            "GET", self.client.config.auth_base + "/login", params={"service": "service"})
        self.client._request.return_value = response(text=HTML.replace(
            '<img id="captchaImg">', '<img id="captchaImg" src=" /fake.png ">'))
        self.assertTrue(self.client._fetch_login_page("service")[2])

    def test_broken_and_throttled_page(self):
        self.client._request = Mock(return_value=response(text="请不要过快点击"))
        with self.assertRaisesRegex(auth.AuthError, "限流"):
            self.client._fetch_login_page("service")
        self.client._request.return_value = response(text="<html>synthetic</html>")
        with self.assertRaisesRegex(auth.AuthError, "execution"):
            self.client._fetch_login_page("service")
        self.assertTrue((self.client.config.log_dir / "debug_login_page_broken.html").exists())

    def test_adapter_https_and_interval(self):
        adapter = auth.ThrottledAdapter(3)
        self.addCleanup(adapter.close)
        adapter._last_at = 100
        req = requests.Request("GET", "http://authserver.snut.edu.cn/authserver/login").prepare()
        with patch("requests.adapters.HTTPAdapter.send", return_value="ok") as send, \
                patch("time.time", side_effect=[101, 103]), patch("time.sleep") as sleep:
            self.assertEqual(adapter.send(req, timeout=60), "ok")
        self.assertEqual(req.url, "https://authserver.snut.edu.cn/authserver/login")
        send.assert_called_once_with(req, timeout=60)
        sleep.assert_called_once_with(2)
        self.assertEqual(adapter._last_at, 103)

    def test_adapter_no_sleep_and_exception_timestamp(self):
        adapter = auth.ThrottledAdapter(3)
        self.addCleanup(adapter.close)
        req = requests.Request("GET", "http://example.test/").prepare()
        with patch("requests.adapters.HTTPAdapter.send", side_effect=RuntimeError), \
                patch("time.time", side_effect=[100, 101]), patch("time.sleep") as sleep:
            with self.assertRaises(RuntimeError):
                adapter.send(req)
        sleep.assert_not_called()
        self.assertEqual(req.url, "http://example.test/")
        self.assertEqual(adapter._last_at, 101)

    def test_session_round_trip_domains_paths_and_sending(self):
        self.client.session.cookies.set("CASTGC", "fake-ticket", domain="auth.example.test", path="/authserver")
        self.client.session.cookies.set("JSESSIONID", "fake-session", domain="eams.example.test", path="/eams")
        with patch("time.time", return_value=123):
            self.client.save_session()
        data = json.loads(self.client._session_file.read_text(encoding="utf-8"))
        self.assertEqual(data["host"], "eams.example.test")
        self.assertEqual(data["saved_at"], 123)
        self.assertEqual({c["domain"] for c in data["cookies"]},
                         {"auth.example.test", "eams.example.test"})
        self.client.session.cookies.clear()
        self.assertTrue(self.client.load_session())
        for url, cookie in [(self.client.config.auth_base + "/login", "CASTGC=fake-ticket"),
                            (self.client.config.eams_base + "/home", "JSESSIONID=fake-session")]:
            prepared = self.client.session.prepare_request(requests.Request("GET", url))
            self.assertEqual(prepared.headers["Cookie"], cookie)
        other = self.client.session.prepare_request(requests.Request("GET", "https://other.test/"))
        self.assertNotIn("Cookie", other.headers)

    def test_session_missing_corrupt_legacy_and_invalid_entries(self):
        self.assertFalse(self.client.load_session())
        self.client._session_file.parent.mkdir()
        for content in ["invalid json", '{}', '{"cookies": []}']:
            self.client._session_file.write_text(content, encoding="utf-8")
            self.assertFalse(self.client.load_session())
        for raw in [{"legacy": "fake"}, [{"name": "legacy", "value": "fake"}, {}]]:
            self.client._session_file.write_text(json.dumps({"cookies": raw}), encoding="utf-8")
            self.assertTrue(self.client.load_session())
            self.assertEqual(self.client.session.cookies.get("legacy"), "fake")

    def test_http_defaults_ssl_fallback_and_headers(self):
        self.assertIn("Chrome/131", self.client.session.headers["User-Agent"])
        self.assertIsInstance(self.client.session.get_adapter("https://"), auth.ThrottledAdapter)
        with patch.object(self.client.session, "request", side_effect=[requests.exceptions.SSLError(), "ok"]) as request:
            self.assertEqual(self.client._request("GET", "https://example.test"), "ok")
        self.assertEqual(request.call_args_list, [
            call("GET", "https://example.test", timeout=60, verify=True),
            call("GET", "https://example.test", timeout=60, verify=False)])
        with patch.object(self.client.session, "request", side_effect=requests.exceptions.SSLError()):
            with self.assertRaises(requests.exceptions.SSLError):
                self.client._request("GET", "https://example.test")

    def test_host_and_error_detection(self):
        self.assertFalse(self.client._login_failed(response()))
        self.assertFalse(self.client._login_failed(response(url="https://EAMS.EXAMPLE.TEST/eams/home")))
        self.assertTrue(self.client._login_failed(response(url="https://eams.example.test.other.test/")))
        self.assertTrue(self.client._login_failed(response(url=self.client.config.auth_base +
                                                        "/login?service=" + self.client.config.sso_service_url)))
        for html, expected in [("<div id='msg'>fake error</div>", "fake error"),
                               ("<p>密码错误</p>", "密码错误"), ("<p>unknown</p>", "auth.example.test")]:
            self.assertIn(expected, self.client._extract_error(html, self.client.config.auth_base))

    def test_silent_sso_and_validation(self):
        self.client._request = Mock(return_value=response())
        self.assertTrue(self.client.silent_sso_login())
        self.client._request.assert_called_once_with("GET", self.client.config.auth_base + "/login",
            params={"service": self.client.config.sso_service_url}, allow_redirects=True)
        self.assertTrue(self.client.is_logged_in())
        self.client._request.assert_called_with("GET", self.client.config.eams_base +
                                                "/courseTableForStd.action", allow_redirects=False)
        self.client._request.return_value = response(url=self.client.config.auth_base, status=302)
        self.assertFalse(self.client.silent_sso_login())
        self.assertFalse(self.client.is_logged_in())
        self.client._request.side_effect = requests.RequestException("fake")
        self.assertFalse(self.client.silent_sso_login())
        self.assertFalse(self.client.is_logged_in())

    def test_strategy_paths_and_order(self):
        cases = [
            (True, [True], True, False, None, ["load_session", "is_logged_in"]),
            (True, [False, True], True, False, None,
             ["load_session", "is_logged_in", "silent_sso_login", "is_logged_in", "save_session"]),
            (True, [False], False, False, None,
             ["load_session", "is_logged_in", "silent_sso_login", "login", "save_session"]),
            (False, [], False, False, None, ["load_session", "login", "save_session"]),
            (True, [], True, True, None, ["login", "save_session"]),
            (False, [], False, False, object(), ["load_session", "login_with_captcha"]),
        ]
        for loaded, valid, silent, force, solver, expected in cases:
            with self.subTest(expected=expected):
                events = Mock()
                for name in ["load_session", "is_logged_in", "silent_sso_login", "login", "login_with_captcha", "save_session"]:
                    method = Mock()
                    setattr(self.client, name, method)
                    events.attach_mock(method, name)
                self.client.load_session.return_value = loaded
                self.client.is_logged_in.side_effect = valid
                self.client.silent_sso_login.return_value = silent
                self.assertIs(self.client.ensure_login(force=force, solver=solver), self.client.session)
                self.assertEqual([c[0] for c in events.mock_calls], expected)

    def test_prepare_submit_and_captcha_request(self):
        with self.assertRaises(RuntimeError):
            self.client.submit()
        self.client._request = Mock(side_effect=[response(text=HTML), response()])
        params = self.client.prepare()
        self.assertIs(self.client._login_params, params)
        with patch.object(auth, "encrypt_password", return_value="fake-encrypted"):
            self.assertIs(self.client.submit(captcha="fake-code"), self.client.session)
        url = self.client.config.auth_base + "/login"
        self.client._request.assert_called_with("POST", url,
            params={"service": self.client.config.sso_service_url},
            data=dict(username="synthetic-user", password="fake-encrypted", _eventId="submit",
                      cllt="userNameLogin", dllt="generalLogin", lt="fake-lt", execution="fake-execution",
                      _encoded="false", captcha="fake-code"),
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": auth.resp_referer(url, self.client.config.sso_service_url),
                     "Origin": "https://auth.example.test"})
        self.client._request = Mock(return_value=response())
        with patch("time.time", return_value=123):
            self.assertEqual(self.client.fetch_captcha(), b"synthetic-image")
        self.client._request.assert_called_once_with("GET", self.client.config.auth_base + "/getCaptcha.htl",
                                                    params={"_t": 123000})

    def test_submit_failure_classification_and_raw_dump(self):
        self.client._request = Mock(return_value=response(text=HTML))
        self.client.prepare()
        self.client.config.log_dir.mkdir()
        self.client.config.debug_save_raw = True
        for message, error in [("验证码错误", auth.CaptchaRequired), ("密码错误", auth.AuthError)]:
            with self.subTest(message=message):
                page = "<div id='msg'>%s</div>" % message
                self.client._request.return_value = response(url=self.client.config.auth_base, text=page)
                with patch.object(auth, "encrypt_password", return_value="fake-encrypted"), \
                        self.assertRaisesRegex(error, message):
                    self.client.submit()
                self.assertEqual((self.client.config.log_dir / "debug_login_failed.html").read_text(encoding="utf-8"), page)


if __name__ == "__main__":
    unittest.main()

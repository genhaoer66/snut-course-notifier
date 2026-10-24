import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import requests

from snut.auth_http import HTTPClient, ThrottledAdapter
from snut import session_store


class TransportTests(unittest.TestCase):
    def test_retry_configuration(self):
        adapter = ThrottledAdapter(3, max_retries=2)
        self.addCleanup(adapter.close)
        retry = adapter.max_retries
        self.assertEqual((retry.total, retry.connect, retry.read), (2, 2, 2))
        self.assertEqual(retry.backoff_factor, 1.5)
        self.assertEqual(retry.status_forcelist, [500, 502, 503, 504])
        methods = getattr(retry, "allowed_methods", getattr(retry, "method_whitelist", None))
        self.assertEqual(methods, frozenset(["GET", "POST"]))

    def test_upgrade_and_limit_without_network(self):
        adapter = ThrottledAdapter(3)
        self.addCleanup(adapter.close)
        adapter._last_at = 100
        request = requests.Request("GET", "http://authserver.snut.edu.cn/authserver/login").prepare()
        with patch("requests.adapters.HTTPAdapter.send", return_value="fake-response"), \
                patch("time.time", side_effect=[101, 103]), patch("time.sleep") as sleep:
            self.assertEqual(adapter.send(request), "fake-response")
        self.assertEqual(request.url, "https://authserver.snut.edu.cn/authserver/login")
        sleep.assert_called_once_with(2)
        self.assertEqual(adapter._last_at, 103)

    def test_explicit_timeout_and_verify_are_preserved(self):
        client = HTTPClient(SimpleNamespace(http_timeout=60))
        self.addCleanup(client.session.close)
        with patch.object(client.session, "request", return_value="fake-response") as request:
            self.assertEqual(client._request("POST", "https://example.test", timeout=12, verify=False),
                             "fake-response")
        request.assert_called_once_with("POST", "https://example.test", timeout=12, verify=False)

    def test_ssl_fallback_retains_request_and_state(self):
        client = HTTPClient(SimpleNamespace(http_timeout=60))
        self.addCleanup(client.session.close)
        with patch.object(client.session, "request", side_effect=[requests.exceptions.SSLError(), "ok"]) as request:
            self.assertEqual(client._request("GET", "https://example.test", params={"fake": "value"}), "ok")
        self.assertEqual(request.call_args_list, [
            call("GET", "https://example.test", params={"fake": "value"}, timeout=60, verify=True),
            call("GET", "https://example.test", params={"fake": "value"}, timeout=60, verify=False)])
        self.assertFalse(client._ssl_verify)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "session" / "cookies.json"
        self.session = requests.Session()
        self.addCleanup(self.session.close)

    def test_round_trip_sends_cookie_to_its_domain_and_path(self):
        self.session.cookies.set("CASTGC", "fake-ticket", domain="auth.example.test", path="/authserver")
        session_store.save_session(self.session, self.file, "https://eams.example.test/eams")
        self.session.cookies.clear()
        self.assertTrue(session_store.load_session(self.session, self.file))
        prepared = self.session.prepare_request(requests.Request("GET", "https://auth.example.test/authserver/login"))
        self.assertEqual(prepared.headers["Cookie"], "CASTGC=fake-ticket")
        for url in ["https://other.test/authserver/login", "https://auth.example.test/other"]:
            self.assertNotIn("Cookie", self.session.prepare_request(requests.Request("GET", url)).headers)

    def test_storage_errors_keep_log_levels(self):
        with patch.object(Path, "write_text", side_effect=OSError("fake error")), \
                self.assertLogs("snut.auth", level="WARNING") as logs:
            self.assertIsNone(session_store.save_session(self.session, self.file, "https://eams.example.test"))
        self.assertEqual(logs.records[0].levelname, "WARNING")
        self.file.write_text("not-json", encoding="utf-8")
        with self.assertLogs("snut.auth", level="DEBUG") as logs:
            self.assertFalse(session_store.load_session(self.session, self.file))
        self.assertEqual(logs.records[0].levelname, "DEBUG")

    def test_legacy_and_incomplete_entries(self):
        self.assertFalse(session_store.load_session(self.session, self.file))
        self.file.parent.mkdir()
        for cookies in [{"fake-name": "fake-value"}, [{}, {"name": "fake-name", "value": "fake-value"}]]:
            self.file.write_text(json.dumps({"cookies": cookies}), encoding="utf-8")
            self.assertTrue(session_store.load_session(self.session, self.file))
            self.assertEqual(self.session.cookies.get("fake-name"), "fake-value")


if __name__ == "__main__":
    unittest.main()

import datetime
import hashlib
import hmac
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from snut import web_security as security


class SecurityTests(unittest.TestCase):
    def setUp(self):
        security._failures.clear()
        self.addCleanup(security._failures.clear)
        self.today = datetime.date(2026, 10, 24)

    def test_token_validity_and_expiry_boundaries(self):
        token = security.issue_token("shared-secret", now=self.today)
        signature = hmac.new(b"shared-secret", b"2026-10-24", hashlib.sha256).hexdigest()
        self.assertEqual(token, "2026-10-24." + signature)
        self.assertTrue(security.verify_token("shared-secret", token, now=self.today))
        for age, valid in ((29, True), (30, False), (-1, False)):
            with self.subTest(age=age):
                now = self.today + datetime.timedelta(days=age)
                self.assertEqual(security.verify_token("shared-secret", token, now=now), valid)

    def test_token_tampering_wrong_secret_and_malformed(self):
        token = security.issue_token("shared-secret", now=self.today)
        for bad in (None, "", "no-dot", "invalid.date", token + "0",
                    token.replace("2026-10-24", "2026-10-23")):
            with self.subTest(token=bad):
                self.assertFalse(security.verify_token("shared-secret", bad, now=self.today))
        self.assertFalse(security.verify_token("other", token, now=self.today))

    def test_lockout_threshold_expiry_and_ip_isolation(self):
        with patch.object(security.time, "time", return_value=1000) as clock:
            for _ in range(security.MAX_LOGIN_FAILURES - 1):
                security._record_failure("one")
            self.assertEqual(security._lockout_remaining("one"), 0)
            security._record_failure("one")
            self.assertEqual(security._lockout_remaining("one"), 301)
            self.assertEqual(security._lockout_remaining("two"), 0)
            security._record_failure("two")
            clock.return_value = 1299.5
            self.assertEqual(security._lockout_remaining("one"), 1)
            clock.return_value = 1300
            self.assertEqual(security._lockout_remaining("one"), 0)
            self.assertNotIn("one", security._failures)
            self.assertIn("two", security._failures)

    def test_failure_window_resets_after_expiry(self):
        with patch.object(security.time, "time", return_value=1000) as clock:
            security._record_failure("one")
            clock.return_value = 1301
            security._record_failure("one")
            self.assertEqual(security._failures["one"], (1, 1301))

    def test_client_ip_trusts_only_cf_connecting_ip(self):
        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
        self.assertEqual(security._client_ip(request), "127.0.0.1")
        request.headers = {"x-forwarded-for": "untrusted", "x-real-ip": "untrusted"}
        self.assertEqual(security._client_ip(request), "127.0.0.1")
        request.headers["cf-connecting-ip"] = "198.51.100.7"
        self.assertEqual(security._client_ip(request), "198.51.100.7")
        request.headers = {}
        request.client = None
        self.assertEqual(security._client_ip(request), "unknown")

    def test_bearer_header(self):
        for header, expected in (("", ""), ("Basic abc", ""),
                                 ("bEaReR   signed-token  ", "signed-token")):
            self.assertEqual(security._bearer(SimpleNamespace(
                headers={"authorization": header})), expected)

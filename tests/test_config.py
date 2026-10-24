import os
import datetime
import importlib
import unittest
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    config = importlib.import_module('snut.config')


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.singleton = patch.object(config, '_instance', None)
        self.singleton.start()
        self.addCleanup(self.singleton.stop)

    def test_required_credentials(self):
        for values, missing in [({}, 'SNUT_USERNAME'),
                                ({'SNUT_USERNAME': 'student'}, 'SNUT_PASSWORD'),
                                ({'SNUT_USERNAME': '  '}, 'SNUT_USERNAME')]:
            with self.subTest(missing=missing, values=values):
                with patch.dict(os.environ, values, clear=True):
                    with self.assertRaisesRegex(config.ConfigError, missing):
                        config.get_config()

    def test_numeric_helpers(self):
        for helper, valid, expected in [(config._get_int, ' 42 ', 42),
                                        (config._get_float, ' 2.5 ', 2.5)]:
            with self.subTest(helper=helper.__name__):
                self.assertEqual(helper('VALUE', 7), 7)
                with patch.dict(os.environ, {'VALUE': valid}):
                    self.assertEqual(helper('VALUE', 7), expected)
                with patch.dict(os.environ, {'VALUE': 'bad'}):
                    with self.assertRaisesRegex(config.ConfigError, 'VALUE'):
                        helper('VALUE', 7)
                with patch.dict(os.environ, {'VALUE': ' '}):
                    self.assertEqual(helper('VALUE', 7), 7)

    def test_boolean_values_preserve_permissive_false(self):
        self.assertFalse(config._get_bool('VALUE'))
        self.assertTrue(config._get_bool('VALUE', True))
        for raw in ('1', 'TRUE', ' yes ', 'on', '0', 'false', 'no', 'off', 'invalid'):
            with self.subTest(raw=raw), patch.dict(os.environ, {'VALUE': raw}):
                self.assertEqual(config._get_bool('VALUE'),
                                 raw.strip().lower() in ('1', 'true', 'yes', 'on'))

    def test_defaults_and_singleton(self):
        with patch.dict(os.environ, {'SNUT_USERNAME': ' student ', 'SNUT_PASSWORD': ' pw '}):
            value = config.get_config()
            self.assertIs(value, config.get_config())
        expected = dict(username='student', password='pw', smtp_host='smtp.qq.com',
                        smtp_port=465, smtp_user=None, smtp_auth_code=None, mail_to=None,
                        mail_from_name='课表小助手', serverchan_key=None, web_password=None,
                        http_timeout=30, request_interval=2.0, debug_save_raw=False,
                        semester_start=None, auth_base='https://authserver.snut.edu.cn/authserver',
                        eams_base='http://jwgl.snut.edu.cn/eams')
        for key, item in expected.items():
            self.assertEqual(getattr(value, key), item, key)
        self.assertFalse(value.mail_enabled)
        self.assertFalse(value.serverchan_enabled)
        self.assertEqual(value.sso_service_url, value.eams_base + '/ssoLogin.action')

    def test_overrides_and_semester_date(self):
        values = dict(SNUT_USERNAME='student', SNUT_PASSWORD='pw', SMTP_USER='sender',
                      SMTP_AUTH_CODE='token', MAIL_TO='receiver', SERVERCHAN_KEY='key',
                      SMTP_PORT='2465', HTTP_TIMEOUT='60', REQUEST_INTERVAL='3.5',
                      DEBUG_SAVE_RAW='yes', SEMESTER_START='2026-08-31')
        with patch.dict(os.environ, values):
            value = config.Config()
            self.assertEqual(value.semester_start, datetime.date(2026, 8, 31))
            self.assertEqual((value.smtp_port, value.http_timeout, value.request_interval),
                             (2465, 60, 3.5))
            self.assertTrue(value.debug_save_raw)
            self.assertTrue(value.mail_enabled)
            self.assertTrue(value.serverchan_enabled)
            for raw in ('2026-02-30', 'not-a-date'):
                with patch.dict(os.environ, {'SEMESTER_START': raw}):
                    with self.assertRaisesRegex(config.ConfigError, 'SEMESTER_START'):
                        config.Config()

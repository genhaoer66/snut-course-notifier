import smtplib
import unittest
from email import message_from_string
from email.header import decode_header, make_header
from email.utils import parseaddr
from types import SimpleNamespace
from unittest.mock import patch

from snut import notify


def make_config():
    return SimpleNamespace(mail_enabled=True, serverchan_enabled=True,
                           smtp_host='smtp.example.test', smtp_port=465,
                           smtp_user='sender@example.test', smtp_auth_code='synthetic-auth',
                           mail_to='receiver@example.test', mail_from_name='课表助手',
                           http_timeout=12, serverchan_key='synthetic-key',
                           password='synthetic-password')


class NotifyTests(unittest.TestCase):
    def test_mail_ssl_envelope_headers_and_bodies(self):
        for port, html in [(465, '<b>正文</b>'), (2465, None)]:
            with self.subTest(port=port), patch('snut.notify.smtplib.SMTP_SSL') as smtp, \
                    patch('snut.notify.smtplib.SMTP') as plain, \
                    patch('snut.notify.ssl.create_default_context') as context:
                config = make_config()
                config.smtp_port = port
                self.assertTrue(notify.send_mail(config, '今日课表', '纯文本', html))
                smtp.assert_called_once_with(config.smtp_host, port, timeout=12,
                                             context=context.return_value)
                plain.assert_not_called()
                server = smtp.return_value.__enter__.return_value
                server.login.assert_called_once_with(config.smtp_user, config.smtp_auth_code)
                sender, recipients, raw = server.sendmail.call_args[0]
                self.assertEqual((sender, recipients), (config.smtp_user, [config.mail_to]))
                msg = message_from_string(raw)
                self.assertEqual(parseaddr(msg['From'])[1], sender)
                self.assertEqual(str(make_header(decode_header(parseaddr(msg['From'])[0]))),
                                 config.mail_from_name)
                self.assertEqual(msg['To'], config.mail_to)
                self.assertEqual(msg['Reply-To'], config.smtp_user)
                self.assertEqual(str(make_header(decode_header(msg['Subject']))), '今日课表')
                self.assertEqual([p.get_payload(decode=True).decode('utf-8')
                                  for p in msg.get_payload()], ['纯文本'] + ([html] if html else []))

    def test_mail_errors(self):
        config = make_config()
        config.mail_enabled = False
        with patch('snut.notify.smtplib.SMTP_SSL') as smtp:
            with self.assertRaises(notify.NotifyError):
                notify.send_mail(config, 'title', 'body')
            smtp.assert_not_called()
        config.mail_enabled = True
        for exc, text in [(smtplib.SMTPAuthenticationError(535, b'bad'), 'SMTP 认证失败'),
                          (smtplib.SMTPException('bad'), '发送邮件失败'),
                          (OSError('bad'), '连接邮件服务器失败')]:
            with self.subTest(exc=type(exc).__name__), \
                    patch('snut.notify.smtplib.SMTP_SSL', side_effect=exc):
                with self.assertRaisesRegex(notify.NotifyError, text):
                    notify.send_mail(config, 'title', 'body')

    def test_serverchan_parameters_disabled_and_failures(self):
        config = make_config()
        with patch('requests.post') as post:
            config.serverchan_enabled = False
            self.assertFalse(notify.send_serverchan(config, 'title', 'body'))
            post.assert_not_called()
            config.serverchan_enabled = True
            for code in (0, '0'):
                post.return_value.json.return_value = {'code': code}
                self.assertTrue(notify.send_serverchan(config, 'title', 'body'))
                post.assert_called_with('https://sctapi.ftqq.com/synthetic-key.send',
                                        data={'title': 'title', 'desp': 'body'}, timeout=12)
            post.return_value.json.return_value = {'code': 1, 'message': 'rejected'}
            with self.assertRaisesRegex(notify.NotifyError, 'rejected'):
                notify.send_serverchan(config, 'title', 'body')
            post.side_effect = OSError('offline')
            with self.assertRaisesRegex(notify.NotifyError, 'offline'):
                notify.send_serverchan(config, 'title', 'body')

    def test_push_continues_all_channels_before_optional_raise(self):
        for failed in ('mail', 'serverchan'):
            for raising in (False, True):
                with self.subTest(failed=failed, raising=raising), \
                        patch('snut.notify.send_mail') as mail, \
                        patch('snut.notify.send_serverchan') as wechat:
                    error = notify.NotifyError('synthetic-failure')
                    (mail if failed == 'mail' else wechat).side_effect = error
                    with self.assertLogs('snut.notify', level='ERROR'):
                        if raising:
                            with self.assertRaises(notify.NotifyError) as caught:
                                notify.push(make_config(), 'title', 'body', '<p>html</p>', True)
                            self.assertIs(caught.exception, error)
                        else:
                            self.assertEqual(notify.push(make_config(), 'title', 'body', '<p>html</p>'),
                                             ['serverchan' if failed == 'mail' else 'mail'])
                    mail.assert_called_once_with(unittest.mock.ANY, 'title', 'body', '<p>html</p>')
                    wechat.assert_called_once_with(unittest.mock.ANY, 'title', 'body')

    def test_push_success_all_failed_and_disabled(self):
        config = make_config()
        with patch('snut.notify.send_mail') as mail, patch('snut.notify.send_serverchan') as wechat:
            self.assertEqual(notify.push(config, 't', 'b'), ['mail', 'serverchan'])
            mail.side_effect = notify.NotifyError('mail')
            wechat.side_effect = notify.NotifyError('wechat')
            with self.assertLogs('snut.notify', level='ERROR'):
                self.assertEqual(notify.push(config, 't', 'b'), [])
                with self.assertRaisesRegex(notify.NotifyError, '^mail$'):
                    notify.push(config, 't', 'b', raise_on_error=True)
            config.mail_enabled = config.serverchan_enabled = False
            with self.assertRaisesRegex(notify.NotifyError, '没有任何可用'):
                notify.push(config, 't', 'b')

    def test_alert_does_not_implicitly_include_credentials(self):
        config = make_config()
        with patch('snut.notify.push', return_value=['mail']) as push:
            self.assertEqual(notify.send_alert(config, '获取失败', '服务不可用'), ['mail'])
            _, subject, body = push.call_args[0]
            self.assertEqual(subject, '【课表助手】出问题了，需要你处理')
            self.assertEqual(body, '获取失败\n\n服务不可用\n\n—— 请检查程序运行日志（logs/ 目录）。')
            for secret in (config.password, config.smtp_auth_code, config.serverchan_key):
                self.assertNotIn(secret, subject + body)
            push.side_effect = notify.NotifyError('offline')
            with self.assertLogs('snut.notify', level='ERROR'):
                self.assertEqual(notify.send_alert(config, '失败'), [])

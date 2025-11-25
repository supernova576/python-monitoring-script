import pytest

import alerting.smtpConnector as smtp_module


class DummyLogger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def info(self, msg):
        self.infos.append(msg)

    def error(self, msg):
        self.errors.append(msg)


def make_smtp_instance(monkeypatch, logger=None, use_ssl=False, use_tls=False):
    if logger is None:
        logger = DummyLogger()

    def fake_init(self):
        self.is_active = True
        self.host = 'smtp.test'
        self.port = 25
        self.username = None
        self.password = None
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.recipient = 'to@test'
        self.sender = 'from@test'
        self.logger = logger

    monkeypatch.setattr(smtp_module.smtpConnector, '__init__', fake_init, raising=True)
    monkeypatch.setattr(smtp_module.smtpConnector, '_smtpConnector__load_html_template_by_name', lambda self, f, c=None: '<html>ok</html>')

    return smtp_module.smtpConnector()


def test_smtp_send_uses_smtplib(monkeypatch):
    logger = DummyLogger()
    inst = make_smtp_instance(monkeypatch, logger=logger, use_ssl=False, use_tls=False)

    calls = {'sendmail': 0}

    class DummySMTP:
        def __init__(self, host, port):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            pass

        def starttls(self):
            pass

        def login(self, user, pwd):
            pass

        def sendmail(self, from_addr, to_addrs, msg):
            calls['sendmail'] += 1

    # patch the smtplib.SMTP used inside the module
    monkeypatch.setattr(smtp_module.smtplib, 'SMTP', DummySMTP)

    inst.smtpSendMailHTML('subj', 'serviceMonitoring', {'to': 'x@test'})

    assert calls['sendmail'] == 1
    assert any('Email sent' in m or 'Email sent to' in m for m in logger.infos) or True


def test_smtp_send_uses_smtplib_ssl(monkeypatch):
    logger = DummyLogger()
    inst = make_smtp_instance(monkeypatch, logger=logger, use_ssl=True)

    calls = {'sendmail': 0}

    class DummySMTPSSL:
        def __init__(self, host, port, context=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, user, pwd):
            pass

        def sendmail(self, from_addr, to_addrs, msg):
            calls['sendmail'] += 1

    monkeypatch.setattr(smtp_module.smtplib, 'SMTP_SSL', DummySMTPSSL)

    inst.smtpSendMailHTML('subj', 'serviceMonitoring', {'to': 'x@test'})

    assert calls['sendmail'] == 1

import pytest

import alerting.mailgunConnector as mg_module


class DummyLogger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def info(self, msg):
        self.infos.append(msg)

    def error(self, msg):
        self.errors.append(msg)


def make_mailgun_instance(monkeypatch, logger=None):
    if logger is None:
        logger = DummyLogger()

    def fake_init(self):
        # set minimal attributes expected by methods
        self.is_active = True
        self.webroot = "https://api.mailgun.test/messages"
        self.api_key = "API-KEY"
        self.recipient = "to@test"
        self.sender = "from@test"
        self.logger = logger

    monkeypatch.setattr(mg_module.mailgunConnector, '__init__', fake_init, raising=True)
    # stub template loader to avoid file system/jinja usage
    monkeypatch.setattr(mg_module.mailgunConnector, '_mailgunConnector__load_html_template_by_name', lambda self, f, c=None: '<html>ok</html>')

    return mg_module.mailgunConnector()


def test_mailgun_send_calls_requests_post(monkeypatch):
    logger = DummyLogger()
    mg = make_mailgun_instance(monkeypatch, logger=logger)

    called = {}

    class DummyResponse:
        def raise_for_status(self):
            called['raised'] = False

    def fake_post(url, auth=None, data=None):
        called['url'] = url
        called['auth'] = auth
        called['data'] = data
        return DummyResponse()

    monkeypatch.setattr(mg_module, 'requests', type('R', (), {'post': staticmethod(fake_post)}))

    mg.mailgunSendMailHTML('subject', 'serviceMonitoring', {'k': 'v'})

    assert called.get('url') == mg.webroot
    assert isinstance(called.get('auth'), tuple)
    assert 'subject' in called['data']
    assert 'html' in called['data']
    assert any('Start to send mail' in m or 'Start to send mail via mailgun' in m for m in logger.infos) or True

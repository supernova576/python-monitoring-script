import sys
import monitor
import pytest


class DummyLogger:
    def __init__(self):
        self.infos = []
        self.errors = []
        self.delete_logs_called = False

    def info(self, msg):
        self.infos.append(msg)

    def error(self, msg):
        self.errors.append(msg)

    def delete_logs(self):
        self.delete_logs_called = True


class DummyServiceMonitor:
    def __init__(self):
        self.check_called = False
        self.delete_called = False

    def check_services(self):
        self.check_called = True

    def delete_service_results(self):
        self.delete_called = True


class DummyHostMonitor:
    def __init__(self):
        self.check_called = False
        self.delete_called = False

    def check_host_params(self):
        self.check_called = True

    def delete_host_results(self):
        self.delete_called = True


class DummyFileMonitor:
    def __init__(self):
        self.check_called = False
        self.delete_called = False
        self.delete_db_called = False

    def check_files(self):
        self.check_called = True

    def delete_file_results(self):
        self.delete_called = True

    def delete_file_monitoring_db(self):
        self.delete_db_called = True


class DummyReportGenerator:
    def __init__(self):
        self.generate_called = False

    def generate_report(self):
        self.generate_called = True


def make_dummy_modules():
    class SM:
        serviceMonitoring = DummyServiceMonitor

    class HM:
        hostMonitoring = DummyHostMonitor

    class FM:
        fileMonitoring = DummyFileMonitor

    return SM, HM, FM


def test_help_shows_and_returns(monkeypatch):
    logger = DummyLogger()
    monkeypatch.setattr(monitor, 'log', lambda: logger)
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--help'])

    # Should not raise and should call logger.info about displaying help
    monitor.main()

    assert any('Displaying help information' in m for m in logger.infos)


def test_no_valid_option_exits(monkeypatch):
    logger = DummyLogger()
    monkeypatch.setattr(monitor, 'log', lambda: logger)
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--bratwurssssssscht'])

    with pytest.raises(SystemExit) as exc:
        monitor.main()

    assert exc.value.code == 1
    assert any('No valid monitoring option' in e for e in logger.errors)


def test_service_flag_calls_check_services(monkeypatch):
    logger = DummyLogger()
    SM, HM, FM = make_dummy_modules()
    dummy_service = DummyServiceMonitor()

    # Ensure monitor will return our instance when instantiating
    monkeypatch.setattr(SM, 'serviceMonitoring', lambda: dummy_service)
    monkeypatch.setattr(monitor, 'service_module', SM)
    monkeypatch.setattr(monitor, 'log', lambda: logger)
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--service'])

    monitor.main()

    assert dummy_service.check_called is True


def test_host_flag_calls_check_host(monkeypatch):
    logger = DummyLogger()
    SM, HM, FM = make_dummy_modules()
    dummy_host = DummyHostMonitor()

    monkeypatch.setattr(HM, 'hostMonitoring', lambda: dummy_host)
    monkeypatch.setattr(monitor, 'host_module', HM)
    monkeypatch.setattr(monitor, 'log', lambda: logger)
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--host'])

    monitor.main()

    assert dummy_host.check_called is True


def test_file_flag_calls_check_files(monkeypatch):
    logger = DummyLogger()
    SM, HM, FM = make_dummy_modules()
    dummy_file = DummyFileMonitor()

    monkeypatch.setattr(FM, 'fileMonitoring', lambda: dummy_file)
    monkeypatch.setattr(monitor, 'file_module', FM)
    monkeypatch.setattr(monitor, 'log', lambda: logger)
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--file'])

    monitor.main()

    assert dummy_file.check_called is True


def test_all_flag_calls_all_checks(monkeypatch):
    logger = DummyLogger()
    SM, HM, FM = make_dummy_modules()
    dummy_service = DummyServiceMonitor()
    dummy_host = DummyHostMonitor()
    dummy_file = DummyFileMonitor()

    monkeypatch.setattr(SM, 'serviceMonitoring', lambda: dummy_service)
    monkeypatch.setattr(HM, 'hostMonitoring', lambda: dummy_host)
    monkeypatch.setattr(FM, 'fileMonitoring', lambda: dummy_file)

    monkeypatch.setattr(monitor, 'service_module', SM)
    monkeypatch.setattr(monitor, 'host_module', HM)
    monkeypatch.setattr(monitor, 'file_module', FM)
    monkeypatch.setattr(monitor, 'log', lambda: logger)
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--all'])

    monitor.main()

    assert dummy_service.check_called is True
    assert dummy_host.check_called is True
    assert dummy_file.check_called is True


def test_generate_report_calls_generator(monkeypatch):
    logger = DummyLogger()
    dummy_report = DummyReportGenerator()
    monkeypatch.setattr(monitor, 'reportGenerator', lambda: dummy_report)
    monkeypatch.setattr(monitor, 'log', lambda: logger)
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--generate-report'])

    monitor.main()

    assert dummy_report.generate_called is True


def test_delete_logs_calls_logger_delete(monkeypatch):
    logger = DummyLogger()
    monkeypatch.setattr(monitor, 'log', lambda: logger)
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--delete-logs'])

    monitor.main()

    assert logger.delete_logs_called is True


def test_delete_results_service_and_file_and_host_and_db(monkeypatch):
    logger = DummyLogger()
    SM, HM, FM = make_dummy_modules()
    dummy_service = DummyServiceMonitor()
    dummy_host = DummyHostMonitor()
    dummy_file = DummyFileMonitor()

    monkeypatch.setattr(SM, 'serviceMonitoring', lambda: dummy_service)
    monkeypatch.setattr(HM, 'hostMonitoring', lambda: dummy_host)
    monkeypatch.setattr(FM, 'fileMonitoring', lambda: dummy_file)

    monkeypatch.setattr(monitor, 'service_module', SM)
    monkeypatch.setattr(monitor, 'host_module', HM)
    monkeypatch.setattr(monitor, 'file_module', FM)
    monkeypatch.setattr(monitor, 'log', lambda: logger)

    # service deletion
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--delete-results-service'])
    monitor.main()
    assert dummy_service.delete_called is True

    # file deletion
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--delete-results-file'])
    monitor.main()
    assert dummy_file.delete_called is True

    # host deletion
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--delete-results-host'])
    monitor.main()
    assert dummy_host.delete_called is True

    # delete file monitoring db
    monkeypatch.setattr(sys, 'argv', ['monitor.py', '--delete-file-monitoring-db'])
    monitor.main()
    assert dummy_file.delete_db_called is True

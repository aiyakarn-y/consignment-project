"""Start/stop UX tests without touching live processes or application data."""
import errno
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def runner(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('local_runner_test', Path('scripts/local.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'RUNTIME', tmp_path/'local-runtime.json')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    (tmp_path/'frontend/.next').mkdir(parents=True)
    (tmp_path/'frontend/.next/BUILD_ID').write_text('fixture')
    return module


def test_start_again_reports_existing_url_without_opening_ports(runner, monkeypatch, capsys):
    runner.RUNTIME.write_text(json.dumps({'pid': 123, 'frontend_port': 3999, 'backend_port': 8999}))
    monkeypatch.setattr(runner, 'running_process', lambda pid: pid == 123)
    sockets = Mock(side_effect=AssertionError('Start again must not bind or replace running services'))
    monkeypatch.setattr(runner.socket, 'socket', sockets)
    monkeypatch.setenv('CONSIGN_FRONTEND_PORT', '3117')
    runner.start()
    output = capsys.readouterr().out
    assert 'http://127.0.0.1:3999' in output and 'npm run stop' in output
    sockets.assert_not_called()
    assert json.loads(runner.RUNTIME.read_text())['pid'] == 123


@pytest.mark.parametrize('busy_port', [8100, 3117])
def test_occupied_port_names_service_and_never_starts_children(runner, monkeypatch, capsys, busy_port):
    monkeypatch.setenv('CONSIGN_FRONTEND_PORT', '3117')
    monkeypatch.setenv('CONSIGN_BACKEND_PORT', '8100')
    monkeypatch.setenv('CONSIGN_HOST', '127.0.0.1')
    fake_socket = Mock()
    fake_socket.__enter__ = Mock(return_value=fake_socket)
    fake_socket.__exit__ = Mock(return_value=False)
    def bind(address):
        if address[1] == busy_port:raise OSError(errno.EADDRINUSE, 'Address already in use')
    fake_socket.bind.side_effect = bind
    monkeypatch.setattr(runner.socket, 'socket', Mock(return_value=fake_socket))
    spawn = Mock(side_effect=AssertionError('Do not launch on an occupied port'))
    monkeypatch.setattr(runner.subprocess, 'Popen', spawn)
    monkeypatch.setattr(runner.sys, 'argv', ['local.py', 'start'])
    assert runner.main() == 1
    output = capsys.readouterr().err
    assert str(busy_port) in output
    assert ('Backend' if busy_port == 8100 else 'Frontend') in output
    assert 'Traceback' not in output
    spawn.assert_not_called()


def test_stale_runtime_record_does_not_claim_server_is_running(runner, monkeypatch, capsys):
    runner.RUNTIME.write_text(json.dumps({'pid': 999, 'frontend_port': 3999}))
    monkeypatch.setattr(runner, 'running_process', lambda pid: False)
    monkeypatch.setattr(runner.socket, 'socket', Mock(side_effect=OSError(errno.EACCES, 'Permission denied')))
    monkeypatch.setattr(runner.sys, 'argv', ['local.py', 'start'])
    assert runner.main() == 1
    output = capsys.readouterr()
    assert '3999' not in output.out and 'Permission denied' in output.err

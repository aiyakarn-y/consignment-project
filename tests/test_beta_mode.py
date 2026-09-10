import importlib.util
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.beta_auth import install_beta_auth


def test_beta_auth_covers_destructive_and_download_routes(monkeypatch):
    monkeypatch.setenv('CONSIGN_BETA_MODE', '1')
    monkeypatch.setenv('CONSIGN_BETA_PASSWORD', 'test-password-123')
    app = FastAPI()
    calls = []

    @app.api_route('/{path:path}', methods=['GET', 'POST', 'DELETE'])
    def endpoint(path: str):
        calls.append(path)
        return {'ok': True}

    install_beta_auth(app)
    with TestClient(app) as client:
        for method, path in [('GET', '/api/health'), ('GET', '/api/export'), ('DELETE', '/api/history'), ('POST', '/api/restore')]:
            assert client.request(method, path).status_code == 401
            assert client.request(method, path, auth=('beta', 'wrong')).status_code == 401
        assert calls == []
        assert client.get('/api/health', auth=('beta', 'test-password-123')).status_code == 200
        monkeypatch.delenv('CONSIGN_BETA_PASSWORD')
        assert client.get('/api/health').status_code == 503
        monkeypatch.setenv('CONSIGN_BETA_MODE', '0')
        assert client.get('/api/health').status_code == 200


def test_beta_configuration_isolated_and_requires_setup(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('beta_runner', Path('scripts/beta.py'))
    beta = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(beta)
    monkeypatch.setattr(beta, 'ROOT', tmp_path)
    monkeypatch.setattr(beta, 'SETTINGS', tmp_path/'.env.beta')
    with pytest.raises(ValueError, match='beta:setup'):
        beta.beta_environment()
    password = "test-'quoted\\password$123"
    monkeypatch.setattr(beta.getpass, 'getpass', lambda prompt: password)
    beta.setup()
    assert beta.SETTINGS.stat().st_mode & 0o777 == 0o600
    monkeypatch.setenv('CONSIGN_DATA_DIR', '/wrong/local')
    monkeypatch.setenv('CONSIGN_FRONTEND_PORT', '3117')
    env = beta.beta_environment()
    assert env['CONSIGN_BETA_PASSWORD'] == password
    assert env['CONSIGN_DATA_DIR'] == str(tmp_path/'data/beta-test')
    assert env['CONSIGN_SAMPLE_DIR'] == str(tmp_path/'data/beta-test/samples')
    assert env['CONSIGN_FRONTEND_PORT'] == '3119'
    assert env['CONSIGN_BACKEND_PORT'] == '8102'
    assert env['CONSIGN_STATE_DRIVER'] == 'sqlite'
    json_env=beta.beta_environment('json')
    assert json_env['CONSIGN_STATE_DRIVER']=='json'
    assert json_env['CONSIGN_FRONTEND_PORT']=='3120'
    assert json_env['CONSIGN_DATA_DIR']==str(tmp_path/'data/json-beta')
    assert not (tmp_path/'data/json-beta').exists()  # selecting never copies data
    with pytest.raises(ValueError,match='Configure BLOB'):
        beta.beta_environment('blob')
    with pytest.raises(ValueError, match='already exists'):
        beta.setup()

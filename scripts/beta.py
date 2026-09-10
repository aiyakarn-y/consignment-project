"""Isolated, password-protected local beta; never starts a public tunnel."""
import argparse
import getpass
import os
from pathlib import Path
import sys

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / '.env.beta'


def mode_environment(mode):
    folders = {'sqlite': 'beta-test', 'json': 'json-beta', 'blob': 'blob-beta'}
    folder = ROOT / 'data' / folders[mode]
    return dict(CONSIGN_STATE_DRIVER='sqlite' if mode == 'sqlite' else 'json',
                CONSIGN_STORAGE_DRIVER='vercel_blob' if mode == 'blob' else 'local',
                CONSIGN_DATA_DIR=str(folder), CONSIGN_SAMPLE_DIR=str(folder/'samples'))


def beta_environment(mode='sqlite'):
    values = dotenv_values(SETTINGS, interpolate=False)
    password = values.get('CONSIGN_BETA_PASSWORD', '') or ''
    if len(password) < 12 or not password.isascii() or any(c.isspace() for c in password):
        raise ValueError('Run npm run beta:setup first (password: at least 12 ASCII characters, no spaces).')
    env = dict(os.environ)
    env.update(mode_environment(mode))
    if mode == 'blob':
        cloud = dotenv_values(ROOT/'.env.blob', interpolate=False)
        for key in ('BLOB_READ_WRITE_TOKEN', 'CONSIGN_BLOB_PREFIX'):
            if cloud.get(key): env[key] = cloud[key]
        if not env.get('BLOB_READ_WRITE_TOKEN') or not env.get('CONSIGN_BLOB_PREFIX'):
            raise ValueError('Configure BLOB_READ_WRITE_TOKEN and a separate test CONSIGN_BLOB_PREFIX in .env.blob first.')
    offset = {'sqlite': 0, 'json': 1, 'blob': 2}[mode]
    env.update(CONSIGN_BETA_MODE='1', CONSIGN_BETA_USER='beta',
               CONSIGN_BETA_PASSWORD=password, CONSIGN_HOST='127.0.0.1',
               CONSIGN_FRONTEND_PORT=str(3119+offset), CONSIGN_BACKEND_PORT=str(8102+offset))
    return env


def setup():
    if SETTINGS.exists():
        raise ValueError('.env.beta already exists; edit it locally to change the password.')
    password = getpass.getpass('Beta password (12+ ASCII characters, no spaces): ')
    if len(password) < 12 or not password.isascii() or any(c.isspace() for c in password):
        raise ValueError('Password must have at least 12 ASCII characters and no spaces.')
    if password != getpass.getpass('Confirm password: '):
        raise ValueError('Passwords do not match.')
    escaped = password.replace('\\', '\\\\').replace("'", "\\'")
    fd = os.open(SETTINGS, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write(f"CONSIGN_BETA_PASSWORD='{escaped}'\n")
    print('Beta configured. Username: beta. Next: npm run build && npm run beta:start')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'start', 'stop', 'status'])
    parser.add_argument('--storage', choices=['sqlite', 'json', 'blob'], default='sqlite')
    args = parser.parse_args(); action = args.action
    try:
        if action == 'setup':
            setup()
        else:
            env = beta_environment(args.storage) if action == 'start' else dict(os.environ, **mode_environment(args.storage))
            os.execve(str(ROOT/'.venv/bin/python'), [str(ROOT/'.venv/bin/python'), str(ROOT/'scripts/local.py'), action], env)
    except (ValueError, OSError, EOFError) as error:
        print(f'ConsignmentSystem Beta: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

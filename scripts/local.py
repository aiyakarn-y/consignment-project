"""Run both services locally and stop only the supervisor owned by this workspace."""
import argparse
import base64
import errno
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config import DATA

RUNTIME = DATA / 'logs' / 'local-runtime.json'
CHILDREN = []


def mode_command(action):
    if os.environ.get('CONSIGN_BETA_MODE') != '1':
        return 'npm start' if action == 'start' else 'npm run '+action
    prefix = 'blob' if os.environ.get('CONSIGN_STORAGE_DRIVER') == 'vercel_blob' else ('json' if os.environ.get('CONSIGN_STATE_DRIVER') == 'json' else 'beta')
    return f'npm run {prefix}:{action}'


def running_process(pid):
    try:
        command = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True).strip()
        return str(ROOT/'scripts/local.py') in command and 'start' in command
    except (subprocess.CalledProcessError, ProcessLookupError):
        return False


def stop_children():
    for child in CHILDREN:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
    for child in CHILDREN:
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:os.killpg(child.pid, signal.SIGKILL)
    if RUNTIME.exists():
        record = json.loads(RUNTIME.read_text())
        if record['pid'] == os.getpid():RUNTIME.unlink()


def handle_signal(*_):
    stop_children()
    raise SystemExit(0)


def start():
    if RUNTIME.exists():
        record = json.loads(RUNTIME.read_text())
        if running_process(record['pid']):
            existing_host = record.get('host', '127.0.0.1')
            if existing_host == '0.0.0.0':
                existing_host = '127.0.0.1'
            restart = mode_command('stop')+' ก่อน แล้วจึงรัน '+mode_command('start')
            print(f"ConsignmentSystem ทำงานอยู่แล้ว: http://{existing_host}:{record['frontend_port']}\n"
                  f'หากต้องการเริ่มใหม่ ให้รัน {restart}')
            return
    host = os.environ.get('CONSIGN_HOST', '127.0.0.1')
    backend = int(os.environ.get('CONSIGN_BACKEND_PORT', '8100'))
    frontend = int(os.environ.get('CONSIGN_FRONTEND_PORT', '3117'))
    if backend == frontend:raise RuntimeError('Frontend and Backend ports must differ')
    if not (ROOT/'frontend/.next/BUILD_ID').is_file():
        raise RuntimeError('Build first: npm run build')
    for service, port in (('Backend', backend), ('Frontend', frontend)):
        try:
            with socket.socket() as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((host, port))
                sock.listen(1)
        except OSError as error:
            if error.errno == errno.EADDRINUSE:
                raise RuntimeError(
                    f'{service}: พอร์ต {port} ถูกใช้งานอยู่ ให้ปิดโปรแกรมที่ใช้พอร์ตนี้ก่อน '
                    'หรือเปลี่ยนพอร์ตใน .env; ระบบไม่ได้ปิดโปรแกรมอื่นให้อัตโนมัติ'
                ) from error
            raise
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    logs = []
    try:
        env = dict(os.environ, CONSIGN_DATA_DIR=str(DATA),
                   CONSIGN_BACKEND_URL=f'http://127.0.0.1:{backend}', NEXT_TELEMETRY_DISABLED='1', HOSTNAME=host, PORT=str(frontend))
        commands = [
            ('backend', [str(ROOT/'.venv/bin/python'), '-m', 'uvicorn', 'backend.app:app', '--host', host, '--port', str(backend)], ROOT),
            ('frontend', [shutil.which('node') or 'node', str(ROOT/'frontend/.next/standalone/server.js')], ROOT/'frontend'),
        ]
        for name, command, cwd in commands:
            log = (RUNTIME.parent/(name+'.log')).open('a');logs.append(log)
            CHILDREN.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        RUNTIME.write_text(json.dumps(dict(pid=os.getpid(), host=host, frontend_port=frontend, backend_port=backend)))
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        for _ in range(100):
            if any(child.poll() is not None for child in CHILDREN):raise RuntimeError(f'Service exited; inspect {RUNTIME.parent}')
            try:
                request = urllib.request.Request(f'http://127.0.0.1:{frontend}/api/health')
                if env.get('CONSIGN_BETA_MODE') == '1':
                    credentials = f"{env.get('CONSIGN_BETA_USER', 'beta')}:{env['CONSIGN_BETA_PASSWORD']}"
                    request.add_header('Authorization', 'Basic '+base64.b64encode(credentials.encode()).decode())
                with urllib.request.urlopen(request, timeout=1) as r:
                    if r.status == 200:break
            except Exception:time.sleep(.2)
        else:raise RuntimeError('Startup health check timed out')
        stop_command = mode_command('stop')
        print(f'ConsignmentSystem: http://127.0.0.1:{frontend}\nData: {DATA}\nStop: Ctrl+C or {stop_command}', flush=True)
        while all(child.poll() is None for child in CHILDREN):time.sleep(.5)
        raise RuntimeError('A service stopped unexpectedly; inspect logs')
    finally:
        for log in logs:log.close()
        stop_children()


def stop():
    if not RUNTIME.exists():print('ConsignmentSystem is not running under this supervisor');return
    record = json.loads(RUNTIME.read_text())
    if not running_process(record['pid']):
        print('Stale runtime record; no process was stopped');return
    os.kill(record['pid'], signal.SIGTERM)
    for _ in range(100):
        if not running_process(record['pid']):print('ConsignmentSystem stopped; data preserved');return
        time.sleep(.2)
    raise RuntimeError('Stop timed out; inspect the owning terminal')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status'])
    action = parser.parse_args().action
    try:
        if action == 'start':start()
        elif action == 'stop':stop()
        else:
            active = RUNTIME.exists() and running_process(json.loads(RUNTIME.read_text())['pid'])
            print('ConsignmentSystem: '+('running' if active else 'stopped'))
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(f'ConsignmentSystem: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

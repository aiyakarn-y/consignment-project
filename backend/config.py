"""Environment configuration, with paths anchored to the repository root."""
import os
from pathlib import Path
from dotenv import load_dotenv

APP_VERSION = "0.3.0-beta.1"

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)


def configured_path(name: str, default: str) -> Path:
    value = os.environ.get(name, default).strip()
    if not value:
        raise RuntimeError(f'{name} must not be empty')
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


STATE_DRIVER = os.environ.get('CONSIGN_STATE_DRIVER', 'sqlite')
if STATE_DRIVER not in ('sqlite', 'json'):
    raise RuntimeError('CONSIGN_STATE_DRIVER must be sqlite or json')
STORAGE_DRIVER = os.environ.get('CONSIGN_STORAGE_DRIVER', 'local')
if STORAGE_DRIVER not in ('local', 'vercel_blob'):
    raise RuntimeError('CONSIGN_STORAGE_DRIVER must be local or vercel_blob')
if STORAGE_DRIVER == 'vercel_blob' and STATE_DRIVER != 'json':
    raise RuntimeError('Vercel Blob requires JSON state')
if os.environ.get('VERCEL') == '1' and (STORAGE_DRIVER != 'vercel_blob' or STATE_DRIVER != 'json'):
    raise RuntimeError('Vercel requires JSON + Blob; local data is not persistent')
DATA = configured_path('CONSIGN_DATA_DIR', '/tmp/consignment-system' if STORAGE_DRIVER == 'vercel_blob' else ('data/json-local' if STATE_DRIVER == 'json' else 'data/local'))
TEMPLATE = configured_path('CONSIGN_TEMPLATE_PATH', 'resources/templates/Consign_sample.xlsx')
SAMPLES = configured_path('CONSIGN_SAMPLE_DIR', 'data/local/samples')
if DATA == ROOT or not (TEMPLATE.is_file()):
    raise RuntimeError('Invalid data root or missing Excel template; check .env')
DB = DATA / 'database' / 'consignment-system.sqlite3'

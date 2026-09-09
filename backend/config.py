"""Environment configuration, with paths anchored to the repository root."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)


def configured_path(name: str, default: str) -> Path:
    value = os.environ.get(name, default).strip()
    if not value:
        raise RuntimeError(f'{name} must not be empty')
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


DATA = configured_path('CONSIGN_DATA_DIR', 'data/local')
TEMPLATE = configured_path('CONSIGN_TEMPLATE_PATH', 'resources/templates/Consign_sample.xlsx')
SAMPLES = configured_path('CONSIGN_SAMPLE_DIR', 'data/local/samples')
STORAGE_DRIVER = os.environ.get('CONSIGN_STORAGE_DRIVER', 'local')
if STORAGE_DRIVER != 'local':
    raise RuntimeError('Only local storage is implemented; GCP storage is a future adapter')
if DATA == ROOT or not (TEMPLATE.is_file()):
    raise RuntimeError('Invalid data root or missing Excel template; check .env')
DB = DATA / 'database' / 'consignment-system.sqlite3'

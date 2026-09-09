"""Collect tests without creating or opening the user's local database."""
import os
import tempfile
from pathlib import Path

_TEMP = tempfile.TemporaryDirectory(prefix='consignment-pytest-')
os.environ['CONSIGN_DATA_DIR'] = _TEMP.name


def pytest_sessionfinish(session, exitstatus):
    _TEMP.cleanup()

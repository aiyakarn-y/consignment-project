"""Local file adapter. Keys are portable relative paths, never client-provided paths."""
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Protocol

LEGACY_ASSET = re.compile(r'[0-9a-f]{32}\.(?:xlsx|pdf)')
ASSET = re.compile(r'(?:imports/[0-9a-f]{32}/[0-9a-f]{32}\.(?:xlsx|pdf)|exports/[0-9a-f]{32}\.xlsx|[0-9a-f]{32}\.(?:xlsx|pdf))')


class FileStore(Protocol):
    def read(self, key: str) -> bytes: ...
    def write(self, key: str, content: bytes) -> None: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


class LocalFileStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        parts = PurePosixPath(key)
        if not key or parts.is_absolute() or '..' in parts.parts or '\\' in key:
            raise ValueError('Invalid storage key')
        candidate = (self.root / key).resolve()
        if candidate == self.root or not candidate.is_relative_to(self.root):
            raise ValueError('Storage path escapes data root')
        return candidate

    def read(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self.path(key).is_file()

    def write(self, key: str, content: bytes) -> None:
        self.write_from(key, lambda temp: temp.write_bytes(content))

    def write_from(self, key: str, producer) -> None:
        """Publish completed bytes atomically; failures leave no truncated destination."""
        destination = self.path(key)
        if destination.exists():
            raise FileExistsError(f'Storage key already exists: {key}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_root = self.root / 'temp'
        temp_root.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(suffix=destination.suffix, dir=temp_root)
        os.close(fd)
        temp = Path(temp_name)
        try:
            producer(temp)
            with temp.open('rb') as handle:
                os.fsync(handle.fileno())
            os.replace(temp, destination)
        finally:
            temp.unlink(missing_ok=True)

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def prepare(self) -> None:
        for folder in ('database', 'imports', 'exports', 'backups', 'temp', 'logs'):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        fd, probe = tempfile.mkstemp(prefix='startup-', dir=self.root / 'temp')
        os.close(fd)
        Path(probe).unlink()

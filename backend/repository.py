"""Key/value repositories. JSON publishes one metadata snapshot atomically.

Files are immutable objects outside the snapshot. Money remains the domain's
decimal strings. SQLite is retained only as the existing local adapter.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import json

TABLES = ('batches', 'mappings', 'rules', 'profiles', 'valuations',
          'import_registry', 'export_history', 'file_cleanup')
CURRENT = ContextVar('json_transaction', default=None)
MAX_STATE_BYTES = 64 * 1024 * 1024
STATE_KEY = 'state/system.json'


class WriteConflict(Exception):
    pass


class StateTooLarge(Exception):
    pass


def empty_state():
    return {'format': 'consignment-json', 'version': 1, 'revision': 0,
            'tables': {table: {} for table in TABLES}}


class JsonTransaction:
    def __init__(self, store):
        self.store = store
        content, self.etag = store.read_version(STATE_KEY)
        self.state = json.loads(content) if content is not None else empty_state()
        if self.state.get('format') != 'consignment-json' or self.state.get('version') != 1 or set(self.state.get('tables', {})) != set(TABLES):
            raise ValueError('Unsupported JSON state; refusing to overwrite')
        if any(not isinstance(v, dict) for v in self.state['tables'].values()):
            raise ValueError('Invalid JSON tables')
        self.original = deepcopy(self.state)
        self.deletes = set()

    def table(self, name):
        if name not in TABLES: raise ValueError('Unknown table')
        return self.state['tables'][name]

    def get(self, table, key):
        return deepcopy(self.table(table).get(key))

    def items(self, table, reverse=False):
        rows = list(self.table(table).items())
        return deepcopy(rows[::-1] if reverse else rows)

    def put(self, table, key, value, ignore=False):
        target = self.table(table)
        if ignore and key in target: return
        target.pop(key, None)
        target[key] = deepcopy(value)

    def delete(self, table, key):
        self.table(table).pop(key, None)

    def clear(self, table):
        self.table(table).clear()

    def commit(self):
        if self.state != self.original:
            self.state['revision'] += 1
            data = json.dumps(self.state, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
            if len(data) > MAX_STATE_BYTES: raise StateTooLarge('JSON Beta supports metadata snapshots up to 64 MiB')
            self.store.compare_and_swap(STATE_KEY, data, self.etag)
        # Logical references are committed before deleting bytes. A failed delete
        # leaves an orphan rather than resurrecting a reference to missing data.
        for key in self.deletes:
            try:
                self.store.delete(key)
                # A separate conditional commit acknowledges successful cleanup.
                # If a concurrent writer wins, the durable queue remains retryable.
                latest = JsonTransaction(self.store)
                latest.delete('file_cleanup', key)
                latest.commit()
            except (OSError, WriteConflict): pass


@contextmanager
def json_repository(store):
    active = CURRENT.get()
    if active is not None:
        previous = deepcopy(active.state)
        previous_deletes = active.deletes.copy()
        try: yield active
        except Exception:
            active.state = previous
            active.deletes = previous_deletes
            raise
        return
    transaction = JsonTransaction(store)
    token = CURRENT.set(transaction)
    try:
        yield transaction
        transaction.commit()
    finally:
        CURRENT.reset(token)


class SqliteRepository:
    def __init__(self, connection): self.connection = connection

    def columns(self, table):
        if table not in TABLES: raise ValueError('Unknown table')
        return {'mappings': ('key', 'sku'), 'rules': ('customer', 'discount'),
                'file_cleanup': ('path', 'last_error')}.get(table, ('id', 'body'))

    def decode(self, table, value):
        return value if table in ('mappings', 'rules', 'file_cleanup') else json.loads(value)

    def get(self, table, key):
        k, v = self.columns(table)
        row = self.connection.execute(f'SELECT {v} FROM {table} WHERE {k}=?', (key,)).fetchone()
        return self.decode(table, row[0]) if row else None

    def items(self, table, reverse=False):
        k, v = self.columns(table)
        order = 'DESC' if reverse else 'ASC'
        return [(key, self.decode(table, value)) for key, value in self.connection.execute(f'SELECT {k},{v} FROM {table} ORDER BY rowid {order}')]

    def put(self, table, key, value, ignore=False):
        self.columns(table)
        if table not in ('mappings', 'rules', 'file_cleanup'): value = json.dumps(value, ensure_ascii=False)
        mode = 'IGNORE' if ignore else 'REPLACE'
        self.connection.execute(f'INSERT OR {mode} INTO {table} VALUES (?,?)', (key, value))

    def delete(self, table, key):
        k, _ = self.columns(table)
        self.connection.execute(f'DELETE FROM {table} WHERE {k}=?', (key,))

    def clear(self, table):
        self.columns(table)
        self.connection.execute(f'DELETE FROM {table}')

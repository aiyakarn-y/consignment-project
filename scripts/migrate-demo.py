"""Copy a stopped v0.1 demo into this workspace; never modify source data."""
import argparse
from contextlib import closing
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.config import DATA, ROOT
from backend.operations import TABLES, checked_backup
from backend.storage import LocalFileStore


def digest(data):
    return hashlib.sha256(data).hexdigest()


def migrate(source: Path, destination: Path):
    source = source.resolve()
    destination = destination.resolve()
    if source == destination or destination.is_relative_to(source):
        raise ValueError('Destination must be outside the legacy data directory')
    target_db = destination / 'database/consignment-system.sqlite3'
    if target_db.exists():
        raise FileExistsError('Destination database exists; refusing to overwrite it')
    store = LocalFileStore(destination)
    store.prepare()
    run_id = uuid.uuid4().hex
    stage_db = destination / 'temp' / (run_id + '.sqlite3')
    created = []
    with closing(sqlite3.connect((source/'demo.sqlite3').as_uri()+'?mode=ro', uri=True)) as old:
        with closing(sqlite3.connect(stage_db)) as stage:
            old.backup(stage)
    try:
        with closing(sqlite3.connect(stage_db)) as connection:
            connection.execute('PRAGMA journal_mode=DELETE')
            tables = {name: [list(r) for r in connection.execute(f'SELECT * FROM {name}')] for name in TABLES}
            original_tables = deepcopy(tables)
            assets = {}
            mapping = {}
            for _, body in tables['batches']:
                batch = json.loads(body)
                for f in batch['files']:
                    key = f"imports/{batch['id']}/{Path(f['path']).name}"
                    mapping[f['path']] = key
                    assets[f['path']] = f['hash']
            for _, body in tables['export_history']:
                record = json.loads(body)
                mapping[record['path']] = 'exports/'+Path(record['path']).name
                assets[record['path']] = record['hash']
            # Validate every source reference and checksum before copying anything.
            content = {}
            source_store = LocalFileStore(source)
            for name, expected in assets.items():
                value = source_store.read(name)
                if digest(value) != expected:
                    raise ValueError('Source checksum mismatch: '+name)
                content[name] = value
            from datetime import datetime, timezone
            manifest = dict(format='consign-demo-backup', version=1,
                            created=datetime.now(timezone.utc).isoformat(), tables=original_tables, assets=assets)
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
                for name, value in content.items():
                    z.writestr('files/'+name, value)
            checked_backup(archive.getvalue())
            migration_backup = 'backups/migration-'+run_id+'.zip'
            store.write(migration_backup, archive.getvalue())
            for name, value in content.items():
                key = mapping[name]
                store.write(key, value)
                created.append(key)
            for table in ('batches', 'export_history'):
                for key, body in tables[table]:
                    obj = json.loads(body)
                    if table == 'batches':
                        for f in obj['files']:
                            f['path'] = mapping[f['path']]
                    else:
                        obj['path'] = mapping[obj['path']]
                    connection.execute(f'UPDATE {table} SET body=? WHERE id=?', (json.dumps(obj, ensure_ascii=False), key))
            connection.execute('CREATE TABLE IF NOT EXISTS file_cleanup (path TEXT PRIMARY KEY, last_error TEXT)')
            connection.execute('PRAGMA user_version=2')
            connection.commit()
            counts = {name: connection.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0] for name in TABLES}
            # Only storage paths may change; all business values and identifiers are preserved.
            for table in TABLES:
                actual = [list(r) for r in connection.execute(f'SELECT * FROM {table}')]
                expected = deepcopy(original_tables[table])
                if table in ('batches', 'export_history'):
                    for record in expected:
                        obj = json.loads(record[1])
                        if table == 'batches':
                            for f in obj['files']:f['path'] = mapping[f['path']]
                        else:obj['path'] = mapping[obj['path']]
                        record[1] = json.dumps(obj, ensure_ascii=False)
                if actual != expected:raise ValueError('Record mismatch: '+table)
            for name, key in mapping.items():
                if digest(store.read(key)) != assets[name]:raise ValueError('Destination checksum mismatch: '+key)
        for legacy_backup in (source/'backups').glob('*.zip'):
            key = 'backups/'+legacy_backup.name
            if store.exists(key):
                if store.read(key) != legacy_backup.read_bytes():raise ValueError('Backup name conflict')
            else:
                store.write(key, legacy_backup.read_bytes());created.append(key)
        # Make the database visible last; originals and migration ZIP remain available.
        stage_db.replace(target_db)
        return dict(counts=counts, rows=sum(len(json.loads(b)['rows']) for _, b in tables['batches']),
                    referenced_files=len(assets), migration_backup=migration_backup,
                    source_records_sha256=digest(json.dumps(original_tables, sort_keys=True).encode()),
                    business_records_preserved=True, source_files_unchanged=True,
                    legacy_unreferenced_assets=sum(p.name not in assets for p in source.glob('*.xlsx'))+sum(p.name not in assets for p in source.glob('*.pdf')))
    except Exception:
        for key in reversed(created):store.delete(key)
        raise
    finally:
        stage_db.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Stopped demo _wrx-output/data directory')
    parser.add_argument('--destination', type=Path, default=DATA)
    args = parser.parse_args()
    report = migrate(args.source, args.destination)
    evidence = ROOT/'_wrx-output/evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence/'migration.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))

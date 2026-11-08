"""One finite synthetic import. Live mode is deliberately unsupported."""
import os
from .postgres import PostgresStore
from .research_adapter import run_fixture
from .store import canonical


def main():
    if os.environ.get('PMS_MODE') != 'synthetic-replay':
        raise SystemExit('Only explicit synthetic-replay mode is supported')
    payload = run_fixture(os.environ['PMS_RESEARCH_SOURCE'])
    store = PostgresStore(os.environ['PMS_WRITER_DATABASE_URL'])
    try:
        snapshot_id, created = store.save('synthetic-ten-name-v1/original', payload)
        print(canonical({'snapshot_id': snapshot_id, 'inserted': created, 'mode': 'synthetic-replay'}))
    finally:
        store.close()


if __name__ == '__main__':
    main()

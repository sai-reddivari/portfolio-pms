import argparse
from pathlib import Path
from .store import Store, canonical
from .public import project, render


def main():
    parser = argparse.ArgumentParser(description='Local synthetic research integration only')
    parser.add_argument('--research-source', required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    from .research_adapter import run_fixture
    payload = run_fixture(args.research_source)
    db = Store(args.database)
    try:
        snapshot_id, created = db.save('synthetic-ten-name-v1/original', payload)
        verified_id, saved = db.load(snapshot_id)
        public = project(verified_id, saved)
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        # Re-exporting after a crash does not rerun or mutate stored effects.
        for name, content in [('snapshot.json', canonical(public)), ('index.html', render(public))]:
            temporary = output / (name + '.tmp')
            temporary.write_text(content)
            temporary.replace(output / name)
        print(canonical({'snapshot_id': snapshot_id, 'inserted': created,
                         'mode': payload['mode'], 'reconciled': True}))
    finally:
        db.close()


if __name__ == '__main__':
    main()

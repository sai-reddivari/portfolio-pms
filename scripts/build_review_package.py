"""Build an allowlisted local review archive; never include work/ or credentials."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    '.dockerignore', '.gitignore', 'README.md', 'Dockerfile',
    'requirements-runtime.txt', 'research.lock.json',
    'deploy/app-spec.review.yaml', 'deploy/resources-review.json',
    'deploy/postgres-schema-proposal.sql', 'deploy/database-roles.review.sql',
    'integration/README.md', 'integration/test_postgres.py',
    'scripts/build_review_package.py',
    'scripts/container_smoke.py', '.github/workflows/container.yml',
    'preview/index.html', 'preview/snapshot.json',
]
FILES += [str(p.relative_to(ROOT)) for folder in ['paper_pms', 'tests']
          for p in sorted((ROOT/folder).glob('*.py'))]


def main():
    manifest = {'status': 'REVIEW ONLY: not deployable until listed release gates pass',
                'contains_secrets': False, 'includes_research_source': False,
                'research_pin': json.loads((ROOT/'research.lock.json').read_text()),
                'files': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                          for name in sorted(FILES)}}
    output = ROOT/'outputs/pms-deployment-review.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(FILES):
            entry = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, (ROOT/name).read_bytes())
        entry = zipfile.ZipInfo('REVIEW-MANIFEST.json', date_time=(2026, 11, 7, 0, 0, 0))
        archive.writestr(entry, json.dumps(manifest, indent=2)+'\n')
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for name, digest in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (ROOT/'outputs/pms-deployment-review.sha256').write_text(f'{digest}  {output.name}\n')
    print(json.dumps({'archive': str(output), 'files': len(FILES)+1, 'sha256': digest}))


if __name__ == '__main__':
    main()

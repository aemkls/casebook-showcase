"""Validate the published indexes, source files, the 32 example quotations and criminal/civil-case anonymization."""
import argparse
import base64
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'static' / 'data'

# Streets named after people ("ул. Молдагалиева А.") are not participants of a case.
STREET_NAMES = {'Молдагалиева', 'Блока'}   # «Блока Б.» is a building block, not a person
NAME_WITH_INITIALS = re.compile(r'(?<![А-ЯЁа-яё])([А-ЯЁ][а-яё]{2,})\s?[А-ЯЁ]\.(?:\s?[А-ЯЁ]\.)?(?![а-яё])')
FULL_NAME = re.compile(r'(?<![А-ЯЁа-яё])[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:ович|евич|овна|евна|ична)(?![а-яё])')


def decode(path):
    return gzip.decompress(base64.b64decode(path.read_bytes(), validate=True)).decode('utf-8')


def load_bucket(data_dir, prefix, cache):
    if prefix not in cache:
        bucket = data_dir / 'source-bundles' / f'{prefix}.json.gz'
        cache[prefix] = json.loads(gzip.decompress(bucket.read_bytes()).decode('utf-8'))
    return cache[prefix]


def validate(data_dir=DATA):
    payload = json.loads(decode(data_dir / 'offline-payload.b64'))
    records = payload['records']
    assert len(records) == payload['stats']['files'], 'File count mismatch'
    assert len({row[0] for row in records}) == len(records), 'Duplicate document ids'
    assert sum(not row[14] for row in records) == payload['stats']['unique'], 'Unique count mismatch'
    examples = {example['id']: example for example in payload['examples']}
    quotes = 0
    buckets = {}
    for row in records:
        doc_id = row[0]
        text = load_bucket(data_dir, doc_id[:2].lower(), buckets).get(doc_id)
        assert isinstance(text, str), f'Missing document: {doc_id}'
        assert text.strip(), f'Empty document: {doc_id}'
        for quote in examples.get(doc_id, {}).get('quotes', []):
            assert text[quote['start']:quote['end']] == quote['text'], f'Quote offset: {doc_id}'
            assert text.count('\n', 0, quote['start']) + 1 == quote['line'], f'Quote line: {doc_id}'
            quotes += 1
    assert quotes == sum(len(example['quotes']) for example in examples.values()), 'Missing example source'
    print(f'Checked {len(records):,} source texts in {len(buckets)} bundles and {quotes} quotations.')


def validate_criminal(data_dir=DATA / 'criminal'):
    payload = json.loads(decode(data_dir / 'offline-payload.b64'))
    records = payload['records']
    stats = payload['stats']
    assert len(records) == stats['files'], 'Criminal file count mismatch'
    assert len({row[0] for row in records}) == len(records), 'Duplicate criminal ids'
    assert all(row[4] in stats['topics'] for row in records if not row[14]), 'Unknown criminal category'
    assert all(row[7] in stats['labels'] for row in records), 'Unknown criminal outcome'
    assert {key for key, _ in stats['factorColumns']} | {''} >= {row[15] for row in records}, 'Unknown punishment type'
    assert all(row[15] for row in records if row[7] in ('convicted', 'partial')), 'Convicted without punishment type'
    buckets = {}
    leaks = []
    for row in records:
        text = load_bucket(data_dir, row[0][:2].lower(), buckets).get(row[0])
        assert isinstance(text, str) and text.strip(), f'Missing criminal document: {row[0]}'
        assert 'ФИО-1' in text, f'No anonymized names: {row[0]}'
        leaks += [(row[0], m.group(0)) for m in NAME_WITH_INITIALS.finditer(text) if m.group(1) not in STREET_NAMES
                  and not re.search(r'(?:ул\.|улиц\w*|пр\.|проспект\w*)\s*$', text[max(0, m.start() - 12):m.start()])]
        leaks += [(row[0], m.group(0)) for m in FULL_NAME.finditer(text)]
        assert not re.search(r'(?<!\d)\d{12}(?!\d)', text), f'Possible IIN: {row[0]}'
    assert not leaks, f'Possible personal names: {leaks[:10]}'
    print(f'Checked {len(records):,} criminal verdicts in {len(buckets)} bundles: names replaced, no IIN found.')


def validate_civil(data_dir=DATA / 'civil'):
    payload = json.loads(decode(data_dir / 'offline-payload.b64'))
    records = payload['records']
    stats = payload['stats']
    assert len(records) == stats['files'], 'Civil file count mismatch'
    assert len({row[0] for row in records}) == len(records), 'Duplicate civil ids'
    assert all(row[4] in stats['topics'] for row in records if not row[14]), 'Unknown civil category'
    assert all(row[7] in stats['labels'] for row in records), 'Unknown civil outcome'
    buckets = {}
    leaks = []
    for row in records:
        text = load_bucket(data_dir, row[0][:2].lower(), buckets).get(row[0])
        assert isinstance(text, str) and text.strip(), f'Missing civil document: {row[0]}'
        assert 'ФИО-1' in text, f'No anonymized names: {row[0]}'
        assert not re.search(r'^\s*\d{1,3}\s*$', text, re.M), f'Line numbers in text: {row[0]}'
        leaks += [(row[0], m.group(0)) for m in NAME_WITH_INITIALS.finditer(text) if m.group(1) not in STREET_NAMES
                  and not re.search(r'(?:ул\.|улиц\w*|пр\.|проспект\w*)\s*$', text[max(0, m.start() - 12):m.start()])]
        leaks += [(row[0], m.group(0)) for m in FULL_NAME.finditer(text)]
        assert not re.search(r'(?<!\d)\d{12}(?!\d)', text), f'Possible IIN: {row[0]}'
    assert not leaks, f'Possible personal names: {leaks[:10]}'
    print(f'Checked {len(records):,} civil judgments in {len(buckets)} bundles: names replaced, no IIN found.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=DATA)
    args = parser.parse_args()
    validate(args.data_dir)
    if (args.data_dir / 'criminal' / 'offline-payload.b64').exists():
        validate_criminal(args.data_dir / 'criminal')
    if (args.data_dir / 'civil' / 'offline-payload.b64').exists():
        validate_civil(args.data_dir / 'civil')

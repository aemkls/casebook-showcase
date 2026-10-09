"""Anonymize civil judgments: same rules as criminal verdicts (see anonymize_criminal.py), plus a sweep.

Names become ФИО-N (numbered per document by first appearance), exact birth dates are cut to the year,
IIN and home addresses are hidden. After the shared pipeline a final sweep replaces any remaining
«Фамилия И.О.» that the model and the dictionary missed. Requires: pip install natasha pymorphy3
"""
import argparse
import re
from pathlib import Path

from anonymize_criminal import anonymize, renumber, stem, UP, LO

SURNAME_INITIALS = re.compile(f'(?<![{UP}{LO}])([{UP}][{LO}]{{2,}})\\s?[{UP}]\\.(?:\\s?[{UP}]\\.)?(?![{LO}])')
# Words that look like «Слово И.» but are not people («Блока Б.» — a building block of a residential complex).
NOT_PEOPLE = {stem(word) for word in ('Блока', 'Блок', 'Литер', 'Секция', 'Подъезд', 'Очередь', 'Корпус')}
# Names that stay visible: they are not participants of the case.
KEEP = set()
# Residual first names found while reading the corpus (replaced as whole words, all case forms of the listed stem).
MANUAL_NAMES = []
# A line holding only a number is a page number of the source document.
PAGE_NUMBER = re.compile(r'^[ \t]*\d{1,3}[ \t]*\n', re.M)


def sweep(text):
    top = max((int(n) for n in re.findall(r'ФИО-(\d+)', text)), default=0)
    ids = {}

    def replace(match):
        key = stem(match.group(1))
        if key in NOT_PEOPLE or match.group(1) in KEEP:
            return match.group(0)
        nonlocal top
        if key not in ids:
            top += 1
            ids[key] = top
        return f'ФИО-{ids[key]}'

    text = SURNAME_INITIALS.sub(replace, text)
    for name in MANUAL_NAMES:
        pattern = re.compile(rf'(?<![{UP}{LO}\-]){name}[{LO}]{{0,3}}(?![{LO}])')
        if pattern.search(text):
            top += 1
            text = pattern.sub(f'ФИО-{top}', text)
    return text


def anonymize_civil(text):
    text = PAGE_NUMBER.sub('', text)
    result, ids = anonymize(text)
    return renumber(sweep(result)), ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_dir', type=Path, help='Folder with raw judgment .txt files (not committed)')
    parser.add_argument('output_dir', type=Path, help='Folder for anonymized .txt files')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(args.source_dir.glob('*.txt'))
    persons = 0
    for path in files:
        text = path.read_text(encoding='utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
        result, ids = anonymize_civil(text)
        persons += len(set(ids.values()))
        (args.output_dir / path.name).write_text(result, encoding='utf-8')
    print(f'Anonymized {len(files)} judgments, {persons:,} person references replaced with ФИО-N.')


if __name__ == '__main__':
    main()

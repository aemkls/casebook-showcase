"""Build the civil-case index and text bundles from anonymized judgments.

Input: a folder of anonymized .txt files (see scripts/anonymize_civil.py).
Output: static/data/civil/offline-payload.b64 and static/data/civil/source-bundles/<x>.json.gz,
in the same format as the criminal section (see build_criminal.py) so one interface reads both.
The category comes from the claims («ТРЕБОВАНИЯ ИСТЦА», «по иску … о …»), never from words mentioned
elsewhere in the text; the outcome is read from the operative part after «РЕШИЛ»/«ПОСТАНОВИЛ».
Texts in Kazakh are skipped: the interface, search and anonymization are Russian-only.
All labels are automatic.
"""
import argparse
import base64
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from build_criminal import ADMIN_PAYLOAD, STOP_WORDS, parse_court, parse_date, plain, search_tokens, sentence_around, sentence_with

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'static' / 'data' / 'civil'

# (key, title, pattern over the claims); the highest number of matches wins, ties go to the earlier row.
CATEGORIES = [
    ('inheritance', 'Наследство', r'наследств|наследодател|наследник'),
    ('family', 'Семейные споры', r'супруг|совместн\w+\s+нажит|общ\w+\s+совместн|алимент|общени\w+\s+с\s+(?:ребенк|дочер|сын|детьм)|расторжени\w+\s+брака|места\s+жительства\s+(?:ребенк|несовершеннолет)|родительск'),
    ('labor', 'Трудовые споры', r'восстановлени\w+\s+на\s+работе|увольнени|трудов\w+\s+договор|дисциплинарн|вынужденн\w+\s+прогул|заработн\w+\s+плат|отпускн'),
    ('corporate', 'Корпоративные споры', r'общ\w+\s+собрани|участник\w+\s+товарищества|собрани\w+\s+(?:участников|акционеров|членов)|уставн\w+\s+капитал|совет\w+\s+директоров|кооператив|акционер|\bосси?\b|протокол'),
    ('honor', 'Честь, достоинство и деловая репутация', r'чест[ьи]|достоинств|деловой\s+репутаци|опроверг|порочащ|моральн'),
    ('construction', 'Строительство и жильё', r'долев\w+\s+участи|строительств|эксплуатацию|жилищн\w+\s+комплекс|застройщик|квартир'),
    ('property', 'Право собственности и имущество', r'освобожден\w+\s+(?:\S+\s+){0,3}(?:от\s+)?(?:арест|описи)|истребовани|виндикац|право\s+собственности|выселен|самовольн|земельн\w+\s+участк|аренд|парковочн|прекращении\s+права'),
    ('transactions', 'Недействительность сделок и договоров', r'недействительн|сделк|расторжени\w+\s+договор|применени\w+\s+последстви'),
    ('debt', 'Взыскание задолженности', r'задолженност|неустойк|штраф|займ|кредит|предоплат|взыскани\w+\s+(?:суммы|долга|денежн)|пени\b'),
    ('damage', 'Возмещение вреда и ущерба', r'возмещени\w+\s+(?:вреда|ущерб|стоимост)|ущерб|вред'),
    ('public', 'Споры с государственными органами', r'незаконн\w+\s+(?:действи|бездействи|приказ|постановлени|решени)|акимат|предписани|исполнить\s+предписание'),
    ('other', 'Прочие гражданские дела', r'(?!)'),
]
TOPICS = {key: title for key, title, _ in CATEGORIES}

# The same groups written for a user's question (matched against the lowercased query).
TOPIC_WORDS = {
    'inheritance': 'наследств|наследник|завещани|умер',
    'family': 'развод|алимент|супруг|муж|жена|ребен|ребён|дет[иь]|брак|опек|общени',
    'labor': 'уволи|увольн|работодател|зарплат|заработн|трудов|дисциплинарн|прогул|восстанов',
    'corporate': 'собрани|участник|товарищест|акционер|директор|доля|кооператив|осси',
    'honor': 'честь|достоинств|репутац|опроверг|клевет|порочащ|моральн',
    'construction': 'застройщик|долев|квартир|новострой|строительств|жк\\b|дду',
    'property': 'арест|имуществ|собственност|выселен|самовольн|земельн|участок|аренд|истреб',
    'transactions': 'недействительн|сделк|договор.{0,15}(?:купли|дарени|залог)|расторж|оспор',
    'debt': 'долг|задолженност|займ|кредит|неустойк|штраф|деньги|взыскат|предоплат',
    'damage': 'ущерб|вред|возмещ|повредил|затоп|дтп|авари',
    'public': 'акимат|орган|предписани|незаконн.{0,10}(?:действи|бездействи)|государствен',
}

LABELS = {
    'granted': 'Иск удовлетворён',
    'partial': 'Частично удовлетворён',
    'refused': 'Отказано в иске',
    'terminated': 'Прекращено или без рассмотрения',
    'upheld': 'Апелляция: без изменения',
    'overturned': 'Апелляция: решение отменено',
    'changed': 'Апелляция: решение изменено',
    'review': 'Нужна проверка',
}
COLUMNS = [['granted', LABELS['granted']], ['partial', LABELS['partial']], ['refused', LABELS['refused']]]

# Phrases from the reasoning part counted by outcome of the case.
FACTORS = [
    ('limitation', 'Срок исковой давности', r'исков\w+\s+давност'),
    ('expertise', 'Экспертиза', r'экспертиз'),
    ('witness', 'Показания свидетелей', r'показани\w+\s+свидетел|свидетел\w+\s+(?:пояснил|показал|подтвердил)'),
    ('contract', 'Условия договора', r'услови\w+\s+договор|согласно\s+договор|в\s+соответствии\s+с\s+договор'),
    ('burden', 'Бремя доказывания', r'бремя\s+доказывани|обязан\w*\s+доказать|не\s+представил\w*\s+(?:\S+\s+){0,2}доказательств|не\s+доказал'),
    ('good_faith', 'Добросовестность', r'добросовестн'),
    ('penalty_reduced', 'Снижение неустойки', r'сниз\w+\s+(?:размер\w*\s+)?неустойк|несоразмерн\w+\s+(?:\S+\s+){0,3}неустойк|297\s+ГК'),
    ('claim_admitted', 'Признание иска ответчиком', r'признал\w*\s+иск|иск\s+признал|признани\w+\s+иска'),
    ('settlement', 'Медиация или мировое соглашение', r'медиац|мирово\w+\s+соглашени'),
    ('state_fee', 'Государственная пошлина', r'государственн\w+\s+пошлин|госпошлин'),
    ('prosecutor', 'Участие прокурора', r'прокурор'),
]

CIVIL_STOP = ['истец', 'истца', 'истцу', 'ответчик', 'ответчика', 'ответчику', 'иск', 'иска', 'иску', 'исковые', 'требования',
              'требований', 'решение', 'решения', 'суд', 'суда', 'судья', 'судебное', 'гражданское', 'гражданского', 'гпк',
              'представитель', 'представителя', 'заседании', 'заседание', 'жалоба', 'коллегия', 'апелляционной']


# Court case numbers look like 7585-24-00-2/101 or 3599-24-00 -2а/2151; contract numbers must not match.
CASE_NUMBER = re.compile(r'(\d{4}\s*-\s*\d{2}\s*-\s*\d{2}\s*-\s*\d[а-яa-z]?\s*[/\\]\s*\d+)')

CASE_NUMBER_SHORT = re.compile(r'(?:дело\s*)?№\s*(\d[а-яa-z]-\d+\s*/\s*\d{2,4})', re.I)


def is_kazakh(text):
    lower = text.lower()
    return len(re.findall(r'[әғқңөұүһі]', lower)) > 0.04 * max(1, len(re.findall(r'[а-яё]', lower)))


def head_kind(text):
    """'decision' (first instance), 'appeal' (appeal ruling) or 'other' (technical rulings, not published)."""
    squeezed = re.sub(r'\s+', '', plain(text[:600])).upper()
    title = min((squeezed.find(word) for word in ('РЕШЕНИЕ', 'ПОСТАНОВЛЕНИЕ', 'ОПРЕДЕЛЕНИЕ') if word in squeezed), default=-1)
    if title >= 0 and squeezed[title:title + 6] == 'РЕШЕНИ':
        return 'decision'
    if re.search(r'апелляционн\w+\s+(?:жалоб|протест|ходатайств)', plain(text[:5000]), re.I) and re.search(r'судебн\w+\s+коллеги', text[:1500], re.I):
        return 'appeal'
    return 'decision' if re.search(r'иск\w*[^.]{0,300}(?:удовлетворить|отказать)', plain(operative_part(text))[:3000]) else 'other'


def operative_part(text):
    marks = list(re.finditer(r'Р\s*Е\s*Ш\s*И\s*Л\s*[АИ]?\b|П\s*О\s*С\s*Т\s*А\s*Н\s*О\s*В\s*И\s*Л\s*[АИ]?\b|О\s*П\s*Р\s*Е\s*Д\s*Е\s*Л\s*И\s*Л\s*[АИ]?\b', text))
    return text[marks[-1].end():] if marks else text[-4000:]


CLAIM_END = r'В\s+СУДЕ\s+УЧАСТВОВАЛИ|ОПИСАТЕЛЬНАЯ|ИСТ[ЕЦ]+\w*\s+ПО\s+ВСТРЕЧН|ОТВЕТЧИК\w*\s+ПО\s+ВСТРЕЧН|ТРЕТЬ[ИЕ]\s+ЛИЦ|УСТАНОВИЛ'


def claims(text):
    """Claim text: the block «ТРЕБОВАНИЯ ИСТЦА» or the subject in «по иску … о …» of the introduction."""
    text = plain(text)
    m = re.search(r'ТРЕБОВАНИЯ\s+ИСТ[ЕЦ]\w*(?:\s+ПО\s+ПЕРВОНАЧАЛЬН\w+\s+ИСКУ)?\s*:?\s*(.{20,2500}?)(?=' + CLAIM_END + r'|$)', text, re.S)
    if m:
        return re.sub(r'\s+', ' ', m.group(1)).strip()
    m = re.search(r'(?:дело|дела)\s+по\s+(?:исковому\s+заявлению|иску)\s+(.{0,1200}?)(?:,?\s+(?:поступивш|по\s+апелляц|по\s+жалоб|в\s+связи|установил)|$)', text[:6000], re.S | re.I)
    if m:
        body = re.sub(r'\s+', ' ', m.group(1))
        subject = re.search(r'(?:^|[\s,])(?:[Оо]б?|[Пп]ризнан\w+|[Вв]зыскан\w+)\s+[а-яё]{4,}.*', body)
        return subject.group(0).strip(' ,') if subject else ''
    return ''


def category(claim, text):
    best, best_score = 'other', 0
    for key, _, pattern in CATEGORIES:
        score = len(re.findall(pattern, claim.lower().replace('ё', 'е')))
        if score > best_score:
            best, best_score = key, score
    if best_score:
        return best, 'высокая'
    body = plain(text)[:12000].lower()   # no claims found: the descriptive part decides, with a higher bar
    scores = [(len(re.findall(pattern, body)), -i, key) for i, (key, _, pattern) in enumerate(CATEGORIES[:-1])]
    score, _, key = max(scores)
    return (key, 'средняя') if score >= 4 else ('other', 'низкая')


def outcome(text, kind):
    part = plain(operative_part(text)).lower()
    part = re.sub(r'\s+', ' ', part)
    if kind == 'appeal':
        if re.search(r'решение[^.]{0,250}?отменить|отменить\s+(?:решение|в\s+части)|вынести\s+новое', part):
            return 'overturned', 'высокая', 'Решение суда первой инстанции отменено'
        if re.search(r'решение[^.]{0,250}?изменить|изменить\s+(?:решение|в\s+части)|решение[^.]{0,250}?изложить', part):
            return 'changed', 'высокая', 'Решение суда первой инстанции изменено'
        if re.search(r'без\s+изменени|без\s+удовлетворения|жалоб\w*[^.]{0,200}?отказать|отказать[^.]{0,80}жалоб', part):
            return 'upheld', 'высокая', 'Решение оставлено без изменения'
        return 'review', 'низкая', 'Итог апелляции не найден автоматически'
    if re.search(r'производство\s+по\s+(?:настоящему\s+)?(?:гражданскому\s+)?делу\s+прекратить|прекратить\s+производство|оставить\s+(?:иск\w*\s+)?без\s+рассмотрени|утвердить\s+мирово', part):
        return 'terminated', 'высокая', 'Производство прекращено, иск оставлен без рассмотрения или утверждено мировое соглашение'
    part = re.split(r'(?:на\s+(?:настоящее\s+)?)?(?:решение|постановление)\s+(?:может|подлежит)\s+(?:быть\s+)?(?:обжал|подан|исполн)|может\s+быть\s+(?:подана|обжаловано)', part)[0]
    refused = granted = partly = False
    for sentence in re.split(r'(?<=[.;])\s+(?=[а-яёa-z«"(])|(?<=[.;])\s+', part):
        if not re.search(r'иск|требовани|заявлени|жалоб|ходатайств', sentence) or 'расход' in sentence and 'иск' not in sentence:
            continue
        if re.search(r'отказать|без\s+удовлетворения|отказано', sentence):
            refused = True
        if re.search(r'частично\s+удовлетвор|удовлетворить\s+частично|в\s+остальной\s+части', sentence):
            partly = True
        if re.search(r'удовлетворить|удовлетворен', sentence) and not re.search(r'отказать|без\s+удовлетворения', sentence):
            granted = True
    if not (refused or granted or partly):
        refused = bool(re.search(r'отказать', part))
        granted = not refused and bool(re.search(r'\b(?:признать|обязать|взыскать|освободить|восстановить|направить|определить|произвести|установить|расторгнуть)\b', part))
    if partly or refused and granted:
        return 'partial', 'высокая' if partly else 'средняя', 'Требования удовлетворены частично или в части отказано'
    if refused:
        return 'refused', 'высокая', 'В резолютивной части отказано в удовлетворении'
    if granted:
        return 'granted', 'высокая', 'В резолютивной части требования удовлетворены'
    return 'review', 'низкая', 'Исход не найден автоматически'


def fragments(text, kind):
    part_start = len(text) - len(operative_part(text))
    rows = []
    sentence = sentence_around(text, part_start, min(len(text), part_start + 160), limit=420)
    if sentence:
        rows.append({'label': 'Резолютивная часть', 'quote': sentence})
    quote = sentence_with(text, r'суд\s+(?:приходит\s+к\s+выводу|считает|находит|полагает|не\s+находит)|судебная\s+коллегия\s+(?:приходит\s+к\s+выводу|считает|находит|полагает)')
    if quote:
        rows.append({'label': 'Вывод суда', 'quote': quote})
    return rows


def build(source_dir, out_dir=OUT):
    files = sorted(source_dir.glob('*.txt'))
    if not files:
        raise SystemExit(f'No .txt files in {source_dir}')
    records, texts, seen, skipped, skipped_other = [], {}, {}, 0, 0
    factor_counts = Counter()
    for path in files:
        text = path.read_text(encoding='utf-8').replace('\r\n', '\n')
        if is_kazakh(text):
            skipped += 1
            continue
        doc_id = path.stem.lower()
        texts[doc_id] = text
        head = text[:1500]
        digest = hashlib.sha1(re.sub(r'\s+', ' ', text).strip().encode()).hexdigest()
        duplicate = seen.setdefault(digest, doc_id)
        duplicate = '' if duplicate == doc_id else duplicate
        number = CASE_NUMBER.search(plain(text[:2500])) or CASE_NUMBER_SHORT.search(plain(text[:2500]))
        kind = head_kind(text)
        if kind == 'other':
            texts.pop(doc_id)
            skipped_other += 1
            continue
        claim_text = claims(text)
        topic, topic_confidence = category(claim_text, text)
        verdict, confidence, basis = outcome(text, kind)
        claim = ('Требования: ' + claim_text[:300].rstrip(' ,;') + ('…' if len(claim_text) > 300 else '')) if claim_text else ''
        records.append([doc_id, parse_date(head), re.sub(r'\s+', '', number.group(1)).replace('\\', '/') if number else '', parse_court(head), topic, TOPICS[topic],
                        claim, verdict, confidence, topic_confidence, basis, fragments(text, kind),
                        search_tokens(text), 'appeal' if kind == 'appeal' else 'decision', duplicate, ''])
        if not duplicate and verdict in {key for key, _ in COLUMNS}:
            reasons = text[len(text) // 3:]
            for key, label, pattern in FACTORS:
                if re.search(pattern, reasons, re.I):
                    factor_counts[(topic, key, label, verdict)] += 1

    unique = [row for row in records if not row[14]]
    stats = {
        'files': len(records), 'unique': len(unique),
        'outcomes': dict(Counter(row[7] for row in unique)),
        'topics': {key: title for key, title in TOPICS.items() if any(row[4] == key for row in unique)},
        'labels': LABELS,
        'counts': [{'topic': t, 'outcome': o, 'n': n} for (t, o), n in sorted(Counter((r[4], r[7]) for r in unique).items())],
        'method': 'Автоматическая разметка по требованиям истца и резолютивной части. Имена заменены на ФИО-N.',
        'dates': [{'year': y, 'n': n} for y, n in sorted(Counter(r[1][:4] for r in unique).items())],
        'section': 'civil',
        'factorColumns': COLUMNS,
        'skippedKazakh': skipped, 'skippedOther': skipped_other,
    }
    stop = set(STOP_WORDS) | set(CIVIL_STOP)
    if ADMIN_PAYLOAD.exists():
        stop |= set(json.loads(gzip.decompress(base64.b64decode(ADMIN_PAYLOAD.read_bytes())))['stop'])
    payload = {
        'stats': stats, 'records': records, 'examples': [], 'guides': {}, 'stop': sorted(stop),
        'topicWords': TOPIC_WORDS,
        'factorRows': [{'topic': t, 'factor': f, 'label': label, 'outcome': o, 'n': n}
                       for (t, f, label, o), n in sorted(factor_counts.items())],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    (out_dir / 'offline-payload.b64').write_bytes(base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)))
    bundles = defaultdict(dict)
    for doc_id, text in texts.items():
        bundles[doc_id[:2]][doc_id] = text
    bundle_dir = out_dir / 'source-bundles'
    bundle_dir.mkdir(exist_ok=True)
    for old in bundle_dir.glob('*.json.gz'):
        old.unlink()
    for prefix, documents in sorted(bundles.items()):
        data = json.dumps(documents, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()
        (bundle_dir / f'{prefix}.json.gz').write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
    return stats, len(bundles)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_dir', type=Path, help='Folder with anonymized judgments')
    parser.add_argument('--output-dir', type=Path, default=OUT)
    args = parser.parse_args()
    stats, bundles = build(args.source_dir, args.output_dir)
    print(f"Built {stats['unique']:,} civil cases ({stats['files']} files, {stats['skippedKazakh']} in Kazakh and {stats['skippedOther']} technical rulings skipped) in {bundles} bundles.")
    print('Outcomes:', stats['outcomes'])
    print('Topics:', Counter({k: sum(1 for c in stats['counts'] if c['topic'] == k for _ in range(c['n'])) for k in stats['topics']}))

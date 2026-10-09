"""Build the criminal-case index and text bundles from anonymized verdicts.

Input: a folder of anonymized .txt files (see scripts/anonymize_criminal.py).
Output: static/data/criminal/offline-payload.b64 and static/data/criminal/source-bundles/<x>.json.gz.
Categories come from the first Special-Part article of the Criminal Code in the charge;
outcome and punishment are read from the operative part. All labels are automatic.
"""
import argparse
import base64
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'static' / 'data' / 'criminal'
ADMIN_PAYLOAD = ROOT / 'static' / 'data' / 'offline-payload.b64'

# Titles of the Criminal Code of the Republic of Kazakhstan (K1400000226) for articles met in the corpus.
ARTICLES = {
    '99': 'Убийство', '101': 'Убийство в состоянии аффекта', '104': 'Причинение смерти по неосторожности',
    '106': 'Умышленное причинение тяжкого вреда здоровью', '107': 'Умышленное причинение средней тяжести вреда здоровью',
    '108': 'Умышленное причинение легкого вреда здоровью', '118': 'Заражение ВИЧ',
    '122': 'Половое сношение с лицом, не достигшим шестнадцатилетнего возраста', '108-1': 'Умышленное причинение легкого вреда здоровью',
    '109': 'Побои', '109-1': 'Побои', '110': 'Истязание', '115': 'Угроза', '119': 'Оставление в опасности',
    '120': 'Изнасилование', '121': 'Насильственные действия сексуального характера',
    '124': 'Развращение лиц, не достигших шестнадцатилетнего возраста', '131': 'Оскорбление',
    '139': 'Неуплата средств на содержание детей или нетрудоспособных родителей',
    '149': 'Нарушение неприкосновенности жилища', '174': 'Разжигание розни', '175': 'Государственная измена',
    '180': 'Сепаратистская деятельность', '182': 'Экстремистская группа', '187': 'Мелкое хищение',
    '188': 'Кража', '188-1': 'Скотокрадство', '189': 'Присвоение или растрата вверенного имущества',
    '190': 'Мошенничество', '191': 'Грабёж', '192': 'Разбой', '194': 'Вымогательство',
    '200': 'Неправомерное завладение транспортным средством', '214': 'Незаконное предпринимательство',
    '216': 'Выписка счёта-фактуры без фактического выполнения работ', '217': 'Финансовая пирамида', '217-1': 'Реклама финансовой пирамиды',
    '218': 'Легализация (отмывание) денег и имущества, полученных преступным путём',
    '233': 'Нарушение правил маркировки подакцизных товаров', '257': 'Террористическая группа',
    '287': 'Незаконный оборот оружия и боеприпасов', '293': 'Хулиганство',
    '295-1': 'Незаконный оборот драгоценных металлов и камней',
    '286': 'Контрабанда изъятых из обращения предметов',
    '296': 'Наркотики без цели сбыта', '297': 'Сбыт наркотических средств',
    '297-1': 'Изготовление наркотических средств в целях сбыта', '300': 'Культивирование растений, содержащих наркотики',
    '340': 'Незаконная порубка деревьев и кустарников',
    '345': 'Нарушение ПДД, повлёкшее последствия', '345-1': 'Нарушение ПДД в состоянии опьянения',
    '346': 'Управление транспортом в состоянии опьянения лицом, лишённым прав',
    '361': 'Злоупотребление должностными полномочиями', '366': 'Получение взятки', '367': 'Дача взятки',
    '368': 'Посредничество во взяточничестве', '378': 'Оскорбление представителя власти',
    '380': 'Насилие в отношении представителя власти', '429': 'Угроза или насилие в отношении сотрудника учреждения изоляции',
    '430': 'Неисполнение судебного акта',
}

# (key, title, matcher by article number); first match wins.
CATEGORIES = [
    ('murder', 'Убийства и причинение смерти', lambda n, a: 99 <= n <= 105),
    ('health', 'Вред здоровью и побои', lambda n, a: 106 <= n <= 112),
    ('sexual', 'Половые преступления', lambda n, a: 120 <= n <= 124),
    ('theft', 'Кражи', lambda n, a: n in (187, 188)),
    ('fraud', 'Мошенничество', lambda n, a: n == 190),
    ('embezzlement', 'Присвоение и растрата', lambda n, a: n == 189),
    ('robbery', 'Грабёж, разбой и вымогательство', lambda n, a: n in (191, 192, 194)),
    ('property', 'Другие преступления против собственности', lambda n, a: 193 <= n <= 213),
    ('drugs', 'Наркотики', lambda n, a: 296 <= n <= 303),
    ('traffic', 'ДТП и вождение в нетрезвом виде', lambda n, a: 344 <= n <= 353),
    ('corruption', 'Коррупция и должностные преступления', lambda n, a: 361 <= n <= 370),
    ('hooliganism', 'Хулиганство и оружие', lambda n, a: n == 293 or 287 <= n <= 292),
    ('economic', 'Экономические преступления', lambda n, a: 214 <= n <= 254 or a == '295-1'),
    ('person', 'Против личности, семьи и прав граждан', lambda n, a: 113 <= n <= 160),
    ('state', 'Экстремизм, терроризм и госбезопасность', lambda n, a: 161 <= n <= 186 or 255 <= n <= 270),
    ('authority', 'Против порядка управления и правосудия', lambda n, a: 371 <= n <= 440),
    ('other', 'Прочие уголовные дела', lambda n, a: True),
]
TOPICS = {key: title for key, title, _ in CATEGORIES}

TOPIC_WORDS = {
    'murder': 'убий|убил|смерт|труп|летальн',
    'health': 'вред.{0,10}здоров|побо|избил|избие|удар|нож|травм',
    'sexual': 'изнасил|сексуал|половы|развращ',
    'theft': 'краж|похит|украл|украд|тайно',
    'fraud': 'мошенн|обман|злоупотреблени.{0,10}довери|кредит|онлайн|предоплат',
    'embezzlement': 'присвоен|растрат|вверенн',
    'robbery': 'грабе|грабёж|разбо|вымогат|отобрал|сорвал',
    'property': 'угон|завладени.{0,15}(?:автомоб|транспорт)|поджог|уничтожени.{0,10}имуществ',
    'drugs': 'наркот|марихуан|гашиш|канабис|каннабис|психотроп|закладк|героин|мефедрон',
    'traffic': 'дтп|пдд|дорожн|наезд|опьянени.{0,30}(?:управл|водит)|лишенн.{0,20}прав',
    'corruption': 'взятк|должностн|коррупц|полномочи',
    'hooliganism': 'хулиган|оружи|обрез|патрон|боеприпас',
    'economic': 'предпринимат|счет.фактур|пирамид|налог|маркировк|акциз',
    'person': 'алимент|оскорбл|жилищ|угроз|оставлени.{0,10}опасност',
    'state': 'розн|экстрем|террор|сепарат|государственн\\w* измен',
    'authority': 'представител.{0,10}власт|полицейск|неисполнени.{0,10}(?:приговор|решени)',
}

LABELS = {
    'convicted': 'Обвинительный приговор',
    'partial': 'Частично оправдан или прекращено',
    'acquitted': 'Оправдательный приговор',
    'terminated': 'Дело прекращено',
    'review': 'Нужна проверка',
}
PUNISHMENTS = {
    'prison': 'Лишение свободы',
    'restriction': 'Ограничение свободы или условно',
    'other': 'Штраф, работы или иное',
}

# Phrases from sentencing reasons (art. 53–54 УК and procedure) counted by punishment type.
FACTORS = [
    ('confession', 'Подсудимый признал вину', r'вин[уы]\s+(?:в\s+\S+\s+)?(?:полностью\s+)?призна|признал[аи]?\s+(?:свою\s+)?вин|признани[ея]\s+вины'),
    ('remorse', 'Раскаяние в содеянном', r'раска[яи]'),
    ('turned_in', 'Явка с повинной или активное способствование', r'явк[аиу]\s+с\s+повинн|активн\w+\s+способствовани'),
    ('compensation', 'Ущерб возмещён', r'(?:возмещени[ея]|возместил[аи]?|возмещ[её]н)\s+(?:\S+\s+){0,3}(?:ущерб|вред)|ущерб\s+(?:\S+\s+){0,2}возмещ'),
    ('reconciliation', 'Примирение с потерпевшим', r'примирени|примирил'),
    ('children', 'Малолетние или несовершеннолетние дети на иждивении', r'(?:малолетн|несовершеннолетн)\w*\s+(?:\S+\s+){0,2}дет\w*|на\s+иждивении'),
    ('first_time', 'Ранее не судим', r'ранее\s+не\s+судим'),
    ('recidivism', 'Рецидив или прежние судимости', r'рецидив|ранее\s+судим|непогашенн'),
    ('intoxication', 'Состояние опьянения', r'состояни\w+\s+(?:алкогольного|наркотического)?\s*опьянени'),
    ('plea_deal', 'Процессуальное соглашение или согласительное производство', r'процессуальн\w+\s+соглашени|согласительн\w+\s+производств'),
    ('short_procedure', 'Сокращённый порядок рассмотрения', r'сокращ[её]нн\w+\s+порядк|ускоренн\w+\s+досудебн'),
]

MONTHS = {m: i for i, m in enumerate('января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split(), 1)}
STOP_WORDS = ['а', 'без', 'был', 'была', 'были', 'в', 'во', 'все', 'года', 'году', 'дела', 'дело', 'для', 'до', 'его', 'ее',
              'есть', 'за', 'и', 'из', 'или', 'к', 'казахстан', 'как', 'которые', 'который', 'ли', 'меня', 'мне', 'можно',
              'на', 'над', 'не', 'него', 'нее', 'нет', 'ни', 'но', 'о', 'об', 'он', 'она', 'они', 'от', 'по', 'под', 'при',
              'про', 'с', 'со', 'так', 'также', 'то', 'том', 'у', 'уже', 'что', 'чтобы', 'это', 'этот', 'я', 'фио', 'тенге',
              'республики', 'суд', 'суда', 'статьи', 'статьей', 'часть', 'части', 'кодекса', 'уголовного', 'наказание',
              'подсудимый', 'подсудимого', 'приговор']


def search_tokens(text):
    words = set(re.findall(r'[а-яa-z]+', text.lower().replace('ё', 'е')))
    stop = set(STOP_WORDS)
    tokens = set()
    for word in words:
        if len(word) < 3 or word in stop:
            continue
        tokens.add(word[:5] if len(word) > 6 else word[:4] if len(word) > 4 else word)
    return ' ' + ' '.join(sorted(tokens))


def parse_date(head):
    m = re.search(r'(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\s+(\d{4})\s*(?:года|г\.?)', head)
    if m:
        return f'{int(m.group(3)):04d}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}'
    m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})\s*(?:года|г\.)', head[:400])
    return f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else ''


def parse_court(head):
    for line in head.split('\n')[:25]:
        line = re.sub(r'\s+', ' ', line).strip()
        line = re.sub(r'^Судья\s+', '', line)
        m = re.match(r'(.{0,160}?(?:суд|райсуд|суда)\b.{0,160}?)(?:\s+в\s+составе|\s+ФИО-\d|:|,|$)', line, re.I)
        if m and not re.match(r'(?:ИМЕНЕМ|ПРИГОВОР|П Р И|\d)', line):
            court = re.sub(r'\bрайсуд\b', 'районный суд', m.group(1)).strip(' ,')
            if 8 < len(court) < 200:
                return court
    return ''


ARTICLE_RE = re.compile(r'(?:стать(?:ей|ями|ям|е|и|я)|ст\.?)\s*(\d{2,3}(?:-\d)?)|(\d{2,3}(?:-\d)?)\s*(?:статьи|статьей|ст\.)', re.I)
NUMBER_RE = re.compile(r'(?<![\d,/№-])(?<!\d\.)(\d{2,3}(?:-\d)?)(?![\d.,]\d|\s*\)|\s*(?:час(?:а|ов)?\b|сут|МРП|месячн|тенге|лет\b|год|мес\.|месяц))')


def plain(text):
    return text.replace('ё', 'е').replace('Ё', 'Е').replace('\xa0', ' ')


def special_articles(clause):
    """Article numbers of the Special Part (99–460) in a short clause like «ст.ст. 28 ч.5, 190 ч.3 п.4 УК».

    The clause is already cut at «УК»/«Уголовного кодекса», so the only numbers left are articles,
    parts and points; parts and points never exceed 98, and General-Part articles (24, 28, 55…) are < 99.
    """
    found = NUMBER_RE.findall(clause)
    return [a for a in dict.fromkeys(found) if 99 <= int(a.split('-')[0]) <= 460]


CODE_END = re.compile(r'Уголовного\s+[Кк]одекса|УК\b')
CHARGE_ANCHOR = re.compile(r'предан[аоы]?\s+суду|по\s+обвинению\s+в\s+совершении|обвиня\w*\s+(?:в\s+совершении|по\s)', re.I)


def clause_until_code(text, start, limit=700):
    """Text from `start` up to and including the first «УК»/«Уголовного кодекса»."""
    segment = text[start:start + limit]
    stop = CODE_END.search(segment)
    if stop:
        return segment[:stop.end()]
    cut = re.search(r'\n\s*\n|ОПИСАТЕЛЬН', segment)
    return segment[:cut.start()] if cut else segment[:250]


def charge(text):
    """Articles of the indictment, read only from the clause «предан суду по обвинению…».

    Earlier convictions («ранее судим… по ст. 188») are listed before this clause and are ignored.
    """
    text = plain(text)
    intro_end = re.search(r'ОПИСАТЕЛЬН|УСТАНОВИЛ', text)
    intro = text[:intro_end.start()] if intro_end and intro_end.start() > 300 else text[:8000]
    articles, phrase = [], ''
    for anchor in CHARGE_ANCHOR.finditer(intro):
        clause = clause_until_code(intro, anchor.start())
        found = special_articles(clause)
        if not found:
            continue
        articles += [a for a in found if a not in articles]
        if not phrase:
            phrase = re.sub(r'\s*\(\s*далее[^)]*\)', '', re.sub(r'\s+', ' ', clause)).strip(' ,')
            cut = re.search(r'предусмотренн\w+\s*', phrase)
            phrase = phrase[cut.end():] if cut else re.sub(
                r'^(?:предан\w*\s+суду\s*)?(?:по\s+обвинению\s+|обвиня\w*\s+)?(?:в\s+совершении\s+(?:уголовн\w+\s+)?(?:правонарушени\w+|проступк\w+|преступлени\w+),?\s*)?(?:по\s+)?', '', phrase, flags=re.I)
    return articles, phrase


def operative_part(text):
    marks = list(re.finditer(r'П\s*Р\s*И\s*Г\s*О\s*В\s*О\s*Р\s*И\s*Л|ПОСТАНОВИЛ|[Пп]риговорил|РЕЗОЛЮТИВНАЯ', text))
    return text[marks[-1].end():] if marks else text[-5000:]


GUILTY = re.compile(r'(?<![нН]е)(?<![нН]е )ви\w{0,2}новн', re.I)   # also catches typos «вивновным», «признатьвиновным»


def conviction_clauses(text):
    """(start, clause) for each «признать … виновным … по ст. … УК» in the operative part."""
    text = plain(text)
    part = operative_part(text)
    offset = len(text) - len(part)
    clauses = []
    for m in GUILTY.finditer(part):
        if not re.search(r'призна', part[max(0, m.start() - 160):m.end() + 160], re.I):
            continue
        start = max(0, m.start() - 160)
        sentence_start = max(part.rfind('\n', 0, m.start()), part.rfind('. ', 0, m.start()))
        start = max(start, sentence_start + 1)
        clauses.append((offset + start, clause_until_code(part, start, 600)))
    return clauses


def convicted_articles(text):
    articles = []
    for _, clause in conviction_clauses(text):
        articles += [a for a in special_articles(clause) if a not in articles]
    return articles


def conviction_phrase(text):
    """«ч.1 ст.287 УК» from the first operative sentence «признать виновным…»."""
    for _, clause in conviction_clauses(text):
        found = re.search(r'(?:предусмотренн\w+|\bпо)\s+((?:ст|ч|п|стать|част|пункт)[^\n]{0,220}?(?:Уголовного\s+[Кк]одекса|УК\b))', clause)
        if found:
            return re.sub(r'\s+', ' ', found.group(1)).strip()
    return ''


GRAVEST = ('murder', 'state', 'sexual')


def main_article(convicted, charged):
    """First article of the operative part; a murder, sexual or terrorism/extremism article takes precedence."""
    pool = convicted or charged
    for key in GRAVEST:
        for article in pool:
            if category(article) == key:
                return article
    if '296' in pool and '297' in pool:
        return '297'   # sale of drugs outweighs possession in the same verdict
    return pool[0] if pool else ''


def category(article):
    number = int(article.split('-')[0])
    for key, _, match in CATEGORIES:
        if match(number, article):
            return key
    return 'other'


def keyword_topic(text):
    lower = text.lower().replace('ё', 'е')
    scores = Counter({key: len(re.findall(pattern, lower)) for key, pattern in TOPIC_WORDS.items()})
    return scores


def outcome(text):
    part = plain(operative_part(text))
    guilty = bool(conviction_clauses(text))
    acquitted = re.search(r'оправда(?:ть|н)|признать\s+\S+(?:\s+\S+)?\s+невиновн|невиновн\w*\s+и\s+оправда', part, re.I)
    # Only the criminal case counts: «производство по гражданскому иску прекратить» is not a termination.
    terminated = re.search(r'(?:уголовное\s+дело|уголовное\s+преследование|производство\s+по\s+(?:уголовному\s+)?делу)[^.]{0,120}?прекрат'
                           r'|прекратить\s+(?:уголовное\s+дело|уголовное\s+преследование|производство\s+по\s+(?:уголовному\s+)?делу)', part, re.I)
    if guilty and (acquitted or terminated):
        return 'partial', 'средняя', 'Есть обвинительная часть и оправдание или прекращение в части'
    if guilty:
        return 'convicted', 'высокая', 'Формулировка «признать виновным» в резолютивной части'
    if acquitted:
        return 'acquitted', 'высокая', 'Формулировка об оправдании в резолютивной части'
    if terminated:
        return 'terminated', 'высокая', 'Уголовное дело прекращено'
    return 'review', 'низкая', 'Исход не найден автоматически'


PUNISHMENT_TERMS = {
    'prison': r'лишени[яею]\s+свободы',
    'restriction': r'ограничени[яею]\s+свободы',
    'other': r'штраф|общественн\w+\s+работ|исправительн\w+\s+работ|\bареста\b|освобод\w+\s+(?:\S+\s+){0,2}от\s+(?:уголовной\s+ответственности|наказания)|без\s+назначения\s+(?:уголовного\s+)?наказания',
}
# A mention is not an imposed punishment when it explains a replacement, a credit of time already served,
# or the regime («день содержания под стражей за один день лишения свободы», «заменить лишением свободы»).
NOT_IMPOSED = re.compile(r'замен|уклон|зачесть|зач[её]т|из\s+расч[её]та|один\s+день|полтора\s+дня|отбывани\w+\s+(?:наказания\s+)?в\s+виде\s*$|лишени\w+\s+права', re.I)


def imposed(window, match):
    """False when the sentence before the mention is about replacement, credit of time or evasion."""
    before = window[:match.start()]
    sentence_start = max(before.rfind('. '), before.rfind('\n'), before.rfind(';'))
    return not NOT_IMPOSED.search(before[sentence_start + 1:])


def clause_punishment(flat, start):
    """Most severe punishment ordered for one defendant: several articles, then the final aggregate one."""
    following = re.search(r'призна\w*\s+(?:\S+\s+){0,4}?ви\w{0,2}новн', flat[start + 40:start + 2500], re.I)
    window = flat[start:start + 40 + following.start() if following else start + 1500]
    found = [(m.start(), key) for key, pattern in PUNISHMENT_TERMS.items()
             for m in re.finditer(pattern, window, re.I) if key == 'other' or imposed(window, m)]
    if not found:
        return 'other', None
    if any(key == 'prison' for _, key in found):
        position = min(pos for pos, key in found if key == 'prison')
        after = flat[start + position:start + position + 2000]
        conditional = re.search(r'считать\s+условн|условн\w*\s+осужд|(?:ст\.?|стать\w*)\s*63\b|наказание\s+условно(?!-)', after, re.I)
        return ('restriction' if conditional else 'prison'), start + position
    position, key = min(found, key=lambda item: (-SEVERITY[item[1]], item[0]))
    return key, start + position


SEVERITY = {'prison': 3, 'restriction': 2, 'other': 1}


def punishment(text):
    """The most severe punishment in the verdict (over all convicted defendants) and the sentence stating it.

    Real imprisonment («лишение свободы») becomes «restriction» when the same order makes it conditional
    (ст. 63 УК, «считать условным»); conditional early release («условно-досрочно») is not counted.
    """
    clauses = conviction_clauses(text)
    if not clauses:
        return '', ''
    flat = plain(text)
    best = max((clause_punishment(flat, start) + (start,) for start, _ in clauses),
               key=lambda item: SEVERITY[item[0]])
    key, position, start = best
    if position is None:
        return key, ''
    return key, sentence_around(text, start, position + 10)


BOUNDARY = re.compile(r'(?:[.!?]\s+(?=[А-ЯЁ«])|\n)')


def sentence_around(text, start, end, limit=420):
    left = [m.end() for m in BOUNDARY.finditer(text, max(0, start - 1500), start)]
    begin = left[-1] if left else max(0, start - 300)
    right = BOUNDARY.search(text, end)
    finish = right.start() + 1 if right else len(text)
    quote = re.sub(r'[ \t\xa0]+', ' ', text[begin:finish]).strip()
    return quote[:limit].rstrip() + ('…' if len(quote) > limit else '')


def sentence_with(text, pattern, limit=420):
    m = re.search(pattern, text, re.I)
    return sentence_around(text, m.start(), m.end(), limit) if m else ''


def fragments(text, sentence):
    rows = []
    if sentence:
        rows.append({'label': 'Назначенное наказание', 'quote': sentence[:420]})
    for label, pattern in [('Смягчающие обстоятельства', r'(?:обстоятельств\w*,?\s+смягчающ\w+|смягчающ\w+\s+(?:\S+\s+){0,3}обстоятельств\w*)[^.]{0,80}(?:признает|учитывает|являются|является|суд\s+признает|:)'),
                           ('Отягчающие обстоятельства', r'(?:обстоятельств\w*,?\s+отягчающ\w+|отягчающ\w+\s+(?:\S+\s+){0,3}обстоятельств\w*)[^.]{0,80}(?:признает|учитывает|являются|является|не\s+установлен|не\s+имеется|:)'),
                           ('Позиция подсудимого', r'вин[уы]\s+(?:в\s+\S+\s+)?(?:полностью\s+|частично\s+)?(?:не\s+)?призна')]:
        quote = sentence_with(text, pattern)
        if quote:
            rows.append({'label': label, 'quote': quote})
    return rows


def build(source_dir, out_dir=OUT):
    files = sorted(source_dir.glob('*.txt'))
    if not files:
        raise SystemExit(f'No .txt files in {source_dir}')
    records, texts, seen = [], {}, {}
    factor_counts = Counter()
    for path in files:
        doc_id = path.stem.lower()
        text = path.read_text(encoding='utf-8').replace('\r\n', '\n')
        texts[doc_id] = text
        head = text[:1500]
        digest = hashlib.sha1(re.sub(r'\s+', ' ', text).strip().encode()).hexdigest()
        duplicate = seen.setdefault(digest, doc_id)
        duplicate = '' if duplicate == doc_id else duplicate
        number = re.search(r'(?:дело|№)\s*№?\s*(\d[\d\-/\\]*[\-/][\d\-/\\]*\d)', head[:900], re.I)
        articles, phrase = charge(text)
        convicted = convicted_articles(text)
        main = main_article(convicted, articles)
        topic = category(main) if main else 'other'
        title = ARTICLES.get(main, '')
        if not title:
            # Unknown article number: fall back to the words describing the act.
            scores = keyword_topic(text)
            best, best_score = scores.most_common(1)[0]
            if best_score >= 3:
                topic = best
        topic_confidence = 'высокая' if title and (convicted or articles) else 'средняя' if main else 'низкая'
        verdict, confidence, basis = outcome(text)
        kind, sentence = punishment(text)
        listed = ', '.join([main] + [a for a in (convicted or articles) if a != main])   # all articles of the verdict
        subtopic = (f'{title} (ст. {listed} УК)' if title else
                    f'{TOPICS[topic]} (ст. {listed} УК)' if main else TOPICS[topic])
        verdict_phrase = conviction_phrase(text)
        claim = ('Обвинение: ' + phrase[:260] if phrase else
                 'Признан виновным: ' + verdict_phrase if verdict_phrase else
                 'Обвинение по ст. ' + ', '.join(articles) + ' УК' if articles else '')
        if verdict_phrase and phrase and set(convicted) != set(articles):
            claim += '. Признан виновным: ' + verdict_phrase
        records.append([doc_id, parse_date(head), number.group(1) if number else '', parse_court(head), topic, subtopic,
                        claim, verdict, confidence, topic_confidence, basis, fragments(text, sentence),
                        search_tokens(text), 'decision', duplicate, kind])
        if not duplicate and kind:
            reasons = text[len(text) // 3:]
            for key, label, pattern in FACTORS:
                if re.search(pattern, reasons, re.I):
                    factor_counts[(topic, key, label, kind)] += 1

    unique = [row for row in records if not row[14]]
    stats = {
        'files': len(records), 'unique': len(unique),
        'outcomes': dict(Counter(row[7] for row in unique)),
        'punishments': dict(Counter(row[15] for row in unique if row[15])),
        'topics': {key: title for key, title in TOPICS.items() if any(row[4] == key for row in unique)},
        'labels': LABELS,
        'counts': [{'topic': t, 'outcome': o, 'n': n} for (t, o), n in sorted(Counter((r[4], r[7]) for r in unique).items())],
        'method': 'Автоматическая разметка по статье УК и резолютивной части. Имена заменены на ФИО-N.',
        'dates': [{'year': y, 'n': n} for y, n in sorted(Counter(r[1][:4] for r in unique).items())],
        'section': 'criminal',
        'factorColumns': [[key, title] for key, title in PUNISHMENTS.items()],
        'factorField': 15,
    }
    stop = STOP_WORDS
    if ADMIN_PAYLOAD.exists():
        stop = sorted(set(stop) | set(json.loads(gzip.decompress(base64.b64decode(ADMIN_PAYLOAD.read_bytes())))['stop']))
    payload = {
        'stats': stats, 'records': records, 'examples': [], 'guides': {}, 'stop': stop,
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
    parser.add_argument('source_dir', type=Path, help='Folder with anonymized verdicts')
    parser.add_argument('--output-dir', type=Path, default=OUT)
    args = parser.parse_args()
    stats, bundles = build(args.source_dir, args.output_dir)
    print(f"Built {stats['unique']:,} criminal cases ({stats['files']} files) in {bundles} bundles.")
    print('Outcomes:', stats['outcomes'])
    print('Punishments:', stats['punishments'])

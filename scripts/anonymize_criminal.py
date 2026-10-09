"""Anonymize criminal verdicts: names -> ФИО-N, exact birth dates -> year, IIN and home addresses hidden.

Detection combines rules (surname + initials, full names with patronymics, procedural roles),
the Natasha NER model and the pymorphy3 dictionary. Every person in a document gets one number
in order of first appearance. Requires: pip install natasha pymorphy3
"""
import re
from collections import Counter
from pathlib import Path
from natasha import Segmenter, NewsEmbedding, NewsNERTagger, Doc

UP = 'А-ЯЁӘҒҚҢӨҰҮҺІ'
LO = 'а-яёәғқңөұүһі'
W = f'[{UP}][{LO}]+(?:-[{UP}]?[{LO}]+)?'          # capitalized word, optional hyphen part
INIT = f'[{UP}]\\.'
INITS = f'{INIT}(?:\\s?{INIT})?'
PATR = f'[{UP}][{LO}]+(?:(?:ович|евич|ьич)(?:а|у|ем|ом|е)?|(?:овн|евн|ичн|иничн)(?:а|ы|е|у|ой)|улы|ұлы|уулы|уулу|оглы|кызы|қызы|гызы)'

ENDINGS = sorted(['ыми','ими','ого','его','ому','ему','ой','ей','ым','им','ом','ем','ую','юю','ая','яя','ий','ый','ое','ые','ие','их','ых','а','у','е','ы','ю','я','о','и'], key=len, reverse=True)

KAZ = str.maketrans('әғқңөұүһі', 'агкноуухи')


def stem(word):
    w = word.lower().replace('ё', 'е').translate(KAZ)
    for e in ENDINGS:
        if w.endswith(e) and len(w) - len(e) >= 3:
            return w[:-len(e)]
    return w

# capitalized words that are never surnames even if followed by initials / role nouns
NOT_NAMES = set(map(stem, '''Суд Судья Республика Казахстан Кодекс Закон Статья Часть Пункт Область Город Район Улица Проспект
Приговор Постановление Решение Апелляционная Кассационная Верховный Генеральный Прокурор Прокуратура Департамент Управление
Полиция Отдел Комитет Министерство Акимат Аким Банк Товарищество Акционерное Общество Казахтелеком Алматы Астана Тараз Шымкент
Нур Султан Караганда Павлодар Семей Актобе Атырау Актау Кызылорда Костанай Петропавловск Уральск Кокшетау Талдыкорган Туркестан
Жезказган Экибастуз Темиртау Рудный Балхаш Конаев Байконур Абай Жетысу Улытау Жамбыл Жамбылская Мангистауская Алматинская
Согласно Кроме Также Таким Вместе Однако Затем После Далее Указанные Данные Подсудимый Подсудимая Потерпевший Потерпевшая Свидетель
Свидетельница Осужденный Осужденная Защитник Адвокат Государственный Обвинитель Секретарь Эксперт Специалист Представитель Гражданин
Гражданка Истец Ответчик Следователь Дознаватель Оперуполномоченный Инспектор Начальник Директор Председатель Вину Признал Виновным
Уголовного Уголовно Процессуального Гражданского Административного Кодекса Указа Конституции Нормативного Министра Президента
ИМЕНЕМ ОПИСАТЕЛЬНАЯ МОТИВИРОВОЧНАЯ РЕЗОЛЮТИВНАЯ ПРИГОВОР Токио Лотус Notes Ватсап Whatsapp Телеграм Каспи Kaspi Халык Халык
Мкр Микрорайон Шоссе Площадь Жилой Массив Поселок Село Аул Станция Конституционный Нормативное Бостандыкский Медеуский Алмалинский
Ауэзовский Турксибский Жетысуский Наурызбайский Алатауский Есильский Сарыаркинский Байконурский Алматинский Нуринский
Тойота Toyota Лексус Мерседес Хюндай Hyundai Лада Ваз Камаз Шевроле Кия Kia Ниссан Ауди Фольксваген Опель Мазда Хонда Субару Тесла
Казпочта Казахстанская Республиканское Коммунальное Государственное Учреждение Предприятие Компания Холдинг Самрук Казына Байтерек
Каспи Kaspi Бог Аллах Господь Интернет Телефон Айфон Самсунг Сяоми Редми Инстаграм Фейсбук Тикток Ютуб Гугл Яндекс Мэйл Вотсап Олх Колеса Крыша
Новый Старый Большой Малый Северо Южно Западно Восточно Центральный Ленинский Советский Октябрьский Кировский Пушкина Ленина Абая
'''.split()))

ROLE = (r'(?:подсудим|осужденн|осуждённ|потерпевш|свидетел|обвиняем|подозреваем|гражданин|гражданк|гр\.|судь|адвокат|защитник|'
        r'прокурор|секретар|эксперт|специалист|представител|следовател|дознавател|оперуполномоченн|инспектор|участков|'
        r'брат|сестр|мать|матер|отец|отц|сын|доч|супруг|муж|жен[аеуы]|сожител|знаком|друг|подруг|ИП|индивидуальн\w+ предпринимател|'
        r'начальник|заместител|директор|врач|фельдшер|педагог|психолог|переводчик|понят|водител|пассажир|продав|кассир|охранник|'
        r'законн\w+ представител|малолетн|несовершеннолетн)[{lo}]*\.?'.replace('{lo}', LO))

PLACE_BEFORE = re.compile(f'(?:(?<![{UP}{LO}\\d])(?:город|города|городе|городу|г\\.|пос\\.|села|село|ул\\.|улица|улице|улицы|пр\\.|пр-т|проспект|проспекта|мкр\\.?|микрорайон|микрорайона|микрорайоне|аула|аул)\\s*)$')
DISTRICT_BEFORE = re.compile(f'(?:[Сс]уд\\w*|прокуратур\\w*|УП|ОП|РОВД|отдел\\w*\\s+полиции)\\s+района\\s+(?:имени\\s+)?(?:{W}\\s+)?$')
STRONG_STOP = set(map(stem, 'Республика Казахстан Суд Статья Часть Пункт Приговор Уголовный Кодекс УК УПК Согласно Кроме'.split()))

GEO_BASES = '''Алматы Астана Шымкент Караганда Актобе Тараз Павлодар Усть-Каменогорск Семей Атырау Костанай Кызылорда Уральск
Петропавловск Актау Темиртау Туркестан Кокшетау Талдыкорган Экибастуз Рудный Жезказган Балхаш Сатпаев Конаев Қонаев Каскелен
Степногорск Риддер Лисаковск Аксу Шахтинск Сарань Житикара Щучинск Атбасар Тайынша Ерейментау Аркалык Байконур Жанаозен Кентау
Арысь Есик Талгар Капшагай Сарыагаш Аягоз Шемонаиха Каратау Хромтау Кульсары Мерке Ұлытау Улытау Жетісу Жетысу Мангистау
Акмола Жамбыл Сарыарка Есиль Алатау Медеу Бостандык Ауэзов Турксиб Наурызбай Алмалы Карасай Иртыш Глубокое Тобыл Кызылжар'''.split()
GEO_WORDS = set()
for _base in GEO_BASES:
    _b = _base.lower()
    GEO_WORDS |= {_b, _b + 'а', _b + 'у', _b + 'е', _b + 'ом', _b + 'ы'}
    if _b.endswith(('а', 'я', 'й', 'ы', 'е')):
        _r = _b[:-1]
        GEO_WORDS |= {_r + e for e in ('а', 'ы', 'у', 'е', 'ой', 'я', 'ю', 'ем', 'и')}
PLACE_AFTER = re.compile(r'^\s+(?:област|район|районн|городск|сельск|межрайон|поселк|аульн|сельского\s+округ)')

def name_forms(name):
    n = name.lower().replace('ё', 'е')
    if n.endswith(('а', 'я')):
        b = n[:-1]; return {n, b + 'ы', b + 'и', b + 'е', b + 'у', b + 'ю', b + 'ой', b + 'ей'}
    if n.endswith('й'):
        b = n[:-1]; return {n, b + 'я', b + 'ю', b + 'ем', b + 'е'}
    return {n, n + 'а', n + 'у', n + 'ом', n + 'е', n + 'ым'}

RAW_STOP = set('''алматы алмате алмату астана тараз тараза шымкент караганда караганду семей семея костанай костаная экибастуз экибастуза балхаш абай абая абаем жамбыла петропавловск степногорск серебрянск кошетау аламты алмалы каспи казпочта казпочты казпочте редми тойота ватсап вотсап телеграм флеш приговор допрошенный допрошенная накладная проникающее кроме при на он действуя продолжая выписки товарищество товариществу квалифицирующие впоследующем чистосердечно сотовому высказываниях претензии гаска мамлютка ребровка новоишимское застанционный кулагер шугыла кобыл жамбылская назарбаева'''.split())

import pymorphy3
_morph = pymorphy3.MorphAnalyzer()
_FUNC = {'PREP', 'CONJ', 'PRCL', 'ADVB', 'PRTF', 'PRTS', 'VERB', 'INFN', 'NPRO', 'GRND', 'PRED', 'NUMR', 'INTJ', 'COMP'}
_cache = {}
def dict_kind(word):
    """'name' if the dictionary allows a person-name reading, 'func' for function words/verbs, 'common' for other known words, '' if unknown."""
    w = word.lower()
    if w in _cache: return _cache[w]
    res = ''
    if '-' in word and re.search(r'-[а-яё]', word):
        res = 'common'
    elif _morph.word_is_known(w):
        parses = _morph.parse(w)
        if any({'Surn', 'Name', 'Patr'} & set(str(p.tag).replace(' ', ',').split(',')) for p in parses): res = 'name'
        elif parses[0].tag.POS in _FUNC: res = 'func'
        else: res = 'common'
    _cache[w] = res
    return res

_tagger = None
def ner_people(text):
    global _tagger
    if _tagger is None:
        emb = NewsEmbedding(); _tagger = (Segmenter(), NewsNERTagger(emb))
    seg, ner = _tagger
    doc = Doc(text); doc.segment(seg); doc.tag_ner(ner)
    return [text[s.start:s.stop] for s in doc.spans if s.type == 'PER']

def lowercase_vocab(text):
    return {stem(w) for w in re.findall(f'(?<![{UP}{LO}])[{LO}]{{3,}}', text)}

class Anonymizer:
    def __init__(self, text):
        self.text = text
        self.ids = {}      # stem -> first person number with this surname
        self.by_init = {}  # (stem, first initial) -> person number; relatives share a surname
        self.unbound = {}  # stem -> person seen only without initials so far
        self.last_used = {}
        self.forms = Counter()   # (surface form, person) -> mentions with initials
        self.order = 0
        self.first = {}    # exact lowercase first-name form -> person number
        self.lower = lowercase_vocab(text)
        self.geo = {m.group(1).lower() for m in re.finditer(
            f'(?<![{UP}{LO}])({W})(?=\\s+(?:област|район|районн|городск|сельск|межрайон))', text)}
        self.lowerwords = set(re.findall(f'(?<![{UP}{LO}])[{LO}]{{3,}}', text.replace('ё', 'е')))
        self.places = {stem(m.group(1)) for m in re.finditer(
            f'(?<![{UP}{LO}])(?:город|города|городе|городу|г\\.|пос\\.|села|село|ул\\.|пр\\.|мкр\\.?|микрорайон|микрорайона|микрорайоне|уроженец|уроженка|аула|аул)\\s*({W})', text)}

    def ok(self, word, strong=False):
        s = stem(word)
        if word.lower().replace('ё', 'е') in GEO_WORDS or word.lower() in self.geo: return False
        kind = dict_kind(word)
        if strong:
            return (len(word) >= 2 and not (kind == 'func' and _morph.parse(word.lower())[0].tag.POS not in ('VERB', 'PRTS')) and word.upper() != word and s not in STRONG_STOP
                    and word.lower().replace('ё', 'е') not in self.lowerwords and (s not in NOT_NAMES or s in ('абай',)))
        if len(s) < 3 and len(word) < 3: return False
        if kind in ('func', 'common'): return False
        if s in NOT_NAMES: return False
        if s in self.lower: return False       # common Russian word in this text
        if s in self.places: return False
        return True

    def ok_firstname(self, word):
        w = word.lower().replace('ё', 'е')
        return len(w) >= 3 and dict_kind(w) in ('name', '') and w not in self.lowerwords and stem(w) not in self.places and w not in RAW_STOP

    def isplace(self, pos, text=None):
        t = self.text if text is None else text
        if DISTRICT_BEFORE.search(t[max(0, pos - 60):pos]): return True
        before = t[max(0, pos - 16):pos]
        m = PLACE_BEFORE.search(before)
        if not m: return False
        if re.match(r'г\.', m.group(0)) and re.search(r'\d\s*$', before[:m.start()]): return False
        return True

    def person(self, key):
        return self.ids.get(key)

    def collect(self):
        t = self.text
        found = []   # (pos, surname stem, firstname stem or None)
        # 1. Full name: Surname Name Patronymic
        for m in re.finditer(f'(?<![{UP}{LO}])({W})\\s+({W})\\s+({PATR})(?![{LO}])', t):
            if self.ok(m.group(1), True) and not self.isplace(m.start()): found.append((m.start(), stem(m.group(1)), m.group(2), m.group(2)[0] + m.group(3)[0]))
        # Name Patronymic Surname
        for m in re.finditer(f'(?<![{UP}{LO}])({W})\\s+({PATR})\\s+({W})(?![{LO}])', t):
            if self.ok(m.group(3), True) and not re.match(PATR, m.group(3)): found.append((m.start(), stem(m.group(3)), m.group(1), m.group(1)[0] + m.group(2)[0]))
        # 2. Surname И.О.
        for m in re.finditer(f'(?<![{UP}{LO}])({W})\\s?({INITS})(?![{LO}])', t):
            if self.ok(m.group(1), True) and not self.isplace(m.start()): found.append((m.start(), stem(m.group(1)), None, ''.join(re.findall(f'[{UP}]', m.group(2)))))
        for m in re.finditer(f'(?<=[{LO}])([{UP}][{LO}]+)\\s?({INITS})(?![{LO}])', t):
            if self.ok(m.group(1), True): found.append((m.start(1), stem(m.group(1)), None, ''.join(re.findall(f'[{UP}]', m.group(2)))))
        # 3. И.О. Surname
        for m in re.finditer(f'(?<![{UP}{LO}.])({INITS})\\s?({W})(?![{LO}])', t):
            if re.search(f'{W}\\s*$', t[max(0, m.start() - 40):m.start()]): continue   # initials belong to the previous surname
            if self.ok(m.group(2)) and not self.isplace(m.start(2)): found.append((m.start(), stem(m.group(2)), None, ''.join(re.findall(f'[{UP}]', m.group(1)))))
        # 4. role noun + Surname
        for m in re.finditer(f'(?<![{LO}]){ROLE}\\s*[-–—,:]?\\s*({W})(?![{LO}])', t, flags=re.I):
            w = m.group(1)
            if self.ok(w): found.append((m.start(1), stem(w), None, None))
        # 5. NER
        for span in ner_people(t):
            raw = re.findall(W, span)
            words = [w for w in raw if self.ok(w)]
            if len(raw) == 1 and not words and self.ok_firstname(raw[0]):
                found.append((t.find(span), None, raw[0], None)); continue
            if not words: continue
            pos = t.find(span)
            if len(words) >= 2 and re.fullmatch(PATR, words[-1]):
                first = words[1] if len(words) > 2 else None
                found.append((pos, stem(words[0]), first, first[0] + words[-1][0] if first else None))
            else:
                for w in words:
                    found.append((pos, stem(w), None, None))
        found.sort(key=lambda x: x[0])
        firstnames = {}
        for pos, sur, first, initial in found:
            if sur is None:
                n = self.order + 1
                for form in name_forms(first):
                    if form in self.first: n = self.first[form]; break
                if n > self.order: self.order = n
                for form in name_forms(first):
                    if form not in self.lowerwords: self.first.setdefault(form, n)
                continue
            n = self.register(sur, initial)
            if first and not re.fullmatch(PATR, first):
                for form in name_forms(first):
                    if form not in NOT_NAMES and form not in self.places and form not in self.lower:
                        self.first.setdefault(form, n)

    @staticmethod
    def norm(initial):
        return initial.upper().replace('Ё', 'Е')[:2] if initial else None

    def find(self, sur, initial):
        """Person with this surname whose initials agree ("А" matches "АШ"; "АА" does not match "АШ")."""
        if (sur, initial) in self.by_init:
            return self.by_init[(sur, initial)]
        matches = {n for (s_, ini), n in self.by_init.items()
                   if s_ == sur and (ini.startswith(initial) or initial.startswith(ini))}
        return matches.pop() if len(matches) == 1 else None

    def register(self, sur, initial):
        """One number per person: same surname with different initials = different people (relatives)."""
        initial = self.norm(initial)
        if initial:
            n = self.find(sur, initial)
            if n:
                self.by_init[(sur, initial)] = n
                return n
        if initial and sur in self.unbound:
            n = self.unbound.pop(sur)
        elif initial or sur not in self.ids:
            self.order += 1; n = self.order
            if not initial: self.unbound[sur] = n
        else:
            return self.ids[sur]
        self.ids.setdefault(sur, n)
        if initial: self.by_init[(sur, initial)] = n
        return n

    def resolve(self, sur, initial, form=''):
        initial = self.norm(initial)
        people = {n for (s_, _), n in self.by_init.items() if s_ == sur}
        if initial and people:
            n = self.find(sur, initial) or self.register(sur, initial)
            self.forms[(form, n)] += 1
        elif len(people) > 1:
            # A bare surname: the person who is written in this exact form most often («Абуовой» — the victim,
            # «Абуова» — the defendant); ties go to the person mentioned last.
            n = max(people, key=lambda p: (self.forms[(form, p)], p == self.last_used.get(sur)))
        else:
            n = self.last_used.get(sur) or self.ids.get(sur)
        if n: self.last_used[sur] = n
        return n

    def replace(self):
        t = self.text
        word_re = re.compile(f'(?<![{UP}])({W})(?![{LO}])')
        lead_re = re.compile(f'(?:(?:{INITS})\\s?|{W}\\s+{PATR}\\s+)$')
        cont_re = re.compile(f'\\s*(?:({W})(?![{LO}])|({INITS})(?![{LO}]))')
        out = []; last = 0; pos = 0
        while True:
            m = word_re.search(t, pos)
            if not m: break
            w = m.group(1)
            sur = stem(w)
            n = self.ids.get(sur) or self.first.get(w.lower().replace('ё', 'е'))
            short_ok = len(w) >= 3 or re.search(r'[^.!?\n\s]\s*$', t[max(0, m.start() - 3):m.start()])
            if not n or self.isplace(m.start(), t) or not short_ok or w.lower() in GEO_WORDS or w.lower() in self.geo:
                pos = m.end(); continue
            start = m.start()
            lb = max(last, start - 60)
            lead = lead_re.search(t[lb:start])
            initial = None
            if lead and '\n' not in lead.group(0):
                start = lb + lead.start()
                initial = ''.join(re.findall(f'[{UP}]', lead.group(0)))[:1] if re.match(f'[{UP}]\\.', lead.group(0)) else None
                if initial is not None: initial = ''.join(re.findall(f'[{UP}](?=\\.)', lead.group(0)))
            end = m.end()
            had_init = False
            name_ini = ''      # initials collected from a full name: «Карину Сергеевну» -> «КС»
            known = {ini for (s_, ini) in self.by_init if s_ == sur}
            while True:
                c = cont_re.match(t, end)
                if not c or '\n' in t[end:c.end()]: break
                if c.group(2):
                    if had_init or name_ini: break
                    end = c.end(); had_init = True
                    initial = initial or ''.join(re.findall(f'[{UP}]', c.group(2)))
                    continue
                if had_init: break
                cw = c.group(1)
                if stem(cw) == sur:
                    end = c.end(); continue
                if re.fullmatch(PATR, cw):
                    name_ini += cw[0]; end = c.end(); continue
                if self.first.get(cw.lower()) == n and len(name_ini) < 1:
                    name_ini += cw[0]; end = c.end(); continue
                c2 = cont_re.match(t, c.end())
                if (c2 and c2.group(1) and re.fullmatch(PATR, c2.group(1)) and '\n' not in t[end:c2.end()]
                        and dict_kind(cw) in ('name', '') and self.ids.get(stem(c2.group(1))) in (None, n)):
                    end = c2.end(); name_ini = cw[0] + c2.group(1)[0]; continue
                # First name (and a non-Russian patronymic) whose initials match this person: «Шораева Нуркена»
                prefix = (name_ini + cw[0]).upper()
                if (len(name_ini) < 2 and dict_kind(cw) in ('name', '') and cw.lower() not in GEO_WORDS
                        and any(ini.startswith(prefix) for ini in known)):
                    name_ini += cw[0]; end = c.end(); continue
                break
            initial = initial or name_ini or None
            if sur in self.ids:
                n = self.resolve(sur, initial, w.lower())
            out.append(t[last:start]); out.append(f'ФИО-{n}')
            last = pos = end
        out.append(t[last:])
        t = ''.join(out)
        t = re.sub(r'(ФИО-(\d+))(?:\s+ФИО-\2(?!\d))+', r'\1', t)
        return t

DATE_BIRTH = re.compile(r'\b\d{1,2}[./]\d{1,2}[./](\d{4})\s*(?:г\.?\s*|года\s+)?(?=(?:г\.?\s*)?р(?:ождения|\.))')
DATE_BIRTH2 = re.compile(r'(\b\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})(\s*(?:года|г\.)\s+рождения)')
IIN = re.compile(r'(?<!\d)(\d{12})(?!\d)')
ADDR = re.compile(r'((?:проживающ|проживает|проживал|зарегистрирован|прописан)[а-яё]*(?:\s+(?:и\s+)?(?:фактически\s+)?(?:проживающ|проживает|зарегистрирован)[а-яё]*)?\s+(?:по\s+адресу|по\s+(?=улиц)|в\s+(?=(?:город|гор\.|г\.|сел|с\.|пос|п\.|аул|[А-ЯЁ][а-яё]+(?:ой|ском)\s+(?:област|район))))[:\s]*)((?:[^,;\n]{1,120}?)(?:,\s*(?:[^,;\n]{0,30}\s(?:район|област|обл\.)|г\.|гор\.|город|ул\.?|улиц|номер|дом|д\.|кв|квартир|мкр|микрорайон|пр\.|проспект|пер\.|переул|сел|с\.|пос|п\.|район|р-н|област|обл\.|корпус|блок|здани|строени|жилой|ж\.м|№|\d)[^,;\n]{0,60}?)*)(?=[,;\n]|\.\s+(?=[А-ЯЁ][а-яё]+\s+[а-яё])|$)', re.I)

def scrub_other(t):
    t = DATE_BIRTH.sub(lambda m: m.group(1) + ' года ' if 'года' in m.group(0) else m.group(1) + ' г. ', t)
    t = DATE_BIRTH2.sub(lambda m: m.group(3) + m.group(4), t)
    t = IIN.sub('[ИИН скрыт]', t)
    t = ADDR.sub(lambda m: m.group(1) + '[адрес скрыт]', t)
    return t

CAPS_STOP = {'СУДЬЯ', 'ПРИГОВОР', 'ПОСТАНОВИЛ', 'ПРИГОВОРИЛ', 'КОПИЯ', 'РЕСПУБЛИКИ', 'КАЗАХСТАН', 'ПОДПИСЬ', 'ВЕРНА', 'ИМЕНЕМ'}

def cleanup(t, a):
    # all-caps surnames with initials (signatures)
    def caps(m):
        w = m.group(1)
        if w in CAPS_STOP: return m.group(0)
        key = stem(w.lower())
        if key not in a.ids:
            a.order += 1; a.ids[key] = a.order
        return f'ФИО-{a.ids[key]}'
    t = re.sub(f'(?<![{UP}{LO}])([{UP}]{{3,}})\\s{{0,2}}(?:{INITS})', caps, t)
    # leftover initials stuck to a replaced name: "ФИО-8.И.С." / "ФИО-8 И.С."
    t = re.sub(f'(ФИО-\\d+)\\.?\\s?(?:[{UP}]\\.){{1,2}}(?=[\\s,;:)])', r'\1', t)
    # name fragments glued to a replacement: "ФИО-44Даулетбекв судебном"
    t = re.sub(f'(ФИО-\\d+)[{UP}][{LO}]+?(в)(?=\\s)', r'\1 \2', t)
    t = re.sub(f'(ФИО-\\d+)[{UP}][{LO}]+', r'\1', t)
    t = re.sub(r'(ФИО-(\d+))(?:\s+ФИО-\2(?!\d))+', r'\1', t)
    return t

# Residual first names found during manual review of the current corpus (forms only replaced as whole words).
MANUAL_NAMES = []

def manual(t, a):
    # "по имени Алмаз", "по фамилии - Иванов", "тетя Фая": the name is then masked everywhere in the document
    called = re.compile(f'(?:по\\s+(?:имени|фамилии|прозвищу|кличке)|агроном|тет[яеи]|тётя|дяд[яеи]|бабушк[аи]|дедушк[аи])\\s*[-–—]?\\s*[«"“]?({W})(?![{LO}])')
    for name in dict.fromkeys(m.group(1) for m in called.finditer(t)):
        if dict_kind(name) == 'func':
            continue
        a.order += 1
        forms = sorted({f.capitalize() for f in name_forms(name)}, key=len, reverse=True)
        rx = re.compile(f'(?<![{UP}{LO}\\-])(?<!санатории )(?<!санатория )(?<!санаторий )(?<!санатория ")(?:' + '|'.join(forms) + f')(?![{LO}\\-])')
        t = rx.sub(f'ФИО-{a.order}', t)
    for base in MANUAL_NAMES:
        if re.search('(ов|ев|ин)$', base):
            forms = {base.lower() + e for e in ('', 'а', 'у', 'ой', 'ым', 'ом', 'е', 'у')}
        else:
            forms = name_forms(base)
        rx = re.compile(f'(?<![{UP}{LO}\\-])(?:' + '|'.join(sorted({f.capitalize() for f in forms}, key=len, reverse=True)) + f')(?![{LO}\\-])')
        if rx.search(t):
            a.order += 1
            t = rx.sub(f'ФИО-{a.order}', t)
    return t

def anonymize(text):
    a = Anonymizer(text); a.collect()
    out = a.replace()
    # second pass: names that only become visible to NER once others are masked
    b = Anonymizer(out); b.order = a.order; b.collect()
    out = b.replace()
    ids = dict(a.ids); ids.update(b.ids)
    out = cleanup(out, b)
    out = manual(out, b)
    return scrub_other(renumber(out)), {**ids, **b.ids}


def renumber(t):
    """Number people 1, 2, 3… in order of first appearance in the final text."""
    order = {}
    for m in re.finditer(r'ФИО-(\d+)', t):
        order.setdefault(m.group(1), str(len(order) + 1))
    return re.sub(r'ФИО-(\d+)', lambda m: 'ФИО-' + order[m.group(1)], t)

def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_dir', type=Path, help='Folder with raw verdict .txt files (not committed)')
    parser.add_argument('output_dir', type=Path, help='Folder for anonymized .txt files')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(args.source_dir.glob('*.txt'))
    persons = 0
    for path in files:
        text = path.read_text(encoding='utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
        result, ids = anonymize(text)
        persons += len(set(ids.values()))
        (args.output_dir / path.name).write_text(result, encoding='utf-8')
    print(f'Anonymized {len(files)} verdicts, {persons:,} person references replaced with ФИО-N.')


if __name__ == '__main__':
    main()

'use strict';

const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
const number = value => Number(value).toLocaleString('ru-RU');
const dateLabel = date => /^\d{4}-\d{2}-\d{2}$/.test(date) ? date.split('-').reverse().join('.') : 'Дата не указана';
const plural = (n, [one, few, many]) => {
  const mod10 = n % 10, mod100 = n % 100;
  return mod10 === 1 && mod100 !== 11 ? one : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14) ? few : many;
};

/* Each section has its own index, text bundles and wording; the interface is shared. */
const SECTIONS = {
  admin: {
    prefix: '',
    payload: 'data/offline-payload.b64',
    bundles: 'data/source-bundles/',
    title: 'Casebook — административные споры Казахстана',
    brand: 'Административные споры · Казахстан',
    collection: 'Коллекция решений',
    units: ['судебный акт', 'судебных акта', 'судебных актов'],
    topicUnits: ['тема', 'темы', 'тем'],
    ready: 'решений',
    topicWord: 'Тема', allTopics: 'Все темы', topicAuto: 'Определить по вопросу', topicLabel: 'Тема спора',
    question: {
      eyebrow: 'Поиск по ситуации',
      heading: 'Найдите опору<br>в судебной практике.',
      intro: 'Опишите спор. Посмотрите, какие доказательства исследовал суд и почему похожие дела закончились по-разному.',
      label: 'Что произошло?',
      placeholder: 'Например: ЧСИ неверно рассчитал задолженность по алиментам. У меня есть банковские переводы.',
      submit: 'Найти решения',
      examples: [
        ['Земельный конкурс', 'Заявку на земельный конкурс отклонили из-за оформления документов'],
        ['Расчёт алиментов', 'ЧСИ неправильно рассчитал задолженность по алиментам и учел переводы другого назначения'],
        ['Налоговое уведомление', 'Налоговая выставила уведомление из-за контрагента. Работы выполнены и оплачены'],
        ['Жилищные выплаты', 'Отказали в жилищных выплатах, потому что есть квартира в ипотеке'],
      ],
      welcome: [
        ['01 / НАЙТИ', 'Похожие дела', 'По предмету спора, требованиям и обстоятельствам.'],
        ['02 / СРАВНИТЬ', 'Позиции суда', 'Удовлетворение иска, частичный результат или отказ.'],
        ['03 / ПРОВЕРИТЬ', 'Первоисточник', 'Полный текст решения и переход к конкретной цитате.'],
      ],
      needsTopic: 'Не удалось определить тему спора. Укажите орган, его действие и причину отказа или выберите тему вручную.',
    },
    registry: {
      nav: 'Реестр решений', heading: 'Реестр решений',
      intro: 'Выберите тему и исход или найдите дело по номеру. Точные повторы исключены из списка.',
      placeholder: 'Например, 2794-21-00-4/481',
    },
    factors: {
      eyebrow: 'Анализ решений', heading: 'Обстоятельства спора',
      intro: 'Какие формулировки встречаются в мотивировках и как распределяются по исходам дел.',
      notice: 'Частота формулировки не показывает вероятность выигрыша. В одном деле может быть несколько требований с разными исходами. Для вывода по своему спору прочитайте полную мотивировку.',
      region: 'Обстоятельства по исходам дел',
    },
    summary: metadata => ['granted', 'partial', 'refused'].map(key => [metadata.outcomes[key], metadata.labels[key]]),
    open: 'Открыть решение', fragments: 'Фрагменты решения', loading: 'Ищем подходящие решения…', registryLoading: 'Загружаем решения…',
    opening: 'Открываем решение…', emptyTitle: 'Подходящих решений не найдено', uncertain: 'Тема или исход требуют проверки по тексту.',
    fragmentNote: 'Фрагменты найдены автоматически. Проверьте их в контексте требований по делу.',
    claimFallback: 'Требования изложены в полном тексте решения.',
    sourceNotice: 'Разметка темы и исхода автоматическая. Последующее обжалование и исполнение решения не проверены.',
    resultsTitle: 'Найденные решения', missing: 'Текст решения не найден в коллекции.', notFound: 'Решение не найдено в коллекции.',
  },
  criminal: {
    prefix: 'criminal/',
    payload: 'data/criminal/offline-payload.b64',
    bundles: 'data/criminal/source-bundles/',
    title: 'Casebook — уголовные дела Казахстана',
    brand: 'Уголовные дела · Казахстан',
    collection: 'Коллекция приговоров',
    units: ['приговор', 'приговора', 'приговоров'],
    topicUnits: ['категория', 'категории', 'категорий'],
    ready: 'приговоров',
    topicWord: 'Категория', allTopics: 'Все категории', topicAuto: 'Определить по описанию', topicLabel: 'Категория дела',
    question: {
      eyebrow: 'Уголовные дела',
      heading: 'Как суды решают<br>похожие уголовные дела.',
      intro: 'Опишите обстоятельства. Посмотрите, какие наказания назначали суды, что учитывали как смягчающие и отягчающие обстоятельства.',
      label: 'Что произошло?',
      placeholder: 'Например: украл телефон в магазине, ущерб возместил, вину признал.',
      submit: 'Найти приговоры',
      examples: [
        ['Кража телефона', 'Тайно похитил сотовый телефон, ущерб возмещён, вину признал'],
        ['Мошенничество', 'Мошенничество через интернет: получил предоплату и не передал товар'],
        ['Наркотики', 'Хранение наркотических средств без цели сбыта'],
        ['Вождение пьяным', 'Управлял автомобилем в состоянии алкогольного опьянения, будучи лишённым прав'],
      ],
      welcome: [
        ['01 / НАЙТИ', 'Похожие приговоры', 'По статье, обстоятельствам и способу совершения.'],
        ['02 / СРАВНИТЬ', 'Наказания', 'Лишение свободы, ограничение свободы, штраф или иное.'],
        ['03 / ПРОВЕРИТЬ', 'Первоисточник', 'Полный обезличенный текст приговора.'],
      ],
      needsTopic: 'Не удалось определить категорию дела. Опишите деяние подробнее (например, «кража», «мошенничество», «побои») или выберите категорию вручную.',
    },
    registry: {
      nav: 'Реестр приговоров', heading: 'Реестр приговоров',
      intro: 'Выберите категорию и исход или найдите дело по номеру. Имена участников заменены на ФИО-1, ФИО-2 и т. д.',
      placeholder: 'Например, 7513-24-00-1/283',
    },
    factors: {
      eyebrow: 'Анализ приговоров', heading: 'Обстоятельства и наказание',
      intro: 'Какие обстоятельства упоминаются в приговорах и как они распределяются по видам назначенного наказания.',
      notice: 'Частота упоминания не показывает, какое наказание назначат по другому делу. Обстоятельство может упоминаться в тексте и в другом контексте, например при перечислении доводов сторон.',
      region: 'Обстоятельства по видам наказания',
    },
    summary: metadata => (metadata.factorColumns || []).map(([key, title]) => [metadata.punishments?.[key] || 0, title]),
    open: 'Открыть приговор', fragments: 'Фрагменты приговора', loading: 'Ищем похожие приговоры…', registryLoading: 'Загружаем приговоры…',
    opening: 'Открываем приговор…', emptyTitle: 'Подходящих приговоров не найдено', uncertain: 'Категория или исход требуют проверки по тексту.',
    fragmentNote: 'Фрагменты найдены автоматически. Проверьте их в контексте всего приговора.',
    claimFallback: 'Обвинение изложено в полном тексте приговора.',
    sourceNotice: 'Категория, исход и вид наказания размечены автоматически. Имена заменены на ФИО-N, даты рождения сокращены до года, адреса и ИИН скрыты. Обжалование приговора не проверено.',
    resultsTitle: 'Найденные приговоры', missing: 'Текст приговора не найден в коллекции.', notFound: 'Приговор не найден в коллекции.',
  },
  civil: {
    prefix: 'civil/',
    payload: 'data/civil/offline-payload.b64',
    bundles: 'data/civil/source-bundles/',
    title: 'Casebook — гражданские дела Казахстана',
    brand: 'Гражданские дела · Казахстан',
    collection: 'Коллекция решений',
    units: ['судебный акт', 'судебных акта', 'судебных актов'],
    topicUnits: ['тема', 'темы', 'тем'],
    ready: 'судебных актов',
    topicWord: 'Тема', allTopics: 'Все темы', topicAuto: 'Определить по описанию', topicLabel: 'Тема дела',
    question: {
      eyebrow: 'Гражданские дела',
      heading: 'Как суды решают<br>гражданские споры.',
      intro: 'Опишите спор. Посмотрите, какие требования заявляли истцы, как суды их оценивали и чем заканчивались похожие дела.',
      label: 'Что произошло?',
      placeholder: 'Например: работодатель уволил меня без объяснения причин, прошу восстановить на работе.',
      submit: 'Найти решения',
      examples: [
        ['Раздел имущества', 'Бывшие супруги делят квартиру и имущество, нажитое в браке'],
        ['Увольнение', 'Работодатель незаконно уволил и не выплатил заработную плату за вынужденный прогул'],
        ['Взыскание долга', 'Взыскание задолженности по договору займа и неустойки'],
        ['Недействительная сделка', 'Признание договора купли-продажи недействительным'],
      ],
      welcome: [
        ['01 / НАЙТИ', 'Похожие дела', 'По требованиям истца, предмету спора и обстоятельствам.'],
        ['02 / СРАВНИТЬ', 'Позиции суда', 'Иск удовлетворён, удовлетворён частично или отказано.'],
        ['03 / ПРОВЕРИТЬ', 'Первоисточник', 'Полный обезличенный текст решения.'],
      ],
      needsTopic: 'Не удалось определить тему дела. Опишите спор подробнее (например, «долг», «увольнение», «раздел имущества») или выберите тему вручную.',
    },
    registry: {
      nav: 'Реестр решений', heading: 'Реестр решений',
      intro: 'Выберите тему и исход или найдите дело по номеру. Имена участников заменены на ФИО-1, ФИО-2 и т. д. Решения судов первой инстанции и апелляционные постановления показаны вместе.',
      placeholder: 'Например, 7585-24-00-2/101',
    },
    factors: {
      eyebrow: 'Анализ решений', heading: 'Обстоятельства спора',
      intro: 'Какие формулировки встречаются в мотивировках и как распределяются по исходам решений первой инстанции.',
      notice: 'Частота формулировки не показывает вероятность выигрыша. В одном деле может быть несколько требований с разными исходами. Для вывода по своему спору прочитайте полную мотивировку.',
      region: 'Обстоятельства по исходам дел',
    },
    summary: metadata => ['granted', 'partial', 'refused'].map(key => [metadata.outcomes[key], metadata.labels[key]]),
    open: 'Открыть решение', fragments: 'Фрагменты решения', loading: 'Ищем похожие дела…', registryLoading: 'Загружаем решения…',
    opening: 'Открываем решение…', emptyTitle: 'Подходящих решений не найдено', uncertain: 'Тема или исход требуют проверки по тексту.',
    fragmentNote: 'Фрагменты найдены автоматически. Проверьте их в контексте требований по делу.',
    claimFallback: 'Требования изложены в полном тексте решения.',
    sourceNotice: 'Тема, исход и обстоятельства размечены автоматически. Имена заменены на ФИО-N, даты рождения сокращены до года, адреса и ИИН скрыты. Обжалование решений первой инстанции не проверено.',
    resultsTitle: 'Найденные решения', missing: 'Текст решения не найден в коллекции.', notFound: 'Решение не найдено в коллекции.',
  },
};

const state = {};
for (const key of Object.keys(SECTIONS)) {
  state[key] = {worker: null, workerURL: null, ready: false, metadata: null, pending: new Map(), sequence: 0,
    loading: null, questionState: null, registryState: {mode: 'registry'}, bundles: new Map(), status: ['', '']};
}
let section = 'admin';
let viewSequence = 0;
let sourceController;
let lastSection = 'question';
let lastScroll = 0;

const S = () => state[section];
const C = () => SECTIONS[section];
const viewHash = (view, key = section) => '#' + SECTIONS[key].prefix + view;
const caseLink = (id, line, key = section) => '#' + SECTIONS[key].prefix + 'case=' + encodeURIComponent(id) + (line ? '&line=' + line : '');

function request(method, params = {}, key = section) {
  const sectionState = state[key];
  return new Promise((resolve, reject) => {
    const id = ++sectionState.sequence;
    sectionState.pending.set(id, {resolve, reject});
    sectionState.worker.postMessage({id, method, params});
  });
}

function setStatus(message, status = '', key = section) {
  state[key].status = [message, status];
  if (key !== section) return;
  $('status-text').textContent = message;
  $('database-status').className = 'database-status ' + status;
  $('retry-load').hidden = status !== 'failed';
}

function rejectPending(key, message) {
  for (const {reject} of state[key].pending.values()) reject(new Error(message));
  state[key].pending.clear();
}

function setControls() {
  document.querySelectorAll('[data-needs-data]').forEach(element => element.disabled = !S().ready);
}

function fillSelect(id, entries, firstLabel) {
  const select = $(id);
  const selected = select.value;
  while (select.options.length) select.remove(0);
  select.add(new Option(firstLabel, ''));
  for (const [key, title] of entries) select.add(new Option(title, key));
  select.value = [...select.options].some(option => option.value === selected) ? selected : '';
}

function applyMetadata() {
  const config = C();
  const metadata = S().metadata;
  fillSelect('question-topic', metadata ? Object.entries(metadata.topics) : [], config.topicAuto);
  fillSelect('registry-topic', metadata ? Object.entries(metadata.topics) : [], config.allTopics);
  fillSelect('factor-topic', metadata ? Object.entries(metadata.topics) : [], config.allTopics);
  fillSelect('registry-outcome', metadata ? Object.entries(metadata.labels).filter(([key]) => metadata.outcomes[key]) : [], 'Все исходы');
  if (!metadata) { $('summary').innerHTML = ''; return; }
  const topics = Object.keys(metadata.topics).length;
  $('unique').textContent = number(metadata.unique);
  $('collection-note').textContent = `${plural(metadata.unique, config.units)} · ${topics} ${plural(topics, config.topicUnits)}`;
  const count = $(section + '-count');
  if (count) count.textContent = number(metadata.unique);
  $('summary').innerHTML = config.summary(metadata).map(([count, label]) =>
    `<div class="metric"><strong>${number(count || 0)}</strong><span>${escapeHTML(label)}</span></div>`).join('');
}

async function initialize(key = section) {
  const sectionState = state[key];
  const config = SECTIONS[key];
  sectionState.ready = false;
  if (key === section) setControls();
  setStatus('Загружаем базу…', '', key);
  if (sectionState.worker) {
    sectionState.worker.onmessage = null;
    sectionState.worker.onerror = null;
    sectionState.worker.terminate();
    if (sectionState.workerURL) URL.revokeObjectURL(sectionState.workerURL);
    rejectPending(key, 'Загрузка перезапущена.');
  }
  try {
    sectionState.workerURL = URL.createObjectURL(new Blob([$('search-worker').textContent], {type: 'text/javascript'}));
    const worker = new Worker(sectionState.workerURL);
    sectionState.worker = worker;
    worker.onerror = () => {
      rejectPending(key, 'Не удалось подготовить поиск. Попробуйте обновить страницу.');
      setStatus('Не удалось подготовить поиск.', 'failed', key);
    };
    worker.onmessage = ({data}) => {
      // WebKit may still be reading the blob until the worker sends its first message.
      if (sectionState.workerURL) { URL.revokeObjectURL(sectionState.workerURL); sectionState.workerURL = null; }
      if (data.type === 'progress') {
        const megabytes = (data.received / 1024 / 1024).toFixed(1);
        setStatus(data.message || 'Загружаем базу · ' + megabytes + ' МБ', '', key);
        return;
      }
      const task = sectionState.pending.get(data.id);
      if (!task) return;
      sectionState.pending.delete(data.id);
      if (data.error) task.reject(new Error(data.error));
      else task.resolve(data.result);
    };
    sectionState.metadata = await request('init', {url: new URL(config.payload, location.href).href}, key);
    sectionState.ready = true;
    setStatus('База готова · ' + number(sectionState.metadata.unique) + ' ' + config.ready, 'ready', key);
    if (key === section) {
      applyMetadata();
      setControls();
      route();
    }
  } catch (error) {
    setStatus(error.message, 'failed', key);
  }
}

function applySection() {
  const config = C();
  document.title = config.title;
  document.documentElement.dataset.section = section;
  $('brand-sub').textContent = config.brand;
  $('collection-eyebrow').textContent = config.collection;
  document.querySelectorAll('.section-link').forEach(link => {
    const active = link.dataset.section === section;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'true'); else link.removeAttribute('aria-current');
  });
  document.querySelectorAll('.nav').forEach(link => link.setAttribute('href', viewHash(link.dataset.view)));
  $('nav-registry').textContent = config.registry.nav;
  const q = config.question;
  $('question-eyebrow').textContent = q.eyebrow;
  $('question-heading').innerHTML = q.heading;
  $('question-intro').textContent = q.intro;
  $('question-label').textContent = q.label;
  $('question').placeholder = q.placeholder;
  $('question').value = '';
  $('question-topic-label').textContent = config.topicLabel;
  $('question-submit').textContent = q.submit;
  $('examples').innerHTML = '<span>Например</span>' + q.examples.map(([label, text]) =>
    `<button type="button" data-needs-data data-question="${escapeHTML(text)}">${escapeHTML(label)}</button>`).join('');
  $('answer').innerHTML = welcome();
  $('registry-heading').textContent = config.registry.heading;
  $('registry-intro').textContent = config.registry.intro;
  $('registry-query').placeholder = config.registry.placeholder;
  $('registry-query').value = '';
  $('registry-results').innerHTML = '';
  $('factors-eyebrow').textContent = config.factors.eyebrow;
  $('factors-heading').textContent = config.factors.heading;
  $('factors-intro').textContent = config.factors.intro;
  $('factors-notice').textContent = config.factors.notice;
  $('factor-results').innerHTML = '';
  document.querySelectorAll('.topic-word').forEach(element => element.textContent = config.topicWord);
  $('unique').textContent = '…';
  $('collection-note').textContent = '';
  applyMetadata();
  setControls();
  const [message, status] = S().status;
  setStatus(message || 'Загружаем базу…', status);
}

function welcome() {
  return '<div class="welcome">' + C().question.welcome.map(([step, title, text]) =>
    `<article><span class="step">${escapeHTML(step)}</span><h2>${escapeHTML(title)}</h2><p>${escapeHTML(text)}</p></article>`).join('') + '</div>';
}

function badge(outcome) {
  return `<span class="tag ${escapeHTML(outcome)}">${escapeHTML(S().metadata.labels[outcome] || outcome)}</span>`;
}

function punishmentTag(row) {
  const columns = S().metadata.factorColumns;
  if (!columns || !row.punishment || row.outcome !== 'convicted' && row.outcome !== 'partial') return '';
  const title = Object.fromEntries(columns)[row.punishment];
  return title ? `<span class="tag punishment ${escapeHTML(row.punishment)}">${escapeHTML(title)}</span>` : '';
}

function documentCard(row) {
  const config = C();
  const metadata = S().metadata;
  const uncertain = row.topicConfidence !== 'высокая' || row.outcomeConfidence !== 'высокая';
  return `<article class="card">
    <div class="card-top"><span class="tags">${badge(row.outcome)}${punishmentTag(row)}</span><span class="case-date">${escapeHTML(dateLabel(row.date))}</span></div>
    <h3>${escapeHTML(row.subtopic || metadata.topics[row.topic])}</h3>
    <div class="meta">${escapeHTML(row.caseNumber || 'Номер дела не указан')}</div>
    <p class="claim">${escapeHTML(row.claim || config.claimFallback)}</p>
    ${uncertain ? `<p class="review-note">${escapeHTML(config.uncertain)}</p>` : ''}
    ${row.fragments.length ? `<details><summary>${escapeHTML(config.fragments)}</summary><p class="muted">${escapeHTML(config.fragmentNote)}</p>
      ${row.fragments.map(fragment => `<p><b>${escapeHTML(fragment.label)}</b></p><blockquote>${escapeHTML(fragment.quote)}</blockquote>`).join('')}
      <small class="muted">Разметка: ${escapeHTML(config.topicWord.toLowerCase())} — ${escapeHTML(row.topicConfidence)}, исход — ${escapeHTML(row.outcomeConfidence)} уверенность.</small>
    </details>` : ''}
    <a class="card-link" href="${caseLink(row.id)}">${escapeHTML(config.open)} <span aria-hidden="true">↗</span></a>
  </article>`;
}

function exampleCard(example) {
  return `<article class="card">
    <div class="card-top">${badge(example.outcome)}<span class="tag example">Пример с разбором</span></div>
    <h3>${escapeHTML(example.title)}</h3><div class="meta">${escapeHTML(dateLabel(example.date))} · ${escapeHTML(example.case_number || 'Номер не указан')}</div>
    <p>${escapeHTML(example.reason)}</p><div class="label">Доказательства</div><p>${escapeHTML(example.evidence)}</p>
    <div class="label">Результат</div><p>${escapeHTML(example.result)}</p>
    <details><summary>Цитаты из решения (${example.quotes.length})</summary>${example.quotes.map(quote =>
      `<blockquote>${escapeHTML(quote.text)}</blockquote><a href="${caseLink(example.id, quote.line)}">Показать в документе ↗</a>`).join('')}</details>
    <a class="card-link" href="${caseLink(example.id)}">Открыть решение ↗</a>
  </article>`;
}

function pagination(data, kind) {
  if (data.total <= data.size) return '';
  return `<div class="pagination" aria-label="Страницы результатов">
    <button class="secondary" data-page="${data.page - 1}" data-kind="${kind}" ${data.page === 0 ? 'disabled' : ''}>← Назад</button>
    <span>${data.page + 1} из ${Math.ceil(data.total / data.size)}</span>
    <button class="secondary" data-page="${data.page + 1}" data-kind="${kind}" ${(data.page + 1) * data.size >= data.total ? 'disabled' : ''}>Далее →</button>
  </div>`;
}

function resultCount(data) {
  return `<p class="result-count">Найдено: ${number(data.matched)}.${data.bounded ? ' Показаны 400 наиболее близких совпадений. Уточните запрос, чтобы сузить список.' : ''}</p>`;
}

function emptyState(message) {
  return `<div class="empty"><h2>${escapeHTML(C().emptyTitle)}</h2><p>${escapeHTML(message)}</p></div>`;
}

async function runQuestion(page = 0, newSearch = false) {
  const sectionState = S();
  if (!sectionState.ready) return;
  if (newSearch || !sectionState.questionState) {
    const query = $('question').value.trim();
    if (!query) { $('question').focus(); return; }
    sectionState.questionState = {query, topic: $('question-topic').value, mode: 'question'};
  }
  const serial = ++viewSequence;
  const config = C();
  const metadata = sectionState.metadata;
  $('answer').innerHTML = `<p class="loading">${escapeHTML(config.loading)}</p>`;
  try {
    const data = await request('search', {...sectionState.questionState, page});
    if (serial !== viewSequence) return;
    if (!data.items.length) {
      $('answer').innerHTML = emptyState(data.needsTopic ? config.question.needsTopic
        : 'Попробуйте сократить запрос, изменить ' + config.topicWord.toLowerCase() + ' или найти дело по номеру в реестре.');
      return;
    }
    let body = `<div class="answer-head"><h2>${escapeHTML(metadata.topics[data.topic] || 'Результаты поиска')}</h2><span class="tag">По материалам коллекции</span></div>`;
    if (data.guide) {
      body += '<h2>Какие доказательства подготовить</h2><p class="muted">Перечень по теме спора. Точный состав зависит от ваших требований и основания отказа.</p><div class="evidence-list">';
      body += data.guide.evidence.map(([title, documents, reason], index) =>
        `<article class="evidence"><span class="index">${String(index + 1).padStart(2, '0')}</span><h3>${escapeHTML(title)}</h3><p>${escapeHTML(documents)}</p><p class="why">${escapeHTML(reason)}</p></article>`).join('') + '</div>';
    }
    if (data.examples.length) {
      body += '<h2>Что повлияло на результат в похожих делах</h2><p class="muted">Примеры по теме. Обстоятельства могут отличаться от вашей ситуации.</p><div class="cards">' + data.examples.map(exampleCard).join('') + '</div>';
    }
    if (data.guide) body += '<div class="questions"><h3>Что ещё уточнить</h3><ol>' + data.guide.questions.map(question => '<li>' + escapeHTML(question) + '</li>').join('') + '</ol></div>';
    body += `<h2 id="question-results-heading">${escapeHTML(config.resultsTitle)}</h2>` + resultCount(data) + '<div class="cards">' + data.items.map(documentCard).join('') + '</div>' + pagination(data, 'question');
    $('answer').innerHTML = body;
    if (page) $('question-results-heading').scrollIntoView();
  } catch (error) {
    if (serial === viewSequence) $('answer').innerHTML = '<p class="error">' + escapeHTML(error.message) + '</p>';
  }
}

async function loadRegistry(page = 0, newSearch = false) {
  const sectionState = S();
  if (!sectionState.ready) return;
  if (newSearch) sectionState.registryState = {query: $('registry-query').value, topic: $('registry-topic').value, outcome: $('registry-outcome').value, mode: 'registry'};
  const serial = ++viewSequence;
  $('registry-results').innerHTML = `<p class="loading">${escapeHTML(C().registryLoading)}</p>`;
  try {
    const data = await request('search', {...sectionState.registryState, page});
    if (serial !== viewSequence) return;
    $('registry-results').innerHTML = data.items.length
      ? resultCount(data) + '<div class="cards">' + data.items.map(documentCard).join('') + '</div>' + pagination(data, 'registry')
      : emptyState('Измените фильтры или проверьте номер дела.');
    if (page) $('registry-results').scrollIntoView();
  } catch (error) {
    if (serial === viewSequence) $('registry-results').innerHTML = '<p class="error">' + escapeHTML(error.message) + '</p>';
  }
}

async function loadFactors() {
  if (!S().ready) return;
  const serial = ++viewSequence;
  const metadata = S().metadata;
  const columns = metadata.factorColumns || [['granted', 'Удовлетворён'], ['partial', 'Частично'], ['refused', 'Отказано']];
  $('factor-results').innerHTML = '<p class="loading">Считаем формулировки…</p>';
  try {
    const data = await request('factors', {topic: $('factor-topic').value});
    if (serial !== viewSequence) return;
    $('factor-results').innerHTML = data.rows.length ? `<div class="tablewrap" tabindex="0" role="region" aria-label="${escapeHTML(C().factors.region)}"><table><caption>Количество текстов с найденной формулировкой</caption><thead><tr><th scope="col">Формулировка</th>` +
      columns.map(([, title]) => `<th scope="col">${escapeHTML(title)}</th>`).join('') + '</tr></thead><tbody>' + data.rows.map(row =>
      '<tr><th scope="row">' + escapeHTML(row.label) + '</th>' + columns.map(([key]) =>
        `<td>${number(row[key] || 0)}<small>из ${number(data.denominators[key] || 0)} текстов</small></td>`).join('') + '</tr>').join('') + '</tbody></table></div><p class="muted">В одном тексте может быть несколько формулировок. Если формулировка не найдена, это не означает отсутствия обстоятельства.</p>'
      : emptyState('Для выбранной категории формулировки не найдены.');
  } catch (error) {
    if (serial === viewSequence) $('factor-results').innerHTML = '<p class="error">' + escapeHTML(error.message) + '</p>';
  }
}

async function fetchSourceText(id, signal) {
  const sectionState = S();
  const bucket = id.slice(0, 2).toLowerCase();
  let documents = sectionState.bundles.get(bucket);
  if (!documents) {
    const response = await fetch(`${C().bundles}${bucket}.json.gz`, {signal});
    if (!response.ok) throw new Error('Не удалось загрузить текст. Проверьте соединение и повторите попытку.');
    const compressed = await response.arrayBuffer();
    const decoded = await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
    documents = JSON.parse(decoded);
    sectionState.bundles.set(bucket, documents);
    if (sectionState.bundles.size > 8) sectionState.bundles.delete(sectionState.bundles.keys().next().value);
  }
  const text = documents[id];
  if (typeof text !== 'string' || !text.trim()) throw new Error(C().missing);
  return text;
}

async function openCase(id, line) {
  const config = C();
  const back = viewHash(lastSection);
  if (!document.querySelector('.shell').hidden) lastScroll = window.scrollY;
  document.querySelector('.shell').hidden = true;
  $('source-view').hidden = false;
  $('source-view').innerHTML = `<div class="source-toolbar"><a class="secondary" href="${back}">← Вернуться к результатам</a></div><p class="loading">${escapeHTML(config.opening)}</p>`;
  window.scrollTo(0, 0);
  const controller = new AbortController();
  sourceController = controller;
  try {
    if (!/^[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}$/i.test(id)) throw new Error('Некорректная ссылка на документ.');
    const row = await request('case', {id});
    if (controller.signal.aborted) return;
    if (!row) throw new Error(config.notFound);
    const timeout = setTimeout(() => controller.abort(new Error('Сервер долго не отвечает. Попробуйте открыть документ ещё раз.')), 45000);
    let text;
    try {
      text = await fetchSourceText(id, controller.signal);
    } finally { clearTimeout(timeout); }
    if (controller.signal.aborted) return;
    const metadata = S().metadata;
    $('source-view').innerHTML = `<div class="source-toolbar"><a class="secondary" href="${back}">← Вернуться к результатам</a><button id="copy-case-link" class="text-button">Скопировать ссылку</button></div>
      <h1>Дело ${escapeHTML(row.caseNumber || row.id)}</h1><p class="source-meta">${escapeHTML(dateLabel(row.date))} · ${escapeHTML(row.subtopic && section !== 'admin' ? row.subtopic : metadata.topics[row.topic])}</p><p class="source-meta">${escapeHTML(row.court)}</p><span class="tags">${badge(row.outcome)}${punishmentTag(row)}</span>
      <p class="notice">${escapeHTML(config.sourceNotice)}</p>
      <div class="fulltext">${text.split('\n').map((content, index) => `<div class="line" id="L${index + 1}"><span>${escapeHTML(content)}</span></div>`).join('')}</div>`;
    $('copy-case-link').addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(location.href);
        $('copy-case-link').textContent = 'Ссылка скопирована';
      } catch {
        $('copy-case-link').textContent = 'Скопируйте адрес из строки браузера';
      }
    });
    const anchor = $('L' + Math.max(1, Number(line) || 1));
    if (line && anchor) { anchor.classList.add('highlight'); anchor.scrollIntoView(); }
    else $('source-view').focus({preventScroll: true});
  } catch (error) {
    if (controller.signal.aborted && controller.signal.reason?.name === 'AbortError') return;
    $('source-view').insertAdjacentHTML('beforeend', '<p class="error" role="alert">' + escapeHTML(error.message) + '</p><button class="secondary" id="retry-source">Попробовать ещё раз</button>');
    $('source-view').querySelector('.loading')?.remove();
    $('retry-source').onclick = () => openCase(id, line);
  }
}

function parseHash() {
  let hash = location.hash.slice(1);
  let key = 'admin';
  for (const [name, config] of Object.entries(SECTIONS)) {
    const bare = config.prefix.replace(/\/$/, '');
    if (bare && (hash === bare || hash.startsWith(config.prefix))) {
      key = name;
      hash = hash.slice(config.prefix.length);
    }
  }
  return {key, hash};
}

function route() {
  sourceController?.abort();
  const {key, hash} = parseHash();
  if (key !== section) {
    section = key;
    ++viewSequence;
    applySection();
    if (!S().ready && !S().loading) S().loading = initialize(key);
    else if (!S().ready) setStatus(...S().status);
  }
  if (hash.startsWith('case=')) {
    if (S().ready) {
      const params = new URLSearchParams(hash);
      openCase(params.get('case') || '', params.get('line'));
    }
    return;
  }
  const view = ['question', 'registry', 'factors', 'method'].includes(hash) ? hash : 'question';
  const returning = !$('source-view').hidden;
  const changed = view !== lastSection;
  lastSection = view;
  $('source-view').hidden = true;
  document.querySelector('.shell').hidden = false;
  document.querySelectorAll('#main-content > section').forEach(element => element.hidden = element.id !== view + '-view');
  document.querySelectorAll('.nav').forEach(link => {
    link.classList.toggle('active', link.dataset.view === view);
    if (link.dataset.view === view) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  if (changed) ++viewSequence;
  if (view === 'registry' && (!returning || !$('registry-results').innerHTML)) loadRegistry();
  if (view === 'factors' && (!returning || !$('factor-results').innerHTML)) loadFactors();
  if (returning) window.scrollTo(0, lastScroll);
  else if (changed) window.scrollTo(0, 0);
}

$('ask').addEventListener('submit', event => { event.preventDefault(); runQuestion(0, true); });
$('filter').addEventListener('submit', event => { event.preventDefault(); loadRegistry(0, true); });
$('factor-topic').addEventListener('change', loadFactors);
$('retry-load').addEventListener('click', () => { S().loading = initialize(section); });
document.addEventListener('click', event => {
  const button = event.target.closest('[data-question], [data-page]');
  if (!button || button.disabled) return;
  if (button.dataset.question) {
    $('question').value = button.dataset.question;
    $('question-topic').value = '';
    runQuestion(0, true);
  } else if (button.dataset.kind === 'registry') loadRegistry(Number(button.dataset.page));
  else runQuestion(Number(button.dataset.page));
});
window.addEventListener('hashchange', route);
section = parseHash().key;
applySection();
route();
S().loading = initialize(section);

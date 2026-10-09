/* Search over the five-character word prefixes stored in a published index (administrative or criminal). */
class PracticeSearch {
  constructor(data) {
    this.data = data;
    this.records = data.records.filter(row => !row[14]);
    this.stopWords = new Set(data.stop);
  }

  normalize(text) {
    return String(text ?? '').toLowerCase().replace(/ё/g, 'е');
  }

  terms(query) {
    const expanded = this.normalize(query)
      .replace(/пристав[а-я]*/g, ' судебный исполнитель чси ')
      .replace(/земл[яюеи](?=\s|$)/g, ' земельный участок ')
      .replace(/долг[а-я]*/g, ' задолженность ')
      .replace(/машин[а-я]*/g, ' автомобиль транспортное ')
      .replace(/ипотек[а-я]*/g, ' ипотечный ')
      .replace(/пенси[яию](?=\s|$)/g, ' пенсионный ')
      .replace(/субсиди[а-я]*/g, ' субсидирование ');
    return [...new Set((expanded.match(/[а-яa-z]+/g) || [])
      .filter(word => word.length >= 3 && !this.stopWords.has(word))
      .map(word => word.length > 6 ? word.slice(0, 5) : word.length > 4 ? word.slice(0, 4) : word))].slice(0, 14);
  }

  inferTopic(query) {
    const text = this.normalize(query);
    const scores = Object.entries(this.data.topicWords).map(([topic, pattern]) => {
      let score = (text.match(new RegExp(pattern, 'g')) || []).length;
      if (score && ['enforcement', 'bankruptcy', 'procurement', 'customs'].includes(topic)) score += 2;
      if (topic === 'tax' && text.includes('налог')) score += 3;
      if (topic === 'construction' && /апз|эскиз|генплан/.test(text)) score += 3;
      if (topic === 'agriculture' && text.includes('субсид')) score += 3;
      return [topic, score];
    }).sort((a, b) => b[1] - a[1]);
    return scores[0]?.[1] ? scores[0][0] : '';
  }

  caseReference(query) {
    const clean = query.trim().replace(/^дело\s*/i, '').replace(/^№\s*/, '').replace(/[–—]/g, '-');
    return /^(?:[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}|\d[\d\s/\-]{3,})$/i.test(clean)
      ? clean.replace(/\s/g, '').toLowerCase() : '';
  }

  card(row) {
    const [id, date, caseNumber, court, topic, subtopic, claim, outcome,
      outcomeConfidence, topicConfidence, outcomeBasis, fragments] = row;
    return {id, date, caseNumber, court, topic, subtopic, claim, outcome,
      outcomeConfidence, topicConfidence, outcomeBasis, fragments, punishment: row[15] || ''};
  }

  search({query = '', topic = '', outcome = '', mode = 'question', page = 0} = {}) {
    query = query.trim().slice(0, 1200);
    const reference = this.caseReference(query);
    const selectedTopic = topic || (mode === 'question' && !reference ? this.inferTopic(query) : '');
    const terms = reference ? [] : this.terms(query);
    const needsTopic = mode === 'question' && !reference && !selectedTopic;
    let rows = needsTopic ? [] : this.records.filter(row =>
      (!selectedTopic || row[4] === selectedTopic) && (!outcome || row[7] === outcome) &&
      (mode !== 'question' || outcome || reference || row[13] === 'decision'));

    if (reference) {
      rows = rows.filter(row => row[0] === reference || row[2].replace(/\s/g, '').includes(reference));
    } else if (terms.length) {
      const candidates = [];
      const frequencies = terms.map(() => 0);
      for (const row of rows) {
        const matches = terms.map((term, i) => {
          const matched = row[12].includes(' ' + term);
          if (matched) frequencies[i]++;
          return matched;
        });
        const hits = matches.filter(Boolean).length;
        if (hits >= Math.min(3, Math.max(1, Math.ceil(terms.length * 0.4)))) {
          candidates.push({row, matches, hits});
        }
      }
      const weights = frequencies.map(count => 1 + Math.log(1 + rows.length / (count + 1)));
      for (const candidate of candidates) {
        const claim = this.normalize(candidate.row[6]);
        candidate.score = candidate.matches.reduce((score, matched, i) =>
          score + (matched ? weights[i] : 0) + (claim.includes(terms[i]) ? weights[i] * 0.5 : 0), 0);
      }
      candidates.sort((a, b) => b.score - a.score || b.hits - a.hits || b.row[1].localeCompare(a.row[1]));
      rows = candidates.map(candidate => candidate.row);
    } else if (query && !reference) {
      rows = [];
    } else {
      rows = [...rows].sort((a, b) => b[1].localeCompare(a[1]) || a[0].localeCompare(b[0]));
    }

    const matched = rows.length;
    const bounded = Boolean(terms.length && matched > 400);
    if (bounded) rows = rows.slice(0, 400);
    const size = 18;
    page = Math.max(0, Math.min(Math.floor(Number(page) || 0), Math.max(0, Math.ceil(rows.length / size) - 1)));
    const guide = selectedTopic && rows.length ? this.data.guides[selectedTopic] : null;
    const examples = guide ? this.data.examples.filter(example => example.topic === selectedTopic) : [];
    const relevance = example => terms.filter(term => this.normalize(example.title + ' ' + example.reason).includes(term)).length;
    examples.sort((a, b) => relevance(b) - relevance(a));
    return {items: rows.slice(page * size, (page + 1) * size).map(row => this.card(row)),
      total: rows.length, matched, bounded, size, page, topic: selectedTopic,
      guide: guide || null, examples: examples.slice(0, 4), needsTopic};
  }

  factors(topic = '') {
    // Admin decisions are compared by outcome (field 7); criminal verdicts by punishment type (field 15).
    const field = this.data.stats.factorField ?? 7;
    const denominators = {};
    for (const row of this.records) {
      if (!topic || row[4] === topic) denominators[row[field]] = (denominators[row[field]] || 0) + 1;
    }
    const groups = new Map();
    for (const row of this.data.factorRows) {
      if (topic && row.topic !== topic) continue;
      if (!groups.has(row.factor)) groups.set(row.factor, {label: row.label});
      const group = groups.get(row.factor);
      group[row.outcome] = (group[row.outcome] || 0) + row.n;
    }
    const rows = [...groups.values()].sort((a, b) =>
      (b.granted || 0) + (b.partial || 0) - (a.granted || 0) - (a.partial || 0));
    return {rows, denominators};
  }

  getCase(id) {
    const row = this.data.records.find(record => record[0] === id);
    return row ? this.card(row) : null;
  }
}

if (typeof module !== 'undefined') module.exports = {PracticeSearch};

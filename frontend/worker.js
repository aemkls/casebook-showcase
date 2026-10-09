/* The index stays in a worker so loading and searching do not freeze the page. */
let engine;

async function loadIndex(url) {
  if (typeof DecompressionStream === 'undefined') {
    throw new Error('Обновите браузер: для открытия базы нужна поддержка gzip.');
  }
  const response = await fetch(url, {signal: AbortSignal.timeout(180000)});
  if (!response.ok) throw new Error('Не удалось загрузить базу. Проверьте соединение и попробуйте ещё раз.');
  const reader = response.body.getReader();
  const total = Number(response.headers.get('Content-Length'));
  let received = 0;
  const chunks = [];
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    self.postMessage({type: 'progress', received, total});
  }
  self.postMessage({type: 'progress', message: 'Подготавливаем поиск…'});
  const encoded = await new Blob(chunks).text();
  const binary = atob(encoded.trim());
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const text = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
  const data = JSON.parse(text);
  engine = new PracticeSearch(data);
  return data.stats;
}

self.onmessage = async ({data: {id, method, params}}) => {
  try {
    let result;
    if (method === 'init') result = await loadIndex(params.url);
    else {
      if (!engine) throw new Error('База ещё загружается.');
      if (method === 'search') result = engine.search(params);
      else if (method === 'factors') result = engine.factors(params.topic);
      else if (method === 'case') result = engine.getCase(params.id);
      else throw new Error('Неизвестная операция.');
    }
    self.postMessage({id, result});
  } catch (error) {
    self.postMessage({id, error: error.message});
  }
};

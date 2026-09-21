// Проверка веб-демо без браузера и сторонних пакетов.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');

const root = __dirname;
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(script, 'Не найден JavaScript веб-демо');

const elements = {
  'msg-input': { value: '', addEventListener() {}, focus() {} },
  'bulk-input': { value: '' },
  'bulk-section': { style: { display: '' } },
  'result-section': { style: { display: '' }, scrollIntoView() {} },
  'results-list': { innerHTML: '' },
};
const alerts = [];
const context = {
  document: { getElementById: id => elements[id] },
  alert: message => alerts.push(message),
};
vm.createContext(context);
vm.runInContext(script[1], context);

const messages = fs.readFileSync(path.join(root, 'messages.txt'), 'utf8').trim().split(/\r?\n/);
const probes = [...messages, 'Жалоба: не выдают справку', 'Не работает медпункт', 'Не работает кафедра'];
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const pythonCode = 'import json, sys, classify; lines=json.load(sys.stdin); print(json.dumps([classify.classify_and_respond(line) for line in lines], ensure_ascii=False))';
const result = spawnSync(python, ['-B', '-c', pythonCode], {
  cwd: root,
  encoding: 'utf8',
  input: JSON.stringify(probes),
  env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
});
assert.equal(result.status, 0, result.stderr);
const expected = JSON.parse(result.stdout);
assert.equal(messages.length, 5);
for (let i = 0; i < probes.length; i++) {
  const actual = context.classifyAndRespond(probes[i]);
  assert.equal(actual.category, expected[i][0], `Категория #${i + 1}`);
  assert.equal(actual.draft, expected[i][1], `Черновик #${i + 1}`);
}

assert.equal(context.classifyAndRespond('Жалоба: не выдают справку').category, 'жалоба');
assert.ok(!context.classifyAndRespond('Не работает медпункт').draft.includes('столовой'));
assert.ok(!context.classifyAndRespond('Не работает кафедра').draft.includes('столовой'));
context.toggleBulk();
assert.equal(elements['bulk-section'].style.display, 'block', 'Пакетный режим должен открываться с первого нажатия');

context.classifySingle();
assert.equal(alerts.pop(), 'Введите текст обращения.');
context.classifyBulk();
assert.equal(alerts.pop(), 'Введите хотя бы одно обращение.');
context.loadDefaults();
context.classifyBulk();
assert.equal((elements['results-list'].innerHTML.match(/class="result-card"/g) || []).length, 5);

elements['msg-input'].value = '<img src=x onerror=alert(1)>';
context.classifySingle();
assert.ok(elements['results-list'].innerHTML.includes('&lt;img'));
assert.ok(!elements['results-list'].innerHTML.includes('<img'));
context.clearAll();
assert.equal(elements['msg-input'].value, '');
assert.equal(elements['bulk-input'].value, '');
assert.equal(elements['result-section'].style.display, 'none');

console.log('Веб-демо: классификация, пакетный режим и экранирование — OK');

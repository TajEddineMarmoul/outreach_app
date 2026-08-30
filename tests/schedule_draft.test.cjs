const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const web = path.resolve(__dirname, '../outreach_web');
const ts = Module.createRequire(path.join(web, 'package.json'))('typescript');
function loadTs(relative, aliases = {}) {
  const filename = path.join(web, 'src', relative);
  const module = new Module(filename);
  module.filename = filename;
  module.paths = Module._nodeModulePaths(path.dirname(filename));
  const normalRequire = module.require.bind(module);
  module.require = id => aliases[id] || normalRequire(id);
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, filename);
  return module.exports;
}
const schedule = loadTs('components/campaigns/workspace/scheduleDraft.ts', {
  '@/lib/timezones': loadTs('lib/timezones.ts'),
});
const draft = { ...schedule.hydrateSchedule({ timezone: 'UTC', send_settings: { mode: 'autopilot' } }), scheduledAt: '2020-01-01T12:00', startOnDate: false };
test('switching to the next autopilot window ignores a date left over from scheduled sending', () => {
  assert.equal(schedule.scheduleProblem(draft), '');
  assert.equal(schedule.schedulePayload(draft).scheduled_at, null);
  assert.equal(schedule.launchRequest(draft).body.scheduled_at, undefined);
});
test('a date explicitly selected for scheduled sending or autopilot is still validated', () => {
  for (const value of [{ ...draft, mode: 'schedule' }, { ...draft, startOnDate: true }]) {
    assert.match(schedule.scheduleProblem(value), /future/);
  }
});
test('after-launch mode never inherits a hidden start date', () => {
  const value = { ...draft, mode: 'send_now', startOnDate: true };
  assert.equal(schedule.scheduleProblem(value), '');
  const request = schedule.launchRequest(value);
  assert.equal(request.endpoint, 'send-now');
  assert.equal(request.body.scheduled_at, undefined);
});

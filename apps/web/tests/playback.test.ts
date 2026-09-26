import { test } from 'node:test';
import assert from 'node:assert/strict';
import { nextBreak, skippedBySeek } from '../lib/playback';

const breaks = [{ candidate_id: 'one', timestamp_sec: 20 }, { candidate_id: 'two', timestamp_sec: 50 }];

test('content reaches break, inserts once despite repeated time events', () => {
  assert.equal(nextBreak(19.9, 20.2, breaks, new Set())?.candidate_id, 'one');
  assert.equal(nextBreak(19.9, 20.2, breaks, new Set(['one'])), undefined);
});
test('does not play late missed slots or replay after seeking backward', () => {
  assert.equal(nextBreak(40, 41, breaks, new Set()), undefined);
  assert.equal(nextBreak(50, 10, breaks, new Set()), undefined);
});
test('forward seek skips crossed slots and keeps later slots available', () => {
  assert.deepEqual(skippedBySeek(10, 30, breaks), ['one']);
  assert.equal(nextBreak(49.9, 50.1, breaks, new Set(['one']))?.candidate_id, 'two');
});

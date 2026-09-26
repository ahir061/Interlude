import { test, expect } from './fixtures';
import fs from 'node:fs';
import path from 'node:path';

test('real accepted manifest pauses content, plays MP4 ad and resumes exact position once', async ({ page }) => {
  const manifestPath = process.env.INTERLUDE_MANIFEST;
  test.skip(!manifestPath, 'Set INTERLUDE_MANIFEST to an actual completed analysis.json with an accepted break.');
  const manifest = JSON.parse(fs.readFileSync(manifestPath!, 'utf8'));
  expect(manifest.ad_breaks.length, 'The real pipeline must have accepted a slot').toBeGreaterThan(0);
  const candidate = process.env.INTERLUDE_CANDIDATE;
  const slot = candidate ? manifest.ad_breaks.find((b: { candidate_id: string }) => b.candidate_id === candidate)
    : manifest.ad_breaks[0];
  expect(slot, 'The requested slot must be present in the real manifest').toBeDefined();
  await page.goto(`/?video=${manifest.video.id}`);
  const content = page.getByTestId('content-video');
  await expect(content).toBeVisible();
  await content.evaluate((element, timestamp) => {
    const video = element as HTMLVideoElement;
    video.muted = true;
    video.currentTime = Math.max(0, timestamp - 1.5);
  }, slot.timestamp_sec);
  await expect.poll(() => content.evaluate(e => (e as HTMLVideoElement).seeking)).toBe(false);
  await content.evaluate(e => (e as HTMLVideoElement).play());
  const ad = page.getByTestId('ad-video');
  await expect(ad).toBeVisible({ timeout: 15_000 });
  const capturedText = (await page.getByTestId('player-status').innerText()).match(/resume at ([\d.]+) seconds/);
  expect(capturedText).not.toBeNull();
  const capturedAt = Number(capturedText![1]);
  const resumeAt = await content.evaluate(e => (e as HTMLVideoElement).currentTime);
  // Browser media time may settle by a millisecond after pause(); compare the
  // actual captured application value, not a second rounded clock reading.
  expect(Math.abs(resumeAt - capturedAt)).toBeLessThan(0.02);
  expect(capturedAt).toBeLessThanOrEqual(slot.latest_start_sec + 0.001);
  expect(resumeAt).toBeGreaterThanOrEqual(slot.timestamp_sec);
  expect(resumeAt).toBeLessThan(slot.timestamp_sec + 1);
  expect(await content.evaluate(e => (e as HTMLVideoElement).paused)).toBe(true);
  await expect.poll(() => ad.evaluate(e => (e as HTMLVideoElement).currentTime)).toBeGreaterThan(0.3);
  // Wait for a genuine ended event; no fake event dispatch or network mocking.
  await expect(ad).toHaveCount(0, { timeout: 20_000 });
  await expect(content).toBeVisible();
  await expect.poll(() => content.evaluate(e => (e as HTMLVideoElement).paused)).toBe(false);
  const resumed = await content.evaluate(e => (e as HTMLVideoElement).currentTime);
  expect(resumed).toBeGreaterThanOrEqual(resumeAt);
  expect(resumed).toBeLessThan(resumeAt + 2);
  await expect(page.getByTestId('player-status')).toContainText(`Content resumed at ${capturedText![1]}`);
  await content.evaluate((e, timestamp) => { (e as HTMLVideoElement).currentTime = timestamp - 0.5; }, slot.timestamp_sec);
  await expect.poll(() => content.evaluate(e => (e as HTMLVideoElement).currentTime)).toBeGreaterThan(slot.timestamp_sec + 0.5);
  await expect(ad).toHaveCount(0);
  await content.evaluate(e => (e as HTMLVideoElement).pause());
  const evidence = { video_id: manifest.video.id, candidate_id: slot.candidate_id, brand_id: slot.brand_id,
    boundary_sec: slot.timestamp_sec, paused_at_sec: resumeAt, captured_resume_sec: capturedAt, resumed_at_sec: resumed,
    actual_ad_playback: true, replay_prevented: true, passed: true };
  fs.writeFileSync(path.join(path.dirname(manifestPath!), candidate ? `browser-evidence-${candidate}.json` : 'browser-evidence.json'), JSON.stringify(evidence, null, 2));
  const smokePath = path.join(path.dirname(manifestPath!), 'smoke.json');
  if (fs.existsSync(smokePath)) {
    const smoke = JSON.parse(fs.readFileSync(smokePath, 'utf8'));
    smoke.browser_verified = true;
    fs.writeFileSync(smokePath, JSON.stringify(smoke, null, 2));
  }
  await page.screenshot({ path: path.join(path.dirname(manifestPath!), candidate ? `player-${candidate}.png` : 'player.png'), fullPage: true });
});

import {test, expect} from './fixtures';
import fs from 'node:fs';

test('schedule click plays the lead-in, then replays the selected real ad and resumes', async ({page}) => {
  const file=process.env.INTERLUDE_MANIFEST;
  test.skip(!file, 'Requires a real completed manifest');
  const manifest=JSON.parse(fs.readFileSync(file!,'utf8'));
  await page.goto(`/?video=${manifest.video.id}`);
  const slot=page.locator('.schedule-item').first();
  await expect(slot).toBeVisible();
  for(let i=0;i<2;i++) {
    await slot.click();
    const content=page.getByTestId('content-video');
    await expect(content).toBeVisible();
    await expect.poll(()=>content.evaluate((v:HTMLVideoElement)=>v.currentTime)).toBeGreaterThanOrEqual(Math.max(0,manifest.ad_breaks[0].timestamp_sec-3)-0.1);
    await expect(page.getByTestId('player-status')).toContainText('Playing episode from');
    const ad=page.getByTestId('ad-video');
    await expect(ad).toBeVisible({timeout:15000});
    await expect(page.getByTestId('player-status')).toContainText(`resume at ${manifest.ad_breaks[0].timestamp_sec.toFixed(3)} seconds`);
    await expect.poll(()=>ad.evaluate((v:HTMLVideoElement)=>v.currentTime)).toBeGreaterThan(0.2);
    await expect(page.getByTestId('content-video')).toBeHidden();
    await expect(ad).toBeHidden({timeout:40000});
    await expect.poll(()=>page.getByTestId('content-video').evaluate((v:HTMLVideoElement)=>v.currentTime)).toBeGreaterThanOrEqual(manifest.ad_breaks[0].timestamp_sec);
  }
});

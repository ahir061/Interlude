import {test, expect} from './fixtures';
import fs from 'node:fs';

test('schedule click always restarts the selected real ad, including after a completed preview', async ({page}) => {
  const file=process.env.INTERLUDE_MANIFEST;
  test.skip(!file, 'Requires a real completed manifest');
  const manifest=JSON.parse(fs.readFileSync(file!,'utf8'));
  await page.goto(`/?video=${manifest.video.id}`);
  const slot=page.locator('.schedule-item').first();
  await expect(slot).toBeVisible();
  for(let i=0;i<2;i++) {
    await slot.click();
    const ad=page.getByTestId('ad-video');
    await expect(ad).toBeVisible();
    await expect.poll(()=>ad.evaluate((v:HTMLVideoElement)=>v.currentTime)).toBeGreaterThan(0.2);
    await expect(page.getByTestId('content-video')).toBeHidden();
    await expect(ad).toBeHidden({timeout:40000});
    await expect.poll(()=>page.getByTestId('content-video').evaluate((v:HTMLVideoElement)=>v.currentTime)).toBeGreaterThanOrEqual(manifest.ad_breaks[0].timestamp_sec);
  }
});

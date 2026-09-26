import { test, expect } from './fixtures';
import fs from 'node:fs';
import path from 'node:path';

test('episode workspace exposes real scene map, ranked decisions and dynamic catalogue', async ({page})=>{
  const manifestPath=process.env.INTERLUDE_MANIFEST;
  test.skip(!manifestPath,'Set a real completed manifest for workspace review.');
  const manifest=JSON.parse(fs.readFileSync(manifestPath!,'utf8'));
  await page.goto(`/?video=${manifest.video.id}`);
  await expect(page.getByRole('heading',{name:'Your episodes, intelligently placed.'})).toBeVisible();
  await expect(page.getByText('H.264 MP4 with audio',{exact:false})).toContainText('120 minutes');
  await expect(page.getByTestId('content-video')).toBeVisible();
  await expect(page.getByLabel('Semantic scene timeline')).toBeVisible();
  await page.getByRole('button',{name:'Selected',exact:true}).click();
  await expect(page.locator('tbody tr')).toHaveCount(manifest.ad_breaks.length);
  await page.locator('tbody tr').first().getByRole('button').click();
  await expect(page.getByText('CANDIDATE DETAIL',{exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'↓ VMAP'})).toHaveAttribute('href',`/api/videos/${manifest.video.id}/vmap`);
  await expect(page.locator('.episode-card').first()).toBeVisible({timeout:30000});
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:path.join(path.dirname(manifestPath!),'workspace.png'),fullPage:true});
  await page.getByRole('button',{name:/Brand catalogue/}).click();
  await expect(page.getByRole('heading',{name:'Brand catalogue',exact:true})).toBeVisible();
  await expect(page.getByText('Never place against',{exact:true}).first()).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});

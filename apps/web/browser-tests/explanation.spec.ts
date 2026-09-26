import {test,expect} from './fixtures';
import fs from 'node:fs';

test('selected brand exposes an actual Qwen explanation and its supporting evidence',async({page})=>{
  test.setTimeout(120000);
  const file=process.env.INTERLUDE_MANIFEST;
  test.skip(!file,'Requires a real completed manifest');
  const manifest=JSON.parse(fs.readFileSync(file!,'utf8'));
  await page.goto(`/?video=${manifest.video.id}`);
  await page.getByRole('button',{name:'Selected',exact:true}).click();
  await page.locator('tbody tr').first().getByRole('button').click();
  const panel=page.getByRole('region',{name:'Brand selection explanation'});
  await expect(panel.getByTestId('brand-explanation')).toBeVisible({timeout:100000});
  expect((await panel.getByTestId('brand-explanation').textContent())!.length).toBeGreaterThan(20);
  await expect(panel.getByText('Independent safety check:',{exact:false}).first()).toBeVisible();
  await panel.getByText('Supporting scene observations').click();
  await expect(panel.locator('details p').first()).toBeVisible();
});

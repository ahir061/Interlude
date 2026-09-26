import {test,expect} from '@playwright/test';

test('protected workspace signs in through the form and signs out',async ({page})=>{
  const password=process.env.INTERLUDE_WORKSPACE_PASSWORD;
  test.skip(!password,'Requires a configured protected workspace.');
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'A better place for a break.'})).toBeVisible();
  await page.getByLabel('Workspace password').fill(password!);
  await page.getByRole('button',{name:'Enter workspace'}).click();
  await expect(page.getByRole('heading',{name:'Ad breaks, intelligently placed.'})).toBeVisible();
  await page.getByRole('button',{name:'Sign out'}).click();
  await expect(page.getByLabel('Workspace password')).toBeVisible();
  const response=await page.request.get('/api/brands');
  expect(response.status()).toBe(401);
});

import {test,expect} from './fixtures';
import fs from 'node:fs';
import path from 'node:path';

test('web accepts a complete episode and cancellation fences its job',async ({page})=>{
  const request=page.request;
  const source=process.env.INTERLUDE_EPISODE_UPLOAD;
  test.skip(!source,'Set a real full-episode file to verify large web uploads.');
  test.setTimeout(180000);
  await page.goto('/');
  await page.getByLabel('Choose episode').setInputFiles(source!);
  const response=page.waitForResponse(r=>r.url().endsWith('/api/videos')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Analyze episode'}).click();
  const uploaded=await response;
  expect(uploaded.status()).toBe(202);
  const result=await uploaded.json();
  expect(result.video.duration_sec).toBeGreaterThan(300);
  await expect(page.getByText('Analysis runs in the background.',{exact:false})).toBeVisible({timeout:30000});
  await expect(page.getByRole('button',{name:'Cancel',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Cancel',exact:true}).click();
  await expect.poll(async()=> (await (await request.get(`/api/jobs/${result.job.id}`)).json()).status,{timeout:30000}).toBe('CANCELLED');
  const directory=process.env.INTERLUDE_REPORT_DIR||path.dirname(process.env.INTERLUDE_MANIFEST!);
  fs.mkdirSync(directory,{recursive:true});
  fs.writeFileSync(path.join(directory,'episode-upload.json'),JSON.stringify({video_id:result.video.id,
    job_id:result.job.id,duration_sec:result.video.duration_sec,source:path.basename(source!),
    file_bytes:fs.statSync(source!).size,upload_via_web:true,cancel_verified:true},null,2));
});

import {test as base,expect} from '@playwright/test';
export const test=base.extend<{workspaceSession:void}>({
  workspaceSession:[async ({context},use)=>{
    const request=context.request;
    const response=await request.get('/api/session');
    const session=await response.json();
    if(!session.authenticated){
      const password=process.env.INTERLUDE_WORKSPACE_PASSWORD;
      if(!password)throw new Error('Protected workspace requires INTERLUDE_WORKSPACE_PASSWORD for browser tests.');
      const login=await request.post('/api/session',{data:{password}});
      expect(login.ok()).toBe(true);
    }
    await use();
  },{auto:true}],
});
export {expect};

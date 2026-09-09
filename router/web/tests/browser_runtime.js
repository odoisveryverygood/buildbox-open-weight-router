// Run after browser_live.js against tests.gateway.browser_fixture ONLY.
// Actual product HTTP/auth/worker/provider transport, SYNTHETIC provider output.
async page => {
  const failures=[];
  page.on('pageerror',e=>failures.push(e.message));
  const base=await page.evaluate(()=>location.origin);
  const status=await (await page.request.get(base+'/api/studio/runtime')).json();
  if(status.mode!=='synthetic_test'||status.live_verified!==false)throw new Error('Explicit synthetic test composition required');
  await page.getByRole('button',{name:'1 Steps & prompts',exact:true}).click();
  await page.getByRole('textbox',{name:'Load policy history by exact version',exact:true}).fill('sample-policy@1');
  await page.getByRole('button',{name:'Load pinned version',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Saved sample-policy@1'}).waitFor();
  await page.getByRole('button',{name:'3 Routes & run',exact:true}).click();
  await page.getByRole('textbox',{name:'Named sample inputs JSON',exact:true}).fill('{"document":"   SYNTHETIC BROWSER DOCUMENT   "}');
  await page.getByRole('button',{name:'Preview executable input and prompts',exact:true}).click();
  await page.getByRole('checkbox',{name:'This sample is synthetic, contains no secrets, and I approve a new sandbox run within the displayed cap.',exact:true}).check();
  const accepted=page.waitForResponse(r=>r.url().endsWith('/api/sandbox/runs')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Run sample (new costed action)',exact:true}).click();
  const response=await accepted;
  if(response.status()!==202)throw new Error('Run not queued');
  const run=await response.json();
  if(run.status!=='queued')throw new Error('HTTP path did not use durable queue');
  let saved;
  for(let i=0;i<30;i++){
    saved=await (await page.request.get(base+'/api/sandbox/runs/'+run.id)).json();
    if(saved.status!=='queued'&&saved.status!=='running')break;
    await page.waitForTimeout(200);
  }
  if(saved.status!=='awaiting_approval')throw new Error('Expected real human pause, not fabricated completion');
  await page.getByRole('button',{name:'Load / refresh run',exact:true}).click();
  await page.getByRole('heading',{name:'Persisted result',exact:true}).waitFor();
  await page.getByRole('button',{name:/classify · attempt 1/}).click();
  await page.locator('#activity').screenshot({path:'output/playwright/7b-runtime-activity.png'});
  const attempts=await (await page.request.get(base+'/api/studio/runs/'+run.id+'/attempts')).json();
  if(attempts.length!==1||attempts[0].usage.actual_micro_usd!==0)throw new Error('Persisted synthetic accounting missing');
  if(attempts[0].trace.served_model.value!=='synthetic/test')throw new Error('Provider identity not observed');
  await page.reload();
  await page.getByRole('button',{name:'4 Activity',exact:true}).click();
  await page.getByRole('textbox',{name:'Run ID',exact:true}).fill(run.id);
  await page.getByRole('button',{name:'Load / refresh run',exact:true}).click();
  await page.getByRole('heading',{name:'Persisted result',exact:true}).waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.locator('#activity').scrollIntoViewIfNeeded();
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Runtime mobile overflow');
  await page.screenshot({path:'output/playwright/7b-runtime-mobile.png'});
  await page.setViewportSize({width:1280,height:900});
  await page.getByRole('button',{name:'3 Routes & run',exact:true}).click();
  await page.getByText('Application keys & runtime status',{exact:true}).click();
  await page.locator('#routes').screenshot({path:'output/playwright/7b-runtime-status.png'});
  if(failures.length)throw new Error('Browser errors: '+failures.join('; '));
  return {status:'PASS',run:run.id,state:saved.status,attempts:attempts.length,mode:'synthetic HTTP fixture; LIVE INFERENCE NOT VERIFIED',screenshots:3};
}

async page => {
  const origin='http://127.0.0.1:5185';
  // Public synthetic test identities, provisioned only in an isolated local DB.
  await page.context().setHTTPCredentials({username:'alice',password:'synthetic-test-password'});
  await page.goto(origin);
  await page.getByRole('button',{name:'Document extraction',exact:true}).click();
  await page.getByRole('combobox',{name:'Catalog source',exact:true}).selectOption('runtime_public');
  await page.getByRole('checkbox',{name:'Allow HTTPS public-metadata research for this version',exact:true}).check();
  const response=page.waitForResponse(r=>r.request().method()==='POST' && r.url().endsWith('/api/plans'));
  await page.getByRole('button',{name:'Save and plan',exact:true}).click();
  const created=await (await response).json();
  await page.getByRole('status').filter({hasText:'Job failed'}).waitFor();
  const path='/api/plans/'+created.plan.id+'/versions/1';
  const saved=await (await page.request.get(origin+path)).json();
  if(saved.result!==null || saved.job.status!=='failed' || JSON.stringify(saved).includes('synthetic-do-not-echo')) throw new Error('Provider failure was concealed or leaked');
  await page.reload();
  await page.getByRole('status').filter({hasText:'Job failed'}).waitFor();
  if(await page.getByRole('button',{name:'Download inactive policy'}).count()) throw new Error('Failed job offered export');
  const bob=await page.evaluate(()=> 'Basic '+btoa('bob:synthetic-test-password'));
  for(const action of ['', '/cancel','/policy']) {
    const response=action ? await page.request.post(origin+path+action,{data:{},headers:{Authorization:bob}}) : await page.request.get(origin+path,{headers:{Authorization:bob}});
    if(response.status()!==404) throw new Error('Cross-tenant resource access: '+response.status());
  }
  await page.getByRole('button',{name:'Document extraction',exact:true}).click();
  await page.getByRole('combobox',{name:'Catalog source',exact:true}).selectOption('runtime_public');
  await page.getByRole('checkbox',{name:'Allow HTTPS public-metadata research for this version',exact:true}).check();
  const pendingResponse=page.waitForResponse(r=>r.request().method()==='POST' && r.url().endsWith('/api/plans'));
  await page.getByRole('button',{name:'Save and plan',exact:true}).click();
  const pending=await (await pendingResponse).json();
  await page.getByRole('button',{name:'Cancel planning',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Job cancelled'}).waitFor();
  await page.waitForTimeout(1200);
  const cancelled=await (await page.request.get(origin+'/api/plans/'+pending.plan.id+'/versions/1')).json();
  if(cancelled.job.status!=='cancelled' || cancelled.result!==null) throw new Error('Cancelled job completed');
  return {case:'injected_provider_outage_reload_cancellation_and_shared_tenant_isolation',status:'PASS',plan:created.plan.id,authentication:'HTTP Basic / PBKDF2',provider_failure:'test-injected at provider boundary; real API/worker/storage',result:saved.job.error,cancelled_plan:pending.plan.id};
}

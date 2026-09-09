// Explicit browser transport fixtures ONLY. The actual app has no fixture fallback.
// Run after browser_live.js; existing saved plan is used only to mount the studio.
async page => {
  const base='http://127.0.0.1:5198';
  const fixturePath='/@fs/Users/aradhyamishra/Documents/ChatGPT/Buildbox-Router-V2-Studio/router/contract-fixtures/sandbox-policy-v2.json';
  const fixtureResponse=await page.request.get(base+fixturePath);
  if(!fixtureResponse.ok())throw new Error('Canonical public fixture unavailable through local Vite');
  const original=await fixtureResponse.json();
  const schema={execution_schema:'2.0'}, now=new Date().toISOString();
  const ref=id=>({...schema,id,version:1});
  const policies=['contract-stack','contract-baseline'].map(id=>({...schema,policy:{...original,id},transition:{...schema,policy:ref(id),sequence:2,status:'sandbox_enabled',admission_id:'contract-only-not-approval',actor_id:'contract-fixture',occurred_at:now,production_approved:false}}));
  const usage={...schema,reservation_id:'fixture-reservation',reserved_micro_usd:10,actual_micro_usd:4,state:'reconciled',tokens:{prompt_tokens:3,completion_tokens:2,total_tokens:5},observed_at:now};
  const run={...schema,id:'contract-run',policy:ref('contract-stack'),status:'succeeded',created_at:now,attempt_ids:['contract-attempt'],output_reference:'contract-output',quality:'untested_provisional',environment:'sandbox'};
  const output={...schema,id:'contract-output',run_id:run.id,node_id:'classify',value:'CONTRACT FIXTURE output, not a real model answer. <script>untrusted text</script>',created_at:now,expires_at:new Date(Date.now()+3600000).toISOString()};
  const sample={...schema,id:'contract-sample',kind:'sample',inputs:{document:'CONTRACT FIXTURE sample'},expected_output:null,observed_output:null,source_label:'Explicit synthetic browser contract test',original_observed_at:null,imported_at:now,data_class:'synthetic',processing:'local_only',retention_days:1,provenance:'user_imported_not_verified'};
  let submissions=0,comparison;
  const intercepted=[];
  await page.route('**/api/studio/**',async route=>{
    const path=route.request().url().replace(base,'').split('?')[0];
    let body;
    if(path.includes('/policies/'))body=policies.find(v=>path.includes('/'+v.policy.id+'/'));
    if(path==='/api/studio/imports/contract-sample')body=sample;
    if(path==='/api/studio/comparisons'&&route.request().method()==='POST'){
      const data=route.request().postDataJSON();
      if(!route.request().headers()['idempotency-key'])throw new Error('No idempotency key');
      submissions++;
      comparison={...schema,id:'contract-comparison',request:data,cells:[{...schema,sample_id:sample.id,policy:ref('contract-stack'),run_id:run.id,status:'completed',output_reference:output.id,usage},{...schema,sample_id:sample.id,policy:ref('contract-baseline'),run_id:null,status:'failed',output_reference:null,usage:null}],quality_claim:'exploratory_not_quality_validation'};
      body=comparison;
    }
    if(path==='/api/studio/comparisons/contract-comparison')body=comparison;
    if(path==='/api/studio/outputs/contract-output')body=output;
    if(!body)return route.continue();
    intercepted.push(path);
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.route('**/api/sandbox/runs/contract-run**',async route=>{
    const path=route.request().url().replace(base,'').split('?')[0];
    if(path.endsWith('/events'))return route.fulfill({status:200,contentType:'text/event-stream',body:`event: run.status\ndata: ${JSON.stringify({...schema,type:'run.status',run_id:run.id,sequence:1,run})}\n\nevent: run.usage\ndata: ${JSON.stringify({...schema,type:'run.usage',run_id:run.id,sequence:2,usage})}\n\n`});
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(path.includes('/outputs/')?output:run)});
  });
  try {
    await page.getByRole('button',{name:'2 Compare samples',exact:true}).click();
    await page.getByRole('textbox',{name:'Policy versions, one per line (policy-id@version)',exact:true}).fill('contract-stack@1\ncontract-baseline@1');
    await page.getByRole('textbox',{name:'Sample IDs, comma separated',exact:true}).fill('contract-sample');
    await page.getByRole('spinbutton',{name:'Maximum experiment cost (integer micro-USD)',exact:true}).fill('100');
    await page.getByRole('button',{name:'Inspect pinned settings',exact:true}).click();
    await page.getByText('contract-stack@1 · sandbox_enabled · 3 stages',{exact:true}).waitFor();
    await page.getByRole('checkbox',{name:'I reviewed the same samples, pinned prompts/bindings and spend cap. This starts new costed runs.',exact:true}).check();
    await page.getByRole('button',{name:'Start bounded comparison',exact:true}).click();
    await page.locator('#compare pre').filter({hasText:output.value}).waitFor();
    if(submissions!==1)throw new Error('Comparison duplicate submission');
    if(await page.locator('#compare script').count())throw new Error('Output interpreted as HTML');
    if(!(await page.locator('#compare').innerText()).includes('failed'))throw new Error('Failed cell hidden');
    await page.locator('#compare').screenshot({path:'output/playwright/lane8-CONTRACT-FIXTURE-comparison.png'});
    await page.getByRole('button',{name:'Load / refresh comparison (no execution)',exact:true}).click();
    if(submissions!==1)throw new Error('Read-only refresh executed new work');
    await page.getByRole('button',{name:'4 Activity',exact:true}).click();
    await page.getByRole('textbox',{name:'Run ID',exact:true}).fill(run.id);
    await page.getByRole('button',{name:'Load / refresh run',exact:true}).click();
    await page.locator('#activity pre').filter({hasText:output.value}).waitFor();
    await page.getByText('#2 · run.usage · reconciled · actual $0.000004',{exact:true}).waitFor();
    await page.locator('#activity').screenshot({path:'output/playwright/lane8-CONTRACT-FIXTURE-activity.png'});
    return {status:'PASS',mode:'Explicit browser transport fixtures, NOT live target inference',submissions,intercepted,screenshots:2};
  } finally {await page.unrouteAll({behavior:'wait'});}
}

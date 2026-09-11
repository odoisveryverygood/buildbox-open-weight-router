// Actual app/API/worker/HTTP transport. Explicit synthetic upstream; no live-quality claim.
async page => {
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  const base=await page.evaluate(()=>location.origin);
  const status=await (await page.request.get(base+'/api/studio/runtime')).json();
  if(status.mode!=='synthetic_test')throw new Error('Synthetic acceptance composition required');
  await page.getByRole('textbox',{name:'Workflow description',exact:true}).fill('Classify input text and return a category');
  await page.getByRole('checkbox',{name:/Propose one model/}).check();
  await page.getByRole('button',{name:'Save and plan',exact:true}).click();
  await page.getByRole('heading',{name:'Result: provisional',exact:true}).waitFor();
  async function load(name,version=1){
    await page.getByRole('button',{name:'1 Steps & prompts',exact:true}).click();
    await page.getByRole('textbox',{name:'Load policy history by exact version',exact:true}).fill(`${name}@${version}`);
    await page.getByRole('button',{name:'Load pinned version',exact:true}).click();
    await page.getByRole('status').filter({hasText:`Saved ${name}@${version}`}).waitFor();
  }
  async function enable(name,admission){
    await page.getByRole('button',{name:'3 Routes & run',exact:true}).click();
    await page.getByRole('textbox',{name:'Operator-issued admission ID',exact:true}).fill(admission);
    await page.getByRole('checkbox',{name:'I explicitly approve the requested sandbox state change for this exact version.',exact:true}).check();
    await page.getByRole('button',{name:'Enable this sandbox version',exact:true}).click();
    await page.getByRole('heading',{name:new RegExp(`${name}.*sandbox_enabled`)}).waitFor();
  }
  async function waitRun(id){
    for(let i=0;i<100;i++){
      const run=await (await page.request.get(base+'/api/sandbox/runs/'+id)).json();
      if(!['queued','running'].includes(run.status))return run;
      await page.waitForTimeout(100);
    }throw new Error('Worker did not settle');
  }
  await load('public-packet'); await enable('public-packet','public-packet-admit');
  await page.getByRole('textbox',{name:'Named sample inputs JSON',exact:true}).fill('{"key":"qwen3"}');
  await page.getByRole('button',{name:'Preview executable input and prompts',exact:true}).click();
  await page.getByRole('checkbox',{name:/This sample is synthetic, contains no secrets/}).check();
  const accepted=page.waitForResponse(r=>r.url().endsWith('/api/sandbox/runs')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Run sample (new costed action)',exact:true}).click();
  const publicRun=await (await accepted).json();
  if((await waitRun(publicRun.id)).status!=='succeeded')throw new Error('Public packet plumbing failed');
  await page.getByRole('button',{name:'Load / refresh run',exact:true}).click();
  await page.getByRole('heading',{name:'Persisted result',exact:true}).waitFor();
  await page.getByText('Persisted stage outputs (3)',{exact:true}).click();
  await page.locator('#activity').screenshot({path:'output/playwright/09-public-packet-activity.png'});
  const outputs=await (await page.request.get(base+`/api/sandbox/runs/${publicRun.id}/outputs`)).json();
  if(!JSON.stringify(outputs).includes('https://huggingface.co/api/models/Qwen/Qwen3-8B'))throw new Error('Retained source packet missing');
  for(const name of ['compare-a','compare-b']){await load(name);await enable(name,name+'-admit');}
  await page.getByRole('button',{name:'2 Compare samples',exact:true}).click();
  await page.getByRole('combobox',{name:'Sample format',exact:true}).selectOption('jsonl');
  const rows=['ok','billing'].map((category,i)=>({inputs:{input:`Synthetic receipt ${i}`},expected_output:{category},expected_reviewed:true,split:'holdout',output_schema:{type:'object',properties:{category:{type:'string'}},required:['category'],additionalProperties:false}}));
  await page.getByRole('textbox',{name:'Paste samples (64 KiB maximum)',exact:true}).fill(rows.map(r=>JSON.stringify(r)).join('\n'));
  await page.getByRole('combobox',{name:'Data class',exact:true}).selectOption('synthetic');
  await page.getByRole('combobox',{name:'Permitted processing',exact:true}).selectOption('approved_hosted');
  await page.getByRole('checkbox',{name:'I reviewed the sample and redaction choices.',exact:true}).check();
  await page.getByRole('checkbox',{name:/I consent to external processing/}).check();
  await page.getByRole('button',{name:'Review import payload',exact:true}).click();
  await page.getByRole('button',{name:'Confirm import to this workspace',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Saved sample IDs:'}).waitFor();
  await page.getByRole('textbox',{name:'Policy versions, one per line (policy-id@version)',exact:true}).fill('compare-a@1\ncompare-b@1');
  await page.getByRole('button',{name:'Inspect pinned settings',exact:true}).click();
  await page.getByText('compare-a@1 · sandbox_enabled · 1 stages',{exact:true}).waitFor();
  await page.getByRole('checkbox',{name:/I reviewed the same samples, pinned prompts/}).check();
  const comparisonResponse=page.waitForResponse(r=>r.url().endsWith('/api/studio/comparisons')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Start bounded comparison',exact:true}).click();
  const comparison=await (await comparisonResponse).json();
  for(const cell of comparison.cells)await waitRun(cell.run_id);
  await page.getByRole('button',{name:'Load / refresh comparison (no execution)',exact:true}).click();
  await page.getByRole('heading',{name:'Returned output',exact:true}).first().waitFor();
  const measured=await (await page.request.get(base+'/api/studio/comparisons/'+comparison.id)).json();
  if(measured.cells.length!==4||measured.cells.some(c=>c.status!=='completed'||c.attempt_usages.length!==1))throw new Error('Incomplete comparison/attempt accounting');
  if(measured.cells.filter(c=>c.checks.some(k=>k.check==='reviewed_exact_match'&&k.status==='fail')).length!==2)throw new Error('Expected semantic failures were hidden');
  await page.locator('#compare').screenshot({path:'output/playwright/09-comparison.png'});
  await load('compare-b');
  await page.getByText('Change a model pin, exclude configurations, or make one stage cheaper',{exact:true}).click();
  await page.getByRole('textbox',{name:'Targeted edit instruction',exact:true}).fill('make respond cheaper');
  await page.getByRole('button',{name:'Propose server-validated edit',exact:true}).click();
  await page.getByRole('button',{name:'Confirm and save executable draft',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Saved compare-b@2'}).waitFor();
  await page.getByRole('button',{name:'3 Routes & run',exact:true}).click();
  await page.getByRole('textbox',{name:'Operator-issued admission ID',exact:true}).fill('compare-b-admit');
  await page.getByRole('checkbox',{name:/I explicitly approve the requested sandbox state/}).check();
  const denied=page.waitForResponse(r=>r.url().includes('/transitions')&&r.status()===403);
  await page.getByRole('button',{name:'Enable this sandbox version',exact:true}).click();await denied;
  await enable('compare-b','compare-b-v2-admit');
  const old=await (await page.request.get(base+'/api/studio/policies/compare-b/versions/1')).json();
  if(old.transition.status!=='sandbox_enabled'||old.policy.stages[0].configuration_id!=='fixture-medium-local')throw new Error('Old version was silently changed');
  await page.reload();
  await page.getByRole('status').filter({hasText:'Saved compare-b@2'}).waitFor();
  await page.getByRole('button',{name:'3 Routes & run',exact:true}).click();
  await page.getByText('Single-stage API alias',{exact:true}).click();
  await page.getByRole('textbox',{name:'Alias ID',exact:true}).fill('compare-b-v2-alias');
  await page.getByRole('combobox',{name:'LLM stage',exact:true}).selectOption('respond');
  await page.getByRole('button',{name:'Create immutable alias',exact:true}).click();
  await page.getByRole('combobox',{name:'Example language',exact:true}).waitFor();
  await page.getByRole('combobox',{name:'Example language',exact:true}).selectOption('typescript');
  await page.locator('#routes').screenshot({path:'output/playwright/09-routes-api.png'});
  await page.getByText('Application keys & runtime status',{exact:true}).click();
  await page.getByRole('textbox',{name:'Allowed saved alias',exact:true}).fill('compare-b-v2-alias');
  const issuance=page.waitForResponse(r=>r.url().endsWith('/api/studio/keys')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Issue scoped application key',exact:true}).click();
  const issued=await (await issuance).json();
  await page.getByRole('button',{name:'Hide key permanently',exact:true}).click();
  await page.locator('li').filter({hasText:issued.metadata.prefix}).getByRole('button',{name:'Revoke',exact:true}).click();
  await page.locator('li').filter({hasText:issued.metadata.prefix}).getByText(/revoked/).waitFor();
  await page.getByRole('button',{name:'4 Activity',exact:true}).click();
  await page.getByText('Aggregated model-attempt usage (chat and workflows)',{exact:true}).click();
  await page.getByRole('button',{name:'Refresh usage without running',exact:true}).click();
  await page.getByText(/6 attempts · known subtotal/).waitFor();
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Mobile overflow');
  await page.locator('#activity').scrollIntoViewIfNeeded();
  await page.screenshot({path:'output/playwright/09-mobile.png'});
  await page.setViewportSize({width:1280,height:900});
  if(errors.length)throw new Error(errors.join(';'));
  return {status:'PASS',public_packet_run:publicRun.id,comparison:comparison.id,cells:4,sample_count:2,expected_exact_match_failures:2,attempts:6,reload:true,stale_admission_rejected:true,old_version_preserved:true,keys:'issued, hidden and revoked',live_provider:false};
}

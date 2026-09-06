async page => {
  const origin = page.url().split('/').slice(0,3).join('/');
  const results = [];
  const assert = (value, message) => { if (!value) throw new Error(message); };
  async function saved(view) {
    const path = '/api/plans/'+view.plan.id+'/versions/'+view.plan.version;
    for (let count=0; count<40; count++) {
      const response = await page.request.get(origin+path);
      const value = await response.json();
      if (['succeeded','failed','cancelled','uncertain'].includes(value.job.status)) {
        await page.getByRole('status').filter({hasText:'Job '+value.job.status}).waitFor();
        return value;
      }
      await page.waitForTimeout(750);
    }
    throw new Error('Persisted job did not finish within bounded browser wait');
  }
  async function save(revision=false) {
    const responsePromise = page.waitForResponse(r => r.request().method()==='POST' && r.url().includes('/api/plans'));
    await page.getByRole('button',{name:revision?'Save changed constraints / answers as new version':'Save and plan',exact:true}).click();
    const response = await responsePromise;
    assert(response.status()===201,'Submission failed: '+response.status());
    return saved(await response.json());
  }
  async function start(name) { await page.getByRole('button',{name,exact:true}).click(); }
  await page.goto(origin);
  await page.evaluate(() => { for (const key of Object.keys(sessionStorage)) if (key.startsWith('request-')) sessionStorage.removeItem(key); });
  await start('Document extraction');
  let value = await save();
  assert(value.result.recommendation.assignments[0].node_id==='extract','Extraction mapped wrong stage');
  assert(value.result.workflow.nodes[0].kind==='code','Code stage lost');
  const firstId=value.plan.id;
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'Download inactive policy'}).click();
  const download=await downloadPromise;
  await download.saveAs('output/playwright/extraction-inactive-policy.json');
  const policy=await (await page.request.post(origin+'/api/plans/'+firstId+'/versions/1/policy',{data:{}})).json();
  assert(policy.active===false && policy.production_write===false && policy.execution_tools.length===0,'Unsafe policy');
  results.push({case:'extraction_and_policy',status:'PASS',plan:firstId});
  await page.getByRole('textbox',{name:'Preserved answer / correction note',exact:true}).fill('Corrected: keep the target cost at zero.');
  await page.getByRole('spinbutton',{name:'Target cost ceiling / 1k tokens',exact:true}).fill('0');
  assert(await page.getByRole('button',{name:'Download inactive policy'}).isDisabled(),'Unsaved changed constraints allowed old export');
  value=await save(true);
  assert(value.plan.version===2 && value.result.recommendation.workflow_version===2,'Exact version mismatch');
  assert(value.plan.input.answers[0].answer.includes('Corrected'),'Answer not preserved');
  await page.reload();
  await page.getByRole('status').filter({hasText:'Version 2'}).waitFor();
  assert((await page.getByRole('textbox',{name:'Preserved answer / correction note',exact:true}).inputValue()).includes('Corrected'),'Reload lost answer');
  await page.goto(origin+'/?plan='+firstId+'&version=1');
  await page.getByText('Stale version.',{exact:false}).waitFor();
  assert(await page.getByRole('button',{name:'Download inactive policy'}).isDisabled(),'Stale export enabled');
  const denied=await page.request.post(origin+'/api/plans/'+firstId+'/versions/1/policy',{data:{}});
  assert(denied.status()===409,'Server allowed stale policy');
  results.push({case:'correction_reload_staleness',status:'PASS'});
  await start('Support and tool workflow');
  value=await save();
  assert(value.result.workflow.nodes.some(n=>n.kind==='tool' && n.tool_id==='knowledge'),'Declared tool missing');
  assert(value.result.recommendation.assignments.length===2,'Support assignments wrong');
  results.push({case:'support_tool',status:'PASS'});
  await start('Company research');
  value=await save();
  assert(value.result.status==='blocked' && value.result.workflow.nodes[0].max_iterations===2,'Bounded research/missing evidence not represented');
  results.push({case:'company_research_bounded_missing_evidence',status:'PASS'});
  await start('Document extraction');
  await page.getByRole('combobox',{name:'Input modality',exact:true}).selectOption('image');
  value=await save();
  assert(value.result.status==='blocked' && value.result.missing_facts.some(x=>x.includes('Image')),'Image requirement ignored');
  results.push({case:'image_requirement',status:'PASS'});
  await start('Document extraction');
  await page.getByRole('combobox',{name:'Target deployment',exact:true}).selectOption('self_hosted');
  value=await save();
  assert(value.result.status==='blocked' && value.result.missing_facts.some(x=>x.includes('Self-hosted')),'Self-host requirement ignored');
  results.push({case:'self_hosted_requirement',status:'PASS'});
  await start('Document extraction');
  await page.getByRole('textbox',{name:'Workflow description',exact:true}).fill('Classify input text, return output. No external processing.');
  await page.getByRole('combobox',{name:'Catalog source',exact:true}).selectOption('runtime_public');
  await page.getByRole('checkbox',{name:'Allow HTTPS public-metadata research for this version',exact:true}).check();
  value=await save();
  assert(value.job.status==='failed' && value.result===null,'Strict egress did not fail closed');
  results.push({case:'strict_egress',status:'PASS'});
  await start('Document extraction');
  await page.getByRole('textbox',{name:'Workflow description',exact:true}).fill('lowercase text');
  value=await save();
  assert(value.result.status==='deterministic' && value.result.recommendation.assignments.length===0,'Deterministic workflow called model');
  results.push({case:'deterministic_no_model',status:'PASS'});
  await start('Document extraction');
  await page.getByRole('combobox',{name:'Catalog source',exact:true}).selectOption('public_snapshot');
  value=await save();
  assert(value.result.status==='blocked' && !value.result.catalog.synthetic && value.result.research.artifacts.length===8,'Retained evidence was not integrated or became false eligibility');
  results.push({case:'retained_public_snapshot_missing_configuration',status:'PASS'});
  // This final case is deliberately live: one fixed public metadata fetch, zero paid spend.
  await start('Document extraction');
  await page.getByRole('combobox',{name:'Catalog source',exact:true}).selectOption('runtime_public');
  await page.getByRole('checkbox',{name:'Allow HTTPS public-metadata research for this version',exact:true}).check();
  value=await save();
  assert(value.job.status==='succeeded','Actual runtime public research failed; inspect saved job '+value.plan.id);
  assert(value.result.research.sources.length===1 && value.result.research.sources[0].synthetic===false,'No actual public source retained');
  assert(value.result.status==='blocked' && value.result.catalog.configurations.length===0,'Metadata incorrectly became verified configuration');
  results.push({case:'live_runtime_public_research',status:'PASS',plan:value.plan.id,source:value.result.research.sources[0].url,observed_at:value.result.research.sources[0].observed_at,paid_spend_usd:0});
  return results;
}

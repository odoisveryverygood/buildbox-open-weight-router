async page => {
  const origin=page.url().split('/').slice(0,3).join('/');
  await page.goto(origin);
  await page.getByRole('button',{name:'Document extraction',exact:true}).click();
  await page.getByRole('textbox',{name:'Workflow description',exact:true}).fill('Use an LLM to classify input text as positive or negative sentiment and return a label.');
  await page.getByRole('combobox',{name:'Interpretation processing',exact:true}).selectOption('local_model');
  await page.getByRole('combobox',{name:'Catalog source',exact:true}).selectOption('runtime_public');
  await page.getByRole('checkbox',{name:'Allow HTTPS public-metadata research for this version',exact:true}).check();
  const response=page.waitForResponse(r=>r.request().method()==='POST' && r.url().endsWith('/api/plans'));
  await page.getByRole('button',{name:'Save and plan',exact:true}).click();
  const created=await (await response).json();
  for(let count=0;count<80;count++) {
    const value=await (await page.request.get(origin+'/api/plans/'+created.plan.id+'/versions/1')).json();
    if(['failed','uncertain'].includes(value.job.status)) throw new Error(JSON.stringify({plan:value.plan.id,phase:value.job.phase,error:value.job.error}));
    if(value.job.status==='succeeded') {
      if(value.job.served_configuration.provider!=='ollama-loopback' || value.job.served_configuration.eval_count<1) throw new Error('No actual local inference usage');
      if(!value.result.workflow.nodes.some(n=>n.kind==='llm') || value.result.workflow.provenance.kind!=='inference') throw new Error('Wrong interpreted graph');
      if(!value.result.research || value.result.research.synthetic || value.result.recommendation!==null) throw new Error('Metadata became target configuration or source missing');
      return {case:'real_runtime_interpretation_and_public_research',status:'PASS',plan:value.plan.id,version:1,processing:value.plan.input.processing,served:value.job.served_configuration,workflow:value.result.workflow,source:value.result.research.sources.map(x=>({url:x.url,observed_at:x.observed_at})),result:value.result.status};
    }
    await page.waitForTimeout(750);
  }
  throw new Error('Runtime job timed out');
}

// Actual integrated UI/API/worker; model facts and responses are synthetic.
async page => {
  const base=await page.evaluate(()=>location.origin);
  const basic=await page.evaluate(()=>btoa('fixture:synthetic-test-password'));
  await page.context().setExtraHTTPHeaders({});
  await page.route('**/api/**',r=>r.continue({headers:{...r.request().headers(),Authorization:'Basic '+basic}}));
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/?intelligence=1');
  const titles=['D · Long context','E · Privacy','F · Hard budget','G · Specialist stages','H · Validation escalation','I · Deployment health','K · Generate → Verify → Repair'];
  const results=[];
  for(const title of titles){
    await page.getByRole('button',{name:title,exact:true}).click();
    await page.getByRole('status').filter({hasText:'Loaded pinned synthetic scenario'}).waitFor();
    const trace=JSON.parse(await page.getByText('Complete decision trace and evidence',{exact:true}).locator('..').locator('pre').textContent());
    if(trace.activation_authority!==false||trace.stages.some(s=>s.confidence!=='low'))throw new Error('Synthetic evidence overstated');
    if(title.startsWith('D')&&trace.stages[0].selected==='advanced-small-loopback')throw new Error('Context gate bypassed');
    if(title.startsWith('E')&&trace.stages[0].selected!=='advanced-small-loopback')throw new Error('Privacy gate bypassed');
    if(title.startsWith('F')&&trace.projected_cost_micro_usd>trace.profile.max_cost_micro_usd)throw new Error('Budget gate bypassed');
    if(title.startsWith('G')&&new Set(trace.stages.map(s=>s.selected)).size!==2)throw new Error('Stage optimization missing');
    if(title.startsWith('I')&&trace.stages[0].selected!=='health-equivalent-loopback')throw new Error('Health gate bypassed');
    await page.getByRole('checkbox',{name:'I reviewed the inputs and approve this exact sandbox execution.',exact:true}).check();
    await page.getByRole('button',{name:'Enable sandbox & run',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Workflow succeeded'}).waitFor();
    if(title.startsWith('H')&&!(await page.getByText(/required_terms: fail/).count()))throw new Error('Failed validation hidden');
    if(title.startsWith('K')){
      await page.getByText(/repair after quality_validation/).waitFor();
      await page.getByText(/2 attempts · 1 repairs · 0 fallbacks/).waitFor();
      if(!(await page.getByText(/required_terms: fail/).count())||!(await page.getByText(/required_terms: pass/).count()))throw new Error('Repair validation trace hidden');
      if(!(await page.getByText(/Incomplete synthetic first result/).count()))throw new Error('Original output not retained');
      await page.getByRole('button',{name:'Save explicit rating',exact:true}).click();
      await page.getByText(/rating 3/).waitFor();
    }
    results.push({scenario:title,status:'succeeded',pins:trace.stages.map(s=>s.selected)});
  }
  // Repeating H must again show two accounted attempts rather than a one-shot trick.
  await page.getByRole('button',{name:'H · Validation escalation',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Loaded pinned synthetic scenario'}).waitFor();
  await page.getByRole('checkbox',{name:'I reviewed the inputs and approve this exact sandbox execution.',exact:true}).check();
  await page.getByRole('button',{name:'Enable sandbox & run',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Workflow succeeded'}).waitFor();
  if(!(await page.getByText(/required_terms: fail/).count()))throw new Error('Repeat escalation missing');
  await page.getByRole('button',{name:'J · Policy what-if',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Loaded pinned synthetic scenario'}).waitFor();
  await page.getByRole('button',{name:'Prioritize quality',exact:true}).click();
  await page.getByRole('status').filter({hasText:'What-if saved separately'}).waitFor();
  await page.getByText(/Original: advanced-small-loopback. What-if: advanced-medium-loopback/).waitFor();
  await page.getByRole('button',{name:'Prepare executable draft',exact:true}).click();
  await page.getByRole('status').filter({hasText:'New exact-version admission is required'}).waitFor();
  if(await page.getByRole('textbox',{name:'Operator-issued exact-version admission',exact:true}).inputValue())throw new Error('Stale admission reused');
  await page.getByRole('button',{name:'Evaluate shadow policy',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Decision-only policy comparison saved'}).waitFor();
  const saved=await page.evaluate(()=>new URL(location.href).searchParams.get('decision'));
  await page.reload();
  await page.getByRole('heading',{name:/respond → advanced-medium-loopback/}).waitFor();
  if(!(await page.getByRole('textbox',{name:'Workload',exact:true}).inputValue()))throw new Error('Saved workload objective missing after reload');
  if(await page.evaluate(()=>new URL(location.href).searchParams.get('decision'))!==saved)throw new Error('Decision reload lost pin');
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Advanced mobile overflow');
  await page.setViewportSize({width:1440,height:1000});
  if(errors.length)throw new Error(errors.join(';'));
  return {status:'PASS',scenarios:results,what_if:'speed to quality; new admission required',decision_reload:true,repeat_escalation:true,model_quality_verified:false};
}

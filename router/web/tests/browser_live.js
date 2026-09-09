// Run with the Playwright CLI on Lane 8's loopback app. Synthetic/local persistence
// only: no target runtime, public network lookup, provider or research charge.
async page => {
  const failures=[];
  page.on('pageerror',e=>failures.push(e.message));
  const base=await page.evaluate(()=>location.origin);
  if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(base))throw new Error('Loopback test app required');
  await page.goto(base);
  await page.getByRole('textbox',{name:'Workflow description',exact:true}).fill('lowercase text');
  await page.getByRole('button',{name:'Save and plan',exact:true}).click();
  await page.getByRole('heading',{name:'Result: deterministic',exact:true}).waitFor();
  await page.getByRole('button',{name:'Propose sandbox-compatible text bindings',exact:true}).click();
  await page.getByRole('button',{name:'Confirm new plan version',exact:true}).click();
  await page.waitForURL(/version=2/);
  await page.getByRole('heading',{name:'Result: deterministic',exact:true}).waitFor();
  await page.getByRole('button',{name:'Prepare executable draft',exact:true}).click();
  await page.getByRole('combobox',{name:'Approved deterministic operation',exact:true}).selectOption('text.lowercase.v1');
  await page.getByRole('button',{name:'Review executable draft diff',exact:true}).click();
  await page.getByRole('button',{name:'Confirm and save executable draft',exact:true}).click();
  await page.getByRole('button',{name:'Propose next draft version',exact:true}).waitFor();
  const savedUrl=page.url();
  const savedPolicy=await page.evaluate(()=>new URLSearchParams(location.search).get('policy'));
  if(!savedPolicy)throw new Error('Saved policy reference missing');
  await page.reload();
  await page.getByRole('button',{name:'Propose next draft version',exact:true}).waitFor();
  await page.getByRole('button',{name:'3 Routes & run',exact:true}).click();
  await page.getByRole('textbox',{name:'Named sample inputs JSON',exact:true}).fill('{"text":"SYNTHETIC INPUT"}');
  await page.getByRole('button',{name:'Preview executable input and prompts',exact:true}).click();
  if(await page.getByRole('button',{name:'Run sample (new costed action)',exact:true}).isEnabled())throw new Error('Draft unexpectedly runnable');
  await page.getByRole('checkbox',{name:'I explicitly approve the requested sandbox state change for this exact version.',exact:true}).check();
  await page.getByRole('button',{name:'Disable this version',exact:true}).click();
  await page.getByRole('heading',{name:new RegExp(savedPolicy.replace('@1','@1')+' · disabled')}).waitFor();
  await page.locator('#routes').screenshot({path:'output/playwright/lane8-real-routes-blocked.png'});
  await page.getByRole('button',{name:'2 Compare samples',exact:true}).click();
  await page.getByRole('combobox',{name:'Data class',exact:true}).selectOption('synthetic');
  await page.getByRole('textbox',{name:'Paste samples (64 KiB maximum)',exact:true}).fill('A SYNTHETIC representative request.');
  await page.getByRole('checkbox',{name:'I reviewed the sample and redaction choices.',exact:true}).check();
  await page.getByRole('button',{name:'Review import payload',exact:true}).click();
  const importResponse=page.waitForResponse(r=>r.url().endsWith('/api/studio/imports')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Confirm import to this workspace',exact:true}).click();
  const imported=await (await importResponse).json();
  if(imported.inputs.text!=='A SYNTHETIC representative request.'||imported.expected_output!==null)throw new Error('Import mismatch');
  if(!(await page.request.get(base+'/api/studio/imports/'+imported.id)).ok())throw new Error('Import not persisted');
  await page.getByRole('textbox',{name:'Open persisted comparison ID',exact:true}).fill('uninstalled-runtime');
  await page.getByRole('button',{name:'Load / refresh comparison (no execution)',exact:true}).click();
  const runtimeStatus=await (await page.request.get(base+'/api/studio/runtime')).json();
  await page.getByRole('alert').filter({hasText:runtimeStatus.installed?'Sandbox resource not found':'Sandbox runtime port not installed'}).waitFor();
  await page.locator('#compare').screenshot({path:'output/playwright/lane8-real-comparison-blocked.png'});
  // Load a retained public snapshot. No public_research opt-in or runtime fetch.
  await page.getByRole('button',{name:'Document extraction',exact:true}).click();
  await page.getByRole('combobox',{name:'Catalog source',exact:true}).selectOption('public_snapshot');
  await page.getByRole('button',{name:'Save and plan',exact:true}).click();
  await page.getByRole('heading',{name:'Model explorer',exact:true}).waitFor();
  await page.getByRole('heading',{name:'Qwen3-8B',exact:false}).first().waitFor();
  await page.getByRole('textbox',{name:'Search models',exact:true}).fill('Qwen3-8B');
  await page.locator('#explorer').screenshot({path:'output/playwright/lane8-public-evidence.png'});
  // New planning version must not mutate the disabled policy pin.
  const [id,version]=savedPolicy.split('@');
  const persisted=await (await page.request.get(`${base}/api/studio/policies/${id}/versions/${version}`)).json();
  if(persisted.transition.status!=='disabled'||persisted.policy.plan.version!==2)throw new Error('Old policy pin changed');
  await page.setViewportSize({width:390,height:844});
  await page.locator('#execution-studio').scrollIntoViewIfNeeded();
  if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth))throw new Error('Mobile horizontal overflow');
  await page.screenshot({path:'output/playwright/lane8-mobile.png'});
  await page.setViewportSize({width:1280,height:900});
  if(failures.length)throw new Error('Browser exceptions: '+failures.join('; '));
  return {status:'PASS',mode:'real local persistence, no runtime execution',policy:savedPolicy,importId:imported.id,url:page.url(),savedUrl,screenshots:4};
}

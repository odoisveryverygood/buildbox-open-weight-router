// Use Playwright CLI run-code --filename, against a fresh make demo instance.
// The test-only Basic identity is public; never capture application-key responses.
async page => {
  const basic=await page.evaluate(()=>btoa('fixture:synthetic-test-password'));
  await page.context().setExtraHTTPHeaders({});
  await page.route('**/api/**',route=>route.continue({headers:{...route.request().headers(),Authorization:'Basic '+basic}}));
  await page.goto('http://127.0.0.1:5202/?demo=1');
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Run workflow',exact:true}).waitFor();
  await page.screenshot({path:'output/playwright/demo-artifacts/01-main.png'});
  await page.getByText('Alternatives considered',{exact:true}).click();
  await page.locator('#demo-decision').screenshot({path:'output/playwright/demo-artifacts/02-routing.png'});
  async function click(name){await page.getByRole('button',{name,exact:true}).click();}
  async function status(text){await page.getByRole('status').filter({hasText:text}).waitFor();await page.getByRole('button',{name:'Run workflow',exact:true}).waitFor({state:'visible'});}
  await click('Run workflow');await status('Workflow succeeded');
  await page.getByRole('button',{name:'Stream stage output',exact:true}).waitFor({state:'visible'});
  await click('Stream stage output');await status('Stream completed and persisted');
  await page.locator('#demo-run').screenshot({path:'output/playwright/demo-artifacts/03-stream.png'});
  await click('Compare alternate route');await status('Comparison complete');
  if(await page.locator('#demo-comparison article').count()!==2)throw new Error('Expected two actual comparison cells');
  await page.locator('#demo-comparison').screenshot({path:'output/playwright/demo-artifacts/04-comparison.png'});
  await click('B · Complex review');
  await click('Run workflow');await status('Workflow succeeded');
  await click('C · Tools + JSON');
  await click('Stream stage output');await status('Read-only tool requested');
  await click('Approve read-only lookup');await status('Structured reply validated');
  const json=JSON.parse(await page.locator('.demo-output').innerText());
  if(json.category!=='shipping')throw new Error('Structured output not preserved');
  await page.locator('#demo-run').screenshot({path:'output/playwright/demo-artifacts/05-tools-json.png'});
  await click('A · Everyday summary');
  await click('Demonstrate safe fallback');await status('Stream completed and persisted');
  await page.locator('#demo-run').screenshot({path:'output/playwright/demo-artifacts/06-fallback.png'});
  await click('Refresh recorded usage');
  await page.locator('#demo-accounting').screenshot({path:'output/playwright/demo-artifacts/07-accounting.png'});
  const response=await page.request.get('http://127.0.0.1:5202/api/studio/usage',{headers:{Authorization:'Basic '+basic}});
  const usage=await response.json();
  const fallback=usage.attempts.filter(a=>a.trace.policy.id==='demo-fallback');
  if(fallback.length!==2||fallback.filter(a=>a.status==='succeeded').length!==1)throw new Error('Fallback attempts not accurately recorded');
  if(fallback.some(a=>a.status!=='succeeded'&&a.usage.actual_micro_usd!==null))throw new Error('Unknown failed-attempt charge was fabricated');
  await page.reload();await page.getByRole('button',{name:'Load last saved result',exact:true}).waitFor();
  await click('Load last saved result');await status('Loaded persisted stream result');
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Mobile horizontal overflow');
  await page.screenshot({path:'output/playwright/demo-artifacts/08-mobile.png'});
  await page.setViewportSize({width:1440,height:1000});
  if(errors.length)throw new Error(errors.join(';'));
  return {status:'PASS',scenarios:3,comparison_cells:2,attempts:usage.attempts.length,fallback_attempts:2,stream_reload:true,tool_result_id:'call-demo-shipping',live_inference:false};
}

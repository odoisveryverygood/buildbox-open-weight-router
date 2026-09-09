import { useState } from 'react';
import { request } from './api';
import { budget, identifier, money, parseRef, policyPath, ref, refKey, type S } from './model';
export default function Comparison({samples, current}: {samples:S['ImportedSample'][]; current?:S['PolicyView']}) {
  const [references,setReferences]=useState(''), [sampleIds,setSampleIds]=useState(''), [cap,setCap]=useState(0), [confirmed,setConfirmed]=useState(false);
  const [views,setViews]=useState<S['PolicyView'][]>([]), [result,setResult]=useState<S['ComparisonResult']>(), [outputs,setOutputs]=useState<Record<string,S['StoredOutput']>>({}), [errors,setErrors]=useState<Record<string,string>>({});
  const [error,setError]=useState(''), [busy,setBusy]=useState(false), [lookup,setLookup]=useState('');
  async function act(work:()=>Promise<void>) {setBusy(true);setError('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function display(value:S['ComparisonResult']) {
    setResult(value); setLookup(value.id); setOutputs({}); setErrors({});
    await Promise.all(value.cells.map(async cell=>{if (!cell.output_reference)return;try {const output=await request<S['StoredOutput']>(`/api/studio/outputs/${cell.output_reference}`);if(output.run_id!==cell.run_id)throw new Error('Output/run identity mismatch');setOutputs(old=>({...old,[cell.output_reference!]:output}));}catch(e){setErrors(old=>({...old,[cell.output_reference!]:String(e)}));}}));
  }
  return <section id="compare"><h2>Compare the same samples</h2><p>Compare 2–3 exact policy versions. For a single-model baseline, supply a separately saved one-LLM policy with equivalent input/output bindings. The server verifies eligibility and admission; the browser never chooses a provider directly.</p>
    <p className="notice">Comparison execution currently requires sandbox-enabled policies in the frozen API. You can prepare the experiment before enabling, but cannot execute it until admission. This is a contract limitation—not a requirement to prove quality before testing.</p>
    <fieldset disabled={busy}><label>Policy versions, one per line (policy-id@version)<textarea rows={3} value={references} placeholder={current ? `${refKey(current.policy)}\nbaseline-policy@1` : 'stack-policy@1\nbaseline-policy@1'} onChange={e=>{setReferences(e.target.value);setViews([]);setConfirmed(false);}} /></label>
    <label>Sample IDs, comma separated<input value={sampleIds} placeholder={samples.map(s=>s.id).join(', ') || 'Import samples above or paste their saved IDs'} onChange={e=>{setSampleIds(e.target.value);setConfirmed(false);}} /></label>
    <label>Maximum experiment cost (integer micro-USD)<input type="number" min="0" max="1000000" step="1" value={cap} onChange={e=>{setCap(Number(e.target.value));setConfirmed(false);}} /></label>
    <button className="secondary" onClick={()=>void act(async()=>{const refs=references.trim().split('\n').map(parseRef);if(refs.length<2||refs.length>3||new Set(refs.map(refKey)).size!==refs.length)throw new Error('Choose 2–3 distinct exact policies.');setViews(await Promise.all(refs.map(r=>request<S['PolicyView']>(policyPath(r)))));})}>Inspect pinned settings</button>
    {views.map(v=><details key={refKey(v.policy)} open><summary>{refKey(v.policy)} · {v.transition.status} · {v.policy.stages.length} stages</summary><p>Models: {v.policy.stages.flatMap(s=>s.configuration_id?[`${s.node_id}: ${s.configuration_id}`]:[]).join(', ')||'None'}</p><pre>{JSON.stringify({prompts:v.policy.prompts,stages:v.policy.stages,budget:v.policy.budget},null,2)}</pre></details>)}
    <label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} />I reviewed the same samples, pinned prompts/bindings and spend cap. This starts new costed runs.</label>
    <button disabled={!confirmed||views.length<2||views.some(v=>v.transition.status!=='sandbox_enabled')} onClick={()=>void act(async()=>{
      const ids=(sampleIds.trim()?sampleIds.split(',').map(x=>x.trim()):samples.map(x=>x.id));
      if(!ids.length||ids.length>20||ids.some(id=>!identifier.test(id))||new Set(ids).size!==ids.length)throw new Error('Choose 1–20 distinct saved sample IDs.');
      if(!Number.isSafeInteger(cap)||cap<0||cap>1000000)throw new Error('Cost cap must be 0–1,000,000 micro-USD.');
      const imported=await Promise.all(ids.map(id=>request<S['ImportedSample']>(`/api/studio/imports/${id}`)));
      if(imported.some(s=>s.processing==='approved_hosted')&&!confirmed)throw new Error('External sample processing needs confirmation.');
      const value:S['ComparisonRequest']={execution_schema:'2.0',sample_ids:ids,policies:views.map(v=>ref(v.policy.id,v.policy.version)),budget:{...budget(20,20),max_cost_micro_usd:cap}};
      setConfirmed(false);await display(await request<S['ComparisonResult']>('/api/studio/comparisons',value,crypto.randomUUID()));
    })}>Start bounded comparison</button></fieldset>
    {views.some(v=>v.transition.status!=='sandbox_enabled')&&<p>Blocked: enable these exact versions after operator admission in Routes. No results have been invented.</p>}
    <div className="form-grid"><label>Open persisted comparison ID<input value={lookup} onChange={e=>setLookup(e.target.value)} /></label><button className="secondary" disabled={busy||!identifier.test(lookup)} onClick={()=>void act(async()=>display(await request<S['ComparisonResult']>(`/api/studio/comparisons/${lookup}`)))}>Load / refresh comparison (no execution)</button></div>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<><p role="status">Experiment {result.id} · {result.request.sample_ids.length} samples · exploratory, not quality validation. No automatic winner.</p><div className="comparison-grid">{result.cells.map((cell,i)=><article className="model-card" key={i}><h3>{refKey(cell.policy)}</h3><p>Sample {cell.sample_id} · <strong>{cell.status}</strong></p><p>Reserved {money(cell.usage?.reserved_micro_usd)} · actual {money(cell.usage?.actual_micro_usd)} · {cell.usage?.state??'No usage report'}</p><p>Tokens: {cell.usage?.tokens?.total_tokens??'Unknown'}</p><p>Time to first content / completion time: not exposed by the current comparison contract.</p>{cell.output_reference&&outputs[cell.output_reference]?<><h4>Returned output</h4><pre>{JSON.stringify(outputs[cell.output_reference].value,null,2)}</pre><p>Persisted output loaded; not a rubric score. Sample size alone does not establish quality.</p></>:<p>{cell.output_reference?errors[cell.output_reference]??'Loading persisted output…':'No returned output. Failed/blocked cells remain visible.'}</p>}</article>)}</div></>}
  </section>;
}

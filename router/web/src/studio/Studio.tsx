import { useEffect, useState } from 'react';
import { request } from './api';
import { diff, draftPolicy, editableShape, parseRef, policyPath, ref, refKey, type S } from './model';
import Imports from './Imports';
import Comparison from './Comparison';
import Routes from './Routes';
import Activity from './Activity';

export default function Studio({view, dirty}: {view:S['PlanView']; dirty:boolean}) {
  const [tab,setTab]=useState('steps'),[draft,setDraft]=useState<S['ExecutablePolicy']>(),[saved,setSaved]=useState<S['PolicyView']>();
  const [lookup,setLookup]=useState(new URLSearchParams(location.search).get('policy')??''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[review,setReview]=useState(false);
  const [samples,setSamples]=useState<S['ImportedSample'][]>([]),[runId,setRunId]=useState<string>();
  async function act(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  function accept(value:S['PolicyView']){setSaved(value);setLookup(refKey(value.policy));const q=new URLSearchParams(location.search);q.set('policy',refKey(value.policy));history.replaceState(null,'',`?${q}`);}
  useEffect(()=>{
    const selected=new URLSearchParams(location.search).get('policy');
    if(!selected)return;
    let disposed=false;
    void (async()=>{try{const value=await request<S['PolicyView']>(policyPath(parseRef(selected)));if(!disposed)setSaved(value);}catch(e){if(!disposed)setError(String(e));}})();
    return()=>{disposed=true;};
  },[]);
  function update(value:S['ExecutablePolicy']){setDraft({...value,quality:'untested_provisional',production_approved:false});setReview(false);}
  const canDraft=!!view.result?.workflow&&!dirty&&!view.stale;
  return <section className="studio"><div className="section-head"><h2>Workflow studio</h2><span className="badge">Sandbox only · quality provisional</span></div>
    <nav className="journey" aria-label="Studio journey">{[['steps','1 Steps & prompts'],['compare','2 Compare samples'],['routes','3 Routes & run'],['activity','4 Activity']].map(([id,label])=><button key={id} aria-pressed={tab===id} className={tab===id?'':'secondary'} onClick={()=>setTab(id)}>{label}</button>)}</nav>
    {error&&<p role="alert" className="error">{error}</p>}
    {tab==='steps'&&<><p>Compile only a saved workflow. Proposed prompts and text types below are editable defaults for review, not discovered requirements. Incomplete bindings must be corrected in the planner; unsupported stages stay blocked.</p>
      <div className="actions"><button disabled={!canDraft||busy} onClick={()=>{try{setDraft(draftPolicy(view));setReview(false);setError('');}catch(e){setError(String(e));}}}>Prepare executable draft</button></div>
      {dirty&&<p className="notice">Planning edits are unsaved. The saved executable version and its aliases remain unchanged.</p>}
      <div className="form-grid"><label>Load policy history by exact version<input value={lookup} onChange={e=>setLookup(e.target.value)} placeholder="policy-id@1" /></label><button className="secondary" disabled={busy||!lookup} onClick={()=>void act(async()=>{accept(await request<S['PolicyView']>(policyPath(parseRef(lookup))));setDraft(undefined);setReview(false);})}>Load pinned version</button></div>
      {saved&&<><p role="status">Saved {refKey(saved.policy)} · {saved.transition.status} · sequence {saved.transition.sequence}. Opening an older version does not roll back any route.</p><button className="secondary" disabled={busy} onClick={()=>{
        const next=structuredClone(saved.policy); next.version+=1;next.quality='untested_provisional';
        next.prompts=(next.prompts??[]).map(p=>({...p,parent:ref(p.id,p.version),version:p.version+1}));
        next.stages=next.stages.map(s=>({...s,prompt:s.prompt?ref(s.prompt.id,s.prompt.version+1):null}));update(next);
      }}>Propose next draft version</button></>}
      {draft&&<fieldset disabled={busy}><h3>Draft {refKey(draft)} — never active</h3><p>{draft.stages.length} stages · {draft.budget.max_model_calls} bounded model calls · {draft.budget.max_tool_calls} bounded tool calls. Planning iteration limits are not assumed sample-call counts.</p>
        {draft.stages.map((stage,index)=>{
          const node=draft.workflow.nodes.find(n=>n.id===stage.node_id)!,prompt=draft.prompts?.find(p=>p.id===stage.prompt?.id&&p.version===stage.prompt.version);
          return <article className="model-card" key={stage.node_id}><h3>{index+1}. {node.purpose}</h3><p>{node.kind} · depends on {node.depends_on?.join(', ')||'workflow input'} · configuration {stage.configuration_id??'No model'}</p>
            <p>Model pins remain the saved server selection. Pin/exclusion changes require the missing server selection contract; editing an execution prompt never silently changes a model.</p>
            {prompt&&<label>Prompt template · {refKey(prompt)}<textarea rows={4} value={prompt.template} onChange={e=>update({...draft,prompts:draft.prompts?.map(p=>p===prompt?{...p,template:e.target.value}:p)})} /></label>}
            {node.kind==='code'&&<label>Approved deterministic operation<select value={stage.operation??''} onChange={e=>update({...draft,stages:draft.stages.map(s=>s===stage?{...s,operation:e.target.value as S['ExecutableStage']['operation']}:s)})}><option value="">Choose explicitly — no inferred operation</option>{['text.trim.v1','text.lowercase.v1','text.uppercase.v1','text.sort_lines.v1','text.deduplicate_lines.v1'].map(op=><option key={op}>{op}</option>)}</select></label>}
            <p>Bindings: <code>{JSON.stringify(node.inputs)}</code></p><div className="form-grid">{Object.entries(stage.output_types).map(([key,type])=><label key={key}>Output {key} type<select value={type} onChange={e=>update({...draft,stages:draft.stages.map(s=>s===stage?{...s,output_types:{...s.output_types,[key]:e.target.value as typeof type}}:s)})}>{['text','json','boolean','number'].map(t=><option key={t}>{t}</option>)}</select></label>)}</div><p className="hint">Changing a type must preserve downstream typed bindings; the server rejects mismatches. Full JSON Schema validation is not in the frozen execution contract.</p>
          </article>;
        })}
        <details><summary>Advanced typed stages, input types and budgets</summary><p>Canonical policy JSON only. Workflow/catalog/selection must stay bound to the saved plan; server validation is authoritative. No production or measured claim is carried into a new draft.</p><label>Executable policy JSON<textarea rows={12} key={`${draft.id}-${draft.version}-${review}`} defaultValue={JSON.stringify(draft,null,2)} onBlur={e=>{try{const parsed=JSON.parse(e.target.value) as S['ExecutablePolicy'];editableShape(draft,parsed);if(parsed.id!==draft.id||parsed.version!==draft.version||JSON.stringify(parsed.workflow)!==JSON.stringify(draft.workflow)||parsed.catalog_id!==draft.catalog_id||JSON.stringify(parsed.plan)!==JSON.stringify(draft.plan)||parsed.stages.some(s=>s.configuration_id!==draft.stages.find(old=>old.node_id===s.node_id)?.configuration_id))throw new Error('Keep policy identity, saved workflow, catalog and server-selected configuration pins unchanged.');update(parsed);}catch(e){setError(String(e));setReview(false);}}} /></label></details>
        <button className="secondary" onClick={()=>setReview(true)}>Review executable draft diff</button>
        {review&&<><pre>{diff(saved?.policy,draft).join('\n')}</pre><p className="notice">Confirming saves a new draft only. Previous enabled versions, aliases and evaluation records are not migrated. Quality remains untested/provisional.</p><button disabled={dirty||view.stale} onClick={()=>void act(async()=>{for(const prompt of draft.prompts??[])await request<S['PromptRevision']>('/api/studio/prompts',prompt);accept(await request<S['PolicyView']>('/api/studio/policies',draft));setDraft(undefined);setReview(false);})}>Confirm and save executable draft</button></>}
      </fieldset>}
      <details><summary>Current structured-edit limits</summary><p>Region, cost ceiling, self-host restriction, required capabilities, language notes and graph edits use the canonical planner above. API-only restrictions, priorities and targeted model pins/exclusions have no frozen request fields. Natural-language edits are preserved as clarification notes, not silently interpreted into selection changes. An integration request covers these missing controls.</p></details>
    </>}
    <div hidden={tab!=='compare'}><Imports onImport={rows=>setSamples(old=>[...old,...rows])}/><Comparison samples={samples} current={saved}/></div>
    <div hidden={tab!=='routes'}><Routes key={saved?refKey(saved.policy):'empty'} value={saved} onChange={accept} onRun={id=>{setRunId(id);setTab('activity');}} /></div>
    <div hidden={tab!=='activity'}><Activity runId={runId}/></div>
  </section>;
}

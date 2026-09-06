import { useEffect, useRef, useState } from 'react';
import type { components } from './generated/api';
type S = components['schemas'];
const defaultsProcessing: S['ProcessingPolicy'] = {schema_version:'1.0', interpretation_role:'interpretation', research_role:'research', inference:'local_only', public_research:false, max_planning_usd:0};
const defaultsRequirements: S['TargetRequirements'] = {schema_version:'1.0', input_modality:'text', deployment:'any', structured_output:false, tool_calling:false};
const declared: S['Provenance'] = {schema_version:'1.0', kind:'user_declared', source:'Explicit planning form', evidence_ids:[]};
const initial: S['PlanInput'] = {schema_version:'1.0', intake: {schema_version:'1.0', example_id:null, tools:[], description:'', constraints: {schema_version:'1.0', open_weight_required:true, max_cost_per_1k_tokens:null, max_latency_ms:null, required_region:null, provenance:declared}}, processing:defaultsProcessing, requirements:defaultsRequirements, answers:[], catalog_mode:'fixture', edited_workflow:null};
const terminal = ['succeeded', 'failed', 'cancelled', 'uncertain'];
async function api<T>(path: string, body?: unknown, key?: string): Promise<T> {
  const response = await fetch(`/api${path}`, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', ...(key ? {'Idempotency-Key': key} : {})}, body: JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.message ?? `Request failed (${response.status})`);
  return result as T;
}
function pathFor(view: S['PlanView']) { return `/plans/${view.plan.id}/versions/${view.plan.version}`; }
export default function PlanningApp() {
  const [examples, setExamples] = useState<S['Example'][]>([]);
  const [capabilities, setCapabilities] = useState<S['PlanningCapabilities']>();
  const [draft, setDraft] = useState<S['PlanInput']>(initial);
  const [view, setView] = useState<S['PlanView']>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [workflowText, setWorkflowText] = useState('');
  const [policy, setPolicy] = useState<S['DraftPolicy']>();
  const pollCount = useRef(0);
  function accept(value: S['PlanView'], hydrate = false) {
    setView(value);
    if (hydrate) { setDraft(value.plan.input); setEditing(false); setPolicy(undefined); pollCount.current = 0; }
    window.history.replaceState(null, '', `?plan=${value.plan.id}&version=${value.plan.version}`);
  }
  useEffect(() => {
    let disposed = false;
    async function load() {
      try {
        const [ex, caps] = await Promise.all([api<S['Example'][]>('/planning-examples'), api<S['PlanningCapabilities']>('/planning-capabilities')]);
        if (disposed) return;
        setExamples(ex); setCapabilities(caps);
        if (caps.mode === 'live') setDraft({...initial, catalog_mode: 'public_snapshot'});
        const query = new URLSearchParams(window.location.search), id = query.get('plan'), version = query.get('version');
        if (id && /^[a-zA-Z0-9_-]{1,80}$/.test(id) && version && /^[1-9][0-9]*$/.test(version)) {
          const saved = await api<S['PlanView']>(`/plans/${id}/versions/${version}`);
          if (!disposed) accept(saved, true);
        }
      } catch (e) { if (!disposed) setError(String(e)); }
      finally { if (!disposed) setLoading(false); }
    }
    void load();
    return () => { disposed = true; };
  }, []);
  useEffect(() => {
    if (!view || terminal.includes(view.job.status)) return;
    let disposed = false;
    const timer = setTimeout(async () => {
      if (++pollCount.current > 300) { setError('Polling paused. Reload this saved URL to inspect persisted state.'); return; }
      try { const next = await api<S['PlanView']>(pathFor(view)); if (!disposed) setView(next); }
      catch (e) { if (!disposed) setError(String(e)); }
    }, 1000);
    return () => { disposed = true; clearTimeout(timer); };
  }, [view]);
  function constraints(changes: Partial<S['Constraints']>) { setDraft({...draft, intake: {...draft.intake, constraints: {...draft.intake.constraints, ...changes, provenance: declared}}}); }
  function processing(changes: Partial<S['ProcessingPolicy']>) { setDraft({...draft, processing: {...defaultsProcessing, ...draft.processing, ...changes}}); }
  function requirements(changes: Partial<S['TargetRequirements']>) { setDraft({...draft, requirements: {...defaultsRequirements, ...draft.requirements, ...changes}}); }
  async function save() {
    setBusy(true); setError(''); setPolicy(undefined);
    try {
      const body: S['PlanInput'] = {...draft, edited_workflow: editing ? JSON.parse(workflowText) as S['Workflow'] : null};
      if (body.edited_workflow && view) body.edited_workflow = {...body.edited_workflow, id: view.plan.id, version: view.plan.version + 1, constraints: draft.intake.constraints, tools: draft.intake.tools ?? []};
      const path = view ? `${pathFor(view)}/revise` : '/plans';
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(path + JSON.stringify(body))))).map(x => x.toString(16).padStart(2, '0')).join('');
      const key = sessionStorage.getItem(`request-${hash}`) ?? crypto.randomUUID();
      sessionStorage.setItem(`request-${hash}`, key);
      accept(await api<S['PlanView']>(path, body, key), true);
      sessionStorage.removeItem(`request-${hash}`);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function cancel() {
    if (!view) return;
    try { accept(await api<S['PlanView']>(`${pathFor(view)}/cancel`, {})); } catch (e) { setError(String(e)); }
  }
  async function exportDraft() {
    if (!view) return;
    try {
      const value = await api<S['DraftPolicy']>(`${pathFor(view)}/policy`, {}); setPolicy(value);
      const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: 'application/json'}));
      const link = document.createElement('a'); link.href = url; link.download = `buildbox-v${view.plan.version}-inactive-policy.json`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(String(e)); }
  }
  const result = view?.result, workflow = result?.workflow, rec = result?.recommendation;
  const pending = view && !terminal.includes(view.job.status);
  const dirty = !!view && (editing || JSON.stringify(draft) !== JSON.stringify(view.plan.input));
  return <div className="shell">
    <aside><a className="brand" href="/">▧ buildbox</a><p className="nav-label">WORKSPACE</p><div className="nav-current">Planning router</div><p className="aside-note">{capabilities?.authentication ?? 'Connecting…'}<br/>Execution tools disconnected</p><span className="mode">PLANNING ALPHA</span></aside>
    <main><header><span>BUILD / EXPLORE / VERIFY</span><span className="pill">{capabilities?.mode === 'fixture' ? 'FIXTURE MODE' : 'Permission-gated runtime'}</span></header>
      <h1>A small stack.<br/><span>A clear decision trail.</span></h1>
      <p className="intro">Plan a workflow and retain the evidence behind a configuration decision. Nothing here executes your workflow or routes production traffic.</p>
      <div className="notice"><strong>{capabilities?.mode === 'fixture' ? 'Fixture mode — synthetic configurations, not verified models.' : 'Live alpha verification is incomplete.'}</strong>Explicit examples replay recorded interpretations. Edited free text needs an approved runtime model unless it is a supported deterministic instruction. {capabilities?.live_gate}</div>
      {loading && <p role="status">Loading saved planning state…</p>}{error && <p role="alert" className="error">{error}</p>}
      <section><h2>1. Describe and constrain</h2>
        <div className="actions">{examples.map(ex => <button className="secondary" key={ex.id} disabled={busy || !!pending} onClick={() => {setDraft({...initial, intake: ex.intake, catalog_mode: capabilities?.mode === 'fixture' ? 'fixture' : 'public_snapshot'}); setView(undefined); setEditing(false); setPolicy(undefined); setError(''); window.history.replaceState(null, '', '/');}}>{ex.title}</button>)}</div>
        <label>Workflow description<textarea rows={5} value={draft.intake.description} onChange={e => setDraft({...draft, intake: {...draft.intake, description: e.target.value}})} placeholder="Inputs, transformations, tools, outputs, and approval. Or try: lowercase text" /></label>
        <div className="form-grid">
          <label>Required target region<input value={draft.intake.constraints.required_region ?? ''} onChange={e => constraints({required_region: e.target.value || null})} placeholder="Unspecified" /></label>
          <label>Target cost ceiling / 1k tokens<input type="number" min="0" step="0.1" value={draft.intake.constraints.max_cost_per_1k_tokens ?? ''} onChange={e => constraints({max_cost_per_1k_tokens: e.target.value === '' ? null : Number(e.target.value)})} /></label>
          <label>Input modality<select value={draft.requirements?.input_modality ?? 'text'} onChange={e => requirements({input_modality: e.target.value as 'text' | 'image'})}><option value="text">Text</option><option value="image">Image</option></select></label>
          <label>Target deployment<select value={draft.requirements?.deployment ?? 'any'} onChange={e => requirements({deployment: e.target.value as 'any' | 'self_hosted'})}><option value="any">Any verified deployment</option><option value="self_hosted">Self-hosted only</option></select></label>
        </div>
        <label className="check"><input type="checkbox" checked={draft.requirements?.structured_output ?? false} onChange={e => requirements({structured_output:e.target.checked})} />Require exact structured-output support</label>
        <label className="check"><input type="checkbox" checked={draft.requirements?.tool_calling ?? false} onChange={e => requirements({tool_calling:e.target.checked})} />Require model tool calling (distinct from deterministic tool stages)</label>
        <details><summary>Declared tools — never connected or executed</summary><pre>{JSON.stringify(draft.intake.tools ?? [], null, 2)}</pre><label>Tool declarations JSON<textarea rows={3} defaultValue={JSON.stringify(draft.intake.tools ?? [])} key={draft.intake.example_id} onBlur={e => {try { const tools = JSON.parse(e.target.value) as S['WorkflowTool'][]; setDraft({...draft, intake: {...draft.intake, tools}}); } catch { setError('Tool declarations must be valid JSON.'); }}} /></label></details>
      </section>
      <section><h2>2. Processing and privacy — before any call</h2>
        <p>Planning models are control-plane choices, not target-stack recommendations. Public research sends only a fixed public model repository ID; no workflow text. No paid research model is used.</p>
        <label>Interpretation processing<select value={draft.processing?.inference ?? 'local_only'} onChange={e => processing({inference: e.target.value as S['ProcessingPolicy']['inference']})}><option value="local_only">Local only — replay / deterministic / manual edit</option><option value="local_model" disabled={!capabilities?.local_model}>Local cached model — {capabilities?.local_model ?? 'not configured'} (no external calls)</option><option value="approved_hosted">Approved hosted model — requires operator permission</option></select></label>
        <label>Catalog source<select value={draft.catalog_mode ?? 'fixture'} onChange={e => setDraft({...draft, catalog_mode: e.target.value as S['PlanInput']['catalog_mode']})}><option value="fixture" disabled={capabilities?.mode !== 'fixture'}>Synthetic fixture (invented configuration facts)</option><option value="public_snapshot">Retained public snapshot — September 6, offline</option><option value="runtime_public">Runtime official public metadata (no paid provider)</option></select></label>
        <label className="check"><input type="checkbox" checked={draft.processing?.public_research ?? false} onChange={e => processing({public_research:e.target.checked})} />Allow HTTPS public-metadata research for this version</label>
        <label>Maximum paid planning spend (USD, capped by server approval)<input type="number" min="0" max="1" step="0.01" value={draft.processing?.max_planning_usd ?? 0} onChange={e => processing({max_planning_usd:Number(e.target.value)})} /></label>
      </section>
      <section><h2>3. Clarification and edits</h2><p>Answers are saved with the version. Correct conflicting text and structured constraints explicitly; notes do not silently override a hard constraint.</p>
        {result?.interpretation.questions?.map(q => <label key={q.field}>{q.question}<input value={draft.answers?.find(a => a.question_id === q.field)?.answer ?? ''} onChange={e => setDraft({...draft, answers:[...(draft.answers ?? []).filter(a => a.question_id !== q.field), ...(e.target.value ? [{question_id:q.field, answer:e.target.value, schema_version:'1.0' as const}] : [])]})} /></label>)}
        <label>Preserved answer / correction note<textarea rows={2} value={draft.answers?.find(a => a.question_id === 'user-note')?.answer ?? ''} onChange={e => setDraft({...draft, answers:[...(draft.answers ?? []).filter(a => a.question_id !== 'user-note'), ...(e.target.value ? [{question_id:'user-note', answer:e.target.value, schema_version:'1.0' as const}] : [])]})} /></label>
        {workflow && <><button className="secondary" onClick={() => {setEditing(!editing); setWorkflowText(JSON.stringify(workflow, null, 2));}}>{editing ? 'Discard graph edit' : 'Edit validated workflow JSON'}</button>{editing && <label>Workflow JSON — current constraints and next version are bound on save<textarea rows={18} value={workflowText} onChange={e => setWorkflowText(e.target.value)} /></label>}</>}
        <div className="actions"><button disabled={loading || busy || !!pending || !draft.intake.description.trim() || !!view?.stale} onClick={save}>{busy ? 'Saving…' : view ? 'Save changed constraints / answers as new version' : 'Save and plan'}</button>{pending && <button className="secondary" onClick={cancel}>Cancel planning</button>}</div>
      </section>
      <section><h2>4. Saved state and decision trail</h2>{!view ? <p>No saved plan yet. Results will appear here.</p> : <>
        <p role="status">Version {view.plan.version} · latest {view.latest_version} · Job {view.job.status} · {view.job.phase}</p>
        {dirty && <p className="notice">Unsaved changes: this saved result does not apply to the edited form. Save a new version before downloading a policy.</p>}
        {view.stale && <p className="error">Stale version. This recommendation does not apply to version {view.latest_version}. <a href={`?plan=${view.plan.id}&version=${view.latest_version}`}>Open latest version</a></p>}
        <p>Persisted progress: {view.job.progress?.join(' → ') || 'queued'}. Evaluation: not run.</p>
        {view.job.error && <p role="alert" className="error">{view.job.error.message}</p>}
        <p>Accounting: {view.job.accounting}. Reserved: ${view.job.reserved_usd ?? 0}; accounted: {view.job.accounted_usd == null ? 'unknown / not yet reported' : `$${view.job.accounted_usd}`}.</p>
        {!!Object.keys(view.job.served_configuration ?? {}).length && <details><summary>Actual served planning configuration and usage</summary><pre>{JSON.stringify(view.job.served_configuration,null,2)}</pre></details>}
        {workflow && <><h3>{workflow.title}</h3><ol className="stages">{workflow.nodes.map(node => <li key={node.id}><strong>{node.id} · {node.kind}</strong><p>{node.purpose}</p><small>Depends on: {node.depends_on?.join(', ') || 'workflow input'}{node.kind === 'bounded_agent' && ` · at most ${node.max_iterations} iterations / ${node.max_model_calls} model calls`}{node.tool_id && ` · tool: ${node.tool_id} (disconnected)`}</small><details><summary>Input/output bindings</summary><pre>{JSON.stringify({inputs:node.inputs, outputs:node.outputs}, null, 2)}</pre></details></li>)}</ol></>}
        {result && <><h3>Result: {result.status}</h3>{result.missing_facts?.map(x => <p className="notice" key={x}>{x}</p>)}{result.assumptions?.map(x => <p key={x}>{x}</p>)}
          {rec && <><h3>{result.catalog?.synthetic ? 'Synthetic' : 'Evidence-backed'} configuration mapping</h3>{rec.assignments.length ? rec.assignments.map(a => <div className="assignment" key={a.node_id}><strong>{a.node_id} → {a.configuration_id}</strong><p>{a.reason}</p></div>) : <p>No model assignments: deterministic/code/approval stages need no model.</p>}<p>Alternatives: {rec.alternatives?.join(', ') || 'None retained; no automatic fallback'}</p>{rec.limitations?.map(x => <p key={x}>{x}</p>)}</>}
          <details><summary>Exclusions and missing configuration facts</summary>{Object.entries(result.exclusions ?? {}).map(([id, reasons]) => <p key={id}><strong>{id}</strong>: {reasons.join('; ')}</p>)}</details>
          <details><summary>Evidence and pinned catalog</summary><p>Snapshot: {result.catalog?.id ?? 'No snapshot'}</p>{result.catalog?.evidence.map(e => <article key={e.id}><h3>{e.title}</h3><p>{e.claim}</p><small>{e.provenance.kind} · {e.captured_at}</small>{e.source_url && /^https:\/\/(huggingface\.co|openrouter\.ai)\//.test(e.source_url) && <p><a href={e.source_url} target="_blank" rel="noreferrer">Official source</a></p>}</article>)}{result.research && <pre>{JSON.stringify(result.research, null, 2)}</pre>}</details>
          <button disabled={!rec || view.stale || dirty || result.status === 'blocked'} onClick={exportDraft}>Download inactive policy</button>
        </>}
      </>}</section>
      {policy && <section className="policy"><h2>Downloaded inactive draft</h2><p>No secrets, no active routing, no connected execution tools.</p><pre>{JSON.stringify(policy, null, 2)}</pre></section>}
      <footer>No measured quality, savings, benchmark badges or production-readiness claims. Evaluation milestone remains unrun.</footer>
    </main>
  </div>;
}

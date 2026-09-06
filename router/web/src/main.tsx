import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { components } from './generated/api';
import './style.css';

type Schema = components['schemas'];
async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.message ?? 'Request failed');
  return result as T;
}

function App() {
  const [examples, setExamples] = useState<Schema['Example'][]>([]);
  const [selected, setSelected] = useState<Schema['Example']>();
  const [submission, setSubmission] = useState<Schema['Submission']>();
  const [restoredWorkflow, setRestoredWorkflow] = useState<Schema['Workflow']>();
  const [job, setJob] = useState<Schema['Job']>();
  const [recommendation, setRecommendation] = useState<Schema['Recommendation']>();
  const [evidence, setEvidence] = useState<Schema['CatalogSnapshot']>();
  const [policy, setPolicy] = useState<Schema['DraftPolicy']>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Schema['Example'][]>('/examples').then(setExamples).catch(e => setError(String(e)));
    const savedId = new URLSearchParams(window.location.search).get('job');
    if (savedId && /^[a-zA-Z0-9_-]{1,80}$/.test(savedId)) {
      api<Schema['Job']>(`/jobs/${savedId}`).then(async saved => {
        setRestoredWorkflow(await api<Schema['Workflow']>(`/workflows/${saved.workflow_id}/versions/${saved.workflow_version}`));
        setJob(saved);
        if (saved.status === 'succeeded') setRecommendation(await api<Schema['Recommendation']>(`/recommendations/${saved.recommendation_id}`));
      }).catch(e => setError(String(e)));
    }
  }, []);
  useEffect(() => {
    if (!job || ['succeeded', 'failed'].includes(job.status)) return;
    let cancelled = false;
    let polls = 0;
    const timer = setInterval(async () => {
      if (++polls > 60) { clearInterval(timer); setError('Polling paused after 60 seconds. Start the backend worker, then reload the saved job.'); return; }
      try {
        const current = await api<Schema['Job']>(`/jobs/${job.id}`);
        if (cancelled) return;
        if (current.status === 'succeeded') {
          const rec = await api<Schema['Recommendation']>(`/recommendations/${current.recommendation_id}`);
          if (!cancelled) { setJob(current); setRecommendation(rec); }
        } else if (current.status === 'failed') { setJob(current); setError(current.error?.message ?? 'Job failed'); }
      } catch (e) { clearInterval(timer); setError(String(e)); }
    }, 1000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [job]);

  async function save() {
    if (!selected) return;
    setBusy(true); setError(''); setRecommendation(undefined); setEvidence(undefined); setPolicy(undefined);
    try {
      const value = await api<Schema['Submission']>('/intakes', selected.intake);
      setSubmission(value); setJob(value.job ?? undefined);
      if (value.job) window.history.replaceState(null, '', `?job=${value.job.id}`);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function inspect() {
    try { setEvidence(await api<Schema['CatalogSnapshot']>(`/recommendations/${recommendation?.id}/evidence`)); } catch (e) { setError(String(e)); }
  }
  async function exportDraft() {
    try {
      const draft = await api<Schema['DraftPolicy']>(`/recommendations/${recommendation?.id}/policy`, {});
      setPolicy(draft);
      const url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], {type: 'application/json'}));
      const link = document.createElement('a'); link.href = url; link.download = 'buildbox-inactive-policy.json'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(String(e)); }
  }

  const workflow = submission?.interpretation.workflow ?? restoredWorkflow;
  return <div className="shell">
    <aside><a className="brand" href="/">▧ buildbox</a><p className="nav-label">WORKSPACE</p><div className="nav-current">Workflow router</div><p className="aside-note">Local fixture identity<br/>No connected execution tools</p><span className="mode">OFFLINE FOUNDATION</span></aside>
    <main><header><span>BUILD / EXPLORE / VERIFY</span><span className="pill">Synthetic data only</span></header>
      <h1>A small stack.<br/><span>A clear decision trail.</span></h1>
      <p className="intro">Turn an example workflow into stage assignments and an inactive policy. Nothing here runs your workflow or changes production traffic.</p>
      <div className="notice"><strong>Fixture mode, not a live model advisor.</strong> This milestone uses one fixed example and invented configurations. Free-text interpretation, live research and inference are not enabled.</div>
      {error && <p role="alert" className="error">{error}</p>}
      <section><div className="section-head"><span className="step">01</span><h2>Choose a workflow</h2></div>
        {examples.map(ex => <button className={`example ${selected?.id === ex.id ? 'selected' : ''}`} key={ex.id} onClick={() => setSelected(ex)}><strong>{ex.title}</strong><span>Normalize → classify → human review</span><small>SYNTHETIC EXAMPLE</small></button>)}
        {selected && <p>{selected.intake.description}</p>}
        <button disabled={!selected || busy || job?.status === 'queued' || job?.status === 'running'} onClick={save}>{busy ? 'Saving…' : 'Save workflow & find fixture stack'}</button>
      </section>
      <section><div className="section-head"><span className="step">02</span><h2>Inspect the recommendation</h2>{job && <span className="pill" role="status">Job: {job.status}</span>}</div>
        {!workflow ? <p className="muted">Your typed workflow and decision trail will appear here.</p> : <>
          <p>Saved immutable workflow v{workflow.version}. Code and approval steps have no model assignment.</p>
          <div className="workflow">{workflow.nodes.map(node => <div key={node.id}><small>{node.kind}</small><strong>{node.id}</strong></div>)}</div>
          {submission?.interpretation.questions.map(q => <p key={q.field}>{q.question}</p>)}
        </>}
        {recommendation && <><h3>Recommended fixture stack</h3>{recommendation.assignments.map(a => <div className="assignment" key={a.node_id}><strong>{a.node_id} → {a.configuration_id}</strong><p>{a.reason}</p></div>)}
          <p><strong>Confidence: synthetic only.</strong> No quality or production suitability has been measured.</p>
          <details><summary>Why other configurations were excluded</summary>{Object.entries(recommendation.filter_result.excluded).map(([id, why]) => <p key={id}><strong>{id}</strong>: {why.join('; ')}</p>)}</details>
          <div className="actions"><button className="secondary" onClick={inspect}>Inspect fixture evidence</button><button onClick={exportDraft}>Export inactive draft policy</button></div>
        </>}
      </section>
      {evidence && <section><h2>Fixture evidence</h2>{evidence.evidence.map(e => <article key={e.id}><h3>{e.title}</h3><p>{e.claim}</p><small>Provenance: {e.provenance.kind} · {e.captured_at}</small></article>)}<p>Latency, hardware and quantization remain unknown. The zero cost is an invented fixture value, not a free provider offer.</p></section>}
      {policy && <section className="policy"><h2>Draft exported · INACTIVE</h2><p>Human approval required. Production writes disabled. No credentials or endpoint connections included.</p><pre>{JSON.stringify(policy, null, 2)}</pre></section>}
      <footer>Decision support only · Canonical contracts v1.0 · Local, synthetic and no-write</footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')!).render(<App/>);

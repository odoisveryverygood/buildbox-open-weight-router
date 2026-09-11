import { useState } from 'react';
import { diff, sourceLink, type S } from './model';

function Fact({value, claims = []}: {value: {value?: unknown; unknown_reason?: string | null; provenance:S['Provenance']}; claims?:S['ClaimRecord'][]}) {
  const stale = claims.some(c => Date.parse(c.expires_at) <= Date.now());
  const status = value.value == null ? 'Unknown' : value.provenance.kind === 'synthetic' ? 'Synthetic' : value.provenance.kind === 'observed' ? 'Observed' : value.provenance.kind === 'inference' ? 'Inference' : 'Declared';
  return <span><span className={`badge ${status === 'Unknown' || stale ? 'muted' : ''}`}>{status}{stale ? ' · stale' : ''}</span> {value.value == null ? value.unknown_reason : Array.isArray(value.value) ? value.value.join(', ') : String(value.value)}</span>;
}
function Claim({claim}: {claim:S['ClaimRecord']}) {
  const href = sourceLink(claim.evidence.source_url);
  return <details className="claim"><summary>{claim.field} · {claim.evidence.title} {Date.parse(claim.expires_at) <= Date.now() ? '· stale' : ''}</summary>
    <p>{claim.evidence.claim}</p><p>Subject: {claim.subject_kind} / {claim.subject_id}</p>
    <p>{href ? <a href={href} target="_blank" rel="noreferrer">{claim.source_type} source</a> : 'Source link unavailable / outside display allowlist'} · Locator: <code>{claim.source_locator}</code></p>
    <p>Observed {claim.observed_at} · expires {claim.expires_at}. Retrieval is not a measurement date.</p>
    <dl><dt>Benchmark / version / split</dt><dd>{claim.benchmark_name.value ?? 'Unknown'} / {claim.benchmark_version.value ?? 'Unknown'} / {claim.benchmark_split.value ?? 'Unknown'}</dd><dt>Reported metric</dt><dd>{claim.raw_metric.value ?? 'Unknown'} {claim.metric_unit.value ?? ''} · n={claim.sample_size.value ?? 'unknown'}</dd><dt>Test date / harness / settings</dt><dd>{claim.tested_at.value ?? 'Unknown'} / {claim.harness.value ?? 'Unknown'} / {claim.settings.value ?? 'Unknown'}</dd></dl>
    <p>Not measured by Buildbox. {claim.limitations.join(' ')}</p><small>Evidence {claim.evidence.id} · source digest {claim.source_digest}</small>
  </details>;
}
export default function CatalogExplorer({view, previous, refresh, busy}: {view:S['PlanView']; previous?:S['PlanView']; refresh:()=>void; busy:boolean}) {
  const [query, setQuery] = useState(''), [task,setTask] = useState(''), [weights,setWeights] = useState(false);
  const result=view.result, ledger=result?.research, catalog=result?.catalog;
  const rows=(catalog?.artifacts ?? []).filter(a => {
    const rich=ledger?.artifacts.find(r=>r.artifact.id===a.id);
    return `${a.name} ${a.id} ${rich?.repository_id ?? ''}`.toLowerCase().includes(query.toLowerCase()) && (!weights || a.open_weight.value === true) && (!task || rich?.declared_task.value === task);
  });
  return <section id="explorer"><div className="section-head"><h2>Model explorer</h2><span className="badge">{catalog?.synthetic ? 'Synthetic test catalog' : 'Retained public evidence'}</span></div>
    <p>Discovered is not eligible. Eligible is not callable here. No connection or hard-policy clearance is inferred from a model listing.</p>
    <div className="form-grid"><label>Search models<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Publisher, repository or release" /></label><label>Declared task<select value={task} onChange={e=>setTask(e.target.value)}><option value="">All tasks (including unknown)</option>{[...new Set(ledger?.artifacts.flatMap(a=>a.declared_task.value ? [a.declared_task.value] : []) ?? [])].map(t=><option key={t}>{t}</option>)}</select></label></div>
    <label className="check"><input type="checkbox" checked={weights} onChange={e=>setWeights(e.target.checked)} />Listed open weights only (not license acceptance)</label>
    <p>Snapshot <code>{catalog?.id ?? 'No completed snapshot'}</code> · {rows.length} artifacts shown · {catalog?.configurations.length ?? 0} bound configurations. Callable status: unknown until server admission and runtime authorization.</p>
    <details><summary>Three bounded research roles and coverage</summary><p>Only persisted job phases are progress: {view.job.progress?.join(' → ') || view.job.status}. Role counts below describe retained evidence, not running agents.</p>
      <ul><li>Discovery: {ledger?.artifacts.length ?? 0} exact artifact records.</li><li>Capability evidence: {ledger?.claims.filter(c=>c.field==='capability').length ?? 0} source-linked claims, not independent agent votes.</li><li>Deployment facts: {ledger?.endpoints.length ?? 0} declared endpoints.</li></ul>
      <p>Parser versions: {ledger?.parser_versions?.join(', ') ?? 'No rich ledger'}. Field freshness is configurable engineering policy.</p>
      {ledger?.issues?.map((issue,i)=><p className="notice" key={i}>{issue.status} · {issue.subject}: {issue.message}</p>)}
    </details>
    <div className="actions"><button className="secondary" disabled={busy || view.stale} onClick={refresh}>Review bounded refresh as a new draft</button></div>
    <p className="hint">Refresh uses the existing planning job, not a second search client. Cached snapshots are preferred. It cannot update an enabled alias. Runtime metadata requires explicit opt-in; this base supports only its fixed repository.</p>
    {previous?.result?.catalog && <details><summary>Snapshot diff versus plan version {previous.plan.version}</summary><p>{previous.result.catalog.id === catalog?.id ? 'Same pinned snapshot; no catalog change.' : 'A different snapshot is proposed. Existing routes remain pinned.'}</p><pre>{diff(previous.result.catalog, catalog).join('\n') || 'No differences'}</pre></details>}
    {!rows.length && <p role="status">No matching retained artifacts. This is not proof that no eligible model exists.</p>}
    {rows.map(artifact=>{
      const rich=ledger?.artifacts.find(a=>a.artifact.id===artifact.id), claims=ledger?.claims.filter(c=>c.subject_id===artifact.id) ?? [];
      const configurations=catalog?.configurations.filter(c=>c.artifact_id===artifact.id) ?? [];
      return <article className="model-card" key={artifact.id}><h3>{artifact.name}</h3><p><span className="badge">Discovered</span> <code>{rich?.repository_id ?? artifact.id}</code> · revision {artifact.revision ?? 'Unknown'}</p>
        <dl><dt>Weights</dt><dd><Fact value={artifact.open_weight} claims={claims.filter(c=>c.field==='access')} /></dd><dt>License declaration</dt><dd><Fact value={artifact.license} claims={claims.filter(c=>c.field==='license')} /> {rich?.license_url.value && sourceLink(rich.license_url.value) && <a href={sourceLink(rich.license_url.value)} target="_blank" rel="noreferrer">License source</a>} · Terms not reviewed/accepted here.</dd>
        {rich && <><dt>Access</dt><dd><Fact value={rich.access} claims={claims.filter(c=>c.field==='access')} /></dd><dt>Modalities · in / out</dt><dd><Fact value={rich.input_modalities} /> / <Fact value={rich.output_modalities} /></dd></>}</dl>
        {configurations.map(config=><details key={config.id}><summary>Configuration {config.id} · {result?.exclusions?.[config.id] ? 'Excluded' : result?.recommendation?.assignments.some(a=>a.configuration_id===config.id) ? 'Selected for this plan (not execution clearance)' : 'Eligibility not established'}</summary><p>Provider: <Fact value={config.provider} /> · region: <Fact value={config.region} /></p><p>Cost / 1k tokens: <Fact value={config.cost_per_1k_tokens} /> · latency: <Fact value={config.latency_ms} /></p><p>{result?.exclusions?.[config.id]?.join('; ')}</p><p>Callable here: not established. Configuration is distinct from its artifact and provider endpoint.</p></details>)}
        {ledger?.endpoints.filter(e=>e.artifact_id===artifact.id).map(ep=><details key={ep.id}><summary>Endpoint {ep.endpoint_tag} · declared, not callable</summary><p>Routing model {ep.routing_model_id} · endpoint identity {ep.id}</p><p>Effective limits (declared): context <Fact value={ep.context_tokens} /> · prompt <Fact value={ep.max_prompt_tokens} /> · completion <Fact value={ep.max_completion_tokens} /></p><p>Supported parameters: <Fact value={ep.supported_parameters} />. No measured tool/structured-output support is inferred.</p><p>Privacy: <Fact value={ep.privacy} /> · restrictions: <Fact value={ep.provider_restrictions} /></p><p>Serving revision: <Fact value={ep.served_revision} /> · quantization: <Fact value={ep.quantization} /> · hardware: <Fact value={ep.hardware} /></p><ul>{ep.prices.map(p=><li key={p.component}>{p.component}: {p.raw_amount} {p.currency} / {p.unit}{p.usd_per_million_tokens != null ? ` (${p.usd_per_million_tokens} USD / million tokens)` : ''}</li>)}</ul><p>Conditional pricing: <Fact value={ep.conditional_pricing} /></p><p>{ep.limitations.join(' ')}</p>{ledger.claims.filter(c=>c.subject_id===ep.id).map(c=><Claim key={c.evidence.id} claim={c} />)}</details>)}
        <details><summary>Exact claim/source relationships ({claims.length})</summary>{claims.map(c=><Claim key={c.evidence.id} claim={c} />)}{!claims.length && <p>No rich claim ledger. {artifact.provenance.source}</p>}</details>
      </article>;
    })}
  </section>;
}

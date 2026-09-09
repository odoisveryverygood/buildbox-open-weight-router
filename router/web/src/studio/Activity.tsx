import { useEffect, useState } from 'react';
import { request } from './api';
import { identifier, money, refKey, type S } from './model';
type Event = S['RunStatusEvent'] | S['RunUsageEvent'] | S['RunErrorEvent'];
export default function Activity({runId}: {runId?:string}) {
  const [id,setId]=useState(runId??new URLSearchParams(location.search).get('run')??''), [run,setRun]=useState<S['SandboxRun']>(), [events,setEvents]=useState<Event[]>([]);
  const [output,setOutput]=useState<S['StoredOutput']>(), [trace,setTrace]=useState<S['DecisionTrace']>(), [traceId,setTraceId]=useState(''), [error,setError]=useState(''), [busy,setBusy]=useState(false);
  useEffect(()=>{if(runId)setId(runId);},[runId]);
  async function load() {
    setBusy(true);setError('');setOutput(undefined);setTrace(undefined);setEvents([]);
    try {const next=await request<S['SandboxRun']>(`/api/sandbox/runs/${id}`);setRun(next); const q=new URLSearchParams(location.search);q.set('run',next.id);history.replaceState(null,'',`?${q}`);
      if(next.output_reference){const value=await request<S['StoredOutput']>(`/api/sandbox/runs/${next.id}/outputs/${next.output_reference}`);if(value.run_id!==next.id)throw new Error('Output identity mismatch');setOutput(value);}
    }catch(e){setError(String(e));}finally{setBusy(false);}
  }
  useEffect(()=>{
    if(!run)return;
    const source=new EventSource(`/api/sandbox/runs/${run.id}/events?after_sequence=0`);
    const listener=(message:MessageEvent)=>{try{const event=JSON.parse(message.data) as Event;
      if(event.run_id!==run.id||!Number.isInteger(event.sequence)||event.sequence<1||!['run.status','run.usage','run.error'].includes(event.type))throw new Error();
      if(event.type==='run.status'&&event.run.id!==run.id)throw new Error();
      setEvents(old=>old.some(e=>e.sequence===event.sequence)?old:[...old,event].sort((a,b)=>a.sequence-b.sequence));
    }catch{source.close();setError('Invalid event received. Stream stopped; refresh persisted run state.');}};
    source.onmessage=listener;
    for(const name of ['run.status','run.usage','run.error'])source.addEventListener(name,listener as EventListener);
    source.onerror=()=>{source.close();}; // no unbounded automatic reconnect; persisted refresh is read-only
    return()=>source.close();
  },[run]);
  const latestStatus=events.filter(e=>e.type==='run.status').at(-1);
  const status=latestStatus?.type==='run.status'?latestStatus.run.status:run?.status;
  const usage=[...new Map(events.filter(e=>e.type==='run.usage').map(e=>[e.usage.reservation_id,e.usage])).values()];
  return <section id="activity"><h2>Activity & usage</h2><p>Open an exact persisted run. Opening or refreshing is read-only; replaying is a new explicitly costed action in Routes.</p><div className="form-grid"><label>Run ID<input value={id} onChange={e=>setId(e.target.value)} /></label><button className="secondary" disabled={busy||!identifier.test(id)} onClick={load}>Load / refresh run</button></div>
    {!run&&<p>No run loaded. The frozen API has no tenant-wide activity list, date/route query or aggregated usage endpoint.</p>}
    {error&&<p role="alert" className="error">{error}</p>}
    {run&&<><p role="status">{run.id} · {status} · {refKey(run.policy)} · {run.quality}</p><p>Created {run.created_at} · attempts {run.attempt_ids.length}. Individual attempt retrieval is not exposed; counts are not assumed calls.</p>
      {['queued','running','awaiting_approval'].includes(status??'')&&<button className="secondary" disabled={busy} onClick={async()=>{setBusy(true);try{setRun(await request<S['SandboxRun']>(`/api/sandbox/runs/${run.id}/cancel`,{}));}catch(e){setError(String(e));}finally{setBusy(false);}}}>Request stop before next dispatch</button>}
      <p>Cancellation does not imply a refund or undo a dispatched call. Failed/uncertain runs are never retried automatically.</p>
      <ol className="stages">{events.map(event=><li key={event.sequence}>#{event.sequence} · {event.type}{event.type==='run.status'?` · ${event.run.status}`:event.type==='run.error'?` · ${event.error.error.code}: ${event.error.error.message}`:` · ${event.usage.state} · actual ${money(event.usage.actual_micro_usd)}`}</li>)}</ol>
      <p>Observed usage events: {usage.length}. {usage.length?`Known reconciled subtotal ${money(usage.reduce((total,u)=>total+(u.actual_micro_usd??0),0))}; ${usage.filter(u=>u.actual_micro_usd==null).length} unresolved reservations.`:'No usage events received; total cost unknown, not zero.'} This is a loaded-event subtotal, not workspace billing.</p>
      {output?<><h3>Persisted result</h3><pre>{JSON.stringify(output.value,null,2)}</pre><p>Expires {output.expires_at}</p></>:<p>No final output loaded; refresh after completion. Partial/failed state is preserved.</p>}
      <details><summary>Request-scoped decision trace</summary><label>Request ID<input value={traceId} onChange={e=>setTraceId(e.target.value)} /></label><button className="secondary" disabled={busy||!identifier.test(traceId)} onClick={async()=>{setBusy(true);try{setTrace(await request<S['DecisionTrace']>(`/api/studio/traces/${traceId}`));}catch(e){setError(String(e));}finally{setBusy(false);}}}>Load trace (no replay)</button>{trace&&<><p>Requested {trace.configuration_id??'deterministic'} · served model {trace.served_model.value??'unknown'} · served endpoint {trace.served_endpoint.value??'unknown'}</p><p>Pinned catalog {trace.catalog_id} · policy {refKey(trace.policy)} · transition {trace.transition_sequence}</p><pre>{JSON.stringify(trace,null,2)}</pre></>}<p>Traces show decisions/provenance, never hidden reasoning. Fallback reasons and stage timing need the missing attempt-read interface.</p></details>
    </>}
  </section>;
}

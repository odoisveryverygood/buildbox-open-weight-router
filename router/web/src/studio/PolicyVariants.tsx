import { useState } from 'react';
import { request } from './api';
import { policyPath, type S } from './model';

export default function PolicyVariants({value,onChange}:{value?:S['PolicyView'];onChange:(v:S['PolicyView'])=>void}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  if(!value)return null;
  return <details><summary>Compile a new draft variant</summary><p>Uses the pinned catalog and existing eligibility selector. Quality/balanced share its uncalibrated heuristic; cost-conscious orders known normalized prices first. No measured quality, savings or runtime permission is implied. Existing aliases never change.</p>
    <div className="actions">{(['quality','balanced','cost_conscious'] as const).map(mode=><button className="secondary" key={mode} disabled={busy} onClick={async()=>{setBusy(true);setError('');try{onChange(await request<S['PolicyView']>(`${policyPath(value.policy)}/variants`,{execution_schema:'2.0',id:'variant-'+crypto.randomUUID(),mode} satisfies S['VariantRequest']));}catch(e){setError(String(e));}finally{setBusy(false);}}}>{mode}: new draft</button>)}</div>
    {value.policy.variant&&<ul>{value.policy.variant.rationale.map((r,i)=><li key={i}>{r}</li>)}</ul>}
    {error&&<p role="alert" className="error">{error}</p>}
  </details>;
}

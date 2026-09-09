import { useEffect, useState } from 'react';
import { request } from './api';
import { identifier, type S } from './model';

export default function RuntimeAccess() {
  const [status,setStatus]=useState<S['RuntimeStatus']>(), [keys,setKeys]=useState<S['ApplicationKeyMetadata'][]>([]);
  const [alias,setAlias]=useState(''), [secret,setSecret]=useState(''), [error,setError]=useState('');
  async function refresh(){try{setStatus(await request<S['RuntimeStatus']>('/api/studio/runtime'));setKeys(await request<S['ApplicationKeyMetadata'][]>('/api/studio/keys'));}catch(e){setError(String(e));}}
  useEffect(()=>{void refresh();},[]);
  return <details><summary>Application keys & runtime status</summary>
    <p role="status">{status ? `${status.mode} · ${status.detail}` : 'Loading actual runtime status…'}</p>
    <p>Application keys are separate from upstream credentials. Keys below expire after one hour, allow only the named immutable chat alias, and have a $0.01 lifetime cap plus server rate limits. Policy and operator budgets still apply. No provider key is accepted here.</p>
    <label>Allowed saved alias<input value={alias} onChange={e=>setAlias(e.target.value)} /></label>
    <button disabled={!status?.installed||!identifier.test(alias)||!!secret} onClick={async()=>{try{setError('');const result=await request<S['IssuedKey']>('/api/studio/keys', {execution_schema:'2.0',expires_at:new Date(Date.now()+3600000).toISOString(), scopes:['models:read','chat:complete','runs:read'],alias_ids:[alias],workflow_policies:[],max_cost_micro_usd:10000} satisfies S['KeyIssueRequest']);setSecret(result.secret);await refresh();}catch(e){setError(String(e));}}}>Issue scoped application key</button>
    {secret&&<div className="notice"><p>Shown once. Not stored in browser storage. Copy securely, then hide.</p><input aria-label="New application key" type="password" readOnly value={secret}/><button onClick={async()=>{try{await navigator.clipboard.writeText(secret);}catch{setError('Clipboard unavailable');}}}>Copy new key</button><button onClick={()=>setSecret('')}>Hide key permanently</button></div>}
    <ul>{keys.map(k=><li key={k.id}>{k.prefix} · expires {k.expires_at} · {k.revoked_at?'revoked':'issued (not proof of a working provider)'} {!k.revoked_at&&<button className="secondary" onClick={async()=>{try{await request(`/api/studio/keys/${k.id}/revoke`,{});setSecret('');await refresh();}catch(e){setError(String(e));}}}>Revoke</button>}</li>)}</ul>
    {error&&<p className="error" role="alert">{error}</p>}
  </details>;
}

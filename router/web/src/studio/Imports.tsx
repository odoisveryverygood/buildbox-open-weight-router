import { useState } from 'react';
import { request } from './api';
import { importRows, type S } from './model';
export default function Imports({onImport}: {onImport:(rows:S['ImportedSample'][])=>void}) {
  const [text,setText]=useState(''), [format,setFormat]=useState<'text'|'json'|'jsonl'>('text'), [inputName,setInputName]=useState('text');
  const [dataClass,setDataClass]=useState<S['ImportedSample']['data_class']>('tenant_private'), [processing,setProcessing]=useState<S['ImportedSample']['processing']>('local_only');
  const [consent,setConsent]=useState(false), [reviewed,setReviewed]=useState(false), [redact,setRedact]=useState('email,token,password,api_key'), [retention,setRetention]=useState(1);
  const [preview,setPreview]=useState<S['ImportedSample'][]>([]), [busy,setBusy]=useState(false), [error,setError]=useState(''), [saved,setSaved]=useState<string[]>([]);
  function reset() {setPreview([]); setReviewed(false); setConsent(false); setError('');}
  async function save() {
    setBusy(true); setError('');
    const done:S['ImportedSample'][]=[];
    try {
      for (const sample of preview) { const row=await request<S['ImportedSample']>('/api/studio/imports',sample); done.push(row); }
      setPreview([]); setText(''); setReviewed(false);
    } catch(e) {setError(`${String(e)}. ${done.length} rows saved before failure. Inspect saved IDs; no automatic retry.`); setPreview([]);}
    finally {setSaved(old=>[...old,...done.map(x=>x.id)]); onImport(done); setBusy(false);}
  }
  return <section><h2>Representative samples</h2><p>Samples remain in memory until you explicitly import. Server tenancy and retention apply. A trace is data, never permission to call its tools.</p>
    <fieldset disabled={busy} onChange={()=>setPreview([])}><div className="form-grid"><label>Sample format<select value={format} onChange={e=>{setFormat(e.target.value as typeof format);reset();}}><option value="text">Text</option><option value="json">JSON record</option><option value="jsonl">JSONL records (≤20)</option></select></label><label>Text input name<input value={inputName} onChange={e=>{setInputName(e.target.value);reset();}} /></label></div>
    <label>Paste samples (64 KiB maximum)<textarea rows={5} value={text} onChange={e=>{setText(e.target.value);reset();}} placeholder={'{"inputs":{"text":"Synthetic document"},"expected_output":null}'} /></label>
    <label>Or choose a local file<input type="file" accept=".txt,.json,.jsonl" onChange={async e=>{const file=e.target.files?.[0]; if (!file)return; reset(); if(file.size>65536){setError('File exceeds 64 KiB; nothing read or uploaded.');return;} setText(await file.text());}} /></label>
    <div className="form-grid"><label>Data class<select value={dataClass} onChange={e=>{setDataClass(e.target.value as typeof dataClass);reset();}}><option value="tenant_private">Tenant-private</option><option value="synthetic">Synthetic (no real personal data)</option></select></label><label>Permitted processing<select value={processing} onChange={e=>{setProcessing(e.target.value as typeof processing);reset();}}><option value="local_only">Local only</option><option value="approved_hosted">Approved external provider</option></select></label><label>Redact these JSON keys recursively<input value={redact} onChange={e=>{setRedact(e.target.value);reset();}} /></label><label>Retention days<input type="number" min="1" max="30" value={retention} onChange={e=>{setRetention(Number(e.target.value));reset();}} /></label></div>
    <p className="hint">Key redaction does not detect secrets inside text. Remove sensitive content manually. Past model answers belong in observed_output, not expected_output. Expected answers are user assertions, not verified ground truth.</p>
    <label className="check"><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)} />I reviewed the sample and redaction choices.</label>
    {processing==='approved_hosted' && <label className="check"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)} />I consent to external processing for these samples, subject to server permissions.</label>}
    <button className="secondary" onClick={()=>{try {setPreview(importRows(text,format,{inputName,dataClass,processing,reviewed,consent,redact:redact.split(',').map(x=>x.trim()).filter(Boolean),retention}));setError('');}catch(e){setError(String(e));}}}>Review import payload</button></fieldset>
    {error&&<p role="alert" className="error">{error}</p>}
    {!!preview.length&&<><h3>{preview.length} records ready for review</h3><pre>{JSON.stringify(preview,null,2)}</pre><button disabled={busy} onClick={save}>{busy?'Importing…':'Confirm import to this workspace'}</button></>}
    {!!saved.length&&<p role="status">Saved sample IDs: {saved.join(', ')}. Copy IDs to recover after reload; sample text is not stored in browser storage.</p>}
    <details><summary>Held-out evaluation and trace limitations</summary><p>JSON/JSONL records support split (tuning, holdout, unspecified), expected_reviewed, output_schema and tool_schemas. Split labels are user-declared, not proof of an uncontaminated holdout. Exact-match checks run only against explicitly reviewed expected answers. Schema checks do not prove semantic accuracy. Imported tool schemas are inert data and never grant execution authority.</p></details>
  </section>;
}

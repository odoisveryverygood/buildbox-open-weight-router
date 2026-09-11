import { useState } from 'react';
import { request } from './api';
import { policyPath, type S } from './model';

export default function EditPolicy({value, onProposal}:{value:S['PolicyView'];onProposal:(p:S['ExecutablePolicy'])=>void}) {
  const [instruction,setInstruction]=useState(''),[stage,setStage]=useState(''),[pin,setPin]=useState(''),[exclude,setExclude]=useState(''),[schema,setSchema]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  return <details><summary>Change a model pin, exclude configurations, or make one stage cheaper</summary>
    <p>Server proposes the next draft against the same pinned evidence. Review the diff before saving. No old admission or measured-quality claim carries forward.</p>
    <label>Targeted edit instruction<input value={instruction} onChange={e=>setInstruction(e.target.value)} placeholder="keep the research model but make extraction cheaper" /></label>
    <div className="form-grid"><label>Stage to pin or structure<select value={stage} onChange={e=>setStage(e.target.value)}><option value="">Choose an LLM stage</option>{value.policy.stages.filter(s=>s.configuration_id).map(s=><option key={s.node_id}>{s.node_id}</option>)}</select></label>
      <label>Exact configuration ID (optional)<input value={pin} onChange={e=>setPin(e.target.value)} /></label>
      <label>Exclude configuration IDs, comma separated<input value={exclude} onChange={e=>setExclude(e.target.value)} /></label></div>
    <label>Strict output JSON Schema for selected stage (optional)<textarea rows={3} value={schema} onChange={e=>setSchema(e.target.value)} placeholder={'{"type":"object","properties":{"category":{"type":"string"}},"required":["category"],"additionalProperties":false}'} /></label>
    <p>Changing output types must preserve downstream bindings. API/self-host restrictions belong to a new planning version. Unknown mandatory capabilities remain blocked at dispatch.</p>
    <button className="secondary" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{
      if((pin||schema)&&!stage)throw new Error('Select the stage to change.');
      const body:S['PolicyEditRequest']={execution_schema:'2.0',cheaper_stage_ids:[],instruction,pins:pin?{[stage]:pin}:{},exclude_configuration_ids:exclude.split(',').map(x=>x.trim()).filter(Boolean),output_schemas:schema?{[stage]:JSON.parse(schema)}:{}};
      onProposal(await request<S['ExecutablePolicy']>(`${policyPath(value.policy)}/propose-edit`,body));
    }catch(e){setError(String(e));}finally{setBusy(false);}}}>Propose server-validated edit</button>
    {error&&<p role="alert" className="error">{error}</p>}
  </details>;
}

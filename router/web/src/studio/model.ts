import type { components } from '../generated/api';
export type S = components['schemas'];
export type Ref = S['VersionRef'];
export const identifier = /^[A-Za-z0-9_-]{1,80}$/;
export const ref = (id: string, version: number): Ref => ({execution_schema: '2.0', id, version});
export const refKey = (value: Ref) => `${value.id}@${value.version}`;
export function parseRef(value: string): Ref {
  const [id, version, extra] = value.trim().split('@');
  if (extra || !identifier.test(id) || !/^[1-9][0-9]*$/.test(version) || !Number.isSafeInteger(Number(version))) throw new Error('Use an exact policy-id@version.');
  return ref(id, Number(version));
}
export function policyPath(value: Ref) { return `/api/studio/policies/${value.id}/versions/${value.version}`; }
export const budget = (models = 0, tools = 0): S['ExecutionBudget'] => ({execution_schema:'2.0', max_attempts:1, max_cost_micro_usd:0, max_model_calls:models, max_tool_calls:tools, max_input_tokens:2048, max_output_tokens:512, timeout_ms:30000, max_retries:0});
export function diff(before: unknown, after: unknown, path = ''): string[] {
  if (JSON.stringify(before) === JSON.stringify(after)) return [];
  if (before && after && typeof before === 'object' && typeof after === 'object' && !Array.isArray(before) && !Array.isArray(after)) {
    const a = before as Record<string, unknown>, b = after as Record<string, unknown>;
    return [...new Set([...Object.keys(a), ...Object.keys(b)])].flatMap(key => diff(a[key], b[key], path ? `${path}.${key}` : key));
  }
  return [`${path || 'Draft'}: ${JSON.stringify(before) ?? 'unset'} → ${JSON.stringify(after) ?? 'unset'}`];
}
// Prevent malformed advanced-editor JSON from crashing the view. This is a
// presentation guard only; canonical server validation remains authoritative.
export function editableShape(before: unknown, after: unknown): void {
  if (before === null) {if(after !== null && typeof after !== 'string')throw new Error('Invalid nullable editor value.');return;}
  if (Array.isArray(before)) {
    if(!Array.isArray(after)||after.length!==before.length)throw new Error('Keep the saved stage/prompt structure; edit the workflow in Planning first.');
    before.forEach((value,i)=>editableShape(value,after[i]));return;
  }
  if (typeof before === 'object') {
    if(!after||typeof after !== 'object'||Array.isArray(after))throw new Error('Expected a typed object in the editor.');
    const a=before as Record<string,unknown>,b=after as Record<string,unknown>;
    if(Object.keys(a).sort().join()!==Object.keys(b).sort().join())throw new Error('Preserve canonical field names; unsupported fields are not accepted.');
    Object.keys(a).forEach(key=>editableShape(a[key],b[key]));return;
  }
  if(typeof before !== typeof after || (typeof after==='number'&&!Number.isFinite(after)))throw new Error('Keep the declared JSON value types.');
}
export function draftPolicy(view: S['PlanView']): S['ExecutablePolicy'] {
  const result = view.result, workflow = result?.workflow, catalog = result?.catalog;
  if (!workflow || !catalog || view.stale) throw new Error('A current saved workflow and pinned catalog are required.');
  const prompts: S['PromptRevision'][] = [];
  const stages: S['ExecutableStage'][] = workflow.nodes.map(node => {
    if (node.kind === 'bounded_agent') throw new Error(`${node.id}: bounded agents are planning-only in the frozen sandbox contract.`);
    if (!Object.keys(node.inputs ?? {}).length) throw new Error(`${node.id}: input bindings are missing. Edit the workflow graph and save a new plan version first.`);
    if (node.kind === 'code' && (Object.keys(node.inputs ?? {}).join() !== 'text' || node.outputs.join() !== 'result')) throw new Error(`${node.id}: sandbox text operations require text input → result output. Use the graph rename proposal in Clarification and edits.`);
    const input_types = Object.fromEntries(Object.keys(node.inputs ?? {}).map(key => [key, 'text' as const]));
    const output_types = Object.fromEntries(node.outputs.map(key => [key, 'text' as const]));
    let prompt: Ref | null = null, configuration_id: string | null = null;
    if (node.kind === 'llm') {
      configuration_id = result.recommendation?.assignments.find(a => a.node_id === node.id)?.configuration_id ?? null;
      if (!configuration_id) throw new Error(`${node.id}: no server-selected configuration. Resolve planning blockers first.`);
      const id = crypto.randomUUID(); prompt = ref(id, 1);
      prompts.push({...prompt, template: `${node.purpose}\n${Object.keys(input_types).map(key => `${key}: {{${key}}}`).join('\n')}`, variables:input_types, parent:null, engine:'literal_placeholders_v1'});
    }
    return {execution_schema:'2.0', node_id:node.id, input_types, output_types, prompt, configuration_id,
      fallback_configuration_ids:[], route_requirements:null, response_format:null,
      workload_profile:null, validation_rules:[], fallback_on:[],
      operation:null, allowed_tool_ids:node.kind === 'tool' && node.tool_id ? [node.tool_id] : [],
      budget:budget(node.kind === 'llm' ? 1 : 0, node.kind === 'tool' ? 1 : 0), stop:{execution_schema:'2.0', on_error:'stop', on_budget_exhausted:'stop', on_cancel:'stop_before_next_dispatch', on_human_approval:'pause'}};
  });
  return {execution_schema:'2.0', id:`studio-${crypto.randomUUID()}`, version:1, plan:ref(view.plan.id, view.plan.version), workflow, catalog_id:catalog.id,
    input_types:Object.fromEntries(workflow.inputs.map(key => [key, 'text' as const])), stages, prompts, variant:null,
    catalog_digest:null, circuit_policy:null, router_policy_ref:null, routing_decision_id:null,
    budget:budget(stages.reduce((n,s) => n+s.budget.max_model_calls,0), stages.reduce((n,s) => n+s.budget.max_tool_calls,0)), quality:'untested_provisional', environment:'sandbox', production_approved:false};
}
export function parseInputs(text: string, types: S['ExecutablePolicy']['input_types']): S['WorkflowRunRequest']['inputs'] {
  if (new TextEncoder().encode(text).length > 65536) throw new Error('Sample exceeds the 64 KiB studio limit.');
  const value = JSON.parse(text);
  if (!value || Array.isArray(value) || typeof value !== 'object' || Object.keys(value).sort().join() !== Object.keys(types).sort().join()) throw new Error('Sample keys must exactly match the pinned workflow input names.');
  for (const [key, type] of Object.entries(types)) {
    if (type !== 'json' && typeof value[key] !== (type === 'text' ? 'string' : type)) throw new Error(`Input ${key} must be ${type}.`);
  }
  return value;
}
export function renderPrompt(prompt: S['PromptRevision'], inputs: S['WorkflowRunRequest']['inputs']) {
  return prompt.template.replace(/\{\{([A-Za-z0-9_-]+)\}\}/g, (_, key: string) => {
    if (!(key in inputs)) return `[upstream binding: ${key}]`;
    return typeof inputs[key] === 'string' ? inputs[key] as string : JSON.stringify(inputs[key]);
  });
}
// UI intake policy, not a competing transport schema. Wire records use generated types.
export function importRows(text: string, format: 'text' | 'json' | 'jsonl', options: {
  inputName:string; dataClass:S['ImportedSample']['data_class']; processing:S['ImportedSample']['processing'];
  consent:boolean; reviewed:boolean; redact:string[]; retention:number;
}): S['ImportedSample'][] {
  if (new TextEncoder().encode(text).length > 65536) throw new Error('Import exceeds 64 KiB.');
  if (!text.trim()) throw new Error('Provide a representative sample.');
  if (!options.reviewed) throw new Error('Review sensitive content and redaction before import.');
  if (options.processing === 'approved_hosted' && !options.consent) throw new Error('Explicit external-processing consent is required.');
  if (!Number.isInteger(options.retention) || options.retention < 1 || options.retention > 30) throw new Error('Retention must be 1–30 days.');
  if (format === 'text' && !identifier.test(options.inputName)) throw new Error('Use a valid workflow input name.');
  const raw: unknown[] = format === 'text' ? [{inputs:{[options.inputName]:text}}] : format === 'jsonl' ? text.trim().split('\n').map(line => JSON.parse(line)) : [JSON.parse(text)];
  if (raw.length > 20) throw new Error('At most 20 samples per import.');
  function scrub(value: unknown, depth = 0): unknown {
    if (depth > 20) throw new Error('Sample nesting exceeds 20 levels.');
    if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('Non-finite numbers are not supported.');
    if (Array.isArray(value)) return value.map(x => scrub(x, depth+1));
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key,v]) => {
      if (['__proto__','constructor','prototype'].includes(key)) throw new Error('Unsafe object key in sample.');
      return [key, options.redact.includes(key) ? '[REDACTED]' : scrub(v,depth+1)];
    }));
    return value;
  }
  return raw.map((rawRow, i) => {
    if (!rawRow || Array.isArray(rawRow) || typeof rawRow !== 'object') throw new Error(`Row ${i+1}: expected an object with inputs.`);
    const row = scrub(rawRow) as Record<string, unknown>;
    const allowed = ['inputs','expected_output','observed_output','kind','source_label','original_observed_at','split','expected_reviewed','output_schema','tool_schemas'];
    if (Object.keys(row).some(key => !allowed.includes(key))) throw new Error(`Row ${i+1}: unsupported fields (including free-form rubrics or tenant IDs). They are not silently discarded.`);
    if(row.split!==undefined&&!['tuning','holdout','unspecified'].includes(String(row.split)))throw new Error('Split must be tuning, holdout or unspecified.');
    if(row.expected_reviewed!==undefined&&typeof row.expected_reviewed!=='boolean')throw new Error('Expected-answer review must be explicit true/false.');
    if(row.expected_reviewed&&row.expected_output==null)throw new Error('Reviewed expected output required.');
    if(row.output_schema!=null&&(typeof row.output_schema!=='object'||Array.isArray(row.output_schema)))throw new Error('Output schema must be an object. Server validates the strict subset.');
    if(row.tool_schemas!==undefined&&(!Array.isArray(row.tool_schemas)||row.tool_schemas.length>10))throw new Error('At most 10 typed tool schemas, never execution permission.');
    if (!row.inputs || Array.isArray(row.inputs) || typeof row.inputs !== 'object' || !Object.keys(row.inputs).length || Object.keys(row.inputs).some(key => !identifier.test(key))) throw new Error(`Row ${i+1}: inputs must have valid named keys.`);
    if (row.kind !== undefined && row.kind !== 'sample' && row.kind !== 'trace') throw new Error('Kind must be sample or trace.');
    if (row.original_observed_at != null && (typeof row.original_observed_at !== 'string' || !/(Z|[+-]\d\d:\d\d)$/.test(row.original_observed_at) || !Number.isFinite(Date.parse(row.original_observed_at)))) throw new Error('Original observation date must include a timezone.');
    if (row.source_label !== undefined && (typeof row.source_label !== 'string' || !row.source_label.trim() || row.source_label.length > 200)) throw new Error('Source label must be 1–200 characters.');
    return {execution_schema:'2.0', id:crypto.randomUUID(), kind:(row.kind ?? 'sample') as S['ImportedSample']['kind'], inputs:row.inputs as S['ImportedSample']['inputs'], expected_output:row.expected_output ?? null, observed_output:row.observed_output ?? null, source_label:(row.source_label ?? `Studio import ${i+1}`) as string, original_observed_at:(row.original_observed_at ?? null) as string | null, imported_at:new Date().toISOString(), data_class:options.dataClass, processing:options.processing, retention_days:options.retention, provenance:'user_imported_not_verified', split:(row.split??'unspecified') as S['ImportedSample']['split'], expected_reviewed:(row.expected_reviewed??false) as boolean, output_schema:(row.output_schema??null) as S['ImportedSample']['output_schema'],tool_schemas:(row.tool_schemas??[]) as S['ImportedSample']['tool_schemas']};
  });
}
export function sourceLink(value: string | null | undefined): string | undefined {
  try { const u = new URL(value ?? ''); return u.protocol === 'https:' && !u.username && !u.password && ['huggingface.co','openrouter.ai'].includes(u.hostname) ? u.href : undefined; } catch { return undefined; }
}
export function money(micro: number | null | undefined) { return micro == null ? 'Unknown' : `$${(micro/1_000_000).toFixed(6)}`; }
export function apiExamples(alias: S['RouteAlias'], origin: string, outputLimit = 1) {
  const url = new URL(origin);
  if (!['https:','http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('API base must be an origin, with no credentials or path.');
  if (url.protocol === 'http:' && !['localhost','127.0.0.1','[::1]'].includes(url.hostname)) throw new Error('Non-loopback API origins require HTTPS.');
  const body: S['ChatCompletionRequest'] = {model:alias.id, messages:[{role:'user', content:'Your stage input here'}], max_tokens:Math.max(1,Math.min(128,outputLimit)), stream:false};
  return {
    curl:[`# Set BUILDBOX_API_BASE=${url.origin}`, '# Set BUILDBOX_API_KEY using your approved application key flow', 'curl "$BUILDBOX_API_BASE/v1/chat/completions" \\', '  -H "Authorization: Bearer $BUILDBOX_API_KEY" \\', '  -H "Content-Type: application/json" \\', '  -H "Idempotency-Key: $BUILDBOX_REQUEST_ID" \\', `  --data '${JSON.stringify(body)}'`].join('\n'),
    python:`import os, json, urllib.request\nbody = ${JSON.stringify(body).replace(':false', ':False')}\nrequest = urllib.request.Request(os.environ["BUILDBOX_API_BASE"] + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + os.environ["BUILDBOX_API_KEY"], "Content-Type": "application/json", "Idempotency-Key": os.environ["BUILDBOX_REQUEST_ID"]})\nwith urllib.request.urlopen(request, timeout=120) as response:\n    print(response.read().decode())`,
    typescript:`const response = await fetch(process.env.BUILDBOX_API_BASE + '/v1/chat/completions', {\n  method: 'POST',\n  headers: {'Authorization': 'Bearer ' + process.env.BUILDBOX_API_KEY, 'Content-Type': 'application/json', 'Idempotency-Key': process.env.BUILDBOX_REQUEST_ID!},\n  body: JSON.stringify(${JSON.stringify(body, null, 2)})\n});\nif (!response.ok) throw new Error('Inspect request status before retrying: ' + response.status);\nconsole.log(await response.json());`,
  };
}

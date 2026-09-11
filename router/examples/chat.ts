// Node 22+ TypeScript stripping, no custom SDK or direct upstream path.
const args = process.argv.slice(2);
const base = process.env.BUILDBOX_API_BASE?.replace(/\/$/, '');
const key = process.env.BUILDBOX_API_KEY;
if (!base || !key) throw new Error('Set BUILDBOX_API_BASE and BUILDBOX_API_KEY securely.');
async function call(body?: Record<string, unknown>) {
  const response = await fetch(base + (body ? '/v1/chat/completions' : '/v1/models'), {
    method: body ? 'POST' : 'GET',
    headers: {'Authorization':'Bearer '+key,'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(120000),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}; inspect persisted request state before any retry.`);
  return response;
}
if (args.includes('--list')) console.log(await (await call()).text());
else {
  const alias = args[args.indexOf('--alias') + 1];
  if (!args.includes('--alias') || !alias) throw new Error('--alias is required');
  const messages: Record<string, unknown>[] = [{role:'user',content:'What is the shipping policy? Use the read-only support lookup if provided.'}];
  const body: Record<string, unknown> = {model:alias,messages,max_tokens:32,stream:args.includes('--stream')};
  if(args.includes('--tool-roundtrip')) {
    if(body.stream) throw new Error('Tool roundtrip example is nonstream');
    body.tools=[{type:'function',function:{name:'lookup_support',strict:true,parameters:{type:'object',properties:{key:{type:'string'}},required:['key'],additionalProperties:false}}}];
  }
  const response=await call(body);
  if(body.stream) {
    const reader=response.body!.getReader(); const decoder=new TextDecoder();
    while(true){const {value,done}=await reader.read();if(done)break;process.stdout.write(decoder.decode(value,{stream:true}));}
    process.stdout.write(decoder.decode());
  } else {
    let result=await response.json();
    if(args.includes('--tool-roundtrip')){
      const reply=result.choices[0].message, calls=reply.tool_calls??[];
      if(calls.length!==1)throw new Error('Expected one read-only tool call; nothing executed');
      const tool=calls[0], arguments_=JSON.parse(tool.function.arguments);
      if(tool.function.name!=='lookup_support'||Object.keys(arguments_).join()!=='key'||arguments_.key!=='shipping')throw new Error('Undeclared/write/unknown tool request denied');
      messages.push(reply,{role:'tool',tool_call_id:tool.id,content:'SIMULATED read-only policy: shipping takes 3 days.'});
      result=await (await call(body)).json();
    }
    console.log(JSON.stringify(result));
  }
}

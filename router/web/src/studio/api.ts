// One same-origin canonical API path; no provider credentials or direct inference.
export async function request<T>(path: string, body?: unknown, key?: string): Promise<T> {
  if (!/^\/api\/(studio|sandbox)\//.test(path)) throw new Error('Unexpected studio API path.');
  const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 125000);
  try {
    const response = await fetch(path, {signal:controller.signal, cache:'no-store', ...(body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json', ...(key ? {'Idempotency-Key':key} : {})}, body:JSON.stringify(body)})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.message ?? result.error?.message ?? `Request rejected (${response.status}); inspect the saved state before retrying.`);
    return result as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('Request timed out; acceptance/accounting may be uncertain. Reload its ID before any new run.');
    throw error;
  } finally { clearTimeout(timeout); }
}

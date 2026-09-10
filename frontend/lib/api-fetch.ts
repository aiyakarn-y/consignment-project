// Large files bypass Vercel Functions. Domain routes still receive multipart
// requests after the backend reads the private, single-use staging object.
export async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set('X-Consign-Fetch', '1');
  let body = init.body;
  if (body instanceof FormData) {
    const size = Array.from(body.values()).reduce((total, v) => total + (v instanceof Blob ? v.size : v.length), 0);
    if (size > 2 * 1024 * 1024) {
      const config = await fetch('/cloud-storage', { signal: init.signal });
      if (!config.ok) return config;
      if ((await config.json()).enabled) {
        const prepared = await fetch('/cloud-storage', { method: 'POST', signal: init.signal });
        if (!prepared.ok) return prepared;
        const target = await prepared.json();
        const encoded = new Response(body);
        const contentType = encoded.headers.get('content-type')!;
        const content = await encoded.blob();
        if (content.size > 260 * 1024 * 1024) throw new Error('ไฟล์รวมใหญ่เกิน 260 MiB');
        const { put } = await import('@vercel/blob/client');
        await put(target.pathname, content, { access: 'private', token: target.token, contentType: 'application/octet-stream', multipart: true, abortSignal: init.signal || undefined });
        headers.set('Content-Type', contentType);
        headers.set('X-Consign-Upload', target.key);
        body = undefined;
      }
    }
  }
  const response = await fetch(url, { ...init, body, headers });
  if (!response.ok || response.headers.get('X-Consign-Download') !== '1') return response;
  const { download } = await response.json();
  const signed = await fetch(download, { headers: { 'X-Consign-Fetch': '1' }, signal: init.signal });
  if (!signed.ok) return signed;
  const { url: signedUrl } = await signed.json();
  const file = await fetch(signedUrl, { credentials: 'omit', signal: init.signal });
  if (!file.ok) throw new Error('ดาวน์โหลดไม่สำเร็จ กรุณาลองใหม่');
  const resultHeaders = new Headers(response.headers);
  resultHeaders.delete('content-length');
  resultHeaders.set('content-type', file.headers.get('content-type') || 'application/octet-stream');
  return new Response(file.body, { status: 200, headers: resultHeaders });
}

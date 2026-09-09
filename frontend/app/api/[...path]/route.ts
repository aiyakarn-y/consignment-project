/** Same-origin API gateway. Backend URL is resolved at runtime for Docker/local. */
import { type NextRequest } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

async function proxy(request: NextRequest) {
  const base = process.env.CONSIGN_BACKEND_URL || 'http://127.0.0.1:8100';
  const incoming = new URL(request.url);
  const target = new URL(incoming.pathname + incoming.search, base);
  const headers = new Headers(request.headers);
  for (const name of ['host', 'connection', 'transfer-encoding', 'content-length', 'accept-encoding']) headers.delete(name);
  try {
    const init = {
      method: request.method,
      headers,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
      signal: request.signal,
      redirect: 'manual' as const,
      duplex: 'half',
    };
    const upstream = await fetch(target, init as RequestInit);
    const responseHeaders = new Headers(upstream.headers);
    for (const name of ['connection', 'transfer-encoding', 'content-encoding', 'content-length']) responseHeaders.delete(name);
    responseHeaders.set('Cache-Control', 'no-store');
    return new Response(upstream.body, {status: upstream.status, headers: responseHeaders});
  } catch {
    return Response.json({detail: 'ติดต่อ Backend ไม่ได้ กรุณาตรวจสถานะระบบ'}, {status: 502});
  }
}

export {proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE};

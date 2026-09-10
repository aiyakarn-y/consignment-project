import { createHmac, timingSafeEqual } from 'node:crypto';
import { issueSignedToken, presignUrl } from '@vercel/blob';
import { requireBetaAuth } from '../../lib/beta-auth';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export async function GET(request: Request) {
  const denied = requireBetaAuth(request); if (denied) return denied;
  const secret = process.env.BLOB_READ_WRITE_TOKEN;
  const prefix = process.env.CONSIGN_BLOB_PREFIX;
  if (!secret || !prefix || process.env.CONSIGN_STORAGE_DRIVER !== 'vercel_blob') return new Response('Cloud storage unavailable', { status: 503 });
  try {
    const ticket = new URL(request.url).searchParams.get('ticket') || '';
    if (ticket.length > 4096) throw new Error('Invalid ticket');
    const [encoded, signature, extra] = ticket.split('.');
    const expected = createHmac('sha256', secret).update(encoded || '').digest('hex');
    if (extra || !/^[0-9a-f]{64}$/.test(signature || '') || !timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) throw new Error('Invalid ticket');
    const body = JSON.parse(Buffer.from(encoded, 'base64url').toString());
    if (!Number.isInteger(body.expires) || body.expires < Date.now() / 1000 || typeof body.key !== 'string' || !body.key.startsWith(prefix + '/')) throw new Error('Expired ticket');
    const key = body.key.slice(prefix.length + 1);
    if (!/^(?:imports\/[0-9a-f]{32}\/[0-9a-f]{32}\.(?:xlsx|pdf)|exports\/[0-9a-f]{32}\.xlsx|backups\/[0-9a-zT_-]+\.zip|[0-9a-f]{32}\.(?:xlsx|pdf))$/.test(key)) throw new Error('Invalid path');
    const delegation = await issueSignedToken({ token: secret, pathname: body.key, operations: ['get'], validUntil: Date.now() + 5 * 60 * 1000 });
    const { presignedUrl } = await presignUrl(delegation, { operation: 'get', access: 'private', pathname: body.key });
    if (request.headers.get('x-consign-fetch') === '1') return Response.json({ url: presignedUrl }, { headers: { 'Cache-Control': 'no-store' } });
    return new Response(null, { status: 303, headers: { Location: presignedUrl, 'Cache-Control': 'no-store' } });
  } catch {
    return Response.json({ detail: 'Download link expired or unavailable; please download again' }, { status: 403 });
  }
}

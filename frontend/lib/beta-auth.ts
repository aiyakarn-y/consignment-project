import { createHash, timingSafeEqual } from 'node:crypto';

export function requireBetaAuth(request: Request): Response | null {
  const mode = process.env.CONSIGN_BETA_MODE;
  if (mode === '0' || (mode !== '1' && process.env.VERCEL !== '1')) return null;
  const password = process.env.CONSIGN_BETA_PASSWORD;
  if (!password) return new Response('Beta credentials are not configured', { status: 503 });
  const match = /^Basic ([A-Za-z0-9+/]+={0,2})$/i.exec(request.headers.get('authorization') || '');
  const digest = (value: Buffer) => createHash('sha256').update(value).digest();
  const expected = Buffer.from(`${process.env.CONSIGN_BETA_USER || 'beta'}:${password}`);
  if (!match || !timingSafeEqual(digest(Buffer.from(match[1], 'base64')), digest(expected))) {
    return new Response('Beta login required', { status: 401, headers: {
      'WWW-Authenticate': 'Basic realm="ConsignmentSystem Beta", charset="UTF-8"', 'Cache-Control': 'no-store',
    } });
  }
  return null;
}

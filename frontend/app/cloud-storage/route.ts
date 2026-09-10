import { randomUUID } from 'node:crypto';
import { generateClientTokenFromReadWriteToken } from '@vercel/blob/client';
import { requireBetaAuth } from '../../lib/beta-auth';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export async function GET(request: Request) {
  const denied = requireBetaAuth(request); if (denied) return denied;
  return Response.json({ enabled: process.env.CONSIGN_STORAGE_DRIVER === 'vercel_blob' }, { headers: { 'Cache-Control': 'no-store' } });
}
export async function POST(request: Request) {
  const denied = requireBetaAuth(request); if (denied) return denied;
  const prefix = process.env.CONSIGN_BLOB_PREFIX;
  if (process.env.CONSIGN_STORAGE_DRIVER !== 'vercel_blob' || !prefix || !/^[A-Za-z0-9_-]{1,80}$/.test(prefix) || !process.env.BLOB_READ_WRITE_TOKEN) {
    return Response.json({ detail: 'Cloud storage is not configured' }, { status: 503 });
  }
  const key = `staging/${randomUUID().replaceAll('-', '')}`;
  const pathname = `${prefix}/${key}`;
  try {
    const token = await generateClientTokenFromReadWriteToken({
      token: process.env.BLOB_READ_WRITE_TOKEN, pathname, addRandomSuffix: false,
      allowOverwrite: false, maximumSizeInBytes: 260 * 1024 * 1024,
      allowedContentTypes: ['application/octet-stream'], validUntil: Date.now() + 15 * 60 * 1000,
    });
    return Response.json({ key, pathname, token }, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return Response.json({ detail: 'Cannot prepare cloud upload' }, { status: 503 });
  }
}

import { NextResponse, type NextRequest } from 'next/server';
import { requireBetaAuth } from './lib/beta-auth';

export function proxy(request: NextRequest) {
  const denied = requireBetaAuth(request);
  if (denied) return denied;
  const response = NextResponse.next();
  if (process.env.CONSIGN_BETA_MODE === '1' || process.env.VERCEL === '1') response.headers.set('Cache-Control', 'no-store');
  return response;
}

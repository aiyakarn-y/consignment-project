import type { NextConfig } from 'next';
const nextConfig: NextConfig = {
  output: 'standalone',
  distDir: process.env.CONSIGN_NEXT_DIR || '.next',
};
export default nextConfig;

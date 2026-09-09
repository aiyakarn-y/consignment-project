import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'ConsignmentSystem · Sales workspace', description: 'นำเข้า ตรวจสอบ และส่งออกยอดขายฝากขาย' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="th"><body>{children}</body></html>;
}

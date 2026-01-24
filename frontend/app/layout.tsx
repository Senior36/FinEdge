import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Sidebar } from '@/components/layout';
import { MainContent } from '@/components/layout';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'FinEdge - Market Intelligence Platform',
  description: 'AI-powered stock market analysis for Indian and US markets',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <MainContent>{children}</MainContent>
        </div>
      </body>
    </html>
  );
}

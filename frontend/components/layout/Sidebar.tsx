'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BarChart3,
  Bookmark,
  Building2,
  CandlestickChart,
  ChevronDown,
  Grid2X2,
  Menu,
  MessageSquareText,
  Plus,
  Search,
  TrendingUp,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: <Grid2X2 size={15} /> },
  { label: 'Analyse Stock', href: '/analyze', icon: <Search size={15} /> },
  { label: 'Fundamental', href: '/fundamental', icon: <Building2 size={15} /> },
  { label: 'Technical', href: '/technical', icon: <CandlestickChart size={15} /> },
  { label: 'Sentiment', href: '/analyze', icon: <MessageSquareText size={15} /> },
  { label: 'Results', href: '/results', icon: <BarChart3 size={15} /> },
];

export function Sidebar() {
  const pathname = usePathname();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const isActive = (href: string, label: string) => {
    if (label === 'Sentiment') {
      return pathname === '/analyze';
    }
    if (href === '/dashboard') {
      return pathname === '/' || pathname.startsWith('/dashboard');
    }
    return pathname.startsWith(href);
  };

  return (
    <>
      <button
        onClick={() => setIsMobileOpen(!isMobileOpen)}
        className="fixed left-4 top-4 z-50 rounded-full border border-slate-200 bg-white p-2 text-slate-900 shadow-sm lg:hidden"
        aria-label="Toggle navigation"
      >
        {isMobileOpen ? <X size={22} /> : <Menu size={22} />}
      </button>

      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-950/30 backdrop-blur-sm lg:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      <aside
        className={cn(
          'fixed left-0 top-0 z-50 flex h-full w-[224px] flex-col border-r border-slate-200 bg-white transition-transform duration-300 ease-in-out',
          'lg:translate-x-0',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex h-[74px] items-center border-b border-slate-200 px-5">
          <Link href="/dashboard" className="flex items-center gap-3" onClick={() => setIsMobileOpen(false)}>
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-600 text-white shadow-[0_12px_24px_-14px_rgba(37,99,235,0.8)]">
              <TrendingUp size={18} strokeWidth={2.6} />
            </div>
            <span className="text-lg font-extrabold tracking-tight text-slate-950">FinEdge</span>
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          <ul className="space-y-1">
            {navItems.map((item) => {
              const active = isActive(item.href, item.label);

              return (
                <li key={`${item.label}-${item.href}`}>
                  <Link
                    href={item.href}
                    className={cn(
                      'flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-bold transition-all duration-200',
                      active
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'text-slate-500 hover:bg-slate-50 hover:text-slate-950'
                    )}
                    onClick={() => setIsMobileOpen(false)}
                  >
                    <span className={cn(active ? 'text-emerald-600' : 'text-slate-400')}>{item.icon}</span>
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>

          <div className="mt-8 border-t border-slate-200 pt-5">
            <button className="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-[13px] font-extrabold uppercase tracking-[0.08em] text-slate-500 hover:bg-slate-50">
              <span className="flex items-center gap-2">
                <Bookmark size={15} className="text-amber-500" />
                Watchlist
              </span>
              <span className="flex items-center gap-2 text-slate-400">
                <Plus size={14} />
                <ChevronDown size={14} />
              </span>
            </button>
          </div>
        </nav>

        <div className="border-t border-slate-200 px-4 py-4 text-[11px] leading-5 text-slate-500">
          <p className="font-semibold">© 2026 FinEdge</p>
          <p>Senior Design Project</p>
        </div>
      </aside>
    </>
  );
}

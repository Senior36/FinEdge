'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  LayoutDashboard, 
  Search, 
  BarChart3, 
  Building2,
  CandlestickChart,
  History, 
  User, 
  Settings, 
  Bell,
  Moon,
  Sun,
  Menu,
  X
} from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Navigation item type
 */
interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

/**
 * Sidebar Component
 * 
 * Fixed 260px width sidebar with dark navy background (#0F172A).
 * Includes Logo area, Navigation menu, and Footer area.
 */
export function Sidebar() {
  const pathname = usePathname();
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const navItems: NavItem[] = [
    { label: 'Dashboard', href: '/dashboard', icon: <LayoutDashboard size={20} /> },
    { label: 'Technical Analysis', href: '/technical', icon: <CandlestickChart size={20} /> },
    { label: 'Fundamental Analysis', href: '/fundamental', icon: <Building2 size={20} /> },
    { label: 'Sentiment Test', href: '/analyze', icon: <Search size={20} /> },
    { label: 'Results', href: '/results', icon: <BarChart3 size={20} /> },
    { label: 'History', href: '/history', icon: <History size={20} /> },
    { label: 'Profile', href: '/profile', icon: <User size={20} /> },
  ];

  const toggleDarkMode = () => {
    setIsDarkMode(!isDarkMode);
    // TODO: Implement actual dark mode toggle logic
  };

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <>
      {/* Mobile menu button */}
      <button
        onClick={() => setIsMobileOpen(!isMobileOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-white rounded-lg shadow-lg"
      >
        {isMobileOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Mobile overlay */}
      {isMobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-0 h-full w-[260px] bg-sidebar-bg text-white flex flex-col z-50 transition-transform duration-300 ease-in-out',
          'lg:translate-x-0',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo Area */}
        <div className="p-6 border-b border-white/10">
          <Link href="/" className="flex items-center gap-3">
            {/* Blue gradient square icon */}
            <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xl">F</span>
            </div>
            <span className="text-xl font-bold">FinEdge</span>
          </Link>
        </div>

        {/* Navigation Menu */}
        <nav className="flex-1 py-6 px-4 overflow-y-auto custom-scrollbar">
          <ul className="space-y-1">
            {navItems.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200',
                    'hover:bg-white/10',
                    isActive(item.href)
                      ? 'bg-white/10 text-white'
                      : 'text-sidebar-text'
                  )}
                  onClick={() => setIsMobileOpen(false)}
                >
                  {item.icon}
                  <span className="font-medium">{item.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* Footer Area */}
        <div className="p-4 border-t border-white/10 space-y-2">
          {/* Alerts with red badge */}
          <Link
            href="/alerts"
            className="flex items-center justify-between px-4 py-3 rounded-lg hover:bg-white/10 transition-all duration-200 group"
            onClick={() => setIsMobileOpen(false)}
          >
            <div className="flex items-center gap-3">
              <Bell size={20} className="text-sidebar-text group-hover:text-white" />
              <span className="font-medium text-sidebar-text group-hover:text-white">Alerts</span>
            </div>
            <span className="bg-danger-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
              3
            </span>
          </Link>

          {/* Settings */}
          <Link
            href="/settings"
            className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-white/10 transition-all duration-200 group"
            onClick={() => setIsMobileOpen(false)}
          >
            <Settings size={20} className="text-sidebar-text group-hover:text-white" />
            <span className="font-medium text-sidebar-text group-hover:text-white">Settings</span>
          </Link>

          {/* Dark Mode Toggle */}
          <button
            onClick={toggleDarkMode}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-white/10 transition-all duration-200"
          >
            {isDarkMode ? (
              <Sun size={20} className="text-sidebar-text" />
            ) : (
              <Moon size={20} className="text-sidebar-text" />
            )}
            <span className="font-medium text-sidebar-text">
              {isDarkMode ? 'Light Mode' : 'Dark Mode'}
            </span>
          </button>
        </div>
      </aside>
    </>
  );
}

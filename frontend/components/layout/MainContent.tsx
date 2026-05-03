'use client';

import { ReactNode } from 'react';

/**
 * MainContent Component
 * 
 * Fluid right side content area with 32px padding and off-white background (#F8FAFC).
 * Provides consistent spacing and background across all pages.
 */
export interface MainContentProps {
  children: ReactNode;
  className?: string;
}

export function MainContent({ children, className = '' }: MainContentProps) {
  return (
    <main className={`finedge-shell flex-1 min-h-screen overflow-y-auto custom-scrollbar lg:ml-[224px] ${className}`}>
      <div className="mx-auto w-full max-w-[1420px] px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
        {children}
      </div>
    </main>
  );
}

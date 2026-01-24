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
    <main className={`flex-1 bg-main-bg min-h-screen overflow-y-auto custom-scrollbar ${className}`}>
      <div className="p-8">
        {children}
      </div>
    </main>
  );
}

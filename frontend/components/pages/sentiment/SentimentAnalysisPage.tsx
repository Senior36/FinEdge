'use client';

import { useState } from 'react';
import { MessageSquareText, Search } from 'lucide-react';
import { Button, Card, CardHeader, CardTitle, CardContent, Input, Tag } from '@/components/ui';
import { SentimentResults } from '@/components/analysis';
import { useSentimentStore } from '@/stores';

export default function AnalyzePage() {
  const [ticker, setTicker] = useState('');
  const [market, setMarket] = useState<'US' | 'IN'>('US');
  const [formError, setFormError] = useState<string | null>(null);

  const {
    analyzeSentiment,
    analysisStatus,
    analysisError,
    currentAnalysis,
    clearAnalysis,
  } = useSentimentStore();

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = ticker.trim().toUpperCase();

    if (!trimmed) {
      setFormError('Please enter a valid ticker.');
      return;
    }

    setFormError(null);
    try {
      await analyzeSentiment(trimmed, market);
    } catch {
      // Error state is handled by the store for UI display
    }
  };

  return (
    <div className="space-y-8">
      <div className="mx-auto max-w-5xl text-center">
        <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-extrabold uppercase tracking-[0.18em] text-slate-500 shadow-card">
          <MessageSquareText size={14} className="text-primary-600" />
          News Intelligence
        </div>
        <h1 className="mt-6 text-4xl font-extrabold tracking-[-0.04em] text-slate-950 md:text-6xl">Sentiment Analysis</h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-slate-500 md:text-base">
          Test the sentiment engine by analyzing a ticker and reviewing article-level scores.
        </p>
      </div>

      <Card className="mx-auto max-w-5xl border border-slate-200" variant="bordered" padding="none">
        <CardHeader className="mb-0 flex flex-col gap-2 border-b border-slate-200 px-6 py-5 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle className="text-xl">Run Analysis</CardTitle>
            <p className="mt-1 text-sm text-slate-500">Fetch articles, score market tone, and summarize key drivers.</p>
          </div>
          <Tag variant="neutral">Real-time articles</Tag>
        </CardHeader>
        <CardContent className="p-6">
          <form
            onSubmit={onSubmit}
            className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] gap-4 items-end"
          >
            <div className="flex flex-col">
              <Input
                label="Ticker"
                placeholder="AAPL, NVDA, RELIANCE.NS"
                value={ticker}
                onChange={(event) => setTicker(event.target.value)}
                leftIcon={<Search size={18} />}
                error={formError || undefined}
                helperText="Use official ticker symbols (US or India)."
              />
            </div>

            <div className="flex flex-col">
              <label className="block text-sm font-medium text-text-primary mb-1">
                Market
              </label>
              <select
                value={market}
                onChange={(event) => setMarket(event.target.value as 'US' | 'IN')}
                className="w-full rounded-full border border-border bg-white px-4 py-3 text-text-primary focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="US">US</option>
                <option value="IN">IN</option>
              </select>
              <p className="mt-1 text-sm text-text-secondary">
                Match the ticker suffix to the market (e.g., .NS for India).
              </p>
            </div>

            <div className="flex items-end">
              <Button
                type="submit"
                variant="primary"
                size="lg"
                fullWidth
                isLoading={analysisStatus === 'loading'}
              >
                Analyze Sentiment
              </Button>
            </div>
          </form>

          {analysisStatus === 'loading' && (
            <div className="mt-6 rounded-lg border border-border bg-white px-4 py-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-medium text-text-primary">Running sentiment analysis</p>
                <span className="text-sm text-text-secondary">This can take up to ~60s</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100 progress-indeterminate" />
              <div className="mt-3 text-xs text-text-secondary">
                Fetching fresh articles, scoring sentiment, and aggregating results.
              </div>
            </div>
          )}

          {analysisError && (
            <div className="mt-4 rounded-lg border border-danger-200 bg-danger-50 px-4 py-3 text-danger-900">
              {analysisError}
            </div>
          )}
        </CardContent>
      </Card>

      {currentAnalysis && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold text-text-primary">Latest Results</h2>
            <Button variant="secondary" onClick={clearAnalysis}>
              Clear
            </Button>
          </div>
          <SentimentResults analysis={currentAnalysis} />
        </div>
      )}
    </div>
  );
}

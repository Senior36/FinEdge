'use client';

import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui';
import { SentimentResults } from '@/components/analysis';
import { useSentimentStore } from '@/stores';

export default function ResultsPage() {
  const { currentAnalysis } = useSentimentStore();

  if (!currentAnalysis) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No Results Yet</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-text-secondary mb-4">
            Run a sentiment analysis to see article scores, trend signals, and the summary.
          </p>
          <Link
            href="/analyze"
            className="inline-flex items-center justify-center font-medium rounded-button transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 bg-primary-600 text-white hover:bg-primary-700 focus:ring-primary-500 px-4 py-2"
          >
            Go to Analyze
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-text-primary">Analysis Results</h1>
        <p className="text-text-secondary mt-2">
          Detailed sentiment breakdown for your latest analysis request.
        </p>
      </div>

      <SentimentResults analysis={currentAnalysis} />
    </div>
  );
}

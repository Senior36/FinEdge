'use client';

import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  BarChart3,
  Bookmark,
  Building2,
  CandlestickChart,
  Circle,
  FileText,
  Loader2,
  Newspaper,
  Search,
} from 'lucide-react';
import { Button, Card, CardContent, Tag } from '@/components/ui';
import {
  FUNDAMENTAL_PROFILES,
  profileFromFundamentalResponse,
  type CoverageTicker,
  type FundamentalProfile,
} from '@/components/pages/fundamental/FundamentalAnalysisPage';
import { cn, fundamentalApi, handleApiError, sentimentApi, technicalApi } from '@/lib';
import type { FundamentalAnalysisResponse, SentimentalAnalysisResponse, TechnicalAnalysisResponse } from '@/types';

type AnalysisTab = 'overview' | 'fundamental' | 'technical' | 'sentiment';
type AnalysisStatus = 'idle' | 'loading' | 'success' | 'error';
type SignalTone = 'success' | 'warning' | 'danger' | 'neutral';

interface StockSnapshot {
  ticker: CoverageTicker;
  companyName: string;
  exchange: string;
  currency: string;
  marketStatus: string;
  price: number;
  change: number;
  changePercent: number;
  preMarket: number;
  marketCap: string;
  revenue: string;
  netIncome: string;
  eps: string;
  peRatio: string;
  forwardPe: string;
  volume: string;
  weekRange: string;
  beta: string;
  nextEarnings: string;
}

interface CombinedStockAnalysis {
  ticker: CoverageTicker;
  snapshot: StockSnapshot;
  profile: FundamentalProfile;
  fundamental: FundamentalAnalysisResponse | null;
  technical: TechnicalAnalysisResponse | null;
  sentiment: SentimentalAnalysisResponse | null;
  fundamentalError: string | null;
  technicalError: string | null;
  sentimentError: string | null;
}

const DEFAULT_TICKER: CoverageTicker = 'AAPL';
const COVERAGE_TICKERS = Object.keys(FUNDAMENTAL_PROFILES) as CoverageTicker[];

const STOCK_SNAPSHOTS: Record<CoverageTicker, StockSnapshot> = {
  MSFT: {
    ticker: 'MSFT',
    companyName: 'Microsoft Corp.',
    exchange: 'NASDAQ',
    currency: 'USD',
    marketStatus: 'Market Closed · opens in 1d 15h',
    price: 428.15,
    change: 5.22,
    changePercent: 1.24,
    preMarket: 429.05,
    marketCap: '$3.2T',
    revenue: '$245.1B',
    netIncome: '$88.1B',
    eps: '11.82',
    peRatio: '36.2',
    forwardPe: '31.4',
    volume: '26.4M',
    weekRange: '309.45 - 430.82',
    beta: '0.91',
    nextEarnings: 'Jul 24, 2026',
  },
  AAPL: {
    ticker: 'AAPL',
    companyName: 'Apple Inc.',
    exchange: 'NASDAQ',
    currency: 'USD',
    marketStatus: 'Market Closed · opens in 1d 15h',
    price: 214.6,
    change: -1.38,
    changePercent: -0.64,
    preMarket: 215.1,
    marketCap: '$3.05T',
    revenue: '$385.6B',
    netIncome: '$97.0B',
    eps: '6.42',
    peRatio: '30.9',
    forwardPe: '28.5',
    volume: '54.2M',
    weekRange: '164.08 - 237.49',
    beta: '1.24',
    nextEarnings: 'Jul 31, 2026',
  },
  NVDA: {
    ticker: 'NVDA',
    companyName: 'NVIDIA Corp.',
    exchange: 'NASDAQ',
    currency: 'USD',
    marketStatus: 'Market Closed · opens in 1d 15h',
    price: 142.8,
    change: 3.14,
    changePercent: 2.25,
    preMarket: 143.35,
    marketCap: '$3.5T',
    revenue: '$130.5B',
    netIncome: '$72.9B',
    eps: '2.94',
    peRatio: '48.6',
    forwardPe: '34.8',
    volume: '48.9M',
    weekRange: '75.61 - 153.13',
    beta: '1.69',
    nextEarnings: 'Aug 27, 2026',
  },
};

const TAB_OPTIONS: Array<{ value: AnalysisTab; label: string }> = [
  { value: 'overview', label: 'Overview' },
  { value: 'fundamental', label: 'Fundamental' },
  { value: 'technical', label: 'Technical' },
  { value: 'sentiment', label: 'Sentiment' },
];

function normalizeCoverageTicker(value: string | null): CoverageTicker | null {
  const normalized = value?.trim().toUpperCase();
  if (!normalized) {
    return null;
  }
  return COVERAGE_TICKERS.includes(normalized as CoverageTicker) ? (normalized as CoverageTicker) : null;
}

function formatMoney(value: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value);
}

function formatSignedPercent(value: number) {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function signalFromFundamental(response: FundamentalAnalysisResponse | null) {
  return response?.rating ?? 'HOLD';
}

function signalFromTechnical(analysis: TechnicalAnalysisResponse | null) {
  if (!analysis?.forecast_bars.length) {
    return 'HOLD';
  }
  const last = analysis.forecast_bars[analysis.forecast_bars.length - 1];
  const movePct = analysis.latest_price > 0 ? ((last.close - analysis.latest_price) / analysis.latest_price) * 100 : 0;
  if (movePct > 0.35) {
    return 'BUY';
  }
  if (movePct < -0.35) {
    return 'SELL';
  }
  return 'HOLD';
}

function signalFromSentiment(analysis: SentimentalAnalysisResponse | null) {
  if (!analysis) {
    return 'NEUTRAL';
  }
  return analysis.overall_sentiment.toUpperCase();
}

function toneFromSignal(signal: string): SignalTone {
  if (['BUY', 'STRONG BUY', 'POSITIVE', 'UP'].includes(signal)) {
    return 'success';
  }
  if (['SELL', 'STRONG SELL', 'NEGATIVE', 'DOWN'].includes(signal)) {
    return 'danger';
  }
  if (['HOLD', 'NEUTRAL'].includes(signal)) {
    return 'warning';
  }
  return 'neutral';
}

function combinedRecommendation(result: CombinedStockAnalysis | null) {
  if (!result) {
    return { label: 'ANALYSE', confidence: 0, tone: 'neutral' as SignalTone };
  }

  const scores = [
    signalFromFundamental(result.fundamental) === 'BUY' ? 1 : signalFromFundamental(result.fundamental) === 'SELL' ? -1 : 0,
    signalFromTechnical(result.technical) === 'BUY' ? 1 : signalFromTechnical(result.technical) === 'SELL' ? -1 : 0,
    result.sentiment?.overall_sentiment === 'Positive' ? 1 : result.sentiment?.overall_sentiment === 'Negative' ? -1 : 0,
  ];
  const score = scores.reduce((sum, item) => sum + item, 0) / scores.length;
  const confidence = Math.round((Math.abs(score) * 0.45 + 0.55) * 100);

  if (score > 0.35) {
    return { label: 'STRONG BUY', confidence, tone: 'success' as SignalTone };
  }
  if (score < -0.35) {
    return { label: 'SELL', confidence, tone: 'danger' as SignalTone };
  }
  return { label: 'HOLD', confidence, tone: 'warning' as SignalTone };
}

export default function StockAnalysisPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryTicker = normalizeCoverageTicker(searchParams.get('ticker'));
  const initialTicker = queryTicker ?? DEFAULT_TICKER;
  const [tickerInput, setTickerInput] = useState<string>(initialTicker);
  const [activeTab, setActiveTab] = useState<AnalysisTab>('overview');
  const [status, setStatus] = useState<AnalysisStatus>(queryTicker ? 'loading' : 'idle');
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<CombinedStockAnalysis | null>(null);

  const runAnalysis = useCallback(async (ticker: CoverageTicker) => {
    setStatus('loading');
    setError(null);
    setTickerInput(ticker);

    const [fundamentalResult, technicalResult, sentimentResult] = await Promise.allSettled([
      fundamentalApi.analyze({
        ticker,
        market: 'US',
        include_peer_context: true,
      }),
      technicalApi.analyze({
        ticker,
        model_version: 'final_1d',
        history_bars: 90,
        forecast_bars: 7,
      }),
      sentimentApi.analyze({
        ticker,
        market: 'US',
      }),
    ]);

    const fallbackProfile = FUNDAMENTAL_PROFILES[ticker];
    const nextAnalysis: CombinedStockAnalysis = {
      ticker,
      snapshot: STOCK_SNAPSHOTS[ticker],
      profile:
        fundamentalResult.status === 'fulfilled'
          ? profileFromFundamentalResponse(fundamentalResult.value)
          : fallbackProfile,
      fundamental: fundamentalResult.status === 'fulfilled' ? fundamentalResult.value : null,
      technical: technicalResult.status === 'fulfilled' ? technicalResult.value : null,
      sentiment: sentimentResult.status === 'fulfilled' ? sentimentResult.value : null,
      fundamentalError: fundamentalResult.status === 'rejected' ? handleApiError(fundamentalResult.reason) : null,
      technicalError: technicalResult.status === 'rejected' ? handleApiError(technicalResult.reason) : null,
      sentimentError: sentimentResult.status === 'rejected' ? handleApiError(sentimentResult.reason) : null,
    };

    setAnalysis(nextAnalysis);
    setStatus(fundamentalResult.status === 'fulfilled' || nextAnalysis.technical || nextAnalysis.sentiment ? 'success' : 'error');
  }, []);

  useEffect(() => {
    if (queryTicker) {
      void runAnalysis(queryTicker);
    }
  }, [queryTicker, runAnalysis]);

  const submitTicker = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = normalizeCoverageTicker(tickerInput);
    if (!normalized) {
      setError(`Choose one of the available tickers: ${COVERAGE_TICKERS.join(', ')}.`);
      return;
    }
    router.push(`/analyze?ticker=${normalized}`);
  };

  const currentTicker = queryTicker ?? normalizeCoverageTicker(tickerInput) ?? DEFAULT_TICKER;
  const snapshot = analysis?.snapshot ?? STOCK_SNAPSHOTS[currentTicker];
  const profile = analysis?.profile ?? FUNDAMENTAL_PROFILES[currentTicker];
  const recommendation = combinedRecommendation(analysis);
  const priceTone = snapshot.change >= 0 ? 'text-emerald-600' : 'text-rose-600';
  const hasTicker = Boolean(queryTicker);

  if (!hasTicker) {
    return (
      <div className="mx-auto max-w-5xl space-y-8">
        <EmptyAnalyzeState />
        <AnalyzeSearchCard
          tickerInput={tickerInput}
          setTickerInput={setTickerInput}
          submitTicker={submitTicker}
          currentTicker={currentTicker}
          status={status}
          error={error}
          routerPush={(ticker) => router.push(`/analyze?ticker=${ticker}`)}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <StockHeader
        snapshot={snapshot}
        profile={profile}
        recommendation={recommendation}
        status={status}
        priceTone={priceTone}
      />

      <AnalyzeSearchCard
        tickerInput={tickerInput}
        setTickerInput={setTickerInput}
        submitTicker={submitTicker}
        currentTicker={currentTicker}
        status={status}
        error={error}
        routerPush={(ticker) => router.push(`/analyze?ticker=${ticker}`)}
      />

      <div className="rounded-2xl bg-slate-100/70 p-2">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {TAB_OPTIONS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              className={cn(
                'rounded-xl px-4 py-3 text-sm font-extrabold text-slate-500 transition-all',
                activeTab === tab.value ? 'bg-white text-slate-950 shadow-card' : 'hover:bg-white/60 hover:text-slate-800'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {status === 'loading' && (
        <Card className="border border-slate-200 bg-white" variant="bordered" padding="none">
          <CardContent className="p-8">
            <div className="flex items-center gap-4">
              <Loader2 className="animate-spin text-primary-600" size={26} />
              <div>
                <p className="text-lg font-extrabold text-slate-950">
                  Analysing {currentTicker} across Fundamental, Technical & Sentiment models...
                </p>
                <p className="mt-1 text-sm text-slate-500">The full stock view will appear as each model response is assembled.</p>
              </div>
            </div>
            <div className="mt-6 h-2 rounded-full bg-slate-100 progress-indeterminate" />
          </CardContent>
        </Card>
      )}

      {status !== 'loading' && (
        <div>
          {activeTab === 'overview' && (
            <OverviewTab
              result={analysis}
              snapshot={snapshot}
              recommendation={recommendation}
            />
          )}
          {activeTab === 'fundamental' && (
            <FundamentalTab
              result={analysis}
              profile={profile}
            />
          )}
          {activeTab === 'technical' && (
            <TechnicalTab
              analysis={analysis?.technical ?? null}
              error={analysis?.technicalError ?? null}
            />
          )}
          {activeTab === 'sentiment' && (
            <SentimentTab
              analysis={analysis?.sentiment ?? null}
              error={analysis?.sentimentError ?? null}
            />
          )}
        </div>
      )}
    </div>
  );
}

function StockHeader({
  snapshot,
  profile,
  recommendation,
  status,
  priceTone,
}: {
  snapshot: StockSnapshot;
  profile: FundamentalProfile;
  recommendation: { label: string; confidence: number; tone: SignalTone };
  status: AnalysisStatus;
  priceTone: string;
}) {
  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-4xl font-extrabold tracking-[-0.04em] text-slate-950 md:text-5xl">
              {snapshot.companyName}
            </h1>
            <span className="text-2xl font-extrabold text-slate-500">{snapshot.ticker}</span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <SignalPill label={status === 'loading' ? 'ANALYSING' : recommendation.label} tone={recommendation.tone} />
            <span className="font-bold text-slate-500">{snapshot.exchange} · {snapshot.currency}</span>
            <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-sm font-bold text-slate-500">
              <Circle size={8} fill="currentColor" />
              {snapshot.marketStatus}
            </span>
          </div>
        </div>
        <Button type="button" variant="secondary" className="gap-2">
          <Bookmark size={17} />
          Add to Watchlist
        </Button>
      </div>

      <div>
        <div className="flex flex-wrap items-end gap-3">
          <p className="text-5xl font-extrabold tracking-[-0.04em] text-slate-950">{formatMoney(snapshot.price)}</p>
          <p className={cn('pb-2 text-xl font-extrabold', priceTone)}>
            {snapshot.change >= 0 ? '+' : ''}{snapshot.change.toFixed(2)} ({formatSignedPercent(snapshot.changePercent)})
          </p>
        </div>
        <p className="mt-1 text-base font-semibold text-slate-500">Pre-market: {formatMoney(snapshot.preMarket)}</p>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{profile.headline}</p>
      </div>
    </section>
  );
}

function AnalyzeSearchCard({
  tickerInput,
  setTickerInput,
  submitTicker,
  currentTicker,
  status,
  error,
  routerPush,
}: {
  tickerInput: string;
  setTickerInput: (value: string) => void;
  submitTicker: (event: FormEvent<HTMLFormElement>) => void;
  currentTicker: CoverageTicker;
  status: AnalysisStatus;
  error: string | null;
  routerPush: (ticker: CoverageTicker) => void;
}) {
  return (
    <Card className="border border-slate-200" variant="bordered" padding="none">
      <CardContent className="p-4 sm:p-5">
        <form onSubmit={submitTicker} className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="flex flex-1 items-center gap-3 rounded-full border border-slate-200 bg-white px-4 py-3">
            <Search size={18} className="shrink-0 text-slate-400" />
            <input
              value={tickerInput}
              onChange={(event) => setTickerInput(event.target.value.toUpperCase())}
              placeholder="Enter ticker"
              className="min-w-0 flex-1 bg-transparent text-sm font-semibold text-slate-900 outline-none placeholder:text-slate-400"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {COVERAGE_TICKERS.map((ticker) => (
              <button
                key={ticker}
                type="button"
                onClick={() => routerPush(ticker)}
                className={cn(
                  'rounded-full border px-3 py-2 text-xs font-extrabold transition-all',
                  ticker === currentTicker
                    ? 'border-primary-600 bg-primary-600 text-white'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-primary-200 hover:text-primary-700'
                )}
              >
                {ticker}
              </button>
            ))}
          </div>
          <Button type="submit" isLoading={status === 'loading'} className="md:min-w-[160px]">
            Analyse
          </Button>
        </form>
        {error && <p className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">{error}</p>}
      </CardContent>
    </Card>
  );
}

function OverviewTab({
  result,
  snapshot,
  recommendation,
}: {
  result: CombinedStockAnalysis | null;
  snapshot: StockSnapshot;
  recommendation: { label: string; confidence: number; tone: SignalTone };
}) {
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_0.95fr]">
      <Card className="border border-slate-200" variant="bordered" padding="none">
        <CardContent className="p-6">
          <h2 className="text-xl font-extrabold text-slate-950">Market Data</h2>
          <div className="mt-5 divide-y divide-slate-100">
            <DataRow label="Market Cap" value={snapshot.marketCap} />
            <DataRow label="Revenue (TTM)" value={snapshot.revenue} />
            <DataRow label="Net Income" value={snapshot.netIncome} />
            <DataRow label="EPS (TTM)" value={snapshot.eps} />
            <DataRow label="P/E Ratio" value={snapshot.peRatio} />
            <DataRow label="Forward P/E" value={snapshot.forwardPe} />
            <DataRow label="Volume" value={snapshot.volume} />
            <DataRow label="52-Week Range" value={snapshot.weekRange} />
            <DataRow label="Beta" value={snapshot.beta} />
            <DataRow label="Next Earnings" value={snapshot.nextEarnings} />
          </div>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card className="border border-slate-200" variant="bordered" padding="none">
          <CardContent className="p-6">
            <h2 className="text-xl font-extrabold text-slate-950">FinEdge Recommendation</h2>
            <div className="mt-5 space-y-4">
              <RecommendationRow label="Fundamental" value={signalFromFundamental(result?.fundamental ?? null)} />
              <RecommendationRow label="Technical" value={signalFromTechnical(result?.technical ?? null)} />
              <RecommendationRow label="Sentiment" value={signalFromSentiment(result?.sentiment ?? null)} />
            </div>
            <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/70 p-5">
              <div className="flex items-center justify-between gap-4">
                <SignalPill label={recommendation.label} tone={recommendation.tone} />
                <p className="text-3xl font-extrabold text-slate-950">{recommendation.confidence || 0}%</p>
              </div>
              <p className="mt-2 text-sm font-semibold text-slate-500">Combined Confidence</p>
              <p className="mt-1 text-xs text-slate-500">Weighted combination of the selected analysis modules.</p>
            </div>
          </CardContent>
        </Card>

        <Card className="border border-slate-200" variant="bordered" padding="none">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-extrabold text-slate-950">Price Chart</h2>
              <Tag variant="neutral">Forecast On</Tag>
            </div>
            <MiniForecastChart technical={result?.technical ?? null} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function FundamentalTab({ result, profile }: { result: CombinedStockAnalysis | null; profile: FundamentalProfile }) {
  const response = result?.fundamental ?? null;
  const metrics = response?.key_metrics;
  const profileTicker = profile.ticker as CoverageTicker;
  const snapshot = result?.snapshot ?? STOCK_SNAPSHOTS[profileTicker];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <StatTile label="Revenue TTM" value={profile.spotlightMetrics[1]?.value ?? 'N/A'} />
        <StatTile label="Net Income TTM" value={snapshot?.netIncome ?? 'N/A'} />
        <StatTile label="Free Cash Flow TTM" value={metrics?.free_cash_flow_margin != null ? `${(metrics.free_cash_flow_margin * 100).toFixed(1)}% margin` : profile.shareholderYield} />
        <StatTile label="Market Cap" value={profile.marketCap} />
      </div>

      <Card className="border border-slate-200" variant="bordered" padding="none">
        <CardContent className="p-6">
          <SectionTitle title="Profitability" subtitle="How much of each dollar of revenue becomes profit" />
          <div className="mt-5 divide-y divide-slate-100">
            <MetricBar label="ROE" value={metrics?.roe != null ? `${(metrics.roe * 100).toFixed(1)}%` : `${profile.qualityScore.toFixed(1)} / 10`} percent={Math.min(100, profile.qualityScore * 10)} status="Above Average" />
            <MetricBar label="Free Cash Flow Margin" value={metrics?.free_cash_flow_margin != null ? `${(metrics.free_cash_flow_margin * 100).toFixed(1)}%` : profile.shareholderYield} percent={72} status="Healthy" />
            <MetricBar label="Revenue Growth" value={metrics?.revenue_growth_yoy != null ? `${(metrics.revenue_growth_yoy * 100).toFixed(1)}%` : 'Monitor'} percent={64} status="Durable" />
            <MetricBar label="Earnings Growth" value={metrics?.earnings_growth_yoy != null ? `${(metrics.earnings_growth_yoy * 100).toFixed(1)}%` : 'Monitor'} percent={58} status="Stable" />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border border-slate-200" variant="bordered" padding="none">
          <CardContent className="p-6">
            <SectionTitle title="Financial Health" subtitle="Balance sheet strength and debt management" />
            <div className="mt-5 space-y-3">
              <HealthRow label="Debt to Equity" detail="Debt load relative to shareholder equity" value={metrics?.debt_to_equity?.toFixed(2) ?? 'N/A'} badge="Monitored" />
              <HealthRow label="Universe Rank" detail="Model rank across the available universe" value={response?.relative_rank ? `#${response.relative_rank}` : 'N/A'} badge="Model" />
              <HealthRow label="Score" detail="Fundamental model assessment" value={response ? `${response.score.toFixed(1)} / 10` : `${profile.qualityScore.toFixed(1)} / 10`} badge={response?.rating ?? 'Profile'} />
            </div>
          </CardContent>
        </Card>

        <Card className="border border-slate-200" variant="bordered" padding="none">
          <CardContent className="p-6">
            <SectionTitle title="Valuation" subtitle="How the market prices this stock relative to fundamentals" />
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <ValuationTile label="P/E Ratio" value={metrics?.pe_ratio?.toFixed(1) ?? 'N/A'} status="Model metric" />
              <ValuationTile label="Fair Value" value={formatMoney(profile.fairValueBase)} status="Base case" />
              <ValuationTile label="Model Score" value={response?.model_score?.toFixed(3) ?? 'N/A'} status="Artifact score" />
              <ValuationTile label="Data Source" value={response?.data_source ?? 'Profile'} status={response?.cached ? 'Cached' : 'Fresh'} />
            </div>
          </CardContent>
        </Card>
      </div>

      {result?.fundamentalError && <ErrorCard message={result.fundamentalError} />}
    </div>
  );
}

function TechnicalTab({ analysis, error }: { analysis: TechnicalAnalysisResponse | null; error: string | null }) {
  const lastForecast = analysis?.forecast_bars[analysis.forecast_bars.length - 1];
  const movePct = analysis && lastForecast ? ((lastForecast.close - analysis.latest_price) / analysis.latest_price) * 100 : 0;
  const direction = movePct >= 0 ? 'UP' : 'DOWN';

  if (!analysis) {
    return <ErrorCard message={error ?? 'Technical analysis is unavailable for this stock.'} />;
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border border-slate-200" variant="bordered" padding="none">
          <CardContent className="p-6">
            <p className="text-sm font-semibold text-slate-500">Price Direction Prediction</p>
            <div className="mt-4 flex items-center gap-4">
              <SignalPill label={direction} tone={direction === 'UP' ? 'success' : 'danger'} />
              <p className="text-4xl font-extrabold text-slate-950">{Math.abs(movePct).toFixed(2)}%</p>
              <p className="font-bold text-slate-500">projected move</p>
            </div>
          </CardContent>
        </Card>

        <Card className="border border-slate-200" variant="bordered" padding="none">
          <CardContent className="p-6">
            <p className="text-sm font-semibold text-slate-500">Policy Overlay</p>
            <div className="mt-4 flex items-end justify-between gap-4">
              <div>
                <p className="text-2xl font-extrabold text-slate-950">{String(analysis.policy.stance ?? 'MODEL')}</p>
                <p className="text-sm font-semibold text-slate-500">{analysis.data_source}</p>
              </div>
              <p className="text-2xl font-extrabold text-slate-950">
                {typeof analysis.policy.recommended_position_pct === 'number'
                  ? `${(analysis.policy.recommended_position_pct * 100).toFixed(0)}%`
                  : 'N/A'}
              </p>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-emerald-500"
                style={{ width: `${Math.max(8, Math.min(100, Number(analysis.policy.recommended_position_pct ?? 0) * 100))}%` }}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border border-slate-200" variant="bordered" padding="none">
        <CardContent className="p-6">
          <SectionTitle title="Price Forecast" subtitle="Observed price path plus forward model projection" />
          <MiniForecastChart technical={analysis} tall />
        </CardContent>
      </Card>

      <Card className="border border-slate-200" variant="bordered" padding="none">
        <CardContent className="p-6">
          <SectionTitle title="Model Ensemble Breakdown" subtitle="Individual model weights before policy overlay" />
          <div className="mt-5 divide-y divide-slate-100">
            {Object.entries(analysis.ensemble_weights).map(([model, weight]) => (
              <DataRow key={model} label={analysis.expert_versions[model] ?? model} value={`${(weight * 100).toFixed(1)}%`} />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function SentimentTab({ analysis, error }: { analysis: SentimentalAnalysisResponse | null; error: string | null }) {
  if (!analysis) {
    return <ErrorCard message={error ?? 'Sentiment analysis is unavailable for this stock.'} />;
  }

  const positivePct = analysis.news_breakdown.article_count > 0
    ? Math.round((analysis.news_breakdown.positive_count / analysis.news_breakdown.article_count) * 100)
    : 0;
  const negativePct = analysis.news_breakdown.article_count > 0
    ? Math.round((analysis.news_breakdown.negative_count / analysis.news_breakdown.article_count) * 100)
    : 0;

  return (
    <div className="space-y-6">
      <Card className="border border-slate-200" variant="bordered" padding="none">
        <CardContent className="p-6 text-center">
          <p className="eyebrow">Sentiment Score</p>
          <div className="mx-auto mt-5 flex h-40 w-40 items-center justify-center rounded-full border-[14px] border-slate-100 border-t-emerald-500 border-r-emerald-400 border-b-amber-400 border-l-rose-500">
            <p className="text-4xl font-extrabold text-slate-950">{analysis.score.toFixed(2)}</p>
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <StatTile label="Current Score" value={analysis.score.toFixed(2)} />
            <StatTile label="Confidence" value={analysis.confidence.toFixed(2)} />
          </div>
          <div className="mt-5">
            <SignalPill label={analysis.overall_sentiment.toUpperCase()} tone={toneFromSignal(analysis.overall_sentiment.toUpperCase())} />
          </div>
        </CardContent>
      </Card>

      <Card className="border border-slate-200" variant="bordered" padding="none">
        <CardContent className="p-6">
          <SectionTitle title={`Article Analysis (${analysis.news_breakdown.article_count} articles)`} subtitle={analysis.analysis_summary} />
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <SentimentCount value={analysis.news_breakdown.positive_count} label="Positive" tone="success" />
            <SentimentCount value={analysis.news_breakdown.neutral_count} label="Neutral" tone="warning" />
            <SentimentCount value={analysis.news_breakdown.negative_count} label="Negative" tone="danger" />
          </div>
          <div className="mt-6 space-y-2">
            <MetricBar label="Positive" value={`${positivePct}%`} percent={positivePct} status="Positive" />
            <MetricBar label="Negative" value={`${negativePct}%`} percent={negativePct} status="Negative" />
          </div>
        </CardContent>
      </Card>

      <Card className="border border-slate-200" variant="bordered" padding="none">
        <CardContent className="p-6">
          <SectionTitle title="Top Articles" subtitle="Most influential articles in the current analysis window" />
          <div className="mt-5 space-y-3">
            {analysis.influential_articles.slice(0, 3).map((article) => (
              <div key={article.title} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <h3 className="font-extrabold text-slate-950">{article.title}</h3>
                  <SignalPill label={article.verdict} tone={toneFromSignal(article.verdict)} />
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-500">{article.reasoning}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function DataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <p className="font-semibold text-slate-500">{label}</p>
      <p className="text-right font-extrabold text-slate-950">{value}</p>
    </div>
  );
}

function RecommendationRow({ label, value }: { label: string; value: string }) {
  const tone = toneFromSignal(value);
  return (
    <div className="flex items-center justify-between gap-4">
      <p className="font-semibold text-slate-500">{label}</p>
      <SignalPill label={value} tone={tone} />
    </div>
  );
}

function SignalPill({ label, tone }: { label: string; tone: SignalTone }) {
  const styles: Record<SignalTone, string> = {
    success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    warning: 'border-amber-200 bg-amber-50 text-amber-700',
    danger: 'border-rose-200 bg-rose-50 text-rose-700',
    neutral: 'border-slate-200 bg-slate-100 text-slate-700',
  };

  return (
    <span className={cn('inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-extrabold', styles[tone])}>
      <Circle size={7} fill="currentColor" />
      {label}
    </span>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h2 className="text-xl font-extrabold text-slate-950">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-slate-500">{subtitle}</p>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-extrabold text-slate-950">{value}</p>
    </div>
  );
}

function MetricBar({ label, value, percent, status }: { label: string; value: string; percent: number; status: string }) {
  return (
    <div className="grid gap-3 py-3 md:grid-cols-[1fr_110px_1.2fr_120px] md:items-center">
      <p className="font-semibold text-slate-600">{label}</p>
      <p className="font-extrabold text-slate-950">{value}</p>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.max(8, Math.min(100, percent))}%` }} />
      </div>
      <p className="text-sm font-bold text-emerald-600">{status}</p>
    </div>
  );
}

function HealthRow({ label, detail, value, badge }: { label: string; detail: string; value: string; badge: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-extrabold text-slate-950">{label}</p>
          <p className="mt-1 text-sm text-slate-500">{detail}</p>
        </div>
        <div className="text-right">
          <p className="text-xl font-extrabold text-slate-950">{value}</p>
          <Tag variant="neutral" size="sm">{badge}</Tag>
        </div>
      </div>
    </div>
  );
}

function ValuationTile({ label, value, status }: { label: string; value: string; status: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-extrabold text-slate-950">{value}</p>
      <p className="mt-1 text-sm font-bold text-slate-500">{status}</p>
    </div>
  );
}

function SentimentCount({ value, label, tone }: { value: number; label: string; tone: SignalTone }) {
  const color = tone === 'success' ? 'text-emerald-600 bg-emerald-50' : tone === 'danger' ? 'text-rose-600 bg-rose-50' : 'text-amber-600 bg-amber-50';
  return (
    <div className={cn('rounded-2xl p-5 text-center', color)}>
      <p className="text-4xl font-extrabold">{value}</p>
      <p className="mt-1 text-sm font-bold">{label}</p>
    </div>
  );
}

function MiniForecastChart({ technical, tall = false }: { technical: TechnicalAnalysisResponse | null; tall?: boolean }) {
  const points = useMemo(() => {
    if (!technical) {
      return [];
    }
    return [...technical.history_bars.slice(-34), ...technical.forecast_bars].map((bar, index) => ({
      index,
      value: bar.close,
      predicted: bar.is_prediction,
    }));
  }, [technical]);

  if (!technical || points.length < 2) {
    return (
      <div className="mt-5 flex h-52 items-center justify-center rounded-2xl bg-slate-50 text-sm font-semibold text-slate-400">
        Run analysis to generate the price forecast.
      </div>
    );
  }

  const width = 680;
  const height = tall ? 280 : 210;
  const padding = 24;
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const coordinates = points.map((point, index) => {
    const x = padding + (index / (points.length - 1)) * (width - padding * 2);
    const y = height - padding - ((point.value - min) / span) * (height - padding * 2);
    return { ...point, x, y };
  });
  const splitIndex = coordinates.findIndex((point) => point.predicted);
  const observed = splitIndex >= 0 ? coordinates.slice(0, splitIndex + 1) : coordinates;
  const forecast = splitIndex >= 0 ? coordinates.slice(splitIndex) : [];
  const line = (items: typeof coordinates) => items.map((point) => `${point.x},${point.y}`).join(' ');

  return (
    <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full">
        <defs>
          <linearGradient id="forecastFill" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#2563eb" stopOpacity="0.14" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0.08" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width={width} height={height} rx="18" fill="url(#forecastFill)" />
        <polyline points={line(observed)} fill="none" stroke="#0f172a" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        {forecast.length > 1 && (
          <polyline points={line(forecast)} fill="none" stroke="#10b981" strokeWidth="4" strokeDasharray="10 10" strokeLinecap="round" strokeLinejoin="round" />
        )}
      </svg>
      <div className="mt-3 flex flex-wrap justify-between gap-2 text-xs font-bold text-slate-500">
        <span>Observed closes</span>
        <span>Forecast: {technical.forecast_bars.length} bars · {technical.data_source}</span>
      </div>
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <Card className="border border-amber-200 bg-amber-50" variant="bordered" padding="none">
      <CardContent className="p-6">
        <div className="flex items-start gap-3">
          <FileText size={20} className="mt-0.5 text-amber-700" />
          <p className="text-sm leading-6 text-amber-950">{message}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export function EmptyAnalyzeState() {
  return (
    <div className="mx-auto max-w-4xl text-center">
      <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-extrabold uppercase tracking-[0.18em] text-slate-500 shadow-card">
        <BarChart3 size={14} className="text-primary-600" />
        Three models. One recommendation.
      </div>
      <h1 className="mt-6 text-4xl font-extrabold tracking-[-0.04em] text-slate-950 md:text-6xl">Analyse any stock.</h1>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-slate-500 md:text-base">
        Search a supported ticker to open the full stock-level analysis workspace.
      </p>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <FeatureCard icon={<Building2 size={20} />} title="Fundamental" text="Financial health, profitability, and valuation vs peers" />
        <FeatureCard icon={<CandlestickChart size={20} />} title="Technical" text="Price momentum and model forecast signals" />
        <FeatureCard icon={<Newspaper size={20} />} title="Sentiment" text="News tone, article mix, and language-model confidence" />
      </div>
    </div>
  );
}

function FeatureCard({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <Card className="border border-slate-200" variant="bordered" padding="none">
      <CardContent className="p-6 text-left">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-primary-600">
          {icon}
        </div>
        <h3 className="mt-4 text-lg font-extrabold text-slate-950">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-slate-500">{text}</p>
      </CardContent>
    </Card>
  );
}

'use client';

import { useCallback, useMemo, useState, type ReactNode } from 'react';
import {
  Activity,
  BarChart3,
  Bookmark,
  CandlestickChart,
  Clock3,
  FileText,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react';
import { SentimentResults } from '@/components/analysis';
import { SparklineChart, TechnicalCandlesChart } from '@/components/charts';
import FundamentalAnalysisPage, {
  FUNDAMENTAL_PROFILES,
  profileFromFundamentalResponse,
  type CoverageTicker,
  type FundamentalProfile,
} from '@/components/pages/fundamental/FundamentalAnalysisPage';
import { Button, Card, CardContent, CardHeader, CardTitle, Modal, Tag } from '@/components/ui';
import { cn, fundamentalApi, handleApiError, sentimentApi, technicalApi } from '@/lib';
import type { FundamentalAnalysisResponse, SentimentalAnalysisResponse, TechnicalAnalysisResponse } from '@/types';

type DashboardStatus = 'idle' | 'loading' | 'success' | 'error';
type ModalView = 'fundamental' | 'technical' | 'sentiment' | null;
type SummaryTone = 'default' | 'success' | 'warning' | 'danger' | 'info';

interface WatchlistItem {
  ticker: CoverageTicker;
  exchange: string;
  change: number;
  changePercent: number;
  volume: string;
  seedSentiment: 'Positive' | 'Negative' | 'Neutral';
  seedTechnicalSignal: 'BUY' | 'SELL' | 'HOLD';
  note: string;
  sparklineData: Array<{ value: number; index: number }>;
}

interface CombinedAnalysisResult {
  ticker: CoverageTicker;
  fundamental: FundamentalProfile;
  fundamentalResponse: FundamentalAnalysisResponse | null;
  technical: TechnicalAnalysisResponse | null;
  sentiment: SentimentalAnalysisResponse | null;
  fundamentalError: string | null;
  technicalError: string | null;
  sentimentError: string | null;
  completedAt: string | null;
}

interface CompositeView {
  title: string;
  tone: SummaryTone;
  summary: string;
  aggregate: SentimentLedAggregate;
}

interface SentimentLedAggregate {
  action: 'BUY' | 'SELL' | 'HOLD';
  targetExposure: number | null;
  supportScore: number;
  technicalAdjustment: number;
  fundamentalAdjustment: number;
  technicalScore: number;
  fundamentalScore: number;
}

const BASE_LONG_EXPOSURE = 0.6;
const TARGET_LONG_EXPOSURE = 1.0;
const TECHNICAL_EXPOSURE_WEIGHT = 0.25;
const FUNDAMENTAL_EXPOSURE_WEIGHT = 0.15;
const BUY_THRESHOLD = 0.15;
const SELL_THRESHOLD = -0.15;

const WATCHLIST: WatchlistItem[] = [
  {
    ticker: 'MSFT',
    exchange: 'NASDAQ',
    change: 5.22,
    changePercent: 1.24,
    volume: '26.4M',
    seedSentiment: 'Positive',
    seedTechnicalSignal: 'BUY',
    note: 'Platform software leader with premium enterprise AI exposure.',
    sparklineData: [
      { value: 412, index: 0 },
      { value: 415, index: 1 },
      { value: 417, index: 2 },
      { value: 418, index: 3 },
      { value: 421, index: 4 },
      { value: 423, index: 5 },
      { value: 425, index: 6 },
      { value: 428, index: 7 },
    ],
  },
  {
    ticker: 'AAPL',
    exchange: 'NASDAQ',
    change: -1.38,
    changePercent: -0.64,
    volume: '31.7M',
    seedSentiment: 'Neutral',
    seedTechnicalSignal: 'HOLD',
    note: 'High-quality consumer ecosystem with services-driven resilience.',
    sparklineData: [
      { value: 219, index: 0 },
      { value: 218, index: 1 },
      { value: 217, index: 2 },
      { value: 216, index: 3 },
      { value: 215, index: 4 },
      { value: 216, index: 5 },
      { value: 215, index: 6 },
      { value: 214, index: 7 },
    ],
  },
  {
    ticker: 'NVDA',
    exchange: 'NASDAQ',
    change: 3.14,
    changePercent: 2.25,
    volume: '48.9M',
    seedSentiment: 'Positive',
    seedTechnicalSignal: 'BUY',
    note: 'AI infrastructure leader with exceptional growth and margin leverage.',
    sparklineData: [
      { value: 132, index: 0 },
      { value: 134, index: 1 },
      { value: 135, index: 2 },
      { value: 137, index: 3 },
      { value: 138, index: 4 },
      { value: 139, index: 5 },
      { value: 141, index: 6 },
      { value: 143, index: 7 },
    ],
  },
];

const TONE_STYLES: Record<
  SummaryTone,
  {
    card: string;
    icon: string;
    tag: 'neutral' | 'success' | 'warning' | 'danger' | 'info';
    bar: string;
  }
> = {
  default: {
    card: 'border-slate-200 bg-slate-50/85',
    icon: 'bg-slate-900',
    tag: 'neutral',
    bar: 'bg-slate-700',
  },
  success: {
    card: 'border-emerald-200 bg-emerald-50/85',
    icon: 'bg-emerald-600',
    tag: 'success',
    bar: 'bg-emerald-500',
  },
  warning: {
    card: 'border-amber-200 bg-amber-50/90',
    icon: 'bg-amber-500',
    tag: 'warning',
    bar: 'bg-amber-500',
  },
  danger: {
    card: 'border-rose-200 bg-rose-50/85',
    icon: 'bg-rose-600',
    tag: 'danger',
    bar: 'bg-rose-500',
  },
  info: {
    card: 'border-blue-200 bg-blue-50/85',
    icon: 'bg-blue-600',
    tag: 'info',
    bar: 'bg-blue-500',
  },
};

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

function getFundamentalGap(profile: FundamentalProfile) {
  const delta = profile.fairValueBase - profile.price;
  const deltaPct = (delta / profile.price) * 100;
  const tone: SummaryTone = delta >= 0 ? 'success' : 'warning';

  return {
    delta,
    deltaPct,
    tone,
  };
}

function getTechnicalForecastStats(analysis: TechnicalAnalysisResponse | null) {
  if (!analysis) {
    return null;
  }

  const lastForecast = analysis.forecast_bars[analysis.forecast_bars.length - 1];
  const projectedMove = lastForecast.close - analysis.latest_price;
  const projectedMovePct = analysis.latest_price > 0 ? (projectedMove / analysis.latest_price) * 100 : 0;

  return {
    lastForecast,
    projectedMove,
    projectedMovePct,
    direction: projectedMove >= 0 ? 'up' : 'down',
  };
}

function clipScore(value: number) {
  return Math.max(-1, Math.min(1, value));
}

function clipExposure(value: number) {
  return Math.max(0, Math.min(TARGET_LONG_EXPOSURE, value));
}

function actionFromScore(score: number): SentimentLedAggregate['action'] {
  if (score >= BUY_THRESHOLD) {
    return 'BUY';
  }
  if (score <= SELL_THRESHOLD) {
    return 'SELL';
  }
  return 'HOLD';
}

function getSentimentAction(sentiment: SentimentalAnalysisResponse | null): SentimentLedAggregate['action'] {
  if (!sentiment) {
    return 'HOLD';
  }
  if (sentiment.overall_sentiment === 'Positive') {
    return 'BUY';
  }
  if (sentiment.overall_sentiment === 'Negative') {
    return 'SELL';
  }
  return actionFromScore(sentiment.score);
}

function getTechnicalSupportScore(analysis: TechnicalAnalysisResponse | null) {
  if (!analysis) {
    return 0;
  }

  const forecastStats = getTechnicalForecastStats(analysis);
  const forecastScore = forecastStats ? Math.tanh((forecastStats.projectedMovePct / 100) / 0.05) : null;
  const policyAction = analysis.policy.recommended_position_pct;
  const policyScore = typeof policyAction === 'number' ? clipScore(policyAction) : null;
  const availableScores = [forecastScore, policyScore].filter((score): score is number => score !== null);

  if (!availableScores.length) {
    return 0;
  }
  return clipScore(availableScores.reduce((sum, score) => sum + score, 0) / availableScores.length);
}

function getFundamentalSupportScore(response: FundamentalAnalysisResponse | null, profile: FundamentalProfile) {
  if (response) {
    if (response.universe_percentile !== null && response.universe_percentile !== undefined) {
      return clipScore((response.universe_percentile * 2) - 1);
    }
    if (response.model_score !== null && response.model_score !== undefined) {
      return clipScore((response.model_score * 2) - 1);
    }
    if (response.rating === 'BUY') {
      return 1;
    }
    if (response.rating === 'SELL') {
      return -1;
    }
    return 0;
  }

  return clipScore(((profile.qualityScore / 10) * 2) - 1);
}

function buildSentimentLedAggregate(result: CombinedAnalysisResult): SentimentLedAggregate {
  const action = getSentimentAction(result.sentiment);
  const technicalScore = getTechnicalSupportScore(result.technical);
  const fundamentalScore = result.fundamentalError
    ? 0
    : getFundamentalSupportScore(result.fundamentalResponse, result.fundamental);
  const technicalAdjustment = technicalScore * TECHNICAL_EXPOSURE_WEIGHT;
  const fundamentalAdjustment = fundamentalScore * FUNDAMENTAL_EXPOSURE_WEIGHT;
  const supportScore = clipScore(technicalAdjustment + fundamentalAdjustment);
  const targetExposure =
    action === 'BUY'
      ? clipExposure(BASE_LONG_EXPOSURE + technicalAdjustment + fundamentalAdjustment)
      : action === 'SELL'
        ? 0
        : null;

  return {
    action,
    targetExposure,
    supportScore,
    technicalAdjustment,
    fundamentalAdjustment,
    technicalScore,
    fundamentalScore,
  };
}

function formatExposure(value: number | null) {
  return value === null ? 'No rebalance' : `${(value * 100).toFixed(0)}%`;
}

function aggregateDetail(aggregate: SentimentLedAggregate) {
  if (aggregate.action === 'SELL') {
    return 'Sentiment leads with SELL, so the aggregate exits to cash.';
  }
  if (aggregate.action === 'HOLD') {
    return 'Sentiment is not directional enough, so support modules do not force a trade.';
  }

  const technicalText = aggregate.technicalAdjustment >= 0 ? 'technical supports' : 'technical reduces';
  const fundamentalText = aggregate.fundamentalAdjustment >= 0 ? 'fundamentals support' : 'fundamentals reduce';
  return `Sentiment leads with BUY; ${technicalText} size and ${fundamentalText} size.`;
}

function buildCompositeView(result: CombinedAnalysisResult | null): CompositeView | null {
  if (!result) {
    return null;
  }

  const aggregate = buildSentimentLedAggregate(result);

  if (aggregate.action === 'BUY') {
    return {
      title: `Aggregate BUY · ${formatExposure(aggregate.targetExposure)}`,
      tone: aggregate.targetExposure !== null && aggregate.targetExposure >= 0.75 ? 'success' : 'warning',
      summary: aggregateDetail(aggregate),
      aggregate,
    };
  }

  if (aggregate.action === 'SELL') {
    return {
      title: 'Aggregate SELL · Cash',
      tone: 'danger',
      summary: aggregateDetail(aggregate),
      aggregate,
    };
  }

  return {
    title: 'Aggregate HOLD',
    tone: 'warning',
    summary: aggregateDetail(aggregate),
    aggregate,
  };
}

export default function DashboardPage() {
  const [status, setStatus] = useState<DashboardStatus>('idle');
  const [focusedTicker, setFocusedTicker] = useState<CoverageTicker | null>(null);
  const [analysis, setAnalysis] = useState<CombinedAnalysisResult | null>(null);
  const [modalView, setModalView] = useState<ModalView>(null);

  const runCombinedAnalysis = useCallback(async (ticker: CoverageTicker) => {
    setFocusedTicker(ticker);
    setModalView(null);
    setStatus('loading');
    setAnalysis(null);

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

    const fallbackFundamental = FUNDAMENTAL_PROFILES[ticker];
    const nextAnalysis: CombinedAnalysisResult = {
      ticker,
      fundamental:
        fundamentalResult.status === 'fulfilled'
          ? profileFromFundamentalResponse(fundamentalResult.value)
          : fallbackFundamental,
      fundamentalResponse: fundamentalResult.status === 'fulfilled' ? fundamentalResult.value : null,
      technical: technicalResult.status === 'fulfilled' ? technicalResult.value : null,
      sentiment: sentimentResult.status === 'fulfilled' ? sentimentResult.value : null,
      fundamentalError: fundamentalResult.status === 'rejected' ? handleApiError(fundamentalResult.reason) : null,
      technicalError: technicalResult.status === 'rejected' ? handleApiError(technicalResult.reason) : null,
      sentimentError: sentimentResult.status === 'rejected' ? handleApiError(sentimentResult.reason) : null,
      completedAt: new Date().toISOString(),
    };

    setAnalysis(nextAnalysis);
    setStatus(fundamentalResult.status === 'fulfilled' || nextAnalysis.technical || nextAnalysis.sentiment ? 'success' : 'error');
  }, []);

  const compositeView = useMemo(() => buildCompositeView(analysis), [analysis]);
  const technicalStats = useMemo(() => getTechnicalForecastStats(analysis?.technical ?? null), [analysis?.technical]);
  const fundamentalGap = useMemo(
    () => (analysis && !analysis.fundamentalError ? getFundamentalGap(analysis.fundamental) : null),
    [analysis]
  );

  return (
    <>
      <div className="space-y-10">
        <section className="mx-auto max-w-5xl">
          <div className="grid max-w-xl gap-3 sm:grid-cols-2">
            <MarketIndexCard label="S&P 500" value="5,321.47" change="+0.82%" />
            <MarketIndexCard label="NASDAQ 100" value="18,742.35" change="+1.14%" />
          </div>

          <div className="mt-14 text-center">
            <h1 className="text-4xl font-extrabold tracking-[-0.04em] text-slate-950 md:text-6xl">
              Smarter Stock Decisions, Simplified.
            </h1>
            <p className="mt-4 text-xs font-extrabold uppercase tracking-[0.24em] text-slate-500">
              Fundamental · Technical · Sentiment
            </p>

            <div className="mx-auto mt-7 flex max-w-2xl items-center gap-2 rounded-full border border-slate-200 bg-white p-2 shadow-card">
              <Search size={18} className="ml-3 shrink-0 text-slate-400" />
              <input
                className="min-w-0 flex-1 bg-transparent px-1 text-sm font-semibold text-slate-800 outline-none placeholder:text-slate-400"
                placeholder="Search any ticker from the watchlist..."
                value={focusedTicker ?? ''}
                readOnly
              />
              <Button
                type="button"
                size="sm"
                onClick={() => runCombinedAnalysis(focusedTicker ?? WATCHLIST[0].ticker)}
                isLoading={status === 'loading'}
              >
                Analyse
              </Button>
            </div>

            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {WATCHLIST.map((item) => (
                <button
                  key={item.ticker}
                  type="button"
                  onClick={() => runCombinedAnalysis(item.ticker)}
                  className={cn(
                    'rounded-full border px-3 py-1 text-xs font-extrabold text-slate-600 transition-all duration-200',
                    focusedTicker === item.ticker
                      ? 'border-primary-600 bg-primary-600 text-white shadow-[0_10px_20px_-14px_rgba(37,99,235,0.9)]'
                      : 'border-slate-200 bg-white hover:border-primary-200 hover:text-primary-700'
                  )}
                >
                  {item.ticker}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          <Card className="border border-slate-200" variant="bordered" padding="none">
            <CardHeader className="mb-0 flex flex-row items-center justify-between border-b border-slate-200 px-6 py-5">
              <div>
                <CardTitle className="text-xl">Your Watchlist</CardTitle>
                <p className="mt-1 text-sm text-slate-500">Select a stock to run the full three-model analysis.</p>
              </div>
              <Tag variant="neutral" size="sm">{WATCHLIST.length} stocks</Tag>
            </CardHeader>
            <CardContent className="divide-y divide-slate-100">
              {WATCHLIST.map((item) => {
                const profile = FUNDAMENTAL_PROFILES[item.ticker];
                const valuation = getFundamentalGap(profile);
                const isActive = focusedTicker === item.ticker;

                return (
                  <button
                    key={item.ticker}
                    type="button"
                    onClick={() => runCombinedAnalysis(item.ticker)}
                    className={cn(
                      'grid w-full gap-4 px-6 py-5 text-left transition-all duration-200 md:grid-cols-[1fr_160px_140px_150px] md:items-center',
                      isActive ? 'bg-blue-50/70' : 'hover:bg-slate-50'
                    )}
                  >
                    <div className="flex items-start gap-4">
                      <div className="mt-1 flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500">
                        <Bookmark size={17} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-xl font-extrabold tracking-tight text-slate-950">{item.ticker}</p>
                          <span className="rounded-full border border-slate-200 px-2 py-0.5 text-[11px] font-bold text-slate-500">
                            {item.exchange}
                          </span>
                        </div>
                        <p className="mt-1 text-sm font-semibold text-slate-700">{profile.companyName}</p>
                        <p className="mt-1 line-clamp-1 text-xs text-slate-500">{item.note}</p>
                      </div>
                    </div>

                    <div>
                      <p className="eyebrow">Price</p>
                      <p className="mt-1 text-lg font-extrabold text-slate-950">{formatMoney(profile.price)}</p>
                    </div>

                    <div>
                      <p className="eyebrow">Fair Gap</p>
                      <p className={cn('mt-1 text-lg font-extrabold', valuation.delta >= 0 ? 'text-emerald-600' : 'text-amber-600')}>
                        {formatSignedPercent(valuation.deltaPct)}
                      </p>
                    </div>

                    <div className="flex items-center gap-3 md:justify-end">
                      <SparklineChart
                        data={item.sparklineData}
                        width={96}
                        height={34}
                        color={item.change >= 0 ? '#10B981' : '#EF4444'}
                      />
                      <span className={cn('text-sm font-extrabold', item.change >= 0 ? 'text-emerald-600' : 'text-rose-600')}>
                        {formatSignedPercent(item.changePercent)}
                      </span>
                    </div>
                  </button>
                );
              })}
            </CardContent>
          </Card>

          <div className="space-y-5">
            <SignalCard
              eyebrow="Today's strongest buy signal"
              ticker="NVDA"
              company="NVIDIA Corp."
              score="0.91"
              tag="Strong Buy"
              tone="success"
            />
            <SignalCard
              eyebrow="Today's biggest risk"
              ticker="AAPL"
              company="Apple Inc."
              score="0.43"
              tag="Monitor"
              tone="warning"
            />
          </div>
        </section>

        <section>
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-2xl font-extrabold tracking-tight text-slate-950">Market Pulse</h2>
              <p className="text-sm text-slate-500">Stocks ranked by combined quality, valuation, and model-readiness.</p>
            </div>
            <Tag variant="neutral">Updated Daily</Tag>
          </div>

          <Card className="overflow-hidden border border-slate-200" variant="bordered" padding="none">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-100 text-sm">
                <thead className="bg-slate-50/80">
                  <tr className="text-left text-[11px] font-extrabold uppercase tracking-[0.16em] text-slate-500">
                    <th className="px-6 py-4">#</th>
                    <th className="px-6 py-4">Stock</th>
                    <th className="px-6 py-4">Reason</th>
                    <th className="px-6 py-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {WATCHLIST.map((item, index) => (
                    <tr key={item.ticker} className="hover:bg-slate-50/70">
                      <td className="px-6 py-4 font-extrabold text-slate-400">{index + 1}</td>
                      <td className="px-6 py-4">
                        <p className="font-extrabold text-slate-950">{item.ticker}</p>
                        <p className="text-xs font-semibold text-slate-500">{FUNDAMENTAL_PROFILES[item.ticker].companyName}</p>
                      </td>
                      <td className="px-6 py-4 text-slate-600">{item.note}</td>
                      <td className="px-6 py-4 text-right">
                        <Button type="button" size="sm" variant="secondary" onClick={() => runCombinedAnalysis(item.ticker)}>
                          Analyse
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>

        {status === 'idle' && !analysis && (
          <Card className="border border-dashed border-slate-300 bg-white/90" variant="bordered" padding="none">
            <CardContent className="px-6 py-10 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-blue-50 text-primary-600">
                <Sparkles size={24} />
              </div>
              <h2 className="mt-4 text-2xl font-semibold text-text-primary">Pick a stock to start the stack</h2>
              <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-text-secondary">
                The dashboard will run technical forecasting and news sentiment in parallel, pair them
                with the company’s fundamental profile, and surface a combined read before you dive deeper.
              </p>
            </CardContent>
          </Card>
        )}

        {status === 'loading' && focusedTicker && (
          <Card className="border border-slate-200/90" variant="bordered" padding="none">
            <CardHeader className="mb-0 border-b border-slate-200 px-6 py-5">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <CardTitle className="text-2xl">Running Full Analysis</CardTitle>
                  <p className="mt-1 text-sm text-text-secondary">
                    Building the combined dashboard view for {focusedTicker}.
                  </p>
                </div>
                <Tag variant="info">Parallel execution</Tag>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 p-6">
              <div className="h-2 rounded-full bg-slate-200 progress-indeterminate" />
              <div className="grid gap-4 md:grid-cols-3">
                <ProgressCard
                  title="Technical engine"
                  detail="Pulling daily candles and forecasting the next 7 trading days."
                  icon={<CandlestickChart size={18} />}
                />
                <ProgressCard
                  title="Sentiment engine"
                  detail="Scoring fresh article flow and generating a news-driven summary."
                  icon={<BarChart3 size={18} />}
                />
                <ProgressCard
                  title="Fundamental synthesis"
                  detail="Mapping valuation, quality, and filing checkpoints into the combined view."
                  icon={<ShieldCheck size={18} />}
                />
              </div>
            </CardContent>
          </Card>
        )}

        {analysis && (
          <div className="space-y-5">
            <Card className="border border-slate-200/90" variant="bordered" padding="none">
              <CardHeader className="mb-0 border-b border-slate-200 px-6 py-5">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <CardTitle className="text-2xl">{analysis.ticker} Combined View</CardTitle>
                      {compositeView && <Tag variant={TONE_STYLES[compositeView.tone].tag}>{compositeView.title}</Tag>}
                    </div>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-text-secondary">
                      {compositeView?.summary ??
                        'The dashboard is showing the latest cross-analysis summary for this stock.'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-text-secondary">
                    <Clock3 size={16} />
                    {analysis.completedAt ? `Updated ${new Date(analysis.completedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Running'}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4 p-6 md:grid-cols-4">
                <OverviewMetric
                  icon={
                    compositeView?.aggregate.action === 'SELL'
                      ? <TrendingDown size={18} />
                      : compositeView?.aggregate.action === 'BUY'
                        ? <TrendingUp size={18} />
                        : <Activity size={18} />
                  }
                  label="Aggregate action"
                  value={compositeView ? `${compositeView.aggregate.action} · ${formatExposure(compositeView.aggregate.targetExposure)}` : 'Unavailable'}
                  detail={compositeView ? `Support score ${compositeView.aggregate.supportScore.toFixed(2)}` : 'Aggregate model unavailable'}
                  tone={compositeView?.tone ?? 'default'}
                />
                <OverviewMetric
                  icon={<Wallet size={18} />}
                  label="Fundamental gap"
                  value={
                    analysis.fundamentalError
                      ? 'Unavailable'
                      : fundamentalGap
                        ? formatSignedPercent(fundamentalGap.deltaPct)
                        : 'N/A'
                  }
                  detail={analysis.fundamentalError ?? analysis.fundamental.balanceSheetLabel}
                  tone={analysis.fundamentalError ? 'danger' : fundamentalGap?.tone ?? 'default'}
                />
                <OverviewMetric
                  icon={technicalStats?.direction === 'down' ? <TrendingDown size={18} /> : <TrendingUp size={18} />}
                  label="Technical move"
                  value={technicalStats ? formatSignedPercent(technicalStats.projectedMovePct) : 'Unavailable'}
                  detail={analysis.technical ? `Model ${analysis.technical.model_version} forecast` : analysis.technicalError ?? 'Technical analysis unavailable'}
                  tone={technicalStats ? (technicalStats.direction === 'up' ? 'success' : 'warning') : 'default'}
                />
                <OverviewMetric
                  icon={<BarChart3 size={18} />}
                  label="Sentiment score"
                  value={analysis.sentiment ? analysis.sentiment.score.toFixed(2) : 'Unavailable'}
                  detail={analysis.sentiment ? `${analysis.sentiment.overall_sentiment} with ${analysis.sentiment.news_breakdown.article_count} articles` : analysis.sentimentError ?? 'Sentiment analysis unavailable'}
                  tone={
                    analysis.sentiment
                      ? analysis.sentiment.overall_sentiment === 'Positive'
                        ? 'success'
                        : analysis.sentiment.overall_sentiment === 'Negative'
                          ? 'danger'
                          : 'warning'
                      : 'default'
                  }
                />
              </CardContent>
            </Card>

            <div className="grid gap-5 xl:grid-cols-3">
              <AnalysisCard
                title="Fundamental Analysis"
                tone={analysis.fundamentalError ? 'danger' : fundamentalGap?.tone ?? 'info'}
                icon={<ShieldCheck size={18} />}
                headline={
                  analysis.fundamentalError
                    ? 'Fundamental model signal is unavailable for this run.'
                    : `${analysis.fundamental.companyName} screens at ${formatSignedPercent((analysis.fundamental.fairValueBase - analysis.fundamental.price) / analysis.fundamental.price * 100)} to the base case.`
                }
                summary={
                  analysis.fundamentalError
                    ? analysis.fundamentalError
                    : analysis.fundamental.lensNotes.blend.summary
                }
                stats={[
                  {
                    label: 'Fair value',
                    value: analysis.fundamentalError ? 'N/A' : formatMoney(analysis.fundamental.fairValueBase),
                  },
                  {
                    label: 'Quality',
                    value: analysis.fundamentalError ? 'N/A' : `${analysis.fundamental.qualityScore.toFixed(1)} / 10`,
                  },
                  { label: 'Yield', value: analysis.fundamentalError ? 'N/A' : analysis.fundamental.shareholderYield },
                ]}
                actionLabel="Open Fundamental"
                onOpen={() => setModalView('fundamental')}
                disabled={Boolean(analysis.fundamentalError)}
              />

              <AnalysisCard
                title="Technical Analysis"
                tone={
                  technicalStats
                    ? technicalStats.direction === 'up'
                      ? 'success'
                      : 'warning'
                    : 'default'
                }
                icon={<CandlestickChart size={18} />}
                headline={
                  technicalStats
                    ? `${analysis.ticker} is projecting ${formatSignedPercent(technicalStats.projectedMovePct)} over the forward 7-day path.`
                    : 'Technical analysis is currently unavailable for this run.'
                }
                summary={
                  analysis.technical
                    ? `Latest price is ${formatMoney(analysis.technical.latest_price)} with forecast bars sourced from ${analysis.technical.data_source}.`
                    : analysis.technicalError ?? 'No technical response was returned.'
                }
                stats={[
                  { label: 'Latest', value: analysis.technical ? formatMoney(analysis.technical.latest_price) : 'N/A' },
                  { label: 'Model', value: analysis.technical?.model_version ?? 'N/A' },
                  { label: 'Source', value: analysis.technical?.data_source ?? 'Unavailable' },
                ]}
                actionLabel="Open Technical"
                onOpen={() => setModalView('technical')}
                disabled={!analysis.technical}
              />

              <AnalysisCard
                title="Sentiment Analysis"
                tone={
                  analysis.sentiment
                    ? analysis.sentiment.overall_sentiment === 'Positive'
                      ? 'success'
                      : analysis.sentiment.overall_sentiment === 'Negative'
                        ? 'danger'
                        : 'warning'
                    : 'default'
                }
                icon={<FileText size={18} />}
                headline={
                  analysis.sentiment
                    ? `${analysis.sentiment.overall_sentiment} news tone with ${analysis.sentiment.confidence.toFixed(2)} confidence.`
                    : 'Sentiment analysis is currently unavailable for this run.'
                }
                summary={analysis.sentiment?.analysis_summary ?? analysis.sentimentError ?? 'No sentiment response was returned.'}
                stats={[
                  { label: 'Trend', value: analysis.sentiment?.trend ?? 'N/A' },
                  { label: 'Articles', value: analysis.sentiment ? String(analysis.sentiment.news_breakdown.article_count) : 'N/A' },
                  { label: 'Market', value: analysis.sentiment?.market ?? 'US' },
                ]}
                actionLabel="Open Sentiment"
                onOpen={() => setModalView('sentiment')}
                disabled={!analysis.sentiment}
              />
            </div>

            {(analysis.fundamentalError || analysis.technicalError || analysis.sentimentError) && (
              <Card className="border border-amber-200 bg-amber-50/85" variant="bordered" padding="none">
                <CardContent className="px-6 py-4 text-sm text-amber-950">
                  {analysis.fundamentalError && <p>Fundamental: {analysis.fundamentalError}</p>}
                  {analysis.technicalError && <p className={cn(analysis.fundamentalError && 'mt-1')}>Technical: {analysis.technicalError}</p>}
                  {analysis.sentimentError && <p className={cn((analysis.fundamentalError || analysis.technicalError) && 'mt-1')}>Sentiment: {analysis.sentimentError}</p>}
                </CardContent>
              </Card>
            )}

            {status === 'error' && !analysis.technical && !analysis.sentiment && (
              <div className="flex justify-start">
                <Button type="button" variant="secondary" onClick={() => focusedTicker && runCombinedAnalysis(focusedTicker)}>
                  <RefreshCw size={16} className="mr-2" />
                  Retry Full Analysis
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      <Modal
        open={modalView !== null && analysis !== null}
        onClose={() => setModalView(null)}
        size={modalView === 'fundamental' ? '6xl' : '4xl'}
        title={
          modalView === 'fundamental'
            ? `${analysis?.ticker ?? ''} Fundamental Analysis`
            : modalView === 'technical'
              ? `${analysis?.ticker ?? ''} Technical Analysis`
              : `${analysis?.ticker ?? ''} Sentiment Analysis`
        }
        description={
          analysis
            ? `${analysis.ticker} · ${analysis.fundamental.companyName}`
            : undefined
        }
      >
        {analysis && modalView === 'fundamental' && (
          <FundamentalAnalysisPage initialTicker={analysis.ticker} showHero={false} showControls={false} />
        )}

        {analysis && modalView === 'technical' && (
          analysis.technical ? (
            <TechnicalDetail analysis={analysis.technical} />
          ) : (
            <UnavailableState message={analysis.technicalError ?? 'Technical analysis is unavailable for this stock.'} />
          )
        )}

        {analysis && modalView === 'sentiment' && (
          analysis.sentiment ? (
            <SentimentResults analysis={analysis.sentiment} />
          ) : (
            <UnavailableState message={analysis.sentimentError ?? 'Sentiment analysis is unavailable for this stock.'} />
          )
        )}
      </Modal>
    </>
  );
}

function MarketIndexCard({ label, value, change }: { label: string; value: string; change: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-card">
      <p className="text-xs font-extrabold text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-extrabold tracking-tight text-slate-950">{value}</p>
      <p className="mt-1 text-sm font-extrabold text-emerald-600">{change}</p>
    </div>
  );
}

function SignalCard({
  eyebrow,
  ticker,
  company,
  score,
  tag,
  tone,
}: {
  eyebrow: string;
  ticker: string;
  company: string;
  score: string;
  tag: string;
  tone: 'success' | 'warning';
}) {
  return (
    <Card className="border border-slate-200" variant="bordered" padding="none">
      <CardContent className="p-6">
        <p className="eyebrow">{eyebrow}</p>
        <div className="mt-5 flex items-end justify-between gap-4">
          <div>
            <p className="text-3xl font-extrabold tracking-tight text-slate-950">{ticker}</p>
            <p className="text-sm font-semibold text-slate-500">{company}</p>
          </div>
          <Tag variant={tone}>{tag}</Tag>
        </div>
        <p className={cn('mt-5 text-5xl font-extrabold tracking-tight', tone === 'success' ? 'text-slate-950' : 'text-slate-400')}>
          {score}<span className="text-sm text-slate-400"> / 1.00</span>
        </p>
      </CardContent>
    </Card>
  );
}

function ProgressCard({
  title,
  detail,
  icon,
}: {
  title: string;
  detail: string;
  icon: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white">
          {icon}
        </div>
        <div>
          <p className="font-semibold text-text-primary">{title}</p>
          <p className="mt-1 text-sm text-text-secondary">{detail}</p>
        </div>
      </div>
    </div>
  );
}

function OverviewMetric({
  icon,
  label,
  value,
  detail,
  tone = 'default',
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone?: SummaryTone;
}) {
  const styles = TONE_STYLES[tone];

  return (
    <div className={cn('rounded-2xl border p-4', styles.card)}>
      <div className="flex items-start gap-4">
        <div className={cn('flex h-11 w-11 items-center justify-center rounded-2xl text-white', styles.icon)}>
          {icon}
        </div>
        <div>
          <p className="text-sm text-text-secondary">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-text-primary">{value}</p>
          <p className="mt-1 text-sm text-text-secondary">{detail}</p>
        </div>
      </div>
    </div>
  );
}

function AnalysisCard({
  title,
  icon,
  headline,
  summary,
  stats,
  actionLabel,
  onOpen,
  tone = 'default',
  disabled = false,
}: {
  title: string;
  icon: ReactNode;
  headline: string;
  summary: string;
  stats: Array<{ label: string; value: string }>;
  actionLabel: string;
  onOpen: () => void;
  tone?: SummaryTone;
  disabled?: boolean;
}) {
  const styles = TONE_STYLES[tone];

  return (
    <Card className={cn('border', styles.card)} variant="bordered" padding="none">
      <CardContent className="space-y-5 p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className={cn('flex h-11 w-11 items-center justify-center rounded-2xl text-white', styles.icon)}>
              {icon}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-primary">{title}</h3>
              <p className="mt-1 text-sm font-medium text-text-primary">{headline}</p>
            </div>
          </div>
          <Tag variant={styles.tag} size="sm">
            Summary
          </Tag>
        </div>

        <p className="text-sm leading-6 text-text-secondary">{summary}</p>

        <div className="grid gap-3 sm:grid-cols-3">
          {stats.map((stat) => (
            <div key={stat.label} className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
              <p className="text-xs text-text-secondary">{stat.label}</p>
              <p className="mt-1 text-base font-semibold text-text-primary">{stat.value}</p>
            </div>
          ))}
        </div>

        <Button type="button" variant={disabled ? 'secondary' : 'primary'} fullWidth onClick={onOpen} disabled={disabled}>
          {actionLabel}
        </Button>
      </CardContent>
    </Card>
  );
}

function TechnicalDetail({ analysis }: { analysis: TechnicalAnalysisResponse }) {
  const technicalStats = getTechnicalForecastStats(analysis);

  if (!technicalStats) {
    return <UnavailableState message="Technical analysis is unavailable for this stock." />;
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-4">
        <OverviewMetric
          icon={<Activity size={18} />}
          label="Latest Price"
          value={formatMoney(analysis.latest_price)}
          detail={`Updated ${new Date(analysis.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
        />
        <OverviewMetric
          icon={<CandlestickChart size={18} />}
          label="Forecast End"
          value={formatMoney(technicalStats.lastForecast.close)}
          detail={`${analysis.forecast_bars.length} candles ahead`}
          tone="info"
        />
        <OverviewMetric
          icon={technicalStats.direction === 'up' ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
          label="Projected Move"
          value={formatSignedPercent(technicalStats.projectedMovePct)}
          detail={`${technicalStats.projectedMove >= 0 ? '+' : '-'}${formatMoney(Math.abs(technicalStats.projectedMove))} versus latest close`}
          tone={technicalStats.direction === 'up' ? 'success' : 'warning'}
        />
        <OverviewMetric
          icon={<Clock3 size={18} />}
          label="Model"
          value={analysis.model_version}
          detail={`Source: ${analysis.data_source}`}
        />
      </div>

      <TechnicalCandlesChart
        ticker={analysis.ticker}
        modelVersion={analysis.model_version}
        history={analysis.history_bars}
        forecast={analysis.forecast_bars}
        dataSource={analysis.data_source}
        timeframe={analysis.timeframe}
      />
    </div>
  );
}

function UnavailableState({ message }: { message: string }) {
  return (
    <Card className="border border-slate-200/90" variant="bordered" padding="none">
      <CardContent className="px-6 py-10 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-700">
          <FileText size={22} />
        </div>
        <p className="mt-4 text-base text-text-secondary">{message}</p>
      </CardContent>
    </Card>
  );
}

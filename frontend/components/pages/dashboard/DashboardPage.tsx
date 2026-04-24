'use client';

import { useCallback, useMemo, useState, type ReactNode } from 'react';
import {
  Activity,
  BarChart3,
  CandlestickChart,
  Clock3,
  FileText,
  RefreshCw,
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
import type { SentimentalAnalysisResponse, TechnicalAnalysisResponse } from '@/types';

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
}

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

function buildCompositeView(result: CombinedAnalysisResult | null): CompositeView | null {
  if (!result) {
    return null;
  }

  const fundamentalGap = getFundamentalGap(result.fundamental);
  const technicalStats = getTechnicalForecastStats(result.technical);
  const technicalPositive = technicalStats ? technicalStats.projectedMove >= 0 : null;
  const sentimentPositive = result.sentiment ? result.sentiment.overall_sentiment === 'Positive' : null;

  const positiveSignals = [fundamentalGap.delta >= 0, technicalPositive, sentimentPositive].filter(Boolean).length;
  const availableSignals = [true, technicalPositive !== null, sentimentPositive !== null].filter(Boolean).length;

  if (positiveSignals >= 3 || (positiveSignals >= 2 && availableSignals >= 2)) {
    return {
      title: 'Constructive combined read',
      tone: 'success',
      summary:
        'The stack leans constructive: intrinsic value is supportive, the near-term price path is favorable, and the news flow is reinforcing the broader thesis.',
    };
  }

  if (positiveSignals === 0 && availableSignals >= 2) {
    return {
      title: 'Cautious combined read',
      tone: 'danger',
      summary:
        'The stack leans cautious: the valuation cushion is limited and the faster-moving signals are not yet offering enough support.',
    };
  }

  return {
    title: 'Mixed combined read',
    tone: 'warning',
    summary:
      'The stack is mixed, which usually means the stock is worth following but still needs a clearer catalyst or a better entry point.',
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

    const fallbackFundamental = FUNDAMENTAL_PROFILES[ticker];
    setAnalysis({
      ticker,
      fundamental: fallbackFundamental,
      technical: null,
      sentiment: null,
      fundamentalError: null,
      technicalError: null,
      sentimentError: null,
      completedAt: null,
    });

    const [fundamentalResult, technicalResult, sentimentResult] = await Promise.allSettled([
      fundamentalApi.analyze({
        ticker,
        market: 'US',
        include_peer_context: true,
      }),
      technicalApi.analyze({
        ticker,
        model_version: 'v1.1',
        history_bars: 60,
        forecast_bars: 50,
      }),
      sentimentApi.analyze({
        ticker,
        market: 'US',
      }),
    ]);

    const nextAnalysis: CombinedAnalysisResult = {
      ticker,
      fundamental:
        fundamentalResult.status === 'fulfilled'
          ? profileFromFundamentalResponse(fundamentalResult.value)
          : fallbackFundamental,
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
    () => (analysis ? getFundamentalGap(analysis.fundamental) : null),
    [analysis]
  );

  return (
    <>
      <div className="space-y-6">
        <div className="rounded-[28px] border border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(37,99,235,0.16),_transparent_32%),linear-gradient(135deg,#08111f_0%,#0f1b35_46%,#eff6ff_100%)] p-6 text-white shadow-xl md:p-8">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-end">
            <div className="space-y-4">
              <Tag variant="info" size="sm" className="bg-white/12 text-blue-50 ring-1 ring-white/15">
                Unified Market Intelligence
              </Tag>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">Dashboard</h1>
                <p className="max-w-3xl text-sm leading-6 text-blue-50/82 md:text-base">
                  Start from the watchlist, run technical, sentiment, and fundamental work together,
                  then drill into any stream from one combined workspace.
                </p>
              </div>
              <div className="flex flex-wrap gap-3 text-xs text-blue-50/80">
                <HeroPill icon={<BarChart3 size={14} />} text="Watchlist-first workflow" />
                <HeroPill icon={<CandlestickChart size={14} />} text="Parallel technical + sentiment runs" />
                <HeroPill icon={<FileText size={14} />} text="Deep-dive popups for every stream" />
              </div>
            </div>

            <div className="rounded-3xl border border-white/12 bg-white/10 p-5 backdrop-blur-sm">
              <p className="text-xs uppercase tracking-[0.2em] text-blue-50/65">Coverage</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                <SpotlightCard label="Watchlist" value={`${WATCHLIST.length} names`} />
                <SpotlightCard label="Live engines" value="2 backend" />
                <SpotlightCard label="Deep dives" value="3 modal views" />
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-3">
          {WATCHLIST.map((item) => {
            const profile = FUNDAMENTAL_PROFILES[item.ticker];
            const valuation = getFundamentalGap(profile);
            const isActive = focusedTicker === item.ticker;

            return (
              <Card
                key={item.ticker}
                className={cn(
                  'border border-slate-200/90 transition-all duration-200',
                  isActive && 'border-primary-400 shadow-[0_20px_48px_rgba(37,99,235,0.12)]'
                )}
                variant="bordered"
                padding="none"
              >
                <CardContent className="space-y-5 p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-3">
                        <h2 className="text-2xl font-semibold text-text-primary">{item.ticker}</h2>
                        <Tag variant="neutral" size="sm">
                          {item.exchange}
                        </Tag>
                      </div>
                      <p className="mt-1 text-sm font-medium text-text-primary">{profile.companyName}</p>
                      <p className="mt-1 text-sm text-text-secondary">{item.note}</p>
                    </div>
                    <Tag variant="info" size="sm">
                      {profile.sector}
                    </Tag>
                  </div>

                  <div className="flex items-end justify-between gap-4">
                    <div>
                      <p className="text-3xl font-semibold text-text-primary">{formatMoney(profile.price)}</p>
                      <p className={cn('mt-1 flex items-center gap-1 text-sm font-medium', item.change >= 0 ? 'text-success-900' : 'text-danger-900')}>
                        {item.change >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                        {item.change >= 0 ? '+' : ''}
                        {item.changePercent.toFixed(2)}% today
                      </p>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
                      <SparklineChart
                        data={item.sparklineData}
                        width={120}
                        height={44}
                        color={item.change >= 0 ? '#10B981' : '#EF4444'}
                      />
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-3">
                    <MiniStat label="Fair value gap" value={formatSignedPercent(valuation.deltaPct)} tone={valuation.tone} />
                    <MiniStat label="Quality score" value={`${profile.qualityScore.toFixed(1)} / 10`} tone="success" />
                    <MiniStat label="Volume" value={item.volume} tone="default" />
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Tag variant={item.seedSentiment === 'Positive' ? 'success' : item.seedSentiment === 'Negative' ? 'danger' : 'neutral'} size="sm">
                      {item.seedSentiment} sentiment
                    </Tag>
                    <Tag variant={item.seedTechnicalSignal === 'BUY' ? 'success' : item.seedTechnicalSignal === 'SELL' ? 'danger' : 'warning'} size="sm">
                      {item.seedTechnicalSignal} technical
                    </Tag>
                  </div>

                  <Button
                    type="button"
                    size="lg"
                    fullWidth
                    isLoading={status === 'loading' && focusedTicker === item.ticker}
                    onClick={() => runCombinedAnalysis(item.ticker)}
                  >
                    Run Full Analysis
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

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
                  detail="Pulling 1-minute candles and forecasting the next 50 bars."
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
              <CardContent className="grid gap-4 p-6 md:grid-cols-3">
                <OverviewMetric
                  icon={<Wallet size={18} />}
                  label="Fundamental gap"
                  value={fundamentalGap ? formatSignedPercent(fundamentalGap.deltaPct) : 'N/A'}
                  detail={analysis.fundamental.balanceSheetLabel}
                  tone={fundamentalGap?.tone ?? 'default'}
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
                tone={fundamentalGap?.tone ?? 'info'}
                icon={<ShieldCheck size={18} />}
                headline={`${analysis.fundamental.companyName} screens at ${formatSignedPercent((analysis.fundamental.fairValueBase - analysis.fundamental.price) / analysis.fundamental.price * 100)} to the base case.`}
                summary={analysis.fundamental.lensNotes.blend.summary}
                stats={[
                  { label: 'Fair value', value: formatMoney(analysis.fundamental.fairValueBase) },
                  { label: 'Quality', value: `${analysis.fundamental.qualityScore.toFixed(1)} / 10` },
                  { label: 'Yield', value: analysis.fundamental.shareholderYield },
                ]}
                actionLabel="Open Fundamental"
                onOpen={() => setModalView('fundamental')}
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
                    ? `${analysis.ticker} is projecting ${formatSignedPercent(technicalStats.projectedMovePct)} over the forward 50-bar path.`
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

            {(analysis.technicalError || analysis.sentimentError) && (
              <Card className="border border-amber-200 bg-amber-50/85" variant="bordered" padding="none">
                <CardContent className="px-6 py-4 text-sm text-amber-950">
                  {analysis.technicalError && <p>Technical: {analysis.technicalError}</p>}
                  {analysis.sentimentError && <p className={cn(analysis.technicalError && 'mt-1')}>Sentiment: {analysis.sentimentError}</p>}
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

function HeroPill({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/8 px-3 py-1.5 backdrop-blur-sm">
      {icon}
      <span>{text}</span>
    </div>
  );
}

function SpotlightCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/8 px-3 py-3">
      <p className="text-xs text-blue-50/65">{label}</p>
      <p className="mt-1 text-base font-semibold text-white">{value}</p>
    </div>
  );
}

function MiniStat({
  label,
  value,
  tone = 'default',
}: {
  label: string;
  value: string;
  tone?: SummaryTone;
}) {
  const styles = TONE_STYLES[tone];

  return (
    <div className={cn('rounded-2xl border px-3 py-3', styles.card)}>
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="mt-1 text-base font-semibold text-text-primary">{value}</p>
    </div>
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

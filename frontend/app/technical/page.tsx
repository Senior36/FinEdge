'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  CandlestickChart,
  Clock3,
  Database,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { TechnicalCandlesChart } from '@/components/charts';
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Tag } from '@/components/ui';
import { cn, handleApiError, technicalApi } from '@/lib';
import type { TechnicalAnalysisResponse } from '@/types';

const DEFAULT_TICKER = 'MSFT';
const DEFAULT_MODEL = 'v1.1';

type ModelVersion = 'v1.1' | 'v1.2';
type AnalysisStatus = 'idle' | 'loading' | 'success' | 'error';

const MODEL_OPTIONS: Array<{
  value: ModelVersion;
  label: string;
  summary: string;
}> = [
  {
    value: 'v1.1',
    label: 'v1.1',
    summary: 'Balanced trend-following with tighter short-term reversion control.',
  },
  {
    value: 'v1.2',
    label: 'v1.2',
    summary: 'Higher momentum persistence with slightly broader intraminute range expansion.',
  },
];

export default function TechnicalPage() {
  const [ticker, setTicker] = useState(DEFAULT_TICKER);
  const [modelVersion, setModelVersion] = useState<ModelVersion>(DEFAULT_MODEL);
  const [status, setStatus] = useState<AnalysisStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<TechnicalAnalysisResponse | null>(null);
  const [lastSubmittedTicker, setLastSubmittedTicker] = useState(DEFAULT_TICKER);
  const initialRequestStarted = useRef(false);

  const runAnalysis = useCallback(async (nextTicker: string, nextModel: ModelVersion) => {
    const normalizedTicker = nextTicker.trim().toUpperCase();

    if (!normalizedTicker) {
      setError('Enter a valid US ticker symbol.');
      setStatus('error');
      return;
    }

    setStatus('loading');
    setError(null);
    setLastSubmittedTicker(normalizedTicker);

    try {
      const response = await technicalApi.analyze({
        ticker: normalizedTicker,
        model_version: nextModel,
        history_bars: 60,
        forecast_bars: 50,
      });
      setAnalysis(response);
      setStatus('success');
    } catch (analysisError) {
      setStatus('error');
      setError(handleApiError(analysisError));
    }
  }, []);

  useEffect(() => {
    if (initialRequestStarted.current) {
      return;
    }
    initialRequestStarted.current = true;
    void runAnalysis(DEFAULT_TICKER, DEFAULT_MODEL);
  }, [runAnalysis]);

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await runAnalysis(ticker, modelVersion);
  };

  const forecastStats = useMemo(() => {
    if (!analysis) {
      return null;
    }

    const lastForecast = analysis.forecast_bars[analysis.forecast_bars.length - 1];
    const projectedMove = lastForecast.close - analysis.latest_price;
    const projectedMovePct = analysis.latest_price > 0
      ? (projectedMove / analysis.latest_price) * 100
      : 0;

    return {
      lastForecast,
      projectedMove,
      projectedMovePct,
      direction: projectedMove >= 0 ? 'up' : 'down',
    };
  }, [analysis]);

  const selectedModel = MODEL_OPTIONS.find((option) => option.value === modelVersion) ?? MODEL_OPTIONS[0];

  return (
    <div className="space-y-6">
      <div className="rounded-[28px] border border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(37,99,235,0.16),_transparent_34%),linear-gradient(135deg,#08111f_0%,#101f3c_46%,#eff6ff_100%)] p-6 text-white shadow-xl md:p-8">
        <div className="max-w-4xl space-y-4">
          <Tag variant="info" size="sm" className="bg-white/12 text-blue-50 ring-1 ring-white/15">
            Intraday Forecasting
          </Tag>
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">Technical Analysis</h1>
            <p className="max-w-3xl text-sm leading-6 text-blue-50/82 md:text-base">
              Pull live 1-minute candles, select a model variant, and project the next 50 bars with
              a forward-looking price path overlay.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-xs text-blue-50/80">
            <HeroPill icon={<Clock3 size={14} />} text="Last 60 live candles" />
            <HeroPill icon={<CandlestickChart size={14} />} text="Next 50 projected candles" />
            <HeroPill icon={<Sparkles size={14} />} text="Two model variants" />
          </div>
        </div>
      </div>

      <Card className="border border-slate-200/90" variant="bordered">
        <CardHeader className="mb-0 border-b border-slate-200 pb-5">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle className="text-2xl">Run Technical Analysis</CardTitle>
              <p className="mt-1 text-sm text-text-secondary">
                Live intraday bars with forward price-path projection.
              </p>
            </div>
            <Tag variant="neutral" className="self-start md:self-auto">
              US equities only
            </Tag>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          <form onSubmit={onSubmit} className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)_220px] xl:items-end">
            <Input
              label="Ticker"
              value={ticker}
              onChange={(event) => setTicker(event.target.value.toUpperCase())}
              placeholder="MSFT, AAPL, NVDA"
              helperText="Uses Alpaca 1-minute bars for live US equity pricing."
            />

            <div className="grid gap-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-text-primary">Model Version</label>
                <span className="text-xs text-text-secondary">Select one forecast profile</span>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {MODEL_OPTIONS.map((option) => {
                  const selected = option.value === modelVersion;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setModelVersion(option.value)}
                      className={cn(
                        'rounded-2xl border px-4 py-3 text-left transition-all duration-200',
                        selected
                          ? 'border-primary-500 bg-blue-50 shadow-[0_12px_28px_rgba(37,99,235,0.12)]'
                          : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                      )}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-base font-semibold text-text-primary">{option.label}</span>
                        <span
                          className={cn(
                            'h-3 w-3 rounded-full border',
                            selected ? 'border-primary-600 bg-primary-600' : 'border-slate-300 bg-white'
                          )}
                        />
                      </div>
                      <p className="mt-2 text-sm leading-5 text-text-secondary">{option.summary}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            <Button type="submit" size="lg" fullWidth isLoading={status === 'loading'} className="h-[52px]">
              Analyze Technicals
            </Button>
          </form>

          {status === 'loading' && (
            <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50/80">
              <div className="border-b border-slate-200 px-4 py-3">
                <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                  <p className="text-sm font-medium text-text-primary">
                    Generating outlook for {lastSubmittedTicker}
                  </p>
                  <span className="text-xs text-text-secondary">
                    Fetching 1-minute bars and producing 50 projected candles
                  </span>
                </div>
              </div>
              <div className="px-4 py-4">
                <div className="h-2 rounded-full bg-slate-200 progress-indeterminate" />
                <div className="mt-3 grid gap-3 text-xs text-text-secondary md:grid-cols-3">
                  <ProgressStep label="1. Market data" description="Pulling the latest 60 one-minute candles." />
                  <ProgressStep label="2. Model inference" description={`Running ${selectedModel.label} forecast synthesis.`} />
                  <ProgressStep label="3. Chart overlay" description="Projecting 50 forward candles on the chart." />
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="mt-6 rounded-2xl border border-danger-200 bg-danger-50 px-4 py-3 text-danger-900">
              {error}
            </div>
          )}
        </CardContent>
      </Card>

      {analysis && forecastStats && (
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              icon={<Activity size={18} />}
              label="Latest Price"
              value={`$${analysis.latest_price.toFixed(2)}`}
              detail={`Updated ${new Date(analysis.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
            />
            <MetricCard
              icon={<CandlestickChart size={18} />}
              label="Forecast End"
              value={`$${forecastStats.lastForecast.close.toFixed(2)}`}
              detail={`${analysis.forecast_bars.length} candles ahead`}
            />
            <MetricCard
              icon={forecastStats.direction === 'up' ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
              label="Projected Move"
              value={`${forecastStats.projectedMove >= 0 ? '+' : ''}${forecastStats.projectedMovePct.toFixed(2)}%`}
              detail={`${forecastStats.projectedMove >= 0 ? '+' : ''}$${forecastStats.projectedMove.toFixed(2)} vs latest close`}
              accent={forecastStats.direction === 'up' ? 'success' : 'danger'}
            />
            <MetricCard
              icon={<Database size={18} />}
              label="Data Feed"
              value={analysis.data_source === 'alpaca' ? 'Alpaca' : 'Fallback feed'}
              detail={analysis.model_version === 'v1.2' ? 'Momentum-biased profile' : 'Mean-reversion profile'}
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
      )}
    </div>
  );
}

function HeroPill({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/8 px-3 py-1.5 backdrop-blur-sm">
      {icon}
      <span>{text}</span>
    </div>
  );
}

function ProgressStep({ label, description }: { label: string; description: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
      <p className="font-medium text-text-primary">{label}</p>
      <p className="mt-1 leading-5">{description}</p>
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
  detail,
  accent = 'default',
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
  accent?: 'default' | 'success' | 'danger';
}) {
  return (
    <Card
      className={cn(
        'border border-slate-200/90',
        accent === 'success' && 'border-emerald-200 bg-emerald-50/55',
        accent === 'danger' && 'border-rose-200 bg-rose-50/60'
      )}
      variant="bordered"
    >
      <CardContent className="flex items-start gap-4 p-5">
        <div
          className={cn(
            'flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white',
            accent === 'success' && 'bg-emerald-600',
            accent === 'danger' && 'bg-rose-600'
          )}
        >
          {icon}
        </div>
        <div>
          <p className="text-sm text-text-secondary">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-text-primary">{value}</p>
          <p className="mt-1 text-sm text-text-secondary">{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}

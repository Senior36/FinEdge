export interface TechnicalCandle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_prediction: boolean;
}

export interface TechnicalAnalysisRequest {
  ticker: string;
  model_version: 'v1.1' | 'v1.2';
  history_bars?: number;
  forecast_bars?: number;
}

export interface TechnicalAnalysisResponse {
  ticker: string;
  timeframe: '1Min';
  model_version: 'v1.1' | 'v1.2';
  data_source: string;
  latest_price: number;
  history_bars: TechnicalCandle[];
  forecast_bars: TechnicalCandle[];
  generated_at: string;
}

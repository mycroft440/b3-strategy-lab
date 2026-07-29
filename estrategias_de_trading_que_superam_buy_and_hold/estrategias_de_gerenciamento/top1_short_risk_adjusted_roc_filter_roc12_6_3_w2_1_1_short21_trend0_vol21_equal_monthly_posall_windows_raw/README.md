# top1_short_risk_adjusted_roc_filter_roc12_6_3_w2_1_1_short21_trend0_vol21_equal_monthly_posall_windows_raw

## Como funciona

- Selecao: `short_risk_adjusted_roc_filter`; conserva no maximo 1 ativo(s).
- Janela principal: 252 candles; defasagem: 0.
- Filtro de tendencia: 0 candles.
- Volatilidade: 21 candles.
- Ponderacao: `equal`; peso maximo: 100.00%.
- Rebalanceamento: `monthly`.
- Momentum absoluto obrigatorio: sim.
- Volatilidade-alvo: 0.00%.
- Precos para sinais: `raw`.

## Configuracao integral

```json
{
  "name": "top1_short_risk_adjusted_roc_filter_roc12_6_3_w2_1_1_short21_trend0_vol21_equal_monthly_posall_windows_raw",
  "lookback": 252,
  "skip": 0,
  "top_n": 1,
  "trend_window": 0,
  "vol_window": 21,
  "rebalance": "monthly",
  "score": "short_risk_adjusted_roc_filter",
  "weighting": "equal",
  "absolute_momentum": true,
  "max_weight": 1.0,
  "target_vol": 0.0,
  "signal_mode": "raw",
  "roc_windows": "252,126,63",
  "roc_weights": "2,1,1",
  "positive_rule": "all_windows",
  "short_window": 21,
  "short_weight": 1.0
}
```

O ranking usa apenas informacoes conhecidas no fechamento. As alteracoes de carteira sao executadas na abertura do candle seguinte.

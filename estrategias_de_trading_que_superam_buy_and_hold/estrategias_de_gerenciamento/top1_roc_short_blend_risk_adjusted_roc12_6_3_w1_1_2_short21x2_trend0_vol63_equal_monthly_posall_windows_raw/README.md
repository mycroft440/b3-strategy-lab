# top1_roc_short_blend_risk_adjusted_roc12_6_3_w1_1_2_short21x2_trend0_vol63_equal_monthly_posall_windows_raw

## Como funciona

- Selecao: `roc_short_blend_risk_adjusted`; conserva no maximo 1 ativo(s).
- Janela principal: 252 candles; defasagem: 0.
- Filtro de tendencia: 0 candles.
- Volatilidade: 63 candles.
- Ponderacao: `equal`; peso maximo: 100.00%.
- Rebalanceamento: `monthly`.
- Momentum absoluto obrigatorio: sim.
- Volatilidade-alvo: 0.00%.
- Precos para sinais: `raw`.

## Configuracao integral

```json
{
  "name": "top1_roc_short_blend_risk_adjusted_roc12_6_3_w1_1_2_short21x2_trend0_vol63_equal_monthly_posall_windows_raw",
  "lookback": 252,
  "skip": 0,
  "top_n": 1,
  "trend_window": 0,
  "vol_window": 63,
  "rebalance": "monthly",
  "score": "roc_short_blend_risk_adjusted",
  "weighting": "equal",
  "absolute_momentum": true,
  "max_weight": 1.0,
  "target_vol": 0.0,
  "signal_mode": "raw",
  "roc_windows": "252,126,63",
  "roc_weights": "1,1,2",
  "positive_rule": "all_windows",
  "short_window": 21,
  "short_weight": 2.0
}
```

O ranking usa apenas informacoes conhecidas no fechamento. As alteracoes de carteira sao executadas na abertura do candle seguinte.

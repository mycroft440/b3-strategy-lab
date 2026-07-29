# top2_roc_short_blend_risk_adjusted_roc12_6_3_w2_1_1_short21x1_trend200_vol63_inv_vol_monthly_posscore_raw

## Como funciona

- Selecao: `roc_short_blend_risk_adjusted`; conserva no maximo 2 ativo(s).
- Janela principal: 252 candles; defasagem: 0.
- Filtro de tendencia: 200 candles.
- Volatilidade: 63 candles.
- Ponderacao: `inv_vol`; peso maximo: 100.00%.
- Rebalanceamento: `monthly`.
- Momentum absoluto obrigatorio: sim.
- Volatilidade-alvo: 0.00%.
- Precos para sinais: `raw`.

## Configuracao integral

```json
{
  "name": "top2_roc_short_blend_risk_adjusted_roc12_6_3_w2_1_1_short21x1_trend200_vol63_inv_vol_monthly_posscore_raw",
  "lookback": 252,
  "skip": 0,
  "top_n": 2,
  "trend_window": 200,
  "vol_window": 63,
  "rebalance": "monthly",
  "score": "roc_short_blend_risk_adjusted",
  "weighting": "inv_vol",
  "absolute_momentum": true,
  "max_weight": 1.0,
  "target_vol": 0.0,
  "signal_mode": "raw",
  "roc_windows": "252,126,63",
  "roc_weights": "2,1,1",
  "positive_rule": "score",
  "short_window": 21,
  "short_weight": 1.0
}
```

O ranking usa apenas informacoes conhecidas no fechamento. As alteracoes de carteira sao executadas na abertura do candle seguinte.

# top1_momentum_lb21_skip0_trend200_vol21_equal_weekly_abs_cap1_raw

## Como funciona

- Selecao: `momentum`; conserva no maximo 1 ativo(s).
- Janela principal: 21 candles; defasagem: 0.
- Filtro de tendencia: 200 candles.
- Volatilidade: 21 candles.
- Ponderacao: `equal`; peso maximo: 100.00%.
- Rebalanceamento: `weekly`.
- Momentum absoluto obrigatorio: sim.
- Volatilidade-alvo: 0.00%.
- Precos para sinais: `raw`.

## Configuracao integral

```json
{
  "name": "top1_momentum_lb21_skip0_trend200_vol21_equal_weekly_abs_cap1_raw",
  "lookback": 21,
  "skip": 0,
  "top_n": 1,
  "trend_window": 200,
  "vol_window": 21,
  "rebalance": "weekly",
  "score": "momentum",
  "weighting": "equal",
  "absolute_momentum": true,
  "max_weight": 1.0,
  "target_vol": 0.0,
  "signal_mode": "raw",
  "roc_windows": "",
  "roc_weights": "",
  "positive_rule": "score",
  "short_window": 0,
  "short_weight": 0.0
}
```

O ranking usa apenas informacoes conhecidas no fechamento. As alteracoes de carteira sao executadas na abertura do candle seguinte.

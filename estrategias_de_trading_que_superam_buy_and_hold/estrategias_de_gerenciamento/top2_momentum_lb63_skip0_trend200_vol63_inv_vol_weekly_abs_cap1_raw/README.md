# top2_momentum_lb63_skip0_trend200_vol63_inv_vol_weekly_abs_cap1_raw

## Como funciona

- Selecao: `momentum`; conserva no maximo 2 ativo(s).
- Janela principal: 63 candles; defasagem: 0.
- Filtro de tendencia: 200 candles.
- Volatilidade: 63 candles.
- Ponderacao: `inv_vol`; peso maximo: 100.00%.
- Rebalanceamento: `weekly`.
- Momentum absoluto obrigatorio: sim.
- Volatilidade-alvo: 0.00%.
- Precos para sinais: `raw`.

## Configuracao integral

```json
{
  "name": "top2_momentum_lb63_skip0_trend200_vol63_inv_vol_weekly_abs_cap1_raw",
  "lookback": 63,
  "skip": 0,
  "top_n": 2,
  "trend_window": 200,
  "vol_window": 63,
  "rebalance": "weekly",
  "score": "momentum",
  "weighting": "inv_vol",
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

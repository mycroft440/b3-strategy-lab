# top1_voltarget_lb252_trend200_vol63_target0.2_monthly_raw

## Como funciona

- Selecao: `momentum`; conserva no maximo 1 ativo(s).
- Janela principal: 252 candles; defasagem: 0.
- Filtro de tendencia: 200 candles.
- Volatilidade: 63 candles.
- Ponderacao: `inv_vol`; peso maximo: 100.00%.
- Rebalanceamento: `monthly`.
- Momentum absoluto obrigatorio: sim.
- Volatilidade-alvo: 20.00%.
- Precos para sinais: `raw`.

## Configuracao integral

```json
{
  "name": "top1_voltarget_lb252_trend200_vol63_target0.2_monthly_raw",
  "lookback": 252,
  "skip": 0,
  "top_n": 1,
  "trend_window": 200,
  "vol_window": 63,
  "rebalance": "monthly",
  "score": "momentum",
  "weighting": "inv_vol",
  "absolute_momentum": true,
  "max_weight": 1.0,
  "target_vol": 0.2,
  "signal_mode": "raw",
  "roc_windows": "",
  "roc_weights": "",
  "positive_rule": "score",
  "short_window": 0,
  "short_weight": 0.0
}
```

O ranking usa apenas informacoes conhecidas no fechamento. As alteracoes de carteira sao executadas na abertura do candle seguinte.

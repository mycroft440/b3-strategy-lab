# equal_all_weekly_raw

## Como funciona

- Selecao: `all`; conserva no maximo 99 ativo(s).
- Janela principal: 1 candles; defasagem: 0.
- Filtro de tendencia: 0 candles.
- Volatilidade: 63 candles.
- Ponderacao: `equal`; peso maximo: 100.00%.
- Rebalanceamento: `weekly`.
- Momentum absoluto obrigatorio: nao.
- Volatilidade-alvo: 0.00%.
- Precos para sinais: `raw`.

## Configuracao integral

```json
{
  "name": "equal_all_weekly_raw",
  "lookback": 1,
  "skip": 0,
  "top_n": 99,
  "trend_window": 0,
  "vol_window": 63,
  "rebalance": "weekly",
  "score": "all",
  "weighting": "equal",
  "absolute_momentum": false,
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

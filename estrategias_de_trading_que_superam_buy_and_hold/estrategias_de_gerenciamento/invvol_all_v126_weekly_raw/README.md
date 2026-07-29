# invvol_all_v126_weekly_raw

## Como funciona

- Selecao: `all`; conserva no maximo 99 ativo(s).
- Janela principal: 1 candles; defasagem: 0.
- Filtro de tendencia: 0 candles.
- Volatilidade: 126 candles.
- Ponderacao: `inv_vol`; peso maximo: 100.00%.
- Rebalanceamento: `weekly`.
- Momentum absoluto obrigatorio: nao.
- Volatilidade-alvo: 0.00%.
- Precos para sinais: `raw`.

## Configuracao integral

```json
{
  "name": "invvol_all_v126_weekly_raw",
  "lookback": 1,
  "skip": 0,
  "top_n": 99,
  "trend_window": 0,
  "vol_window": 126,
  "rebalance": "weekly",
  "score": "all",
  "weighting": "inv_vol",
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

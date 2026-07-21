# Inventario de estrategias

Catalogo gerado a partir de `b3_strategy_lab/strategies.py`.

## benchmark

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| buy_and_hold | nao | `-` | Compra no primeiro candle e mantem ate o fim. |

## momentum

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| momentum | sim | `lookback=126` | Compra quando o fechamento supera o fechamento de N candles atras. |
| roc_trend | sim | `lookback=126;sma_window=200` | Momentum positivo com filtro de media movel. |

## reversao

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| bollinger_reversion | sim | `window=20;num_std=2.0;exit_z=0.0` | Compra na banda inferior de Bollinger e sai no retorno ao centro. |
| connors_rsi_reversion | sim | `rsi_period=3;streak_rsi_period=2;rank_period=100;lower=20.0;upper=70.0` | Reversao por Connors RSI. |
| down_streak_reversion | sim | `streak_length=3;ibs_lower=0.35;ibs_upper=0.75;trend_window=200;max_hold=10` | Compra apos sequencia de quedas com IBS baixo. |
| ibs_reversion | sim | `ibs_lower=0.2;ibs_upper=0.8;max_hold=3;trend_window=0` | Reversao curta por Internal Bar Strength. |
| rsi2_trend_reversion | sim | `rsi_period=2;lower=5.0;upper=70.0;trend_window=200;sma_window=5;max_hold=10` | Reversao por RSI curto com filtro de tendencia e saida por media curta. |
| rsi_bollinger | sim | `rsi_period=14;lower=50.0;upper=80.0;window=20;num_std=2.0;exit_z=0.0` | Combina sobrevenda por RSI e Bollinger. |
| rsi_cross_reversion | sim | `rsi_period=14;lower=50.0;upper=80.0` | Entra quando o RSI recupera acima do limite inferior. |
| rsi_ibs_reversion | sim | `rsi_period=2;lower=5.0;upper=60.0;ibs_lower=0.25;ibs_upper=0.75;trend_window=200;max_hold=10` | Combina RSI curto e IBS baixo para entrada. |
| rsi_reversion | sim | `rsi_period=14;lower=30.0;upper=70.0` | Compra sobrevenda por RSI e sai em sobrecompra. |
| rsi_reversion_atr | sim | `rsi_period=14;lower=50.0;upper=80.0;atr_period=14;atr_mult=3.0` | Reversao por RSI com stop de volatilidade por ATR. |
| rsi_reversion_hold | sim | `rsi_period=14;lower=50.0;upper=80.0;max_hold=20` | Reversao por RSI com tempo maximo de permanencia. |
| rsi_reversion_trend_entry | sim | `rsi_period=14;lower=50.0;upper=80.0;trend_window=200` | Reversao por RSI com filtro de tendencia apenas na entrada. |
| trend_pullback | sim | `trend_window=200;rsi_period=14;lower=40.0;upper=70.0` | Compra pullback em tendencia positiva. |

## rompimento

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| atr_breakout | sim | `lookback=20;atr_period=14;atr_mult=3.0` | Rompimento de maxima com stop movel por ATR. |
| breakout | sim | `lookback=55;exit_lookback=20` | Compra rompimento de maxima e sai na perda de minima. |
| chandelier_breakout | sim | `lookback=20;atr_period=14;atr_mult=3.0;volume_window=0;volume_mult=1.0` | Rompimento com saida Chandelier/ATR e filtro opcional de volume. |
| keltner_breakout | sim | `window=20;atr_period=10;atr_mult=2.0;exit_z=0.0;trend_window=0` | Rompimento de canal de Keltner com filtro opcional de tendencia. |
| range_expansion_breakout | sim | `range_mult=0.5;atr_period=14;atr_mult=3.0;trend_window=50;volume_window=20;volume_mult=1.0;max_hold=40` | Compra expansao de range no fechamento com stop por ATR. |

## tendencia

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| ema_cross | sim | `fast=12;slow=26` | Cruzamento de medias moveis exponenciais. |
| macd | sim | `fast=12;slow=26;signal_window=9` | Segue a linha MACD contra a linha de sinal. |
| price_sma | sim | `sma_window=200` | Fica comprado quando o preco fecha acima da media simples. |
| sma_cross | sim | `fast=50;slow=200` | Cruzamento de medias moveis simples. |
| sma_stop | sim | `sma_window=200;stop_pct=0.2` | Segue media simples com stop percentual a partir do topo. |
| supertrend_follow | sim | `atr_period=10;atr_mult=3.0` | Segue tendencia pelo indicador SuperTrend baseado em ATR. |

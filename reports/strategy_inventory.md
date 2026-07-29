# Inventario de estrategias

Catalogo gerado a partir de `b3_strategy_lab/strategies.py`.

## avancada

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| dsma_trend | sim | `window=40;trend_window=200` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| dsma_trend_fast | sim | `window=20;trend_window=100` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| dsma_trend_slow | sim | `window=80;trend_window=200` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| ema_rsi_stochastic_adx_10_30 | sim | `fast=10;slow=30;rsi_period=14;stoch_period=14;adx_period=14;adx_threshold=20.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| ema_rsi_stochastic_adx_20_50 | sim | `fast=20;slow=50;rsi_period=14;stoch_period=14;adx_period=14;adx_threshold=20.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| ema_rsi_stochastic_adx_50_100 | sim | `fast=50;slow=100;rsi_period=14;stoch_period=21;adx_period=21;adx_threshold=20.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| ema_rsi_stochastic_adx_50_200 | sim | `fast=50;slow=200;rsi_period=14;stoch_period=21;adx_period=21;adx_threshold=25.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| profit_only_exit_sma100_atr3_catastrophe6 | sim | `sma_window=100;atr_period=14;atr_mult=3.0;catastrophe_mult=6.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| profit_only_exit_sma200_atr4_catastrophe8 | sim | `sma_window=200;atr_period=21;atr_mult=4.0;catastrophe_mult=8.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| profit_only_exit_sma_atr_catastrophe | sim | `sma_window=50;atr_period=14;atr_mult=4.0;catastrophe_mult=6.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |

## benchmark

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| buy_and_hold | nao | `-` | Compra no primeiro candle e mantem ate o fim. |

## combinada

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| adx_rsi_trend_14_20_sma100 | sim | `adx_period=14;threshold=20.0;trend_window=100;rsi_period=14` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_rsi_trend_14_25_sma200 | sim | `adx_period=14;threshold=25.0;trend_window=200;rsi_period=14` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_rsi_trend_21_20_sma200 | sim | `adx_period=21;threshold=20.0;trend_window=200;rsi_period=7` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_14_15_sma50 | sim | `adx_period=14;threshold=15.0;trend_window=50;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_14_20_sma100 | sim | `adx_period=14;threshold=20.0;trend_window=100;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_14_25_sma200 | sim | `adx_period=14;threshold=25.0;trend_window=200;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_21_20_sma100 | sim | `adx_period=21;threshold=20.0;trend_window=100;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_21_25_sma200 | sim | `adx_period=21;threshold=25.0;trend_window=200;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_7_15_sma50 | sim | `adx_period=7;threshold=15.0;trend_window=50;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_7_20_sma100 | sim | `adx_period=7;threshold=20.0;trend_window=100;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| cci_momentum_10_0_m100_sma50 | sim | `period=10;entry_level=0.0;exit_level=-100.0;trend_window=50` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_momentum_14_0_m100_sma100 | sim | `period=14;entry_level=0.0;exit_level=-100.0;trend_window=100` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_momentum_20_0_m100_sma100 | sim | `period=20;entry_level=0.0;exit_level=-100.0;trend_window=100` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_momentum_20_50_m50_sma200 | sim | `period=20;entry_level=50.0;exit_level=-50.0;trend_window=200` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_momentum_30_50_m50_sma200 | sim | `period=30;entry_level=50.0;exit_level=-50.0;trend_window=200` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_trend_10_m100_100_sma50 | sim | `period=10;entry_level=-100.0;exit_level=100.0;trend_window=50` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_trend_14_m100_100_sma100 | sim | `period=14;entry_level=-100.0;exit_level=100.0;trend_window=100` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_trend_20_m100_100_sma100 | sim | `period=20;entry_level=-100.0;exit_level=100.0;trend_window=100` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_trend_20_m100_100_sma200 | sim | `period=20;entry_level=-100.0;exit_level=100.0;trend_window=200` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_trend_30_m100_100_sma200 | sim | `period=30;entry_level=-100.0;exit_level=100.0;trend_window=200` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| ema100_stochastic_14_20_80 | sim | `average_type=ema;trend_window=100;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| ema200_stochastic_14_20_80 | sim | `average_type=ema;trend_window=200;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| ema20_stochastic_14_20_80 | sim | `average_type=ema;trend_window=20;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| ema50_stochastic_14_20_80 | sim | `average_type=ema;trend_window=50;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| ema50_stochastic_21_30_75 | sim | `average_type=ema;trend_window=50;k_period=21;lower=30.0;upper=75.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| rsi_bollinger_14_30_bb20_2 | sim | `rsi_period=14;lower=30.0;upper=70.0;window=20;num_std=2.0;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_14_30_bb20_2_trend200 | sim | `rsi_period=14;lower=30.0;upper=70.0;window=20;num_std=2.0;trend_window=200` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_14_30_bb30_25 | sim | `rsi_period=14;lower=30.0;upper=70.0;window=30;num_std=2.5;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_14_35_bb10_15 | sim | `rsi_period=14;lower=35.0;upper=65.0;window=10;num_std=1.5;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_2_5_bb20_2 | sim | `rsi_period=2;lower=5.0;upper=70.0;window=20;num_std=2.0;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_2_5_bb20_2_trend100 | sim | `rsi_period=2;lower=5.0;upper=70.0;window=20;num_std=2.0;trend_window=100` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_2_5_bb20_2_trend200 | sim | `rsi_period=2;lower=5.0;upper=70.0;window=20;num_std=2.0;trend_window=200` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_3_10_bb20_2 | sim | `rsi_period=3;lower=10.0;upper=70.0;window=20;num_std=2.0;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_5_20_bb20_2 | sim | `rsi_period=5;lower=20.0;upper=65.0;window=20;num_std=2.0;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_5_20_bb20_2_trend100 | sim | `rsi_period=5;lower=20.0;upper=65.0;window=20;num_std=2.0;trend_window=100` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| sma100_stochastic_14_20_80 | sim | `average_type=sma;trend_window=100;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| sma200_stochastic_14_20_80 | sim | `average_type=sma;trend_window=200;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| sma200_stochastic_21_30_75 | sim | `average_type=sma;trend_window=200;k_period=21;lower=30.0;upper=75.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| sma20_stochastic_14_20_80 | sim | `average_type=sma;trend_window=20;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| sma50_stochastic_14_20_80 | sim | `average_type=sma;trend_window=50;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| supertrend_rsi_10_2_14 | sim | `atr_period=10;atr_mult=2.0;oscillator=rsi;oscillator_period=14;lower=40.0;upper=75.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_rsi_10_3_14 | sim | `atr_period=10;atr_mult=3.0;oscillator=rsi;oscillator_period=14;lower=45.0;upper=75.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_rsi_14_3_14 | sim | `atr_period=14;atr_mult=3.0;oscillator=rsi;oscillator_period=14;lower=45.0;upper=70.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_rsi_21_4_21 | sim | `atr_period=21;atr_mult=4.0;oscillator=rsi;oscillator_period=21;lower=45.0;upper=70.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_rsi_7_2_7 | sim | `atr_period=7;atr_mult=2.0;oscillator=rsi;oscillator_period=7;lower=40.0;upper=75.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_stochastic_10_2_14 | sim | `atr_period=10;atr_mult=2.0;oscillator=stochastic;oscillator_period=14;lower=25.0;upper=80.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_stochastic_10_3_14 | sim | `atr_period=10;atr_mult=3.0;oscillator=stochastic;oscillator_period=14;lower=25.0;upper=80.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_stochastic_14_3_21 | sim | `atr_period=14;atr_mult=3.0;oscillator=stochastic;oscillator_period=21;lower=30.0;upper=75.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_stochastic_21_4_21 | sim | `atr_period=21;atr_mult=4.0;oscillator=stochastic;oscillator_period=21;lower=30.0;upper=75.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_stochastic_7_2_14 | sim | `atr_period=7;atr_mult=2.0;oscillator=stochastic;oscillator_period=14;lower=25.0;upper=80.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |

## momentum

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| momentum | sim | `lookback=126` | Compra quando o fechamento supera o fechamento de N candles atras. |
| roc_trend | sim | `lookback=126;sma_window=200` | Momentum positivo com filtro de media movel. |
| time_series_momentum_12m | sim | `lookback=252;skip=21;trend_window=0` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_12m_no_skip | sim | `lookback=252;skip=0;trend_window=0` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_12m_trend100 | sim | `lookback=252;skip=21;trend_window=100` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_12m_trend200 | sim | `lookback=252;skip=21;trend_window=200` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_18m_skip1m | sim | `lookback=378;skip=21;trend_window=200` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_3m | sim | `lookback=63;skip=0;trend_window=0` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_6m | sim | `lookback=126;skip=0;trend_window=0` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_6m_trend100 | sim | `lookback=126;skip=0;trend_window=100` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_6m_trend200 | sim | `lookback=126;skip=0;trend_window=200` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_9m | sim | `lookback=189;skip=0;trend_window=0` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |

## reversao

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| bollinger_reversion | sim | `window=20;num_std=2.0;exit_z=0.0` | Compra na banda inferior de Bollinger e sai no retorno ao centro. |
| connors_rsi_reversion | sim | `rsi_period=3;streak_rsi_period=2;rank_period=100;lower=20.0;upper=70.0` | Reversao por Connors RSI. |
| down_streak_reversion | sim | `streak_length=3;ibs_lower=0.35;ibs_upper=0.75;trend_window=200;max_hold=10` | Compra apos sequencia de quedas com IBS baixo. |
| ibs_reversion | sim | `ibs_lower=0.2;ibs_upper=0.8;max_hold=3;trend_window=0` | Reversao curta por Internal Bar Strength. |
| rsi14_reversion_25_60 | sim | `rsi_period=14;lower=25.0;upper=60.0;trend_window=0;max_hold=30` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi14_reversion_30_70_trend200 | sim | `rsi_period=14;lower=30.0;upper=70.0;trend_window=200;max_hold=30` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi2_reversion_10_70 | sim | `rsi_period=2;lower=10.0;upper=70.0;trend_window=0;max_hold=10` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi2_reversion_5_70 | sim | `rsi_period=2;lower=5.0;upper=70.0;trend_window=0;max_hold=10` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi2_reversion_5_70_trend100 | sim | `rsi_period=2;lower=5.0;upper=70.0;trend_window=100;max_hold=10` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi2_reversion_5_70_trend200 | sim | `rsi_period=2;lower=5.0;upper=70.0;trend_window=200;max_hold=10` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi2_trend_reversion | sim | `rsi_period=2;lower=5.0;upper=70.0;trend_window=200;sma_window=5;max_hold=10` | Reversao por RSI curto com filtro de tendencia e saida por media curta. |
| rsi3_reversion_15_70 | sim | `rsi_period=3;lower=15.0;upper=70.0;trend_window=0;max_hold=15` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi5_reversion_20_65 | sim | `rsi_period=5;lower=20.0;upper=65.0;trend_window=0;max_hold=20` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi5_reversion_20_65_trend100 | sim | `rsi_period=5;lower=20.0;upper=65.0;trend_window=100;max_hold=20` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi7_reversion_25_65 | sim | `rsi_period=7;lower=25.0;upper=65.0;trend_window=0;max_hold=20` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
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
| atr_breakout_10_atr7_x2 | sim | `lookback=10;atr_period=7;atr_mult=2.0;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_20_atr10_x2 | sim | `lookback=20;atr_period=10;atr_mult=2.0;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_20_atr14_x25 | sim | `lookback=20;atr_period=14;atr_mult=2.5;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_20_atr14_x3_trend100 | sim | `lookback=20;atr_period=14;atr_mult=3.0;trend_window=100` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_20_atr14_x3_trend50 | sim | `lookback=20;atr_period=14;atr_mult=3.0;trend_window=50` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_20_atr14_x4 | sim | `lookback=20;atr_period=14;atr_mult=4.0;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_55_atr14_x3 | sim | `lookback=55;atr_period=14;atr_mult=3.0;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_55_atr14_x3_trend100 | sim | `lookback=55;atr_period=14;atr_mult=3.0;trend_window=100` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_55_atr21_x4 | sim | `lookback=55;atr_period=21;atr_mult=4.0;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_55_atr21_x4_trend200 | sim | `lookback=55;atr_period=21;atr_mult=4.0;trend_window=200` | Rompimento de maxima com stop movel calculado por ATR. |
| breakout | sim | `lookback=55;exit_lookback=20` | Compra rompimento de maxima e sai na perda de minima. |
| chandelier_breakout | sim | `lookback=20;atr_period=14;atr_mult=3.0;volume_window=0;volume_mult=1.0` | Rompimento com saida Chandelier/ATR e filtro opcional de volume. |
| donchian_breakout_100_50 | sim | `entry_window=100;exit_window=50;trend_window=0` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_100_50_trend200 | sim | `entry_window=100;exit_window=50;trend_window=200` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_10_5 | sim | `entry_window=10;exit_window=5;trend_window=0` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_20_10 | sim | `entry_window=20;exit_window=10;trend_window=0` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_20_10_trend100 | sim | `entry_window=20;exit_window=10;trend_window=100` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_20_10_trend50 | sim | `entry_window=20;exit_window=10;trend_window=50` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_40_20 | sim | `entry_window=40;exit_window=20;trend_window=0` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_55_20 | sim | `entry_window=55;exit_window=20;trend_window=0` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_55_20_trend100 | sim | `entry_window=55;exit_window=20;trend_window=100` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_55_20_trend200 | sim | `entry_window=55;exit_window=20;trend_window=200` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| keltner_breakout | sim | `window=20;atr_period=10;atr_mult=2.0;exit_z=0.0;trend_window=0` | Rompimento de canal de Keltner com filtro opcional de tendencia. |
| range_expansion_breakout | sim | `range_mult=0.5;atr_period=14;atr_mult=3.0;trend_window=50;volume_window=20;volume_mult=1.0;max_hold=40` | Compra expansao de range no fechamento com stop por ATR. |

## tendencia

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| ema_cross | sim | `fast=12;slow=26` | Cruzamento de medias moveis exponenciais. |
| ema_cross_100_200 | sim | `average_type=ema;fast=100;slow=200` | Cruzamento de medias EMA 100/200. |
| ema_cross_10_30 | sim | `average_type=ema;fast=10;slow=30` | Cruzamento de medias EMA 10/30. |
| ema_cross_20_50 | sim | `average_type=ema;fast=20;slow=50` | Cruzamento de medias EMA 20/50. |
| ema_cross_50_100 | sim | `average_type=ema;fast=50;slow=100` | Cruzamento de medias EMA 50/100. |
| ema_cross_5_20 | sim | `average_type=ema;fast=5;slow=20` | Cruzamento de medias EMA 5/20. |
| macd | sim | `fast=12;slow=26;signal_window=9` | Segue a linha MACD contra a linha de sinal. |
| macd_10_30_9 | sim | `fast=10;slow=30;signal_window=9;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_12_26_12 | sim | `fast=12;slow=26;signal_window=12;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_12_26_5 | sim | `fast=12;slow=26;signal_window=5;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_12_26_9_trend100 | sim | `fast=12;slow=26;signal_window=9;trend_window=100` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_12_26_9_trend200 | sim | `fast=12;slow=26;signal_window=9;trend_window=200` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_12_26_9_trend50 | sim | `fast=12;slow=26;signal_window=9;trend_window=50` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_19_39_9 | sim | `fast=19;slow=39;signal_window=9;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_24_52_18 | sim | `fast=24;slow=52;signal_window=18;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_5_35_5 | sim | `fast=5;slow=35;signal_window=5;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_8_17_9 | sim | `fast=8;slow=17;signal_window=9;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| price_sma | sim | `sma_window=200` | Fica comprado quando o preco fecha acima da media simples. |
| sma_cross | sim | `fast=50;slow=200` | Cruzamento de medias moveis simples. |
| sma_cross_100_200 | sim | `average_type=sma;fast=100;slow=200` | Cruzamento de medias SMA 100/200. |
| sma_cross_10_50 | sim | `average_type=sma;fast=10;slow=50` | Cruzamento de medias SMA 10/50. |
| sma_cross_20_100 | sim | `average_type=sma;fast=20;slow=100` | Cruzamento de medias SMA 20/100. |
| sma_cross_50_100 | sim | `average_type=sma;fast=50;slow=100` | Cruzamento de medias SMA 50/100. |
| sma_cross_5_20 | sim | `average_type=sma;fast=5;slow=20` | Cruzamento de medias SMA 5/20. |
| sma_stop | sim | `sma_window=200;stop_pct=0.2` | Segue media simples com stop percentual a partir do topo. |
| supertrend_follow | sim | `atr_period=10;atr_mult=3.0` | Segue tendencia pelo indicador SuperTrend baseado em ATR. |

## volume

| Estrategia | Sweep | Parametros padrao | Descricao |
|---|---|---|---|
| mfi_momentum_10_50_30_sma100 | sim | `period=10;entry_level=50.0;exit_level=30.0;trend_window=100` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_momentum_14_55_35_sma100 | sim | `period=14;entry_level=55.0;exit_level=35.0;trend_window=100` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_momentum_14_55_35_sma200 | sim | `period=14;entry_level=55.0;exit_level=35.0;trend_window=200` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_momentum_21_60_40_sma200 | sim | `period=21;entry_level=60.0;exit_level=40.0;trend_window=200` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_momentum_7_50_30_sma50 | sim | `period=7;entry_level=50.0;exit_level=30.0;trend_window=50` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_trend_10_20_80_sma100 | sim | `period=10;entry_level=20.0;exit_level=80.0;trend_window=100` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_trend_14_20_80_sma100 | sim | `period=14;entry_level=20.0;exit_level=80.0;trend_window=100` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_trend_14_25_75_sma200 | sim | `period=14;entry_level=25.0;exit_level=75.0;trend_window=200` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_trend_21_25_75_sma200 | sim | `period=21;entry_level=25.0;exit_level=75.0;trend_window=200` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_trend_7_20_80_sma50 | sim | `period=7;entry_level=20.0;exit_level=80.0;trend_window=50` | Money Flow Index combina preco e volume com filtro de tendencia. |

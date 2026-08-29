# Inventario de estrategias

Catalogo gerado a partir de `b3_strategy_lab/strategies.py`.

## avancada

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| dsma_trend | sim | sim | `window=40;trend_window=200` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| dsma_trend_fast | sim | sim | `window=20;trend_window=100` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| dsma_trend_slow | sim | sim | `window=80;trend_window=200` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| ema_rsi_stochastic_adx_10_30 | sim | sim | `fast=10;slow=30;rsi_period=14;stoch_period=14;adx_period=14;adx_threshold=20.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| ema_rsi_stochastic_adx_20_50 | sim | sim | `fast=20;slow=50;rsi_period=14;stoch_period=14;adx_period=14;adx_threshold=20.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| ema_rsi_stochastic_adx_50_100 | sim | sim | `fast=50;slow=100;rsi_period=14;stoch_period=21;adx_period=21;adx_threshold=20.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| ema_rsi_stochastic_adx_50_200 | sim | sim | `fast=50;slow=200;rsi_period=14;stoch_period=21;adx_period=21;adx_threshold=25.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| profit_only_exit_sma100_atr3_catastrophe6 | sim | sim | `sma_window=100;atr_period=14;atr_mult=3.0;catastrophe_mult=6.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| profit_only_exit_sma200_atr4_catastrophe8 | sim | sim | `sma_window=200;atr_period=21;atr_mult=4.0;catastrophe_mult=8.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |
| profit_only_exit_sma_atr_catastrophe | sim | sim | `sma_window=50;atr_period=14;atr_mult=4.0;catastrophe_mult=6.0` | Refinamento avancado com tendencia, osciladores e controle de saida. |

## benchmark

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| buy_and_hold | nao | sim | `-` | Mantem o sinal de compra ativo em todos os candles; no teste por ativo, compra na primeira abertura e permanece comprado ate o fim. |

## combinada

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| adx_rsi_trend_14_20_sma100 | sim | sim | `adx_period=14;threshold=20.0;trend_window=100;rsi_period=14` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_rsi_trend_14_25_sma200 | sim | sim | `adx_period=14;threshold=25.0;trend_window=200;rsi_period=14` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_rsi_trend_21_20_sma200 | sim | sim | `adx_period=21;threshold=20.0;trend_window=200;rsi_period=7` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_14_15_sma50 | sim | sim | `adx_period=14;threshold=15.0;trend_window=50;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_14_20_sma100 | sim | sim | `adx_period=14;threshold=20.0;trend_window=100;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_14_25_sma200 | sim | sim | `adx_period=14;threshold=25.0;trend_window=200;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_21_20_sma100 | sim | sim | `adx_period=21;threshold=20.0;trend_window=100;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_21_25_sma200 | sim | sim | `adx_period=21;threshold=25.0;trend_window=200;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_7_15_sma50 | sim | sim | `adx_period=7;threshold=15.0;trend_window=50;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| adx_trend_7_20_sma100 | sim | sim | `adx_period=7;threshold=20.0;trend_window=100;rsi_period=0` | ADX e direcionais confirmam forca compradora acima da media de tendencia. |
| cci_momentum_10_0_m100_sma50 | sim | sim | `period=10;entry_level=0.0;exit_level=-100.0;trend_window=50` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_momentum_14_0_m100_sma100 | sim | sim | `period=14;entry_level=0.0;exit_level=-100.0;trend_window=100` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_momentum_20_0_m100_sma100 | sim | sim | `period=20;entry_level=0.0;exit_level=-100.0;trend_window=100` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_momentum_20_50_m50_sma200 | sim | sim | `period=20;entry_level=50.0;exit_level=-50.0;trend_window=200` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_momentum_30_50_m50_sma200 | sim | sim | `period=30;entry_level=50.0;exit_level=-50.0;trend_window=200` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_trend_10_m100_100_sma50 | sim | sim | `period=10;entry_level=-100.0;exit_level=100.0;trend_window=50` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_trend_14_m100_100_sma100 | sim | sim | `period=14;entry_level=-100.0;exit_level=100.0;trend_window=100` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_trend_20_m100_100_sma100 | sim | sim | `period=20;entry_level=-100.0;exit_level=100.0;trend_window=100` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_trend_20_m100_100_sma200 | sim | sim | `period=20;entry_level=-100.0;exit_level=100.0;trend_window=200` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| cci_trend_30_m100_100_sma200 | sim | sim | `period=30;entry_level=-100.0;exit_level=100.0;trend_window=200` | CCI identifica impulso ou pullback dentro de uma tendencia de alta. |
| ema100_stochastic_14_20_80 | sim | sim | `average_type=ema;trend_window=100;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| ema200_stochastic_14_20_80 | sim | sim | `average_type=ema;trend_window=200;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| ema20_stochastic_14_20_80 | sim | sim | `average_type=ema;trend_window=20;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| ema50_stochastic_14_20_80 | sim | sim | `average_type=ema;trend_window=50;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| ema50_stochastic_21_30_75 | sim | sim | `average_type=ema;trend_window=50;k_period=21;lower=30.0;upper=75.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| heikin_ashi_stochastic | sim | sim | `k_period=14;slowing=3;d_period=3;lower=20.0;upper=80.0` | Reversao Heikin-Ashi confirmada por cruzamento estocastico em zona extrema. |
| rsi_bollinger_14_30_bb20_2 | sim | sim | `rsi_period=14;lower=30.0;upper=70.0;window=20;num_std=2.0;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_14_30_bb20_2_trend200 | sim | sim | `rsi_period=14;lower=30.0;upper=70.0;window=20;num_std=2.0;trend_window=200` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_14_30_bb30_25 | sim | sim | `rsi_period=14;lower=30.0;upper=70.0;window=30;num_std=2.5;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_14_35_bb10_15 | sim | sim | `rsi_period=14;lower=35.0;upper=65.0;window=10;num_std=1.5;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_2_5_bb20_2 | sim | sim | `rsi_period=2;lower=5.0;upper=70.0;window=20;num_std=2.0;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_2_5_bb20_2_trend100 | sim | sim | `rsi_period=2;lower=5.0;upper=70.0;window=20;num_std=2.0;trend_window=100` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_2_5_bb20_2_trend200 | sim | sim | `rsi_period=2;lower=5.0;upper=70.0;window=20;num_std=2.0;trend_window=200` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_3_10_bb20_2 | sim | sim | `rsi_period=3;lower=10.0;upper=70.0;window=20;num_std=2.0;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_5_20_bb20_2 | sim | sim | `rsi_period=5;lower=20.0;upper=65.0;window=20;num_std=2.0;trend_window=0` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| rsi_bollinger_5_20_bb20_2_trend100 | sim | sim | `rsi_period=5;lower=20.0;upper=65.0;window=20;num_std=2.0;trend_window=100` | RSI em sobrevenda confirmado pela banda inferior de Bollinger. |
| sma100_stochastic_14_20_80 | sim | sim | `average_type=sma;trend_window=100;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| sma200_stochastic_14_20_80 | sim | sim | `average_type=sma;trend_window=200;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| sma200_stochastic_21_30_75 | sim | sim | `average_type=sma;trend_window=200;k_period=21;lower=30.0;upper=75.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| sma20_stochastic_14_20_80 | sim | sim | `average_type=sma;trend_window=20;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| sma50_stochastic_14_20_80 | sim | sim | `average_type=sma;trend_window=50;k_period=14;lower=20.0;upper=80.0` | Media movel define a tendencia; Estocastico define o pullback e a saida. |
| supertrend_rsi_10_2_14 | sim | sim | `atr_period=10;atr_mult=2.0;oscillator=rsi;oscillator_period=14;lower=40.0;upper=75.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_rsi_10_3_14 | sim | sim | `atr_period=10;atr_mult=3.0;oscillator=rsi;oscillator_period=14;lower=45.0;upper=75.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_rsi_14_3_14 | sim | sim | `atr_period=14;atr_mult=3.0;oscillator=rsi;oscillator_period=14;lower=45.0;upper=70.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_rsi_21_4_21 | sim | sim | `atr_period=21;atr_mult=4.0;oscillator=rsi;oscillator_period=21;lower=45.0;upper=70.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_rsi_7_2_7 | sim | sim | `atr_period=7;atr_mult=2.0;oscillator=rsi;oscillator_period=7;lower=40.0;upper=75.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_stochastic_10_2_14 | sim | sim | `atr_period=10;atr_mult=2.0;oscillator=stochastic;oscillator_period=14;lower=25.0;upper=80.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_stochastic_10_3_14 | sim | sim | `atr_period=10;atr_mult=3.0;oscillator=stochastic;oscillator_period=14;lower=25.0;upper=80.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_stochastic_14_3_21 | sim | sim | `atr_period=14;atr_mult=3.0;oscillator=stochastic;oscillator_period=21;lower=30.0;upper=75.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_stochastic_21_4_21 | sim | sim | `atr_period=21;atr_mult=4.0;oscillator=stochastic;oscillator_period=21;lower=30.0;upper=75.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |
| supertrend_stochastic_7_2_14 | sim | sim | `atr_period=7;atr_mult=2.0;oscillator=stochastic;oscillator_period=14;lower=25.0;upper=80.0` | SuperTrend define a direcao e um oscilador confirma entrada e saida. |

## momentum

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| awesome_oscillator | sim | sim | `fast_period=5;slow_period=34` | Awesome Oscillator: momentum do preco mediano acima ou abaixo de zero. |
| coppock_curve | sim | sim | `short_roc=11;long_roc=14;wma_period=10` | Coppock: compra a inflexao negativa para cima e sai na inflexao positiva. |
| gap_momentum | sim | sim | `period=40;signal_period=20` | Gap Momentum de Kaufman: compra quando a linha-sinal sobe e sai quando ela cai. |
| know_sure_thing | sim | sim | `roc1=10;roc2=15;roc3=20;roc4=30;sma1=10;sma2=10;sma3=10;sma4=15;signal_period=9` | Know Sure Thing de Pring: quatro horizontes de ROC contra a linha de sinal. |
| momentum | sim | sim | `lookback=126` | Compra quando o fechamento supera o fechamento de N candles atras. |
| roc_trend | sim | sim | `lookback=126;sma_window=200` | Momentum positivo com filtro de media movel. |
| schaff_trend_cycle | sim | sim | `fast_period=23;slow_period=50;cycle_period=10;smoothing=0.5;lower=25.0;upper=75.0` | Schaff Trend Cycle: ciclo estocastico duplo do MACD com zonas de histerese. |
| time_series_momentum_12m | sim | sim | `lookback=252;skip=21;trend_window=0` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_12m_no_skip | sim | sim | `lookback=252;skip=0;trend_window=0` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_12m_trend100 | sim | sim | `lookback=252;skip=21;trend_window=100` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_12m_trend200 | sim | sim | `lookback=252;skip=21;trend_window=200` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_18m_skip1m | sim | sim | `lookback=378;skip=21;trend_window=200` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_3m | sim | sim | `lookback=63;skip=0;trend_window=0` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_6m | sim | sim | `lookback=126;skip=0;trend_window=0` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_6m_trend100 | sim | sim | `lookback=126;skip=0;trend_window=100` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_6m_trend200 | sim | sim | `lookback=126;skip=0;trend_window=200` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| time_series_momentum_9m | sim | sim | `lookback=189;skip=0;trend_window=0` | Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional. |
| trix_signal | sim | sim | `period=15;signal_period=9` | TRIX: cruzamento da variacao da tripla EMA contra sua linha de sinal. |
| true_strength_index | sim | sim | `long_period=25;short_period=13;signal_period=7` | True Strength Index: momentum duplamente suavizado contra a linha de sinal. |

## price_action

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| inside_bar_breakout | sim | sim | `expiry=5;atr_period=14;atr_mult=3.0;hold_limit=20` | Inside Bar: rompe a maxima da barra-mae com saidas objetivas. |
| nr7_breakout | sim | sim | `setup_period=7;expiry=5;atr_period=14;atr_mult=3.0;hold_limit=20` | NR7 de Crabel: rompe a maxima do menor range em sete barras. |

## regime

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| low_vol_trend | sim | sim | `vol_period=63;trend_window=100;max_vol=0.35` | Tendencia de preco filtrada por baixa volatilidade realizada. |
| realized_vol_low_momentum | sim | sim | `vol_period=63;momentum_lookback=63;max_vol=0.45` | Momentum positivo apenas em regime de volatilidade realizada controlada. |
| vertical_horizontal_filter | sim | sim | `period=28;entry_level=0.4;exit_level=0.25;trend_window=50` | VHF: entra em tendencia altista direcional e sai quando o regime enfraquece. |

## reversao

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| bollinger_reversion | sim | sim | `window=20;num_std=2.0;exit_z=0.0` | Compra na banda inferior de Bollinger e sai no retorno ao centro. |
| connors_rsi_reversion | sim | sim | `rsi_period=3;streak_rsi_period=2;rank_period=100;lower=20.0;upper=70.0` | Reversao por Connors RSI. |
| down_streak_reversion | sim | sim | `streak_length=3;ibs_lower=0.35;ibs_upper=0.75;trend_window=200;max_hold=10` | Compra apos sequencia de quedas com IBS baixo. |
| fisher_transform_reversal | sim | sim | `period=10;lower=-1.5;upper=1.5` | Fisher Transform: compra a virada na sobrevenda e sai na virada da sobrecompra. |
| ibs_reversion | sim | sim | `ibs_lower=0.2;ibs_upper=0.8;max_hold=3;trend_window=0` | Reversao curta por Internal Bar Strength. |
| laguerre_rsi_reversal | sim | sim | `gamma=0.5;lower=0.2;upper=0.8` | Laguerre RSI de Ehlers: recuperacao da sobrevenda com saida apos sobrecompra. |
| mass_index_reversal | sim | sim | `ema_period=9;sum_period=25;bulge_level=27.0;trigger_level=26.5;exit_window=9;hold_limit=20` | Mass Index: lado comprador da reversal bulge com saida por EMA ou tempo. |
| rsi14_reversion_25_60 | sim | sim | `rsi_period=14;lower=25.0;upper=60.0;trend_window=0;max_hold=30` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi14_reversion_30_70_trend200 | sim | sim | `rsi_period=14;lower=30.0;upper=70.0;trend_window=200;max_hold=30` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi2_reversion_10_70 | sim | sim | `rsi_period=2;lower=10.0;upper=70.0;trend_window=0;max_hold=10` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi2_reversion_5_70 | sim | sim | `rsi_period=2;lower=5.0;upper=70.0;trend_window=0;max_hold=10` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi2_reversion_5_70_trend100 | sim | sim | `rsi_period=2;lower=5.0;upper=70.0;trend_window=100;max_hold=10` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi2_reversion_5_70_trend200 | sim | sim | `rsi_period=2;lower=5.0;upper=70.0;trend_window=200;max_hold=10` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi2_trend_reversion | sim | sim | `rsi_period=2;lower=5.0;upper=70.0;trend_window=200;sma_window=5;max_hold=10` | Reversao por RSI curto com filtro de tendencia e saida por media curta. |
| rsi3_reversion_15_70 | sim | sim | `rsi_period=3;lower=15.0;upper=70.0;trend_window=0;max_hold=15` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi5_reversion_20_65 | sim | sim | `rsi_period=5;lower=20.0;upper=65.0;trend_window=0;max_hold=20` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi5_reversion_20_65_trend100 | sim | sim | `rsi_period=5;lower=20.0;upper=65.0;trend_window=100;max_hold=20` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi7_reversion_25_65 | sim | sim | `rsi_period=7;lower=25.0;upper=65.0;trend_window=0;max_hold=20` | Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais. |
| rsi_bollinger | sim | sim | `rsi_period=14;lower=50.0;upper=80.0;window=20;num_std=2.0;exit_z=0.0` | Combina sobrevenda por RSI e Bollinger. |
| rsi_cross_reversion | sim | sim | `rsi_period=14;lower=50.0;upper=80.0` | Entra quando o RSI recupera acima do limite inferior. |
| rsi_ibs_reversion | sim | sim | `rsi_period=2;lower=5.0;upper=60.0;ibs_lower=0.25;ibs_upper=0.75;trend_window=200;max_hold=10` | Combina RSI curto e IBS baixo para entrada. |
| rsi_reversion | sim | sim | `rsi_period=14;lower=30.0;upper=70.0` | Compra sobrevenda por RSI e sai em sobrecompra. |
| rsi_reversion_atr | sim | sim | `rsi_period=14;lower=50.0;upper=80.0;atr_period=14;atr_mult=3.0` | Reversao por RSI com stop de volatilidade por ATR. |
| rsi_reversion_hold | sim | sim | `rsi_period=14;lower=50.0;upper=80.0;max_hold=20` | Reversao por RSI com tempo maximo de permanencia. |
| rsi_reversion_trend_entry | sim | sim | `rsi_period=14;lower=50.0;upper=80.0;trend_window=200` | Reversao por RSI com filtro de tendencia apenas na entrada. |
| rvi_reversal | sim | sim | `period=10;entry_level=-0.4;exit_level=0.0` | Reversao por cruzamento do Relative Vigor Index apos fraqueza extrema. |
| trend_pullback | sim | sim | `trend_window=200;rsi_period=14;lower=40.0;upper=70.0` | Compra pullback em tendencia positiva. |
| turtle_soup | sim | sim | `lookback=20;sma_window=5;atr_period=14;stop_atr=0.5;hold_limit=5` | Turtle Soup long-only: falso rompimento da minima com saida por media, ATR ou tempo. |
| typical_price_pullback | sim | sim | `period=50;pullback_pct=0.03` | Compra desconto do Typical Price contra sua media e sai na recuperacao. |

## reversao_volume

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| mfi_reversal | sim | sim | `period=14;lower=25.0;upper=70.0` | MFI recupera da sobrevenda; sai em sobrecompra. |

## rompimento

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| atr_breakout | sim | sim | `lookback=20;atr_period=14;atr_mult=3.0` | Rompimento de maxima com stop movel por ATR. |
| atr_breakout_10_atr7_x2 | sim | sim | `lookback=10;atr_period=7;atr_mult=2.0;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_20_atr10_x2 | sim | sim | `lookback=20;atr_period=10;atr_mult=2.0;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_20_atr14_x25 | sim | sim | `lookback=20;atr_period=14;atr_mult=2.5;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_20_atr14_x3_trend100 | sim | sim | `lookback=20;atr_period=14;atr_mult=3.0;trend_window=100` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_20_atr14_x3_trend50 | sim | sim | `lookback=20;atr_period=14;atr_mult=3.0;trend_window=50` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_20_atr14_x4 | sim | sim | `lookback=20;atr_period=14;atr_mult=4.0;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_55_atr14_x3 | sim | sim | `lookback=55;atr_period=14;atr_mult=3.0;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_55_atr14_x3_trend100 | sim | sim | `lookback=55;atr_period=14;atr_mult=3.0;trend_window=100` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_55_atr21_x4 | sim | sim | `lookback=55;atr_period=21;atr_mult=4.0;trend_window=0` | Rompimento de maxima com stop movel calculado por ATR. |
| atr_breakout_55_atr21_x4_trend200 | sim | sim | `lookback=55;atr_period=21;atr_mult=4.0;trend_window=200` | Rompimento de maxima com stop movel calculado por ATR. |
| breakout | sim | sim | `lookback=55;exit_lookback=20` | Compra rompimento de maxima e sai na perda de minima. |
| chandelier_breakout | sim | sim | `lookback=20;atr_period=14;atr_mult=3.0;volume_window=0;volume_mult=1.0` | Rompimento com saida Chandelier/ATR e filtro opcional de volume. |
| donchian_breakout_100_50 | sim | sim | `entry_window=100;exit_window=50;trend_window=0` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_100_50_trend200 | sim | sim | `entry_window=100;exit_window=50;trend_window=200` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_10_5 | sim | sim | `entry_window=10;exit_window=5;trend_window=0` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_20_10 | sim | sim | `entry_window=20;exit_window=10;trend_window=0` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_20_10_trend100 | sim | sim | `entry_window=20;exit_window=10;trend_window=100` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_20_10_trend50 | sim | sim | `entry_window=20;exit_window=10;trend_window=50` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_40_20 | sim | sim | `entry_window=40;exit_window=20;trend_window=0` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_55_20 | sim | sim | `entry_window=55;exit_window=20;trend_window=0` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_55_20_trend100 | sim | sim | `entry_window=55;exit_window=20;trend_window=100` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| donchian_breakout_55_20_trend200 | sim | sim | `entry_window=55;exit_window=20;trend_window=200` | Canal de Donchian com maxima anterior para entrada e minima anterior para saida. |
| keltner_breakout | sim | sim | `window=20;atr_period=10;atr_mult=2.0;exit_z=0.0;trend_window=0` | Rompimento de canal de Keltner com filtro opcional de tendencia. |
| range_expansion_breakout | sim | sim | `range_mult=0.5;atr_period=14;atr_mult=3.0;trend_window=50;volume_window=20;volume_mult=1.0;max_hold=40` | Compra expansao de range no fechamento com stop por ATR. |
| squeeze_breakout | sim | sim | `window=20;num_std=2.0;atr_period=20;keltner_mult=1.5;squeeze_bars=3;atr_mult=3.0` | Rompimento altista apos Bollinger comprimir dentro do canal de Keltner. |

## rompimento_volatilidade

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| high_vol_breakout | sim | sim | `vol_period=63;breakout_lookback=55;min_vol=0.3` | Rompimento de maxima em regime de volatilidade elevada. |
| realized_vol_breakout | sim | sim | `vol_period=63;breakout_lookback=20;min_vol=0.2;exit_sma=20` | Rompimento acompanhado de volatilidade realizada minima, com saida por media. |

## sazonalidade

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| halloween_effect | sim | sim | `entry_month=11;exit_month=5` | Efeito Halloween: comprado de novembro a abril e em caixa de maio a outubro. |
| turn_of_month | sim | sim | `sessions_before=1;sessions_after=3` | Janela sazonal do ultimo pregao ate o terceiro pregao do mes seguinte. |

## tendencia

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| aroon_trend | sim | sim | `period=25;strong_level=70.0` | Aroon: segue novas maximas e sai quando novas minimas dominam. |
| atr_channel_trend | sim | sim | `ema_period=50;atr_period=20;atr_mult=1.5` | Entrada acima de canal EMA+ATR e saida na perda da media. |
| atr_trailing_trend | sim | sim | `trend_period=100;atr_period=20;atr_mult=3.0` | Tendencia acima da EMA com trailing stop baseado em ATR. |
| cmf_ema_trend | sim | sim | `cmf_period=21;ema_period=100;entry_cmf=0.05;exit_cmf=-0.05` | Tendencia de preco por EMA confirmada por Chaikin Money Flow. |
| donchian_40_20_trend | sim | sim | `entry_lookback=40;exit_lookback=20` | Donchian 40/20: rompe maxima de 40 e sai na minima de 20. |
| donchian_80_30_trend | sim | sim | `entry_lookback=80;exit_lookback=30` | Donchian mais lento 80/30 para tendencias prolongadas. |
| efficiency_ratio_trend | sim | sim | `period=40;threshold=0.35` | Razao de eficiencia alta e direcao positiva para filtrar ruido lateral. |
| ema_cross | sim | sim | `fast=12;slow=26` | Cruzamento de medias moveis exponenciais. |
| ema_cross_100_200 | sim | sim | `average_type=ema;fast=100;slow=200` | Cruzamento de medias EMA 100/200. |
| ema_cross_10_30 | sim | sim | `average_type=ema;fast=10;slow=30` | Cruzamento de medias EMA 10/30. |
| ema_cross_20_50 | sim | sim | `average_type=ema;fast=20;slow=50` | Cruzamento de medias EMA 20/50. |
| ema_cross_50_100 | sim | sim | `average_type=ema;fast=50;slow=100` | Cruzamento de medias EMA 50/100. |
| ema_cross_5_20 | sim | sim | `average_type=ema;fast=5;slow=20` | Cruzamento de medias EMA 5/20. |
| ema_fast_slow_trend | sim | sim | `fast=20;slow=80` | EMA curta acima da longa com preco acima da EMA curta. |
| ema_pullback_trend | sim | sim | `fast=21;slow=100` | Compra recuperacao da EMA curta durante tendencia definida pela EMA longa. |
| ema_slope_price_trend | sim | sim | `ema_period=80;slope_lookback=20` | Preco acima de EMA cuja inclinacao permanece positiva. |
| ema_triple_alignment_trend | sim | sim | `fast=20;middle=50;slow=200` | Alinhamento de tres EMAs em ordem de alta. |
| frama_trend | sim | sim | `window=16` | Tendencia pela media fractal adaptativa FRAMA de Ehlers. |
| highest_close_breakout_trend | sim | sim | `entry_lookback=60;exit_lookback=20` | Rompimento do maior fechamento com saida pelo menor fechamento recente. |
| ichimoku_cloud | sim | sim | `tenkan_period=9;kijun_period=26;span_b_period=52;displacement=26` | Ichimoku causal: preco acima da nuvem e Tenkan acima da Kijun. |
| kama_trend | sim | sim | `er_period=10;fast_period=2;slow_period=30` | Tendencia por KAMA de Kaufman com confirmacao simultanea de preco e inclinacao. |
| low_vol_momentum_trend | sim | sim | `vol_period=63;ema_period=100;momentum_lookback=63;max_vol=0.4` | Momentum e EMA positivos sob teto de volatilidade realizada. |
| macd | sim | sim | `fast=12;slow=26;signal_window=9` | Segue a linha MACD contra a linha de sinal. |
| macd_10_30_9 | sim | sim | `fast=10;slow=30;signal_window=9;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_12_26_12 | sim | sim | `fast=12;slow=26;signal_window=12;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_12_26_5 | sim | sim | `fast=12;slow=26;signal_window=5;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_12_26_9_trend100 | sim | sim | `fast=12;slow=26;signal_window=9;trend_window=100` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_12_26_9_trend200 | sim | sim | `fast=12;slow=26;signal_window=9;trend_window=200` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_12_26_9_trend50 | sim | sim | `fast=12;slow=26;signal_window=9;trend_window=50` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_19_39_9 | sim | sim | `fast=19;slow=39;signal_window=9;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_24_52_18 | sim | sim | `fast=24;slow=52;signal_window=18;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_5_35_5 | sim | sim | `fast=5;slow=35;signal_window=5;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_8_17_9 | sim | sim | `fast=8;slow=17;signal_window=9;trend_window=0` | MACD parametrizado com confirmacao de tendencia opcional. |
| macd_signal_long_trend | sim | sim | `fast=12;slow=26;signal_period=9;trend_period=100` | MACD acima do sinal e de zero, confirmado por EMA longa. |
| macd_zero_trend | sim | sim | `fast=12;slow=26` | MACD acima de zero com preco acima da EMA lenta. |
| nvi_dual_ema_trend | sim | sim | `fast=50;slow=150` | NVI acima de duas EMAs alinhadas em alta. |
| parabolic_sar_trend | sim | sim | `af_step=0.02;af_max=0.2` | Parabolic SAR de Wilder: comprado apenas no estado ascendente. |
| precision_trend_ehlers | sim | sim | `long_period=250;short_period=40` | Precision Trend de Ehlers: compra no ROC positivo do filtro e sai no ROC negativo. |
| price_sma | sim | sim | `sma_window=200` | Fica comprado quando o preco fecha acima da media simples. |
| roc_dual_horizon_trend | sim | sim | `short=63;long=126` | ROC positivo simultaneamente em dois horizontes. |
| roc_stack_trend | sim | sim | `short=21;middle=63;long=126` | Momentum positivo em tres horizontes para confirmar tendencia. |
| sma_cross | sim | sim | `fast=50;slow=200` | Cruzamento de medias moveis simples. |
| sma_cross_100_200 | sim | sim | `average_type=sma;fast=100;slow=200` | Cruzamento de medias SMA 100/200. |
| sma_cross_10_50 | sim | sim | `average_type=sma;fast=10;slow=50` | Cruzamento de medias SMA 10/50. |
| sma_cross_20_100 | sim | sim | `average_type=sma;fast=20;slow=100` | Cruzamento de medias SMA 20/100. |
| sma_cross_50_100 | sim | sim | `average_type=sma;fast=50;slow=100` | Cruzamento de medias SMA 50/100. |
| sma_cross_5_20 | sim | sim | `average_type=sma;fast=5;slow=20` | Cruzamento de medias SMA 5/20. |
| sma_pullback_trend | sim | sim | `fast=20;slow=100` | Compra recuperacao da SMA curta dentro de tendencia de alta. |
| sma_slope_price_trend | sim | sim | `sma_period=100;slope_lookback=20` | Preco acima de SMA com inclinacao positiva. |
| sma_stop | sim | sim | `sma_window=200;stop_pct=0.2` | Segue media simples com stop percentual a partir do topo. |
| sma_triple_alignment_trend | sim | sim | `fast=20;middle=50;slow=200` | Alinhamento de tres SMAs em ordem de alta. |
| supertrend_follow | sim | sim | `atr_period=10;atr_mult=3.0` | Segue tendencia pelo indicador SuperTrend baseado em ATR. |
| typical_price_sma_trend | sim | sim | `period=50` | Typical Price acima de sua media simples. |
| ultimate_oscillator_ehlers | sim | sim | `band_edge=20;bandwidth=2.0;rms_period=100` | Ultimate Oscillator de Ehlers: comprado acima de zero e em caixa abaixo de zero. |
| vortex_trend | sim | sim | `period=14` | Vortex de Botes-Siepman: comprado enquanto VI+ permanece acima de VI-. |

## tendencia_volume

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| cmf_price_trend | sim | sim | `cmf_period=21;price_period=50;entry_cmf=0.03;exit_cmf=-0.02` | Tendencia de preco com CMF acima de limiar positivo. |
| efi_trend_confirm | sim | sim | `period=13;trend_window=100` | Force Index positivo confirmado por media de preco. |
| eom_trend_confirm | sim | sim | `period=14;trend_window=100` | Ease of Movement positivo com tendencia de preco. |
| mfi_price_trend | sim | sim | `mfi_period=14;price_period=50;entry_mfi=52.0;exit_mfi=45.0` | Typical Price em tendencia com confirmacao do MFI. |
| mfi_trend_follow | sim | sim | `period=14;trend_window=100;entry=55.0;exit=45.0` | MFI forte confirmado por tendencia de preco. |
| nvi_price_confirm | sim | sim | `nvi_ema=100;price_sma=100` | NVI acima da EMA e preco acima da media. |

## volatilidade

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| choppiness_breakout | sim | sim | `period=14;high_level=61.8;low_level=38.2;trend_window=20;atr_period=14;atr_mult=3.0` | Rompimento depois que o Choppiness Index sai de compressao para tendencia. |

## volume

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| chaikin_money_flow | sim | sim | `period=21;trend_window=100` | Cruzamento positivo do Chaikin Money Flow com filtro opcional de tendencia. |
| cmf_threshold_hysteresis | sim | sim | `period=21;entry=0.05;exit=-0.02` | CMF com bandas distintas de entrada e saida para reduzir ruido. |
| cmf_zero_cross | sim | sim | `period=21` | Comprado enquanto Chaikin Money Flow permanece positivo. |
| ease_of_movement | sim | sim | `period=14` | Ease of Movement suavizado: comprado quando preco e volume favorecem alta. |
| efi_zero_cross | sim | sim | `period=13` | Elder Force Index positivo como regime comprador. |
| elder_force_index | sim | sim | `period=13;trend_window=50` | Force Index de Elder positivo com confirmacao da tendencia de preco. |
| eom_zero_cross | sim | sim | `period=14` | Ease of Movement positivo como sinal de compra. |
| klinger_volume_oscillator | sim | sim | `fast_period=34;slow_period=55;signal_period=13` | Klinger Volume Oscillator acima da EMA de sinal. |
| mfi_momentum_10_50_30_sma100 | sim | sim | `period=10;entry_level=50.0;exit_level=30.0;trend_window=100` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_momentum_14_55_35_sma100 | sim | sim | `period=14;entry_level=55.0;exit_level=35.0;trend_window=100` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_momentum_14_55_35_sma200 | sim | sim | `period=14;entry_level=55.0;exit_level=35.0;trend_window=200` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_momentum_21_60_40_sma200 | sim | sim | `period=21;entry_level=60.0;exit_level=40.0;trend_window=200` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_momentum_7_50_30_sma50 | sim | sim | `period=7;entry_level=50.0;exit_level=30.0;trend_window=50` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_trend_10_20_80_sma100 | sim | sim | `period=10;entry_level=20.0;exit_level=80.0;trend_window=100` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_trend_14_20_80_sma100 | sim | sim | `period=14;entry_level=20.0;exit_level=80.0;trend_window=100` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_trend_14_25_75_sma200 | sim | sim | `period=14;entry_level=25.0;exit_level=75.0;trend_window=200` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_trend_21_25_75_sma200 | sim | sim | `period=21;entry_level=25.0;exit_level=75.0;trend_window=200` | Money Flow Index combina preco e volume com filtro de tendencia. |
| mfi_trend_7_20_80_sma50 | sim | sim | `period=7;entry_level=20.0;exit_level=80.0;trend_window=50` | Money Flow Index combina preco e volume com filtro de tendencia. |
| negative_volume_index | sim | sim | `ema_period=255` | Negative Volume Index de Fosback acima de sua EMA anual. |
| nvi_ema_trend | sim | sim | `ema_period=100` | Negative Volume Index acima de sua EMA. |

## volume_hibrido

| Estrategia | Sweep | Matriz de carteira | Parametros padrao | Descricao |
|---|---|---|---|---|
| cmf_efi_confirm | sim | sim | `cmf_period=21;efi_period=13` | Chaikin Money Flow e Force Index simultaneamente positivos. |
| eom_nvi_confirm | sim | sim | `eom_period=14;nvi_ema=100` | Ease of Movement positivo com NVI acima da EMA. |
| mfi_cmf_confirm | sim | sim | `mfi_period=14;cmf_period=21;entry_mfi=55.0;exit_mfi=45.0` | MFI e CMF precisam confirmar fluxo comprador. |
| mfi_efi_confirm | sim | sim | `mfi_period=14;efi_period=13;entry_mfi=55.0;exit_mfi=45.0` | MFI e Elder Force Index confirmam entrada e saida. |
| nvi_mfi_confirm | sim | sim | `nvi_ema=100;mfi_period=14;entry_mfi=52.0;exit_mfi=45.0` | NVI acima da EMA combinado com MFI comprador. |
| volume_triple_confirm | sim | sim | `cmf_period=21;efi_period=13;eom_period=14` | CMF, Force Index e Ease of Movement confirmam o regime comprador. |

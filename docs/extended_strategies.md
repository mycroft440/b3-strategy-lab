# Segundo lote pesquisado: 21 motores distintos

Este lote amplia o catalogo de 168 para 189 estrategias testaveis sem remover
ou renomear qualquer motor anterior. Sao regras candidatas a backtest, nao
promessas de superar `buy_and_hold`. A avaliacao deve considerar custos,
slippage, teste fora da amostra e diferentes ativos e regimes.

## Contrato comum

- universo operacional long-only: sinal 1 significa comprado e sinal 0, caixa;
- os indicadores de preco usam apenas dados conhecidos ate o fechamento atual;
- uma mudanca de sinal somente e executada na abertura do candle seguinte;
- as nuvens deslocadas do Ichimoku sao realinhadas de forma causal;
- regras de price action sao confirmadas pelo fechamento, sem presumir a ordem
  intrabar entre maxima e minima;
- os valores abaixo sao os parametros canonicos da matriz completa.

## Entradas e saidas deterministicas

| Estrategia | Entrada | Saida | Parametros canonicos |
|---|---|---|---|
| `fisher_transform_reversal` | Fisher anterior em/abaixo de -1,5 e Fisher atual vira para cima | Fisher anterior em/acima de 1,5 e Fisher atual vira para baixo | `period=10`, `lower=-1.5`, `upper=1.5` |
| `laguerre_rsi_reversal` | Laguerre RSI cruza 0,2 para cima | cruza 0,8 para baixo | `gamma=0.5`, `lower=0.2`, `upper=0.8` |
| `ichimoku_cloud` | fechamento acima da nuvem causal e Tenkan acima da Kijun | fechamento abaixo da nuvem ou Tenkan abaixo da Kijun | `tenkan_period=9`, `kijun_period=26`, `span_b_period=52`, `displacement=26` |
| `parabolic_sar_trend` | Parabolic SAR reverte para o estado ascendente e fica abaixo do fechamento | SAR reverte para o estado descendente ou fica acima do fechamento | `af_step=0.02`, `af_max=0.2` |
| `aroon_trend` | Aroon Up >= 70 e acima do Aroon Down | Aroon Down >= 70 e acima do Aroon Up | `period=25`, `strong_level=70` |
| `trix_signal` | TRIX acima da EMA de sinal | TRIX abaixo ou igual a EMA de sinal | `period=15`, `signal_period=9` |
| `schaff_trend_cycle` | STC cruza 25 para cima | STC cruza 75 para baixo | `fast_period=23`, `slow_period=50`, `cycle_period=10`, `smoothing=0.5`, `lower=25`, `upper=75` |
| `coppock_curve` | curva negativa vira para cima | curva positiva vira para baixo | `short_roc=11`, `long_roc=14`, `wma_period=10` |
| `know_sure_thing` | KST fica acima da SMA 9 de sinal | KST fica abaixo ou igual a linha de sinal | ROCs `10/15/20/30`, SMAs `10/10/10/15`, `signal_period=9` |
| `true_strength_index` | TSI fica acima da EMA 7 de sinal | TSI fica abaixo ou igual a linha de sinal | `long_period=25`, `short_period=13`, `signal_period=7` |
| `awesome_oscillator` | SMA 5 do preco mediano menos SMA 34 fica positiva | oscilador fica em zero ou negativo | `fast_period=5`, `slow_period=34` |
| `choppiness_breakout` | CHOP primeiro alcanca 61,8; depois cai a 38,2 ou menos no mesmo fechamento que rompe a maxima dos 14 candles anteriores | CHOP volta a 61,8, fechamento perde SMA 20 ou trailing stop de 3 ATR | `period=14`, niveis `61.8/38.2`, `trend_window=20`, `atr_period=14`, `atr_mult=3` |
| `elder_force_index` | EMA 13 da forca e positiva e fechamento esta acima da SMA 50 | qualquer uma das duas condicoes deixa de existir | `period=13`, `trend_window=50` |
| `ease_of_movement` | SMA 14 do Ease of Movement fica positiva | SMA fica em zero ou negativa | `period=14` |
| `negative_volume_index` | NVI fica acima da EMA de 255 candles | NVI fica abaixo ou igual a EMA | `ema_period=255` |
| `klinger_volume_oscillator` | KVO (EMA 34 menos EMA 55 da forca de volume) fica acima da EMA 13 de sinal | KVO fica abaixo ou igual a linha de sinal | `fast_period=34`, `slow_period=55`, `signal_period=13` |
| `mass_index_reversal` | Mass Index alcanca 27, recua abaixo de 26,5 e a EMA 9 de preco aponta para baixo | fechamento recupera a EMA 9 ou completa 20 candles | `ema_period=9`, `sum_period=25`, niveis `27/26.5`, `exit_window=9`, `hold_limit=20` |
| `vertical_horizontal_filter` | VHF >= 0,4 e fechamento acima da SMA 50 | VHF <= 0,25 ou fechamento abaixo da SMA 50 | `period=28`, niveis `0.4/0.25`, `trend_window=50` |
| `nr7_breakout` | fechamento rompe a maxima da barra de menor range entre as ultimas 7, em ate 5 candles | perde a minima do setup, trailing stop de 3 ATR ou 20 candles | `setup_period=7`, `expiry=5`, `atr_period=14`, `atr_mult=3`, `hold_limit=20` |
| `inside_bar_breakout` | apos inside bar, fechamento rompe a maxima da barra-mae em ate 5 candles | perde o meio da barra-mae, trailing stop de 3 ATR ou 20 candles | `expiry=5`, `atr_period=14`, `atr_mult=3`, `hold_limit=20` |
| `halloween_effect` | sinal no fechamento anterior a primeira sessao conhecida de novembro | sinal de saida no fechamento anterior a primeira sessao conhecida de maio | `entry_month=11`, `exit_month=5` |

O `halloween_effect` consulta somente a data da proxima sessao presente no
arquivo, nunca seu preco. O ultimo candle recebe sinal zero porque nao existe
uma abertura seguinte conhecida no conjunto.

## Fontes das formulas e dos conceitos

- John Ehlers, [Using The Fisher Transform](https://c.mql5.com/forextsd/forum/3/130fish.pdf).
- John Ehlers, [Laguerre RSI](https://www.whselfinvest.com/en-lu/trading-platform/trader-indicators/technical-analysis/05-laguerre-rsi).
- [Ichimoku Kinko Hyo: componentes e deslocamentos](https://en.wikipedia.org/wiki/Ichimoku_Kink%C5%8D_Hy%C5%8D).
- TradingView, [Parabolic SAR](https://www.tradingview.com/support/solutions/43000502597-parabolic-sar-sar/).
- TC2000, [Aroon e Aroon Oscillator](https://help.tc2000.com/m/69404/l/744755-aroon-aroon-oscillator).
- AnyChart, [TRIX](https://docs.anychart.com/Stock_Charts/Technical_Indicators/Triple_Exponential_Moving_Average_%28TRIX%29).
- thinkorswim, [Schaff Trend Cycle](https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/SchaffTrendCycle).
- TC2000, [Coppock Curve](https://help.tc2000.com/m/69445/l/755850-coppock-curve).
- TradingView, [Know Sure Thing](https://www.tradingview.com/support/solutions/43000502329-know-sure-thing-kst/).
- TC2000, [True Strength Index](https://help.tc2000.com/m/69445/l/755888-true-strength-index).
- AvaTrade, [Awesome Oscillator](https://www.avatrade.com/education/technical-analysis-indicators-strategies/awesome-oscillator-indicator-strategies).
- TradingView, [Choppiness Index](https://www.tradingview.com/support/solutions/43000501980-choppiness-index-chop/).
- TC2000, [Elder Force Index](https://help.tc2000.com/m/69445/l/755859-elder-force-index).
- cTrader, [Ease of Movement](https://help.ctrader.com/indicators/built-in/volume/ease-of-movement/).
- TradingView, [Negative Volume Index](https://www.tradingview.com/support/solutions/43000773005-negative-volume-index-nvi/).
- TradingView, [Klinger Oscillator](https://www.tradingview.com/support/solutions/43000589157-klinger-oscillator/).
- TC2000, [Mass Index](https://help.tc2000.com/m/69404/l/751728-mass-index).
- TTR, [Vertical Horizontal Filter](https://rdrr.io/cran/TTR/man/VHF.html).
- StockCharts, [Narrow Range Day NR7](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7).
- PriceAction.com, [Inside Bar](https://priceaction.com/price-action-university/strategies/inside-bar/).
- Bouman e Jacobsen, [The Halloween Indicator, Sell in May and Go Away](https://www.aeaweb.org/articles?id=10.1257%2F000282802762024683).

As fontes definem o indicador ou o efeito estudado. Quando uma fonte nao
prescreve um sistema long-only completo, a tabela documenta a adaptacao
operacional exata do laboratorio, inclusive filtros, stops e prazo de validade.

# Estrategias pesquisadas: regras e fontes

Este lote adiciona 12 motores distintos ao catalogo. Eles sao candidatos de
backtest, nao promessas de superar `buy_and_hold`. Toda comparacao deve incluir
custos realistas, teste fora da amostra e verificacao em diferentes ativos e
regimes.

## Contrato comum

- universo operacional: long-only, alternando entre comprado e caixa;
- cada regra usa OHLCV e estado conhecidos no fechamento do candle;
- a mudanca de posicao e executada apenas na abertura do candle seguinte;
- o sinal nao decide pela maxima ou minima atingida primeiro dentro do candle;
- parametros abaixo sao os valores canonicos usados na matriz completa.

## Regras deterministicas

| Estrategia | Entrada | Saida | Parametros canonicos |
|---|---|---|---|
| `precision_trend_ehlers` | ROC do Precision Trend fica positivo | ROC fica negativo | `long_period=250`, `short_period=40` |
| `ultimate_oscillator_ehlers` | oscilador normalizado fica positivo | oscilador fica negativo | `band_edge=20`, `bandwidth=2`, `rms_period=100` |
| `gap_momentum` | media do gap ratio passa a subir | media do gap ratio passa a cair | `period=40`, `signal_period=20` |
| `heikin_ashi_stochastic` | candle Heikin-Ashi vira altista no mesmo fechamento em que %K cruza %D para cima, ambos na zona de sobrevenda | Heikin-Ashi vira baixista, ou %K cruza %D para baixo na sobrecompra | `k_period=14`, `slowing=3`, `d_period=3`, `lower=20`, `upper=80` |
| `vortex_trend` | VI+ fica acima de VI- | VI- fica acima de VI+ | `period=14` |
| `kama_trend` | fechamento acima da KAMA e KAMA ascendente | fechamento abaixo da KAMA ou KAMA descendente | `er_period=10`, `fast_period=2`, `slow_period=30` |
| `frama_trend` | fechamento acima da FRAMA e FRAMA ascendente | fechamento abaixo da FRAMA ou FRAMA descendente | `window=16` |
| `rvi_reversal` | RVI anterior abaixo de -0,4 e cruzamento altista da linha-sinal | RVI anterior acima de zero e cruzamento baixista | `period=10`, `entry_level=-0.4`, `exit_level=0` |
| `chaikin_money_flow` | CMF cruza zero para cima e fechamento esta acima da media de tendencia | CMF negativo ou fechamento abaixo da media | `period=21`, `trend_window=100` |
| `squeeze_breakout` | depois de tres candles de Bollinger dentro de Keltner, a primeira liberacao fecha acima da banda superior | fechamento abaixo da media de Bollinger ou do trailing stop de 3 ATR | `window=20`, `num_std=2`, `atr_period=20`, `keltner_mult=1.5`, `squeeze_bars=3`, `atr_mult=3` |
| `turtle_soup` | minima rompe a menor minima dos 20 candles anteriores, mas o fechamento recupera esse nivel | fechamento na/acima da SMA 5, abaixo da minima do setup menos 0,5 ATR, ou apos cinco candles | `lookback=20`, `sma_window=5`, `atr_period=14`, `stop_atr=0.5`, `hold_limit=5` |
| `turn_of_month` | sinal no fechamento anterior ao ultimo pregao do mes | sinal de saida depois do terceiro pregao do mes seguinte | `sessions_before=1`, `sessions_after=3` |

`turn_of_month` reconhece as fronteiras no calendario global de pregoes
verificados, recebido separadamente dos candles do ativo. A decisao no
fechamento continua estavel quando novos precos sao anexados: saber que a proxima
sessao e o primeiro ou o ultimo pregao do mes nao depende de observar esse preco.

## Fontes de formula

- John Ehlers, [Precision Trend Analysis - Traders' Tips, setembro de 2024](https://traders.com/Documentation/FEEDbk_docs/2024/09/TradersTips.html).
- John Ehlers, [The Ultimate Oscillator - Traders' Tips, abril de 2025](https://traders.com/Documentation/FEEDbk_docs/2025/04/TradersTips.html).
- Perry Kaufman, [Gap Momentum - Traders' Tips, janeiro de 2024](https://traders.com/Documentation/FEEDbk_docs/2024/01/TradersTips.html).
- Sylvain Vervoort, [material Heikin-Ashi da Stocata](https://stocata.org/youtube/video_012.html). A confirmacao estocastica e uma regra operacional explicita deste laboratorio.
- Etienne Botes e Douglas Siepman, [The Vortex Indicator](https://technical.traders.com/free/v28c01005BOTE.pdf).
- Perry Kaufman, [formula do Efficiency Ratio/KAMA](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/kaufmans-adaptive-moving-average-kama).
- John Ehlers, [Fractal Adaptive Moving Average](https://c.mql5.com/forextsd/forum/26/frama.doc).
- John Ehlers, [Relative Vigor Index - Traders' Tips, janeiro de 2002](https://traders.com/documentation/feedbk_docs/2002/01/TradersTips/TradersTips.html).
- Fidelity, [Chaikin Money Flow](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/cmf).
- thinkorswim, [TTM Squeeze](https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/T-U/TTM-Squeeze). A entrada por rompimento e as saidas sao regras deterministicas deste laboratorio.
- Linda Bradford Raschke e Laurence Connors, *Street Smarts*; resumo do conceito de falso rompimento em [Turtle Soup](https://www.whselfinvest.com/en-lu/trading-platform/free-trading-strategies/tradingsystem/38-turtle-soup). Esta implementacao e a variante long-only confirmada no fechamento descrita acima.
- John McConnell e Wei Xu, [Equity Returns at the Turn of the Month](https://business.purdue.edu/faculty/mcconnell/publications/Equity-Returns-at-the-Turn-of-the-Month.pdf).

As fontes de Ehlers, Kaufman, Vortex, FRAMA e RVI definem diretamente os
indicadores. Quando o artigo nao prescreve um sistema long-only completo, a
tabela acima identifica sem ambiguidade a adaptacao de entrada e saida usada no
codigo.

# B3 Strategy Lab

Laboratorio para testar estrategias compradas por ativo e combina-las com
gerenciamentos de carteira sobre BBSE3, BBDC3, CSMG3, FLRY3, GGBR3, IRBR3,
JHSF3, LOGG3, MLAS3, PETR4, TUPY3 e VALE3.

## Fonte e candles

O caminho verificado usa os arquivos anuais COTAHIST, publicados gratuitamente
pela B3. Os campos `raw_*` preservam o OHLC e o volume oficiais sem ajuste; os
campos `open`, `high`, `low` e `close` sao normalizados somente por eventos que
alteram a quantidade de acoes. Dividendos e JCP ficam excluidos.

Cada manifesto registra hashes dos candles, dos eventos e dos ZIPs de origem.
As razoes de split usadas no periodo padrao estao ligadas a evidencias oficiais
da B3 ou do RI do emissor. A metodologia, os campos e as alternativas oficiais
gratuitas estao em [docs/data_provenance.md](docs/data_provenance.md).

## Comandos

Construir ou atualizar a base oficial diaria e semanal:

```powershell
python scripts\build_verified_market_data.py --years 2000:2026 --download
python -m b3_strategy_lab verify-data --interval 1d
```

`python -m b3_strategy_lab fetch` usa Yahoo apenas como fonte legada e grava em
`data/legacy`; esses arquivos nao entram no backtest verificado.

Rodar media movel 50/200 contra buy and hold, um ativo por vez:

```powershell
python -m b3_strategy_lab backtest --strategy sma_cross --fast 50 --slow 200
```

Rodar breakout com custo de 5 bps por ordem:

```powershell
python -m b3_strategy_lab backtest --strategy breakout --lookback 55 --exit-lookback 20 --cost-bps 5
```

Rodar com custo, slippage e lote inteiro:

```powershell
python -m b3_strategy_lab backtest --strategy breakout --lookback 10 --exit-lookback 40 --cost-bps 20 --slippage-bps 5 --lot-size 1
```

O modo `raw_events` permanece apenas para diagnostico e exige liberacao
explicita enquanto dividendos/JCP nao tiverem ledger oficial completo:

```powershell
python -m b3_strategy_lab backtest --strategy breakout --lookback 10 --exit-lookback 40 --price-mode raw_events --signal-mode raw --cost-bps 20 --slippage-bps 5 --lot-size 1
```

Rodar uma reversao por RSI:

```powershell
python -m b3_strategy_lab backtest --strategy rsi_reversion --rsi-period 2 --lower 20 --upper 80 --cost-bps 5
```

Rodar uma das estrategias pesquisadas com seus parametros canonicos, ou
sobrescrever um parametro especifico:

```powershell
python -m b3_strategy_lab backtest --strategy frama_trend
python -m b3_strategy_lab backtest --strategy frama_trend --strategy-param window=24
```

Varredura de parametros, ainda por ativo individual:

```powershell
python -m b3_strategy_lab sweep --strategy sma_cross --fast-values 10 20 50 --slow-values 100 150 200 --top 3
```

Escolher parametros no periodo de treino e medir no futuro:

```powershell
python -m b3_strategy_lab train-test --strategy rsi_reversion --cost-bps 20 --slippage-bps 5 --lot-size 1 --train-ratio 0.7
```

Organizar Heikin Ashi, inventario e historicos separados por ano:

```powershell
python scripts\organize_market_data.py
```

Rodar uma estrategia ano a ano, sem testar o historico inteiro como um unico periodo:

```powershell
python -m b3_strategy_lab backtest --by-year --strategy sma_cross --fast 20 --slow 50
```

Filtrar anos especificos:

```powershell
python -m b3_strategy_lab sweep --by-year --years 2024 2025 --strategy breakout
```

Gerar inventario organizado das estrategias:

```powershell
python scripts\organize_strategies.py
```

## Matriz de estrategia e gerenciamento

O executor combina sinais de elegibilidade com 478 gerenciamentos de carteira.
Ele usa sinal no fechamento, execucao na abertura seguinte, OHLC normalizado
somente por splits e exclui dividendos/JCP. O historico de indicadores das
estrategias e dos gerenciamentos comeca no aquecimento certificado em
2017-01-01. O catalogo possui 189 estrategias
parametrizadas e `buy_and_hold`, que nao entra em varreduras de parametros, mas
entra normalmente na matriz. Uma execucao integral atual cruza 190 x 478 =
90.820 combinacoes.

```powershell
python scripts\backtest_strategy_management_combinations.py
```

Para testar somente Buy and Hold contra todos os gerenciamentos:

```powershell
python scripts\backtest_strategy_management_combinations.py --strategies buy_and_hold --output reports\buy_and_hold_managements_adjusted_no_dividends_1d.csv
```

Artefatos atuais de Buy & Hold, calculados de 2018-01-02 a 2026-07-31:

- [ranking dos 478 gerenciamentos](reports/buy_and_hold_managements_adjusted_no_dividends_1d.csv);
- [manifesto com hashes dos dez datasets e do universo](reports/buy_and_hold_managements_adjusted_no_dividends_1d.manifest.json);
- [retornos anuais das cinco melhores combinacoes](reports/buy_and_hold_managements_adjusted_no_dividends_1d_top5_annual.md).

A melhor combinacao deste recorte foi `buy_and_hold` com
`top1_risk_adjusted_lb21_skip0_trend0_vol21_equal_monthly_abs_cap1_adjusted`:
retorno total de 979,11%, CAGR de 31,97% e drawdown maximo de -51,27%. Esses
numeros usam custos, impostos e slippage iguais a zero e o universo fixo declara
`survivorship_safe=false`.

O ranking completo anterior, com 74.568 combinacoes e dados ate 2026-07-22, e
mantido apenas como artefato historico. Ele nao contem Buy & Hold e foi gerado
antes da correcao da semantica dos campos `raw_*`; nao deve ser comparado
diretamente com o ranking atual de Buy & Hold:

- [ranking completo das 74.568 combinacoes](reports/strategy_management_combinations_adjusted_no_dividends_1d_t252.csv);
- [manifesto da execucao](reports/strategy_management_combinations_adjusted_no_dividends_1d_t252.manifest.json);
- [retornos anuais das cinco melhores combinacoes](reports/strategy_management_combinations_adjusted_no_dividends_1d_t252_top5_annual.md).

A primeira colocada foi `mfi_momentum_7_50_30_sma50` com
`top1_roc_combo_roc12_6_3_w1_1_1_skip0_trend0_vol63_equal_monthly_posscore_adjusted`:
retorno total de 2.946,56%, CAGR de 49,12%, media anual aritmetica de 55,14% e
drawdown maximo de -39,26%.

Os rankings usam todo o periodo (`full_period`), sem holdout ou walk-forward.
O campo `train_ratio_applied=false` do manifesto torna isso explicito.

Arquivos gerados:

- `data/candles/<ticker>_1d.csv`: candles COTAHIST brutos e normalizados por splits.
- `data/manifests/<ticker>_<intervalo>.json`: hashes, fontes, janela e status de verificacao.
- `data/corporate_actions/split_evidence.json`: evidencia oficial dos splits desde 2017.
- `data/universes/fixed_2018.json`: universo, data de selecao e declaracao de vies.
- `data/heikin_ashi/<ticker>_1d.csv`: candles Heikin Ashi derivados nas duas bases de preco.
- `data/yearly/<ano>/candles/<intervalo>/<ticker>_<intervalo>.csv`: candles separados por ano.
- `data/yearly/<ano>/heikin_ashi/<intervalo>/<ticker>_<intervalo>.csv`: Heikin Ashi separado por ano.
- `data/corporate_actions/<ticker>_actions.csv`: ledger legado; splits desde 2017 possuem evidencia separada, dividendos/JCP nao.
- `data/legacy`: dados sem proveniencia suficiente, excluidos do caminho verificado.
- `reports/summary_<strategy>_1d.csv`: resumo por ticker.
- `reports/summary_<strategy>_<price_mode>_<signal_mode>_<intervalo>_by_year.csv`: resumo de backtest ano a ano.
- `reports/yearly_data_status.csv`: inventario dos arquivos anuais.
- `reports/backtest_data_audit.json`: alinhamento das sessoes, metadados e cobertura dos splits no universo da matriz.
- `reports/strategy_inventory.csv`: inventario das estrategias, familias e parametros padrao.
- `reports/<ticker>_<strategy>_1d_equity.csv`: curva da estrategia e do buy and hold.
- `reports/sweep_<strategy>_1d.csv`: ranking de parametros testados.
- `reports/train_test_<strategy>_<objective>_1d.csv`: melhores parametros no treino e resultado no teste.

## Estrategias incluidas

O catalogo completo, incluindo os presets, pode ser consultado com
`python -m b3_strategy_lab list-strategies`. As 12 formulas pesquisadas e suas
regras exatas estao em [docs/researched_strategies.md](docs/researched_strategies.md).
O segundo lote preserva essas 168 estrategias e adiciona 21 motores distintos,
documentados em [docs/extended_strategies.md](docs/extended_strategies.md), para
um total de 189 estrategias com sweep de parametros. Somado ao sinal permanente
`buy_and_hold`, o executor da matriz combina 190 estrategias com os
gerenciamentos de carteira.

- `atr_breakout`: rompimento de maxima com stop movel baseado em ATR.
- `bollinger_reversion`: compra na banda inferior de Bollinger e sai no retorno ao meio/superior.
- `chandelier_breakout`: rompimento de maxima com saida por Chandelier/ATR.
- `down_streak_reversion`: compra apos sequencia de fechamentos negativos e IBS baixo.
- `ema_cross`: cruzamento de medias exponenciais.
- `ibs_reversion`: reversao curta por Internal Bar Strength.
- `keltner_breakout`: rompimento de canal de Keltner com filtro opcional de tendencia.
- `macd`: comprado quando a linha MACD fica acima da linha de sinal.
- `sma_cross`: comprado quando a media curta fica acima da media longa.
- `momentum`: comprado quando o fechamento atual supera o fechamento de N candles atras.
- `price_sma`: comprado quando o preco fecha acima da media.
- `range_expansion_breakout`: compra expansao de range no fechamento com stop por ATR.
- `roc_trend`: momentum positivo com filtro de media movel.
- `breakout`: comprado em rompimento de maxima e sai em perda de minima.
- `connors_rsi_reversion`: reversao por Connors RSI, combinando RSI do preco, RSI da sequencia de altas/baixas e percent rank.
- `rsi_bollinger`: compra quando RSI e Bollinger indicam sobrevenda ao mesmo tempo.
- `rsi_cross_reversion`: espera o RSI recuperar acima do limite inferior antes de entrar.
- `rsi_ibs_reversion`: combina RSI curto e IBS baixo para entrada de reversao.
- `rsi2_trend_reversion`: reversao por RSI curto com filtro de tendencia e saida por media curta.
- `rsi_reversion`: comprado em sobrevenda por RSI e sai em sobrecompra.
- `rsi_reversion_atr`: reversao por RSI com stop de volatilidade baseado em ATR.
- `rsi_reversion_hold`: reversao por RSI com tempo maximo de permanencia.
- `rsi_reversion_trend_entry`: reversao por RSI que exige tendencia positiva apenas na entrada.
- `trend_pullback`: compra sobrevenda apenas quando o ativo esta acima da media de tendencia.
- `sma_stop`: segue tendencia por media movel com stop percentual a partir do topo.
- `supertrend_follow`: segue tendencia pelo indicador SuperTrend baseado em ATR.
- `precision_trend_ehlers`: tendencia pelo ROC do Precision Trend de Ehlers.
- `ultimate_oscillator_ehlers`: oscilador de Ehlers normalizado por RMS.
- `gap_momentum`: direcao da linha-sinal do gap ratio de Kaufman.
- `heikin_ashi_stochastic`: reversao Heikin-Ashi confirmada por estocastico.
- `vortex_trend`: tendencia pelo cruzamento de VI+ e VI-.
- `kama_trend`: tendencia adaptativa pela KAMA de Kaufman.
- `frama_trend`: tendencia adaptativa pela dimensao fractal de Ehlers.
- `rvi_reversal`: reversao por cruzamento do Relative Vigor Index.
- `chaikin_money_flow`: fluxo de volume com filtro de tendencia.
- `squeeze_breakout`: rompimento depois de compressao Bollinger/Keltner.
- `turtle_soup`: reversao de falso rompimento da minima anterior.
- `turn_of_month`: janela do ultimo ao terceiro pregao do mes seguinte.
- `fisher_transform_reversal` e `laguerre_rsi_reversal`: reversoes por filtros digitais de Ehlers.
- `ichimoku_cloud`, `parabolic_sar_trend` e `aroon_trend`: seguidores de tendencia por estruturas diferentes.
- `trix_signal`, `schaff_trend_cycle`, `coppock_curve`, `know_sure_thing`, `true_strength_index` e `awesome_oscillator`: motores de momentum com horizontes e suavizacoes distintos.
- `choppiness_breakout`, `mass_index_reversal` e `vertical_horizontal_filter`: volatilidade, reversao de range e classificacao de regime.
- `elder_force_index`, `ease_of_movement`, `negative_volume_index` e `klinger_volume_oscillator`: quatro leituras independentes de preco e volume.
- `nr7_breakout` e `inside_bar_breakout`: price action com setup, validade e saidas objetivas.
- `halloween_effect`: sazonalidade novembro-abril, alternando com caixa.
- `buy_and_hold`: mantem o sinal de compra ativo em todos os candles. Na matriz,
  todos os ativos ficam elegiveis e o gerenciamento define selecao, pesos, caixa
  e rebalanceamento; por isso ele mede o resultado puro de cada gerenciamento.

O simulador executa sinais no `open` do candle seguinte. Isso evita olhar o
fechamento de hoje e comprar no proprio fechamento de hoje.

## Cuidados de interpretacao

- `sweep` e in-sample: bom para explorar, ruim para concluir.
- `train-test` escolhe parametros no trecho inicial e mede o trecho futuro; ainda nao substitui walk-forward completo.
- `price-mode price_only` e `adjusted` usam OHLC COTAHIST normalizado somente por splits; nao representam retorno total.
- `price-mode raw_events` usa OHLC COTAHIST bruto e exige eventos corporativos completos; fica bloqueado enquanto dividendos/JCP estiverem `unverified`.
- `signal-mode adjusted` e o padrao seguro. `signal-mode raw` preserva saltos de escala de splits e serve apenas para diagnostico.
- O universo fixo da matriz declara `survivorship_safe=false`; o resultado pode conter vies de selecao e sobrevivencia.
- A certificacao atual de splits comeca em 2017. Periodos anteriores nao tem o mesmo nivel de garantia.
- Custos e slippage devem ser ligados antes de comparar contra buy and hold.
- Impostos, aluguel, emolumentos e restricoes de liquidez nao sao modelados por padrao.

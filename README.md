# B3 Strategy Lab

Laboratorio para testar estrategias compradas por ativo e combina-las com
gerenciamentos de carteira. O universo verificado padrao possui 40 acoes da B3:
as 10 originais mais 30 adicoes liquidas, com dados diarios de 2018 ate o ultimo
pregao fechado e aquecimento desde 2017.

## Fonte e candles

O caminho verificado usa os arquivos anuais COTAHIST, publicados gratuitamente
pela B3. Os campos `raw_open`, `raw_high`, `raw_low` e `raw_close` preservam o
OHLC do mercado padrao (`010`, BDI `02`). `raw_volume`, `trades` e
`financial_volume` consolidam a atividade oficial dos mercados padrao e
fracionario (`020`, BDI `96`); os campos `fractional_*` preservam separadamente a
parcela fracionaria. Precos e quantidade ajustados sao normalizados somente por
eventos que alteram a quantidade de acoes. Dividendos e JCP ficam excluidos.

Cada manifesto registra hashes dos candles, dos eventos e dos ZIPs de origem.
As razoes de split usadas no periodo padrao estao ligadas a evidencias oficiais
da B3, da CVM ou do RI do emissor. A metodologia, os campos e as alternativas
oficiais gratuitas estao em
[docs/data_provenance.md](docs/data_provenance.md).

## Comandos

Sincronizar o universo de 40 acoes, a base oficial diaria/semanal e os eventos
que alteram a quantidade de acoes:

```powershell
python scripts\sync_official_universe.py --download --refresh-current --refresh-actions --refresh-selection
python -m b3_strategy_lab verify-data --interval 1d
python scripts\audit_backtest_readiness.py --max-age-calendar-days 4
python scripts\audit_volume_indicators.py
```

O sincronizador usa o COTAHIST e o cadastro de eventos corporativos da propria
B3, cruza os eventos por ISIN, exclui o dia corrente e grava hashes das fontes.
Como a resposta corrente da B3 omite parte do historico, 25 eventos desde 2017
foram recuperados de documentos oficiais dos emissores/CVM no registro
`supplemental_split_events.json`. A sincronizacao so termina se todos os
marcadores `EB/EG` do COTAHIST estiverem cobertos.
O arquivo [universe_40_selection_2018.csv](reports/universe_40_selection_2018.csv)
reproduz o ranking usado para escolher as 30 adicoes.
Como esse ranking usa o volume do ano completo de 2018 e a matriz comeca em
2 de janeiro, o manifesto declara explicitamente o vies de selecao; o filtro de
continuidade ate a atualizacao tambem produz vies de sobrevivencia.

O auditor de volume verifica `QUATOT`, `TOTNEG` e `VOLTOT` dos mercados `010+020`
em todos os pregoes,
confere a normalizacao inversa de preco e quantidade nos eventos de capital e
executa testes de causalidade para todas as 17 estrategias que usam volume. Isso
inclui MFI, Chaikin Money Flow, Elder Force Index, Ease of Movement, Negative
Volume Index, Klinger e os filtros de volume dos rompimentos. O resultado
reproduzivel tambem exige a cobertura dos eventos que mudam a quantidade e fica em
[volume_indicator_audit_40.json](reports/volume_indicator_audit_40.json).

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

O executor aplica todas as estrategias e indicadores aos 40 ativos e combina
os sinais de elegibilidade com 478 gerenciamentos de carteira.
Ele usa sinal no fechamento, execucao na abertura seguinte, OHLC normalizado
somente por splits e exclui dividendos/JCP. O historico de indicadores das
estrategias e dos gerenciamentos comeca no aquecimento certificado em
2017-01-01. O gerenciamento escolhe e pondera a cesta apenas nas datas de
rebalanceamento; dentro desse intervalo, mudancas do sinal binario retiram ou
recolocam cada ativo da cesta na abertura seguinte, sem refazer o ranking.
Estrategias sazonais recebem o calendario global de pregoes verificados; assim,
uma fronteira mensal nunca e inferida pela chegada de um candle futuro do ativo.
O catalogo atual possui 233 estrategias
parametrizadas e `buy_and_hold`, que nao entra em varreduras de parametros, mas
entra normalmente na matriz. Uma execucao integral atual cruza 234 x 478 =
111.852 combinacoes.

```powershell
python scripts\backtest_strategy_management_combinations.py --initial-cash 1000 --cost-bps 3.2 --slippage-bps 10
python scripts\audit_matrix_results.py
```

O executor usa ate 8 processos por padrao e compartilha calculos de
momentum/tendencia/volatilidade entre configuracoes semanticamente equivalentes.
Use `--workers 1` para a referencia serial ou ajuste o valor conforme a memoria e
as CPUs disponiveis.

Os resultados publicados ficam em um branch separado. A
[ultima matriz publicada](https://github.com/mycroft440/b3-strategy-lab/blob/backtest-results/reports/latest_backtest/TOP_10.md),
seu [manifesto](https://github.com/mycroft440/b3-strategy-lab/blob/backtest-results/reports/latest_backtest/MANIFEST.json)
e sua [auditoria](https://github.com/mycroft440/b3-strategy-lab/blob/backtest-results/reports/latest_backtest/AUDIT.json)
devem ser lidos em conjunto. O workflow tambem versiona nesse branch o CSV
completo da matriz e o snapshot exato de candles, manifestos e eventos cujos
hashes aparecem no manifesto, permitindo repetir a auditoria sem depender da
retencao temporaria de artifacts. A execucao publicada em 20/08/2026 usou dados ate
10/08/2026 e custos/slippage zero; por isso ela e apenas um artefato retrospectivo
anterior a estas correcoes, nao uma estimativa de dinheiro real. Uma nova matriz
so substitui essa referencia depois que o workflow publicar `STATUS=SUCCESS`,
hashes coerentes e os novos custos no manifesto.

Para iniciar sem terminal, use `abrir_painel_backtest.bat` no Windows ou
`./abrir_painel_backtest.sh` no Linux/macOS. O painel atualiza e audita os dados,
aceita subconjuntos do universo, aplica custos/slippage e mostra a janela
efetivamente simulada. Consulte [docs/PAINEL_BACKTEST.md](docs/PAINEL_BACKTEST.md).

Para testar somente Buy and Hold contra todos os gerenciamentos:

```powershell
python scripts\backtest_strategy_management_combinations.py --strategies buy_and_hold --output reports\buy_and_hold_managements_adjusted_no_dividends_1d.csv
```

Os artefatos de Buy & Hold abaixo sao o recorte historico anterior de 10 ativos,
calculado de 2018-01-02 a 2026-07-31:

- [ranking dos 478 gerenciamentos](reports/buy_and_hold_managements_adjusted_no_dividends_1d.csv);
- [manifesto com hashes dos dez datasets e do universo anterior](reports/buy_and_hold_managements_adjusted_no_dividends_1d.manifest.json);
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

Para validação econômica, use o painel separado
`abrir_painel_realista.bat`/`abrir_painel_realista.sh` ou o pipeline documentado
em [docs/realistic_backtest_methodology.md](docs/realistic_backtest_methodology.md).
Ele modela universo point-in-time, lote padrão/fracionário, proventos, tarifas,
slippage e tributação, mantendo `cash_events_complete=false` enquanto não houver
certificação independente de cobertura histórica.

Arquivos gerados:

- `data/candles/<ticker>_1d.csv`: candles COTAHIST brutos e normalizados por splits.
- `data/manifests/<ticker>_<intervalo>.json`: hashes, fontes, janela e status de verificacao.
- `data/corporate_actions/split_evidence.json`: evidencia oficial dos splits desde 2017.
- `data/corporate_actions/supplemental_split_events.json`: eventos historicos ausentes na resposta corrente da B3, com fontes oficiais do emissor/CVM.
- `data/universes/fixed_40_2018.json`: universo padrao de 40 acoes, criterio de selecao e declaracao de vies.
- `data/universes/fixed_2018.json`: universo anterior de 10 acoes, preservado para reproduzir relatorios antigos.
- `data/heikin_ashi/<ticker>_1d.csv`: candles Heikin Ashi derivados nas duas bases de preco.
- `data/yearly/<ano>/candles/<intervalo>/<ticker>_<intervalo>.csv`: candles separados por ano.
- `data/yearly/<ano>/heikin_ashi/<intervalo>/<ticker>_<intervalo>.csv`: Heikin Ashi separado por ano.
- `data/corporate_actions/<ticker>_actions.csv`: ledger legado; splits desde 2017 possuem evidencia separada, dividendos/JCP nao.
- `data/legacy`: dados sem proveniencia suficiente, excluidos do caminho verificado.
- `reports/summary_<strategy>_1d.csv`: resumo por ticker.
- `reports/summary_<strategy>_<price_mode>_<signal_mode>_<intervalo>_by_year.csv`: resumo de backtest ano a ano.
- `reports/yearly_data_status.csv`: inventario dos arquivos anuais.
- `reports/universe_40_selection_2018.csv`: ranking de liquidez, presenca anual e selecao das 30 adicoes.
- `reports/backtest_data_audit_40.json`: alinhamento das sessoes, metadados e cobertura dos splits no universo da matriz.
- `reports/volume_indicator_audit_40.json`: inventario e testes de todos os leitores de volume.
- `reports/strategy_management_combinations_40_adjusted_no_dividends_1d.audit.json`: cardinalidade, ordenacao, identidades matematicas e hashes da matriz completa.
- `reports/strategy_inventory.csv`: inventario das estrategias, familias e parametros padrao.
- `reports/<ticker>_<strategy>_1d_equity.csv`: curva da estrategia e do buy and hold.
- `reports/sweep_<strategy>_1d.csv`: ranking de parametros testados.
- `reports/train_test_<strategy>_<objective>_1d.csv`: melhores parametros no treino e resultado no teste.

## Estrategias incluidas

O catalogo completo, incluindo os presets, pode ser consultado com
`python -m b3_strategy_lab list-strategies`. As 12 formulas pesquisadas e suas
regras exatas estao em [docs/researched_strategies.md](docs/researched_strategies.md).
O segundo lote preservou as 168 estrategias iniciais e adicionou 21 motores
distintos, documentados em
[docs/extended_strategies.md](docs/extended_strategies.md). Extensoes posteriores
levaram o catalogo atual a 233 estrategias com sweep de parametros. Somado ao
sinal permanente `buy_and_hold`, o executor da matriz combina 234 estrategias
com os gerenciamentos de carteira.

Novas estrategias e indicadores podem ser adicionados apenas com decorators em
`b3_strategy_lab/user_extensions.py`, sem editar o registro central. Veja
[docs/adding_strategies.md](docs/adding_strategies.md).

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
- O universo de 40 acoes declara `survivorship_safe=false`: exigir continuidade ate a data atual usa informacao futura e introduz vies de sobrevivencia.
- A certificacao atual de splits comeca em 2017. Periodos anteriores nao tem o mesmo nivel de garantia.
- A matriz retrospectiva usa por padrao 3,2 bps de custos e 10 bps de slippage,
  mas ainda exclui impostos e proventos; valores pessoais precisam do caminho
  realista e de uma tabela de corretagem adequada.
- Impostos, aluguel, emolumentos e restricoes de liquidez nao sao modelados por padrao.

# Revisão da melhor combinação da matriz (23/09/2026)

Matriz completa: 249 estratégias × 478 gerenciamentos = 119.022 combinações, de
2018-01-02 a 2026-08-19, R$ 1.000 iniciais, custos de 3,2 bps + slippage de 10 bps por
ordem, lote de 1 ação, universo point-in-time survivorship-safe (top 40 por liquidez
passada, recalculado a cada semana). Dividendos/JCP não entram.

> Os números desta revisão são anteriores à correção de `89889e6`: ao zerar uma posição,
> o motor podia deixar uma ação residual. A referência atual é a
> [matriz sem ações problemáticas](../matriz_sem_problematicas/REVISAO.md), executada
> com o motor corrigido. Os replays realistas daqui também são anteriores às correções
> do motor realista de 25/09/2026 (`157111a`, `e04f91a`, `93f4751`) e ao conserto do
> sinal `cci_trend` (`19ddaf6`).

## Veredito

A campeã agora está **calculada corretamente**: os preços batem com a B3, os sinais
não usam dados do futuro e o motor realista reproduz o resultado. Mas ela **não é uma
expectativa confiável para o futuro**. Ela foi escolhida entre 72.518 combinações
olhando o período inteiro e era só a 169ª quando se olha apenas o treino. Escolhendo
de forma honesta, só com o treino, a melhor combinação perdeu dinheiro de 2023 a 2026.

| R$ 1.000 investidos | Matriz | Motor realista |
| :--- | ---: | ---: |
| Campeã do período inteiro, 2018–2026 | R$ 18.701 (40,4% a.a.) | **R$ 17.152 (39,0% a.a.)** |
| Campeã do período inteiro, teste 2023–2026 | R$ 2.593 (30,0% a.a.) | **R$ 2.417 (27,6% a.a.)** |
| Campeã escolhida só no treino, teste 2023–2026 | R$ 510 (−17,0% a.a.) | **R$ 591 (−13,5% a.a.)** |
| CDI bruto, 2018–2026 / 2023–2026 | R$ 2.121 / R$ 1.560 | — |

## Erro encontrado e corrigido na primeira execução

A primeira execução apontou `supertrend_rsi_21_4_21` +
`top1_risk_adjusted_lb21_skip0_trend0_vol63_equal_monthly_abs_cap1_adjusted` com
R$ 1.000 → R$ 163.995 (80,6% a.a.). Quase todo o lucro veio de um único pregão:
em 19/07/2021 o patrimônio multiplicou por 88 na troca de código BTOW3 → AMER3. A
matriz precificava a posição com o candle da AMER3, normalizado pelo grupamento 100:1
de 2024, e transferia a quantidade 1:1. O preço negociado caiu 9% nesse dia.

O erro afetava sete trocas de código certificadas (BVMF3→B3SA3, KROT3→COGN3,
VIVT4→VIVT3, BTOW3→AMER3, BRDT3→VBBR3, VIIA3→BHIA3 e ELET3→AXIA3). A correção
está no commit `ed4779e`, com teste de regressão. Com ela, aquela combinação vira
R$ 67,03 (−93%): ela ficou com AMER3 no escândalo contábil de janeiro de 2023. As
duas matrizes foram executadas de novo depois da correção.

## A campeã

`rsi_cross_reversion` +
`top1_roc_combo_roc12_6_3_w1_1_1_skip21_trend0_vol63_equal_monthly_posall_windows_adjusted`:
compra reversões por RSI e, uma vez por mês, fica com a ação de maior momentum
combinado (12, 6 e 3 meses, pulando o último mês) entre as que têm sinal de compra.

| Ano | Retorno |
| :--- | ---: |
| 2018 | +93,4% |
| 2019 | +24,2% |
| 2020 | +132,5% |
| 2021 | +34,2% |
| 2022 | −2,7% |
| 2023 | −41,3% |
| 2024 | +214,8% |
| 2025 | +9,8% |
| 2026 (até 19/08) | +26,2% |

Drawdown máximo de −62,1%; 113 negociações; 95% do tempo investida, quase sempre em uma
única ação.

## O que foi verificado

| Verificação | Resultado |
| :--- | :--- |
| Auditoria oficial da matriz (`audit_matrix_results.py`) | Cardinalidade, ordenação, métricas e hashes conferem nas duas matrizes |
| Reprodução isolada | Mesmo resultado da matriz (R$ 18.701,38) |
| Uso de dados do futuro | 1.080 cortes (90 ativos × 12 datas): o sinal calculado só com o passado é idêntico ao da série completa |
| Motor de decisão | Decide no fechamento com o universo daquela semana e executa na abertura seguinte; sem abertura, falha em vez de usar preço antigo |
| Saltos suspeitos | Os maiores dias são da crise da Covid (MGLU3 ±20% em março de 2020), reais |
| Preços das operações de 2024 | BRFS3 e EMBR3 conferem com as aberturas oficiais do COTAHIST |
| Liquidez | Ordens de R$ 4 mil a R$ 12 mil contra volume diário de R$ 87 a 280 milhões |
| Custos maiores | Slippage de 20/30/50 bps: 38,5% / 36,9% / 33,2% a.a. no período inteiro; 28,3% / 26,4% / 23,0% a.a. no teste |
| Motor realista | Preços oficiais, lotes padrão/fracionário, slippage por liquidez, tarifas B3 e IR: R$ 17.151,84 (202 ordens, R$ 232,71 de tarifas, R$ 1,02 de IR) |
| IR | Quase zero porque as vendas mensais ficam abaixo de R$ 20 mil (isenção); isso acaba com um patrimônio maior |

O lucro está concentrado: EMBR3 (+R$ 7.382), COGN3 (+R$ 5.460), BRFS3 (+R$ 5.344) e
ENEV3 (+R$ 3.718); CSMG3 (−R$ 4.259) e MRFG3 (−R$ 2.454) foram as maiores perdas. O
+214,8% de 2024 veio de BRFS3 e EMBR3, duas das maiores altas da bolsa naquele ano.

## Por que o resultado não é confiável para o futuro

1. **Seleção entre muitas combinações.** A mediana das 72.518 combinações válidas rende
   −0,9% a.a. e só 6,5% superam o CDI. A primeira da lista é, por construção, a que teve
   mais sorte no período inteiro.
2. **Escolha só no treino.** A campeã era a 169ª no treino (48,9% a.a.). A que liderava
   o treino, `time_series_momentum_12m_trend200` +
   `top1_momentum_lb126_skip21_trend0_vol21_equal_monthly_abs_cap1_adjusted`
   (65,6% a.a. no treino), perdeu 49% no teste pela matriz e 41% no motor realista.
3. **Pico isolado.** A mesma estratégia com os outros 427 gerenciamentos válidos tem
   mediana de 12,0% a.a. O mesmo gerenciamento com as outras 230 estratégias tem
   mediana de −2,1% a.a. Os 40,4% a.a. dependem do par específico.
4. **Concentração.** Uma ação por vez, com drawdown de −62% e um ano de −41%.

## Limitações registradas

- **Combinações descartadas:** 46.504 de 119.022 foram marcadas inválidas porque
  carregavam uma ação em evento societário que a matriz não sabe valorar: fechamento de
  capital da Cielo (38.153), reorganização da JBS (5.306), incorporação do Carrefour
  Brasil (2.261) e outras (784). O ranking compara só as combinações válidas.
- **Dividendos/JCP** ficam de fora nos dois motores.
- **Fração não documentada:** a bonificação de 10% da COGN3 em 2025-12-26 gerou 0,8
  ação fracionária, que o motor realista descartou com valor zero (cerca de R$ 2,57;
  `__DIAGNOSTIC_FRACTIONS_AT_ZERO`). O custo fiscal dessa bonificação também não é
  aplicado (`__BONUS_TAX_BASIS_UNCERTIFIED`).
- **Transições:** `__UNBOUND_TICKER_TRANSITIONS` por AZUL4, PETZ3 e TIMP3 sem
  sucessor documentado; nenhum deles estava na carteira nessas datas.

## Como reproduzir

```powershell
python scripts\run_realistic_pipeline.py --start 2018-01-02 --end 2026-08-19 --initial-cash 1000 --mode research --skip-walk-forward
python scripts\backtest_strategy_management_combinations.py --workers 4 --top 10 --output reports\matriz_completa\strategy_management_combinations_pit_2018_2026.csv.gz
python scripts\backtest_strategy_management_combinations.py --workers 4 --top 10 --end 2022-12-29 --output reports\matriz_completa\strategy_management_combinations_pit_treino_2018_2022.csv.gz
python scripts\audit_matrix_results.py --results reports\matriz_completa\strategy_management_combinations_pit_2018_2026.csv.gz --annual-report reports\matriz_completa\strategy_management_combinations_pit_2018_2026_top10_annual.md

python scripts\diagnose_fractional_blockers.py --strategy rsi_cross_reversion --management top1_roc_combo_roc12_6_3_w1_1_1_skip21_trend0_vol63_equal_monthly_posall_windows_adjusted --start 2018-01-02 --end 2026-08-19 --initial-cash 1000 --output reports\matriz_completa\replay_realista\campea_2018_2026_resumo.json
```

O pipeline realista termina com erro na etapa própria do `gap_momentum` (fração da RADL3
sem liquidação documentada), depois de preparar os dados usados aqui. Os resultados por
período e custo saem do mesmo script da matriz com `--strategies`, `--start`, `--end` e
`--slippage-bps`.

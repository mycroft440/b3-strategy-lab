# Matriz sem ações problemáticas (24/09/2026)

Mesma matriz da [revisão anterior](../matriz_completa/REVISAO.md) (249 estratégias ×
478 gerenciamentos = 119.022 combinações, 2018-01-02 a 2026-08-19, R$ 1.000, custos de
3,2 bps + slippage de 10 bps, universo point-in-time), sem as ações cujos eventos os
motores não sabem valorar.

## Ações removidas

`scripts/build_universe_without_unsupported_events.py` removeu 11 das 86 ações
selecionáveis, sem colocar outras no lugar; ficam 34 a 40 ações por semana. Lista e
motivos em [`acoes_removidas.json`](acoes_removidas.json):

| Ação | Motivo |
| :--- | :--- |
| AZUL4 | reorganização em 2025-12-23 |
| BRFS3 | incorporação pela MBRF3 em 2025-09-23 |
| BRML3 | incorporação pela ALSO3 em 2023-01-09 |
| CIEL3 | cancelamento de registro em 2024-08-27 |
| CRFB3 | incorporação em 2025-06-02 |
| FIBR3 | incorporação pela SUZB3 em 2019-01-04 |
| GNDI3 | incorporação pela HAPV3 em 2022-02-14 |
| JBSS3 | reorganização em 2025-06-09 |
| PETZ3 | saiu da bolsa em 2026-01-02 sem sucessor documentado |
| SMLS3 | incorporação em 2021-06-07 |
| TIMP3 | saiu da bolsa em 2020-10-09 sem sucessor documentado |

Com isso, as 119.022 combinações ficam válidas (antes eram 72.518). Saber em 2018 quais
empresas passariam por esses eventos era impossível: o filtro é retrospectivo e fica
marcado como `selection_is_retrospective_user_filter`.

## Melhor resultado

**`ema_cross_50_100` + `top1_risk_adjusted_lb126_skip21_trend0_vol21_equal_monthly_abs_cap1_adjusted`**

- Sinal: a ação fica elegível enquanto a média exponencial de 50 pregões está acima da
  de 100.
- Gerenciamento: uma vez por mês, entre as elegíveis do universo daquela semana, compra
  100% em **uma** ação: a de maior retorno de 6 meses (pulando o último mês) dividido
  pela volatilidade de 21 pregões, desde que esse retorno seja positivo.

| R$ 1.000 investidos | Matriz | Motor realista |
| :--- | ---: | ---: |
| 2018-01-02 a 2026-08-19 | R$ 17.711,99 | **R$ 16.809,62** |
| Ganho médio composto (CAGR) | 39,54% a.a. | **38,70% a.a.** |
| Média simples dos anos completos (2018–2025) | 57,60% a.a. | 55,26% a.a. |
| Drawdown máximo | −49,82% | −51,52% |
| CDI bruto no mesmo período | R$ 2.121,49 (9,11% a.a.) | |

A média simples é maior porque os anos de +120% a +147% pesam mais do que as perdas; o
CAGR é o ganho anual que, repetido, leva de R$ 1.000 ao valor final.

| Ano | Matriz | Motor realista |
| :--- | ---: | ---: |
| 2018 | +46,2% | +46,0% |
| 2019 | +44,5% | +41,5% |
| 2020 | +129,6% | +122,2% |
| 2021 | +139,1% | +146,8% |
| 2022 | +9,0% | −1,5% |
| 2023 | −23,5% | −19,7% |
| 2024 | +47,7% | +38,5% |
| 2025 | +68,3% | +68,4% |
| 2026 (até 19/08) | −26,2% | −19,5% |

## Teste honesto: escolha só com 2018–2022

A mesma matriz restrita a 2018-01-02 a 2022-12-29 aponta **a mesma combinação** como
primeira (R$ 1.000 → R$ 12.614,61; 66,22% a.a.). Por isso o período seguinte é um
teste real fora da amostra:

| 2023-01-02 a 2026-08-19 | Resultado |
| :--- | ---: |
| Matriz | R$ 1.423,21 (10,22% a.a.; drawdown −36,05%) |
| Motor realista | **R$ 1.481,53 (11,44% a.a.; drawdown −35,42%)** |
| CDI bruto | R$ 1.560,01 (13,04% a.a.) |

Fora da amostra ela ganhou dinheiro, mas **menos que o CDI**, com risco muito maior.

## Verificações

| Verificação | Resultado |
| :--- | :--- |
| Auditoria oficial da matriz | Período inteiro aprovado para pesquisa. Na matriz de treino, só `calculation_worktree_was_clean` falhou: o novo script do filtro existia sem commit quando o manifesto foi gravado. Os hashes de todas as fontes do cálculo conferem com o commit `e497b12` |
| Ações removidas | Nenhuma delas aparece nas negociações do motor realista |
| Uso de dados do futuro | 1.080 cortes, nenhuma divergência |
| Saltos suspeitos | Os maiores dias são reais: Covid em março de 2020 (MGLU3 ±20%) e EMBR3 (+16% em 21/12/2021; +15,5% em 05/02/2025) |
| Motor realista | Preços oficiais, lotes padrão/fracionário, slippage por liquidez, tarifas B3 e IR: 259 ordens, R$ 399,71 de tarifas, R$ 8,94 de IR |
| Custos maiores | Slippage de 20/30/50 bps: 36,8% / 33,9% / 30,1% a.a. no período inteiro; 8,1% / 6,7% / 3,8% a.a. no teste |

Maiores contribuições: EMBR3 (+R$ 8.274), TOTS3 (+R$ 3.335), MRFG3 (+R$ 2.990),
PRIO3 (+R$ 2.514). Maiores perdas: COGN3 (−R$ 3.175), CYRE3 (−R$ 2.442), PETR4
(−R$ 1.914).

## Leitura

- O resultado vem do gerenciamento, não do sinal: `buy_and_hold` com o mesmo
  gerenciamento rende 38,74% a.a. no período inteiro, e o top 10 do treino e do período
  inteiro é dominado por essa mesma família de gerenciamento.
- Ainda assim é um pico: a mediana da mesma estratégia com os 478 gerenciamentos é
  6,5% a.a., a do mesmo gerenciamento com as 249 estratégias é 3,7% a.a., e a de todas as
  combinações é −0,5% a.a. (7,6% delas acima do CDI).
- Quase todo o ganho está em 2018–2021. Uma ação por vez gera quedas de 50%.
- Dividendos/JCP não entram. A fração de 0,4 ação de ITSA4 na bonificação de
  2018-06-01 (cerca de R$ 4) foi valorizada em zero.

## Como reproduzir

```powershell
python scripts\run_realistic_pipeline.py --start 2018-01-02 --end 2026-08-19 --initial-cash 1000 --mode research --skip-walk-forward
python scripts\build_universe_without_unsupported_events.py
python scripts\backtest_strategy_management_combinations.py --universe-manifest .cache\universo_sem_problematicas\universo_matriz.json --workers 4 --top 10 --output reports\matriz_sem_problematicas\strategy_management_combinations_pit_filtrado_2018_2026.csv.gz
python scripts\backtest_strategy_management_combinations.py --universe-manifest .cache\universo_sem_problematicas\universo_matriz.json --workers 4 --top 10 --end 2022-12-29 --output reports\matriz_sem_problematicas\strategy_management_combinations_pit_filtrado_treino_2018_2022.csv.gz
python scripts\diagnose_fractional_blockers.py --universe-manifest .cache\universo_sem_problematicas\universo_realista.json --snapshots .cache\universo_sem_problematicas\snapshots_filtrados.csv --strategy ema_cross_50_100 --management top1_risk_adjusted_lb126_skip21_trend0_vol21_equal_monthly_abs_cap1_adjusted --start 2018-01-02 --end 2026-08-19 --initial-cash 1000 --output reports\matriz_sem_problematicas\replay_realista\campea_2018_2026_resumo.json
```

O arquivo de universo exato usado nesta execução está em
[`universo_filtrado.json`](universo_filtrado.json); seu SHA-256 está nos manifestos.

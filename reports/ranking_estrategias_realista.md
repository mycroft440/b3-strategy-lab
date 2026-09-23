# Ranking fora da amostra das estrategias B3 (motor estrito, Nivel 1)

Treino: 2018-01-02 a 2022-12-29. Teste: 2023-01-02 a 2026-08-19. Capital inicial: R$ 1.000,00. Custos 3,2 bps + slippage 10 bps por ordem; lote de 1 acao. 160 gerenciamentos por estrategia (`base`), escolhidos pelo `cagr` do treino.

`validity=OUT_OF_SAMPLE_SELECTION__BIASED_UNIVERSE` · `economic_scope=strict_level1_split_adjusted_no_dividends_no_income_tax`

Este relatorio e pesquisa (Nivel 1), nao estimativa de dinheiro real:

- o universo fixo `data/universes/fixed_40_2018.json` foi escolhido com a liquidez de 2018 e exige continuidade ate hoje (`survivorship_safe=false`), o que favorece acoes que sobreviveram;
- os precos sao normalizados por splits; dividendos/JCP e imposto de renda nao entram;
- quantidades inteiras sao calculadas sobre o preco normalizado, nao sobre o preco historico negociado;
- valores de conta real exigem o motor realista ([metodologia](../docs/realistic_backtest_methodology.md)).

## Resultado do protocolo (escolha somente no treino)

O melhor par do treino entre as 25 estrategias foi `sma_cross` + `top1_risk_adjusted_lb126_skip0_trend0_vol63_equal_monthly_abs_cap1_adjusted` (70,21% de CAGR no treino).

No teste ele rendeu 0,25% ao ano (0,90% no periodo; R$ 1.000,00 -> R$ 1.008,97), com drawdown maximo de -42,06%. Leitura: **ABAIXO DO CDI**.

Este e o unico numero desta tabela que mede a selecao fora da amostra.

## Referencias no mesmo periodo de teste

- CDI (BCB SGS 12): 13,04% ao ano, 56,00% no periodo (R$ 1.000,00 -> R$ 1.560,01), bruto de impostos.
- Carteira igual-ponderada dos mesmos ativos (`buy_and_hold` + `equal_all_monthly_adjusted`), com os mesmos custos: 1,77% ao ano, 6,58% no periodo, drawdown maximo -21,55%.

## Tabela (ordem do treino)

`p Bonf.` e o p-valor unilateral do excesso diario sobre o CDI (aproximacao normal), multiplicado por 25 candidatos. A coluna `Rank teste` e descritiva.

| Treino | Rank teste | Estrategia | Treino CAGR | Teste CAGR | Retorno teste | Patrimonio final | Max DD | Sharpe | Retorno - CDI | t | p Bonf. | Leitura |
| ---: | ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 1 | 8 | `sma_cross` | 70,21% | 0,25% | 0,90% | R$ 1.008,97 | -42,06% | 0,16 | -55,10 p.p. | -0,46 | 1,000 | ABAIXO DO CDI |
| 2 | 12 | `momentum` | 60,60% | -0,78% | -2,80% | R$ 971,96 | -42,06% | 0,13 | -58,80 p.p. | -0,54 | 1,000 | PERDA NO TESTE |
| 3 | 13 | `time_series_momentum_6m` | 60,60% | -0,78% | -2,80% | R$ 971,96 | -42,06% | 0,13 | -58,80 p.p. | -0,54 | 1,000 | PERDA NO TESTE |
| 4 | 9 | `buy_and_hold` | 59,62% | 0,25% | 0,90% | R$ 1.008,97 | -42,06% | 0,16 | -55,10 p.p. | -0,46 | 1,000 | ABAIXO DO CDI |
| 5 | 10 | `sma_stop` | 57,41% | -0,26% | -0,94% | R$ 990,62 | -44,88% | 0,14 | -56,94 p.p. | -0,51 | 1,000 | PERDA NO TESTE |
| 6 | 15 | `roc_trend` | 56,24% | -1,67% | -5,93% | R$ 940,71 | -43,14% | 0,10 | -61,93 p.p. | -0,60 | 1,000 | PERDA NO TESTE |
| 7 | 11 | `price_sma` | 54,18% | -0,40% | -1,46% | R$ 985,42 | -43,14% | 0,14 | -57,46 p.p. | -0,50 | 1,000 | PERDA NO TESTE |
| 8 | 3 | `time_series_momentum_3m` | 52,32% | 8,48% | 34,37% | R$ 1.343,68 | -34,74% | 0,45 | -21,63 p.p. | -0,08 | 1,000 | ABAIXO DO CDI |
| 9 | 6 | `atr_breakout` | 48,13% | 0,75% | 2,74% | R$ 1.027,41 | -34,56% | 0,15 | -53,26 p.p. | -0,72 | 1,000 | ABAIXO DO CDI |
| 10 | 18 | `donchian_40_20_trend` | 40,90% | -7,31% | -24,06% | R$ 759,40 | -50,55% | -0,13 | -80,06 p.p. | -1,09 | 1,000 | PERDA NO TESTE |
| 11 | 2 | `range_expansion_breakout` | 39,91% | 10,69% | 44,53% | R$ 1.445,27 | -40,75% | 0,47 | -11,47 p.p. | 0,21 | 1,000 | ABAIXO DO CDI |
| 12 | 16 | `breakout` | 39,01% | -4,98% | -16,93% | R$ 830,71 | -51,26% | 0,01 | -72,93 p.p. | -0,71 | 1,000 | PERDA NO TESTE |
| 13 | 14 | `chaikin_money_flow` | 38,10% | -1,25% | -4,46% | R$ 955,41 | -40,33% | 0,08 | -60,46 p.p. | -0,73 | 1,000 | PERDA NO TESTE |
| 14 | 1 | `gap_momentum` | 35,73% | 37,34% | 216,11% | R$ 3.161,07 | -33,90% | 0,99 | +160,11 p.p. | 1,31 | 1,000 | ACIMA DO CDI (NAO SIGNIFICATIVO) |
| 15 | 5 | `ema_cross` | 30,26% | 2,38% | 8,90% | R$ 1.089,00 | -36,75% | 0,22 | -47,10 p.p. | -0,47 | 1,000 | ABAIXO DO CDI |
| 16 | 7 | `keltner_breakout` | 29,74% | 0,74% | 2,70% | R$ 1.027,00 | -46,70% | 0,15 | -53,30 p.p. | -0,66 | 1,000 | ABAIXO DO CDI |
| 17 | 23 | `macd` | 28,99% | -15,21% | -45,03% | R$ 549,69 | -59,56% | -0,46 | -101,03 p.p. | -1,71 | 1,000 | PERDA NO TESTE |
| 18 | 19 | `connors_rsi_reversion` | 27,60% | -7,80% | -25,51% | R$ 744,89 | -42,31% | -0,20 | -81,51 p.p. | -1,33 | 1,000 | PERDA NO TESTE |
| 19 | 22 | `ibs_reversion` | 25,08% | -14,40% | -43,12% | R$ 568,79 | -49,91% | -0,55 | -99,12 p.p. | -2,06 | 1,000 | PERDA NO TESTE |
| 20 | 20 | `frama_trend` | 21,81% | -10,02% | -31,81% | R$ 681,85 | -70,05% | -0,20 | -87,82 p.p. | -1,16 | 1,000 | PERDA NO TESTE |
| 21 | 4 | `turn_of_month` | 20,92% | 6,52% | 25,74% | R$ 1.257,41 | -31,20% | 0,38 | -30,26 p.p. | -0,26 | 1,000 | ABAIXO DO CDI |
| 22 | 21 | `rsi2_trend_reversion` | 17,00% | -10,67% | -33,60% | R$ 663,98 | -45,81% | -0,53 | -89,60 p.p. | -2,31 | 1,000 | PERDA NO TESTE |
| 23 | 25 | `bollinger_reversion` | 12,09% | -31,90% | -75,19% | R$ 248,13 | -79,45% | -1,26 | -131,19 p.p. | -3,26 | 1,000 | PERDA NO TESTE |
| 24 | 17 | `mfi_reversal` | 6,15% | -7,08% | -23,37% | R$ 766,27 | -34,23% | -0,19 | -79,37 p.p. | -1,33 | 1,000 | PERDA NO TESTE |
| 25 | 24 | `rsi_reversion` | 1,60% | -16,73% | -48,53% | R$ 514,66 | -64,41% | -0,54 | -104,54 p.p. | -1,89 | 1,000 | PERDA NO TESTE |

## Leitura automatica

- 1 de 25 estrategias superaram o CDI no teste.
- 0 de 25 superaram o CDI com p Bonferroni < 0,05.
- 16 de 25 perderam capital no teste.
- Mediana da variacao de CAGR entre treino e teste: -43,84 p.p..
- A melhor linha do teste e `gap_momentum` (37,34% ao ano; 14a no treino). Escolhe-la agora e selecao no holdout entre 25 candidatos; o resultado dela precisa de dados posteriores ou do motor realista antes de qualquer alegacao.

# RSI + WMA Heikin Ashi - backtest sem gerenciamento de carteira

## Regras testadas

- **Compra**: RSI(14) do fechamento acima de 50 e WMA(20) do fechamento Heikin Ashi subindo (WMA[t] > WMA[t-1]).
- **Venda**: RSI abaixo de 50 ou WMA Heikin Ashi caindo (WMA[t] < WMA[t-1]).
- **Selecao**: somente 1 acao por vez. A entrada so ocorre na abertura seguinte ao PRIMEIRO candle do sinal; se a vaga estiver ocupada, o sinal e descartado (nunca ha entrada tardia). So entram sinais novos com ROC de 3 meses (63 pregoes) acima de 0; entre eles, compra-se o de maior ROC. Sem candidato, a carteira fica em caixa. A posicao fica ate o sinal de venda (o ROC so e exigido na entrada).
- **Prioridade** (variantes de comparacao): fechamento OU SMA20 acima da SMA50.
- "RSI acima de 0" foi lido como RSI centralizado (RSI - 50 > 0), ou seja RSI > 50.
- Sinal no fechamento, execucao na abertura seguinte; custos 3.2 bps + slippage 10.0 bps por ordem; lote de 1 acao.
- Universo: 40 acoes (`fixed_research_universe_40_2018`), candles ajustados por splits, sem dividendos/JCP. O universo tem vies de sobrevivencia declarado.
- **Sem gerenciamento**: sem rebalanceamento periodico e sem alvo de volatilidade. Todo o patrimonio vai para a acao escolhida e fica parado ate o sinal de venda.

## Variantes

- `roc3m_positivo_primeiro_candle`: PRINCIPAL. Somente sinais no primeiro candle com ROC de 63 pregoes acima de 0; entre eles, o maior ROC.
- `roc3m_primeiro_candle`: Igual a principal, sem exigir ROC positivo (maior ROC mesmo se negativo).
- `prioridade_roc3m_positivo_primeiro_candle`: Igual a principal, com sinais prioritarios (preco ou SMA20 > SMA50) antes do ROC.
- `alfabetica_roc3m_positivo_primeiro_candle`: Igual a principal, mas sem ordenar pelo ROC: empate pela ordem alfabetica (mede o efeito do ranking).
- `roc3m_positivo_primeiro_candle_sem_custos`: Diagnostico: regra principal com custos e slippage zerados (mostra quanto os custos pesam).
- `buy_and_hold_peso_igual`: Referencia: as 40 acoes compradas em peso igual (com fracoes de acao), sem rebalancear.

## Carteira seguindo o sinal

| Periodo | Variante | Vagas | CAGR | Retorno total | Max DD | Sharpe | Calmar | Exposicao | Trades | Acerto | Fator lucro | Sinais descartados |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018+ | `roc3m_positivo_primeiro_candle` | 1 | **-6.76%** | -45.34% | -85.27% | -0.05 | -0.08 | 86.81% | 179 | 25.14% | 0.98 | 1906 |
| 2018+ | `roc3m_primeiro_candle` | 1 | **-17.36%** | -80.70% | -90.81% | -0.39 | -0.19 | 93.20% | 224 | 26.34% | 0.75 | 4048 |
| 2018+ | `prioridade_roc3m_positivo_primeiro_candle` | 1 | **-4.77%** | -34.38% | -85.12% | 0.02 | -0.06 | 86.91% | 174 | 25.86% | 1.02 | 1911 |
| 2018+ | `alfabetica_roc3m_positivo_primeiro_candle` | 1 | **-3.34%** | -25.37% | -76.11% | 0.05 | -0.04 | 86.02% | 172 | 27.91% | 1.03 | 1913 |
| 2018+ | `roc3m_positivo_primeiro_candle_sem_custos` | 1 | **-1.51%** | -12.26% | -79.07% | 0.12 | -0.02 | 86.81% | 179 | 26.82% | 1.09 | 1906 |
| 2018+ | `buy_and_hold_peso_igual` | 40 | **4.53%** | 46.53% | -48.83% | 0.31 | 0.09 | 100.00% | 0 | - | - | 0 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle` | 1 | **-19.62%** | -54.73% | -62.60% | -0.53 | -0.31 | 87.43% | 85 | 25.88% | 0.67 | 720 |
| 2023+ (teste) | `roc3m_primeiro_candle` | 1 | **-29.11%** | -71.29% | -75.72% | -0.85 | -0.38 | 94.27% | 102 | 23.53% | 0.58 | 1664 |
| 2023+ (teste) | `prioridade_roc3m_positivo_primeiro_candle` | 1 | **-15.91%** | -46.66% | -63.55% | -0.39 | -0.25 | 87.54% | 81 | 27.16% | 0.73 | 724 |
| 2023+ (teste) | `alfabetica_roc3m_positivo_primeiro_candle` | 1 | **-12.83%** | -39.24% | -52.82% | -0.30 | -0.24 | 86.44% | 87 | 25.29% | 0.81 | 718 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle_sem_custos` | 1 | **-14.48%** | -43.31% | -55.14% | -0.33 | -0.26 | 87.43% | 85 | 27.06% | 0.76 | 720 |
| 2023+ (teste) | `buy_and_hold_peso_igual` | 40 | **2.26%** | 8.46% | -23.22% | 0.22 | 0.10 | 100.00% | 0 | - | - | 0 |

## Retorno anual da variante principal (`roc3m_positivo_primeiro_candle`)

| Ano | Estrategia | Buy and hold peso igual |
| :--- | ---: | ---: |
| 2018 | 61.93% | 17.06% |
| 2019 | 76.42% | 40.94% |
| 2020 | -26.42% | 11.34% |
| 2021 | -20.29% | -21.88% |
| 2022 | -42.58% | -6.31% |
| 2023 | -25.50% | 12.16% |
| 2024 | -22.53% | -15.50% |
| 2025 | -5.10% | 16.46% |
| 2026 | 3.73% | -1.25% |

## Efeito da prioridade (todos os trades do sinal com ROC 3m positivo na entrada, sem limite de vagas)

| Grupo | Trades | Acerto | Retorno medio | Mediana | Ganho medio | Perda media | Fator lucro | Pregoes medios |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Todos | 2083 | 27.36% | 0.27% | -1.69% | 8.63% | -2.88% | 1.13 | 9.86 |
| Prioritarios (preco ou SMA20 > SMA50) | 1725 | 27.88% | 0.15% | -1.79% | 8.31% | -3.01% | 1.07 | 10.16 |
| Nao prioritarios | 358 | 24.86% | 0.85% | -1.32% | 10.36% | -2.29% | 1.50 | 8.40 |

## Ativo isolado (100% do capital em cada ativo, entrada so com ROC 3m positivo, 2018-01-02 a 2026-08-19)

Estrategia superou o buy and hold do proprio ativo em **17 de 40** ativos. CAGR mediano da estrategia: **0.12%**; buy and hold mediano: **0.85%**.

| Ativo | CAGR | Retorno total | Max DD | Sharpe | Exposicao | Ordens | B&H CAGR | B&H Max DD | Excesso (retorno total) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| JHSF3 | 19.98% | 381.28% | -38.65% | 0.93 | 27.73% | 108 | 22.40% | -66.60% | -90.48% |
| CSNA3 | 10.93% | 144.72% | -46.44% | 0.57 | 20.78% | 90 | -7.22% | -91.72% | 192.33% |
| WEGE3 | 7.95% | 93.53% | -25.87% | 0.52 | 26.28% | 102 | 20.98% | -50.48% | -323.62% |
| BRAP4 | 7.72% | 89.96% | -25.40% | 0.54 | 27.21% | 96 | -2.69% | -78.61% | 110.91% |
| USIM5 | 7.70% | 89.65% | -45.50% | 0.43 | 24.42% | 100 | -4.49% | -83.34% | 122.39% |
| CSMG3 | 6.93% | 78.30% | -58.77% | 0.48 | 28.52% | 102 | 16.62% | -54.70% | -198.33% |
| BBDC3 | 6.35% | 70.03% | -19.83% | 0.49 | 23.49% | 84 | -3.00% | -61.24% | 93.15% |
| MRVE3 | 5.47% | 58.31% | -45.56% | 0.36 | 22.41% | 94 | -12.20% | -81.38% | 125.77% |
| SBSP3 | 5.39% | 57.27% | -40.97% | 0.39 | 33.60% | 112 | 15.84% | -54.03% | -198.35% |
| VALE3 | 4.36% | 44.57% | -38.90% | 0.35 | 29.31% | 106 | 6.90% | -58.48% | -33.26% |
| GOAU4 | 4.13% | 41.79% | -34.79% | 0.33 | 26.65% | 99 | 10.51% | -64.59% | -95.00% |
| RADL3 | 3.41% | 33.57% | -52.27% | 0.28 | 31.78% | 116 | 0.23% | -55.53% | 31.55% |
| GGBR3 | 3.20% | 31.26% | -33.45% | 0.28 | 23.30% | 96 | 10.64% | -60.82% | -107.99% |
| BRKM5 | 2.61% | 24.87% | -38.89% | 0.23 | 18.17% | 66 | -21.61% | -92.75% | 112.63% |
| TUPY3 | 2.49% | 23.60% | -33.23% | 0.23 | 19.57% | 84 | -2.71% | -63.83% | 44.73% |
| CSAN3 | 1.77% | 16.30% | -35.80% | 0.19 | 22.88% | 100 | -12.26% | -88.48% | 83.95% |
| UGPA3 | 1.69% | 15.53% | -47.95% | 0.18 | 22.79% | 91 | -1.21% | -73.82% | 25.51% |
| RENT3 | 0.84% | 7.44% | -43.50% | 0.14 | 30.80% | 100 | 5.48% | -62.65% | -50.98% |
| SANB11 | 0.67% | 5.93% | -31.73% | 0.12 | 18.83% | 93 | -1.37% | -54.90% | 17.19% |
| ITSA4 | 0.56% | 4.95% | -26.19% | 0.11 | 24.14% | 102 | 5.79% | -47.51% | -57.52% |
| BBAS3 | -0.32% | -2.69% | -40.64% | 0.05 | 22.09% | 78 | 1.38% | -59.87% | -15.21% |
| CMIG4 | -0.37% | -3.17% | -42.55% | 0.06 | 26.61% | 128 | 13.12% | -50.40% | -192.74% |
| ITUB4 | -0.66% | -5.57% | -32.69% | 0.01 | 24.79% | 118 | 4.98% | -48.25% | -57.65% |
| EGIE3 | -1.09% | -9.05% | -30.45% | -0.03 | 25.58% | 130 | 3.56% | -35.90% | -44.24% |
| BBSE3 | -1.49% | -12.13% | -29.47% | -0.04 | 26.75% | 108 | 2.88% | -51.92% | -39.88% |
| SUZB3 | -1.77% | -14.25% | -35.52% | -0.03 | 22.55% | 98 | 10.19% | -54.75% | -145.17% |
| TAEE11 | -2.28% | -18.03% | -34.80% | -0.15 | 27.87% | 142 | 6.63% | -30.49% | -92.03% |
| ABEV3 | -3.54% | -26.75% | -36.36% | -0.27 | 18.97% | 94 | -4.18% | -55.40% | 4.03% |
| EQTL3 | -4.34% | -31.79% | -48.05% | -0.27 | 26.84% | 134 | 11.95% | -40.95% | -196.58% |
| IRBR3 | -4.51% | -32.82% | -61.24% | -0.21 | 19.71% | 82 | -18.41% | -97.91% | 49.89% |
| MGLU3 | -4.51% | -32.83% | -68.99% | -0.09 | 25.26% | 98 | -18.59% | -98.49% | 50.21% |
| FLRY3 | -5.71% | -39.77% | -50.91% | -0.39 | 21.71% | 100 | -4.94% | -66.27% | -4.38% |
| MULT3 | -6.03% | -41.52% | -60.98% | -0.38 | 24.18% | 128 | 1.04% | -53.66% | -50.82% |
| QUAL3 | -6.09% | -41.87% | -71.61% | -0.18 | 19.80% | 98 | -28.87% | -96.96% | 52.84% |
| HYPE3 | -7.09% | -46.96% | -54.65% | -0.43 | 22.65% | 110 | -6.02% | -66.88% | -5.50% |
| KLBN11 | -7.33% | -48.16% | -50.57% | -0.76 | 12.21% | 90 | 1.34% | -42.88% | -60.36% |
| LREN3 | -8.33% | -52.79% | -66.64% | -0.43 | 23.35% | 132 | -10.08% | -78.77% | 7.21% |
| PETR4 | -9.26% | -56.77% | -74.57% | -0.39 | 26.75% | 138 | 11.99% | -63.50% | -222.47% |
| RAIL3 | -11.33% | -64.57% | -67.33% | -0.69 | 26.84% | 138 | 0.66% | -54.08% | -70.44% |
| CVCB3 | -12.44% | -68.22% | -70.03% | -0.62 | 11.65% | 82 | -32.20% | -98.01% | 28.28% |

Resultados retrospectivos: sem otimizacao de parametros, mas com universo fixo (vies de sobrevivencia), sem impostos e sem proventos. Nao representam expectativa de dinheiro real.

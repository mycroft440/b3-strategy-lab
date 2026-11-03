# RSI + WMA Heikin Ashi - backtest sem gerenciamento de carteira

## Regras testadas

- **Compra**: RSI(14) do fechamento acima de 50 e WMA(20) do fechamento Heikin Ashi subindo (WMA[t] > WMA[t-1]), com o fechamento ACIMA da SMA200 (fechamento > SMA).
- **Venda**: basta um dos dois: RSI abaixo de 50 ou WMA Heikin Ashi caindo (WMA[t] < WMA[t-1]). A SMA so filtra a compra; o preco cair abaixo dela nao vende.
- **Selecao**: somente 1 acao por vez. A entrada so ocorre na abertura seguinte ao PRIMEIRO candle do sinal; se a vaga estiver ocupada, o sinal e descartado (nunca ha entrada tardia). So entram sinais novos com ROC de 3 meses (63 pregoes) acima de 0; entre eles, compra-se o de maior ROC. Sem candidato, a carteira fica em caixa. A posicao fica ate o sinal de venda (o ROC so e exigido na entrada).
- **Prioridade** (fechamento OU SMA20 acima da SMA50): nao entra na escolha da regra principal; aparece apenas nas estatisticas de trades.
- "RSI acima de 0" foi lido como RSI centralizado (RSI - 50 > 0), ou seja RSI > 50.
- Sinal no fechamento, execucao na abertura seguinte; custos 3.2 bps + slippage 10.0 bps por ordem; lote de 1 acao.
- Universo: 40 acoes (`fixed_research_universe_40_2018`), candles ajustados por splits, sem dividendos/JCP. O universo tem vies de sobrevivencia declarado.
- **Sem gerenciamento**: sem rebalanceamento periodico e sem alvo de volatilidade. Todo o patrimonio vai para a acao escolhida e fica parado ate o sinal de venda.

## Variantes

- `roc3m_positivo_primeiro_candle`: PRINCIPAL. Somente sinais no primeiro candle com ROC de 63 pregoes acima de 0; entre eles, o maior ROC.
- `roc3m_primeiro_candle`: Igual a principal, sem exigir ROC positivo (maior ROC mesmo se negativo).
- `alfabetica_roc3m_positivo_primeiro_candle`: Igual a principal, mas sem ordenar pelo ROC: empate pela ordem alfabetica (mede o efeito do ranking).
- `roc3m_positivo_primeiro_candle_filtro_sma50`: Comparacao: regra principal com fechamento acima da SMA50 no lugar da SMA200.
- `roc3m_positivo_primeiro_candle_sem_filtro_sma`: Comparacao: regra principal sem filtro de media na compra.
- `roc3m_positivo_primeiro_candle_sem_custos`: Diagnostico: regra principal com custos e slippage zerados (mostra quanto os custos pesam).
- `buy_and_hold_peso_igual`: Referencia: as 40 acoes compradas em peso igual (com fracoes de acao), sem rebalancear.

## Carteira seguindo o sinal

| Periodo | Variante | Vagas | CAGR | Retorno total | Max DD | Sharpe | Calmar | Exposicao | Trades | Acerto | Fator lucro | Sinais descartados |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018+ | `roc3m_positivo_primeiro_candle` | 1 | **-9.09%** | -56.05% | -87.13% | -0.16 | -0.10 | 87.19% | 176 | 28.41% | 0.92 | 1752 |
| 2018+ | `roc3m_primeiro_candle` | 1 | **-8.89%** | -55.20% | -84.97% | -0.10 | -0.10 | 91.05% | 191 | 28.27% | 0.92 | 2421 |
| 2018+ | `alfabetica_roc3m_positivo_primeiro_candle` | 1 | **-6.48%** | -43.89% | -75.14% | -0.07 | -0.09 | 86.77% | 171 | 31.58% | 0.93 | 1757 |
| 2018+ | `roc3m_positivo_primeiro_candle_filtro_sma50` | 1 | **-3.59%** | -27.07% | -80.96% | 0.05 | -0.04 | 86.81% | 161 | 29.81% | 1.06 | 1781 |
| 2018+ | `roc3m_positivo_primeiro_candle_sem_filtro_sma` | 1 | **-6.76%** | -45.34% | -85.27% | -0.05 | -0.08 | 86.81% | 179 | 25.14% | 0.98 | 1906 |
| 2018+ | `roc3m_positivo_primeiro_candle_sem_custos` | 1 | **-4.13%** | -30.50% | -82.88% | 0.01 | -0.05 | 87.19% | 176 | 28.98% | 1.03 | 1752 |
| 2018+ | `buy_and_hold_peso_igual` | 40 | **4.53%** | 46.53% | -48.83% | 0.31 | 0.09 | 100.00% | 0 | - | - | 0 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle` | 1 | **-1.30%** | -4.64% | -33.47% | 0.11 | -0.04 | 87.65% | 72 | 31.94% | 1.05 | 663 |
| 2023+ (teste) | `roc3m_primeiro_candle` | 1 | **-6.78%** | -22.48% | -43.46% | -0.03 | -0.16 | 90.96% | 85 | 29.41% | 0.91 | 941 |
| 2023+ (teste) | `alfabetica_roc3m_positivo_primeiro_candle` | 1 | **6.28%** | 24.74% | -33.09% | 0.35 | 0.19 | 86.99% | 69 | 30.43% | 1.30 | 666 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle_filtro_sma50` | 1 | **-13.37%** | -40.60% | -52.40% | -0.29 | -0.26 | 87.65% | 74 | 31.08% | 0.79 | 659 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle_sem_filtro_sma` | 1 | **-19.62%** | -54.73% | -62.60% | -0.53 | -0.31 | 87.43% | 85 | 25.88% | 0.67 | 720 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle_sem_custos` | 1 | **4.05%** | 15.50% | -27.95% | 0.28 | 0.15 | 87.65% | 72 | 33.33% | 1.22 | 663 |
| 2023+ (teste) | `buy_and_hold_peso_igual` | 40 | **2.26%** | 8.46% | -23.22% | 0.22 | 0.10 | 100.00% | 0 | - | - | 0 |

## Retorno anual da variante principal (`roc3m_positivo_primeiro_candle`)

| Ano | Estrategia | Buy and hold peso igual |
| :--- | ---: | ---: |
| 2018 | 34.73% | 17.06% |
| 2019 | 76.29% | 40.94% |
| 2020 | -50.27% | 11.34% |
| 2021 | -36.79% | -21.88% |
| 2022 | -42.17% | -6.31% |
| 2023 | -3.58% | 12.16% |
| 2024 | -12.78% | -15.50% |
| 2025 | 8.08% | 16.46% |
| 2026 | 12.00% | -1.25% |

## Todos os trades do sinal (mesma regra de entrada, sem limite de vagas)

| Grupo | Trades | Acerto | Retorno medio | Mediana | Ganho medio | Perda media | Fator lucro | Pregoes medios |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Todos | 1927 | 27.92% | 0.23% | -1.79% | 8.86% | -3.11% | 1.10 | 10.89 |
| Prioritarios (preco ou SMA20 > SMA50) | 1690 | 28.28% | 0.18% | -1.90% | 8.83% | -3.23% | 1.08 | 11.27 |
| Nao prioritarios | 237 | 25.32% | 0.59% | -1.35% | 9.13% | -2.30% | 1.34 | 8.20 |

## Ativo isolado (100% do capital em cada ativo, entrada so com ROC 3m positivo, 2018-01-02 a 2026-08-19)

Estrategia superou o buy and hold do proprio ativo em **15 de 40** ativos. CAGR mediano da estrategia: **-0.42%**; buy and hold mediano: **0.85%**.

| Ativo | CAGR | Retorno total | Max DD | Sharpe | Exposicao | Ordens | B&H CAGR | B&H Max DD | Excesso (retorno total) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| JHSF3 | 14.57% | 223.23% | -52.81% | 0.71 | 30.71% | 112 | 22.40% | -66.60% | -248.53% |
| CSNA3 | 13.73% | 203.48% | -32.57% | 0.66 | 21.81% | 72 | -7.22% | -91.72% | 251.09% |
| USIM5 | 10.30% | 132.89% | -25.84% | 0.56 | 22.23% | 82 | -4.49% | -83.34% | 165.63% |
| GGBR3 | 9.31% | 115.54% | -29.57% | 0.63 | 23.67% | 84 | 10.64% | -60.82% | -23.71% |
| GOAU4 | 6.89% | 77.65% | -29.62% | 0.48 | 28.29% | 97 | 10.51% | -64.59% | -59.14% |
| BRAP4 | 6.39% | 70.61% | -28.18% | 0.46 | 27.03% | 88 | -2.69% | -78.61% | 91.56% |
| SBSP3 | 5.84% | 63.11% | -37.92% | 0.42 | 31.59% | 98 | 15.84% | -54.03% | -192.50% |
| CSMG3 | 5.11% | 53.70% | -61.16% | 0.38 | 32.67% | 106 | 16.62% | -54.70% | -222.92% |
| BBDC3 | 5.03% | 52.66% | -19.91% | 0.42 | 22.65% | 82 | -3.00% | -61.24% | 75.78% |
| WEGE3 | 4.62% | 47.68% | -40.03% | 0.34 | 27.45% | 108 | 20.98% | -50.48% | -369.47% |
| BRKM5 | 4.23% | 42.95% | -35.85% | 0.30 | 18.59% | 58 | -21.61% | -92.75% | 130.71% |
| VALE3 | 2.55% | 24.29% | -45.09% | 0.24 | 29.22% | 94 | 6.90% | -58.48% | -53.53% |
| SANB11 | 2.17% | 20.36% | -29.06% | 0.22 | 20.97% | 84 | -1.37% | -54.90% | 31.62% |
| CSAN3 | 1.12% | 10.07% | -27.86% | 0.15 | 22.69% | 82 | -12.26% | -88.48% | 77.72% |
| UGPA3 | 1.06% | 9.54% | -43.03% | 0.15 | 21.81% | 79 | -1.21% | -73.82% | 19.52% |
| RENT3 | 0.60% | 5.28% | -48.92% | 0.12 | 30.48% | 96 | 5.48% | -62.65% | -53.13% |
| CMIG4 | 0.39% | 3.45% | -42.47% | 0.11 | 27.63% | 118 | 13.12% | -50.40% | -186.11% |
| BBAS3 | -0.05% | -0.42% | -44.12% | 0.07 | 20.60% | 66 | 1.38% | -59.87% | -12.95% |
| ITUB4 | -0.24% | -2.09% | -26.15% | 0.04 | 25.49% | 112 | 4.98% | -48.25% | -54.17% |
| TUPY3 | -0.39% | -3.32% | -44.21% | 0.06 | 21.44% | 82 | -2.71% | -63.83% | 17.81% |
| RADL3 | -0.45% | -3.80% | -54.03% | 0.06 | 31.22% | 110 | 0.23% | -55.53% | -5.82% |
| IRBR3 | -0.64% | -5.41% | -51.26% | 0.07 | 23.35% | 80 | -18.41% | -97.91% | 77.29% |
| SUZB3 | -0.80% | -6.70% | -34.78% | 0.03 | 23.07% | 92 | 10.19% | -54.75% | -137.62% |
| ITSA4 | -1.30% | -10.65% | -29.36% | -0.04 | 25.68% | 102 | 5.79% | -47.51% | -73.12% |
| MRVE3 | -1.34% | -11.01% | -54.77% | 0.03 | 21.39% | 86 | -12.20% | -81.38% | 56.45% |
| EGIE3 | -2.19% | -17.42% | -37.25% | -0.11 | 28.38% | 132 | 3.56% | -35.90% | -52.61% |
| BBSE3 | -2.80% | -21.73% | -32.72% | -0.13 | 28.89% | 104 | 2.88% | -51.92% | -49.48% |
| TAEE11 | -3.25% | -24.78% | -38.41% | -0.25 | 26.89% | 130 | 6.63% | -30.49% | -98.78% |
| ABEV3 | -4.04% | -29.93% | -37.42% | -0.29 | 21.95% | 88 | -4.18% | -55.40% | 0.86% |
| MGLU3 | -4.43% | -32.37% | -68.78% | -0.08 | 25.07% | 90 | -18.59% | -98.49% | 50.67% |
| CVCB3 | -4.77% | -34.42% | -48.36% | -0.16 | 13.33% | 64 | -32.20% | -98.01% | 62.09% |
| EQTL3 | -5.16% | -36.70% | -50.08% | -0.33 | 28.24% | 132 | 11.95% | -40.95% | -201.48% |
| KLBN11 | -6.07% | -41.74% | -46.81% | -0.50 | 17.29% | 86 | 1.34% | -42.88% | -53.94% |
| MULT3 | -6.68% | -44.90% | -60.32% | -0.44 | 24.37% | 120 | 1.04% | -53.66% | -54.21% |
| QUAL3 | -6.84% | -45.74% | -69.04% | -0.29 | 16.08% | 80 | -28.87% | -96.96% | 48.97% |
| HYPE3 | -7.64% | -49.61% | -51.39% | -0.52 | 21.53% | 92 | -6.02% | -66.88% | -8.14% |
| FLRY3 | -8.14% | -51.91% | -54.72% | -0.65 | 19.57% | 88 | -4.94% | -66.27% | -16.52% |
| PETR4 | -8.98% | -55.61% | -74.23% | -0.39 | 23.77% | 114 | 11.99% | -63.50% | -221.30% |
| LREN3 | -11.27% | -64.37% | -71.51% | -0.65 | 23.39% | 122 | -10.08% | -78.77% | -4.37% |
| RAIL3 | -13.08% | -70.16% | -72.49% | -0.80 | 28.66% | 140 | 0.66% | -54.08% | -76.03% |

Resultados retrospectivos: sem otimizacao de parametros, mas com universo fixo (vies de sobrevivencia), sem impostos e sem proventos. Nao representam expectativa de dinheiro real.

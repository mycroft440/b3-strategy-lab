# RSI + WMA Heikin Ashi - backtest sem gerenciamento de carteira

## Regras testadas

- **Compra**: RSI(14) do fechamento acima de 50 e WMA(20) do fechamento Heikin Ashi subindo (WMA[t] > WMA[t-1]).
- **Venda**: RSI abaixo de 50 ou WMA Heikin Ashi caindo (WMA[t] < WMA[t-1]).
- **Selecao**: somente 1 acao por vez. A entrada so ocorre na abertura seguinte ao PRIMEIRO candle do sinal; se a vaga estiver ocupada, o sinal e descartado (nunca ha entrada tardia). Entre os sinais novos do mesmo fechamento, compra-se o de maior ROC de 3 meses (63 pregoes). A posicao fica ate o sinal de venda.
- **Prioridade** (variantes de comparacao): fechamento OU SMA20 acima da SMA50.
- "RSI acima de 0" foi lido como RSI centralizado (RSI - 50 > 0), ou seja RSI > 50.
- Sinal no fechamento, execucao na abertura seguinte; custos 3.2 bps + slippage 10.0 bps por ordem; lote de 1 acao.
- Universo: 40 acoes (`fixed_research_universe_40_2018`), candles ajustados por splits, sem dividendos/JCP. O universo tem vies de sobrevivencia declarado.
- **Sem gerenciamento**: sem rebalanceamento periodico e sem alvo de volatilidade. Todo o patrimonio vai para a acao escolhida e fica parado ate o sinal de venda.

## Variantes

- `roc3m_primeiro_candle`: PRINCIPAL. Somente sinais no primeiro candle; maior ROC de 63 pregoes.
- `roc3m_positivo_primeiro_candle`: Igual a principal, exigindo ROC de 3 meses acima de zero.
- `prioridade_roc3m_primeiro_candle`: Igual a principal, com sinais prioritarios (preco ou SMA20 > SMA50) antes do ROC.
- `alfabetica_primeiro_candle`: Primeiro candle sem ROC: empate resolvido pela ordem alfabetica (mede o efeito do ROC).
- `roc3m_primeiro_candle_sem_custos`: Diagnostico: regra principal com custos e slippage zerados (mostra quanto os custos pesam).
- `buy_and_hold_peso_igual`: Referencia: as 40 acoes compradas em peso igual (com fracoes de acao), sem rebalancear.

## Carteira seguindo o sinal

| Periodo | Variante | Vagas | CAGR | Retorno total | Max DD | Sharpe | Calmar | Exposicao | Trades | Acerto | Fator lucro | Sinais descartados |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018+ | `roc3m_primeiro_candle` | 1 | **-17.36%** | -80.70% | -90.81% | -0.39 | -0.19 | 93.20% | 224 | 26.34% | 0.75 | 4048 |
| 2018+ | `roc3m_positivo_primeiro_candle` | 1 | **-6.76%** | -45.34% | -85.27% | -0.05 | -0.08 | 86.81% | 179 | 25.14% | 0.98 | 1906 |
| 2018+ | `prioridade_roc3m_primeiro_candle` | 1 | **-19.45%** | -84.53% | -89.12% | -0.42 | -0.22 | 93.62% | 236 | 25.42% | 0.77 | 4036 |
| 2018+ | `alfabetica_primeiro_candle` | 1 | **-21.51%** | -87.62% | -91.35% | -0.40 | -0.24 | 93.71% | 221 | 27.15% | 0.70 | 4053 |
| 2018+ | `roc3m_primeiro_candle_sem_custos` | 1 | **-11.49%** | -65.12% | -84.92% | -0.19 | -0.14 | 93.20% | 224 | 29.02% | 0.85 | 4048 |
| 2018+ | `buy_and_hold_peso_igual` | 40 | **4.53%** | 46.53% | -48.83% | 0.31 | 0.09 | 100.00% | 0 | - | - | 0 |
| 2023+ (teste) | `roc3m_primeiro_candle` | 1 | **-29.11%** | -71.29% | -75.72% | -0.85 | -0.38 | 94.27% | 102 | 23.53% | 0.58 | 1664 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle` | 1 | **-19.62%** | -54.73% | -62.60% | -0.53 | -0.31 | 87.43% | 85 | 25.88% | 0.67 | 720 |
| 2023+ (teste) | `prioridade_roc3m_primeiro_candle` | 1 | **-11.15%** | -34.88% | -71.20% | -0.12 | -0.16 | 94.49% | 96 | 21.88% | 1.01 | 1670 |
| 2023+ (teste) | `alfabetica_primeiro_candle` | 1 | **-21.41%** | -58.28% | -67.67% | -0.53 | -0.32 | 94.71% | 102 | 26.47% | 0.66 | 1664 |
| 2023+ (teste) | `roc3m_primeiro_candle_sem_custos` | 1 | **-23.57%** | -62.28% | -68.31% | -0.62 | -0.34 | 94.27% | 102 | 26.47% | 0.65 | 1664 |
| 2023+ (teste) | `buy_and_hold_peso_igual` | 40 | **2.26%** | 8.46% | -23.22% | 0.22 | 0.10 | 100.00% | 0 | - | - | 0 |

## Retorno anual da variante principal (`roc3m_primeiro_candle`)

| Ano | Estrategia | Buy and hold peso igual |
| :--- | ---: | ---: |
| 2018 | 69.39% | 17.06% |
| 2019 | 9.42% | 40.94% |
| 2020 | -41.88% | 11.34% |
| 2021 | -30.64% | -21.88% |
| 2022 | -24.51% | -6.31% |
| 2023 | -14.74% | 12.16% |
| 2024 | -36.82% | -15.50% |
| 2025 | 5.50% | 16.46% |
| 2026 | -39.78% | -1.25% |

## Efeito da prioridade (todos os trades do sinal, sem limite de vagas)

| Grupo | Trades | Acerto | Retorno medio | Mediana | Ganho medio | Perda media | Fator lucro | Pregoes medios |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Todos | 4266 | 26.47% | 0.06% | -1.61% | 8.18% | -2.86% | 1.03 | 9.01 |
| Prioritarios (preco ou SMA20 > SMA50) | 2622 | 27.73% | 0.30% | -1.79% | 9.00% | -3.03% | 1.14 | 10.09 |
| Nao prioritarios | 1644 | 24.45% | -0.32% | -1.40% | 6.70% | -2.59% | 0.84 | 7.29 |

## Ativo isolado (100% do capital em cada ativo, 2018-01-02 a 2026-08-19)

Estrategia superou o buy and hold do proprio ativo em **14 de 40** ativos. CAGR mediano da estrategia: **-1.89%**; buy and hold mediano: **0.85%**.

| Ativo | CAGR | Retorno total | Max DD | Sharpe | Exposicao | Ordens | B&H CAGR | B&H Max DD | Excesso (retorno total) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| JHSF3 | 25.50% | 609.75% | -51.30% | 0.89 | 48.88% | 208 | 22.40% | -66.60% | 137.99% |
| WEGE3 | 13.23% | 192.06% | -43.98% | 0.65 | 49.35% | 199 | 20.98% | -50.48% | -225.09% |
| SBSP3 | 7.68% | 89.31% | -49.80% | 0.44 | 51.16% | 180 | 15.84% | -54.03% | -166.31% |
| GGBR3 | 7.64% | 88.70% | -41.82% | 0.44 | 49.58% | 226 | 10.64% | -60.82% | -50.55% |
| SUZB3 | 7.55% | 87.36% | -37.68% | 0.41 | 45.34% | 196 | 10.19% | -54.75% | -43.56% |
| BBAS3 | 6.50% | 72.18% | -29.12% | 0.41 | 43.10% | 160 | 1.38% | -59.87% | 59.66% |
| GOAU4 | 6.02% | 65.52% | -53.99% | 0.36 | 50.33% | 207 | 10.51% | -64.59% | -71.26% |
| CSMG3 | 5.70% | 61.37% | -59.99% | 0.35 | 50.61% | 220 | 16.62% | -54.70% | -215.26% |
| ITUB4 | 4.36% | 44.50% | -26.19% | 0.33 | 48.09% | 212 | 4.98% | -48.25% | -7.58% |
| BBDC3 | 4.23% | 42.93% | -28.67% | 0.31 | 42.92% | 188 | -3.00% | -61.24% | 66.05% |
| CSNA3 | 3.28% | 32.07% | -77.34% | 0.26 | 41.33% | 208 | -7.22% | -91.72% | 79.68% |
| ITSA4 | 3.28% | 32.06% | -30.73% | 0.27 | 47.76% | 202 | 5.79% | -47.51% | -30.41% |
| RENT3 | 2.26% | 21.26% | -64.03% | 0.21 | 50.33% | 192 | 5.48% | -62.65% | -37.16% |
| VALE3 | 1.24% | 11.21% | -49.13% | 0.17 | 49.95% | 210 | 6.90% | -58.48% | -66.61% |
| CMIG4 | 1.22% | 11.02% | -53.49% | 0.17 | 49.53% | 236 | 13.12% | -50.40% | -178.54% |
| MGLU3 | 0.29% | 2.57% | -77.36% | 0.20 | 43.71% | 176 | -18.59% | -98.49% | 85.62% |
| BBSE3 | -0.88% | -7.38% | -32.93% | 0.04 | 46.74% | 200 | 2.88% | -51.92% | -35.12% |
| UGPA3 | -1.21% | -9.95% | -52.27% | 0.07 | 45.57% | 215 | -1.21% | -73.82% | 0.02% |
| USIM5 | -1.22% | -10.04% | -78.10% | 0.11 | 42.31% | 212 | -4.49% | -83.34% | 22.70% |
| KLBN11 | -1.82% | -14.65% | -44.07% | -0.02 | 43.24% | 240 | 1.34% | -42.88% | -26.85% |
| IRBR3 | -1.96% | -15.71% | -66.36% | 0.11 | 39.56% | 172 | -18.41% | -97.91% | 67.00% |
| EQTL3 | -2.81% | -21.81% | -42.80% | -0.07 | 49.39% | 224 | 11.95% | -40.95% | -186.59% |
| ABEV3 | -3.19% | -24.42% | -35.93% | -0.11 | 41.43% | 188 | -4.18% | -55.40% | 6.37% |
| SANB11 | -3.60% | -27.13% | -55.04% | -0.09 | 40.45% | 215 | -1.37% | -54.90% | -15.87% |
| EGIE3 | -3.69% | -27.73% | -45.43% | -0.16 | 45.62% | 242 | 3.56% | -35.90% | -62.92% |
| BRKM5 | -4.06% | -30.05% | -59.15% | 0.01 | 36.95% | 176 | -21.61% | -92.75% | 57.71% |
| TAEE11 | -4.66% | -33.76% | -47.04% | -0.27 | 47.16% | 248 | 6.63% | -30.49% | -107.76% |
| TUPY3 | -5.83% | -40.43% | -60.55% | -0.13 | 40.77% | 212 | -2.71% | -63.83% | -19.30% |
| RADL3 | -6.30% | -42.98% | -71.62% | -0.18 | 47.53% | 226 | 0.23% | -55.53% | -45.00% |
| CSAN3 | -6.50% | -44.02% | -59.30% | -0.17 | 40.59% | 202 | -12.26% | -88.48% | 23.63% |
| MRVE3 | -7.09% | -46.98% | -71.26% | -0.11 | 38.77% | 209 | -12.20% | -81.38% | 20.48% |
| PETR4 | -7.83% | -50.49% | -71.88% | -0.19 | 49.67% | 229 | 11.99% | -63.50% | -216.19% |
| LREN3 | -8.29% | -52.58% | -64.89% | -0.21 | 42.36% | 238 | -10.08% | -78.77% | 7.42% |
| FLRY3 | -8.30% | -52.65% | -65.07% | -0.38 | 41.47% | 213 | -4.94% | -66.27% | -17.27% |
| BRAP4 | -9.50% | -57.74% | -77.86% | -0.13 | 45.62% | 218 | -2.69% | -78.61% | -36.80% |
| MULT3 | -9.64% | -58.30% | -72.42% | -0.39 | 45.81% | 236 | 1.04% | -53.66% | -67.61% |
| RAIL3 | -13.78% | -72.16% | -78.90% | -0.59 | 46.23% | 252 | 0.66% | -54.08% | -78.02% |
| HYPE3 | -13.83% | -72.31% | -73.87% | -0.65 | 42.87% | 242 | -6.02% | -66.88% | -30.85% |
| CVCB3 | -21.41% | -87.49% | -89.36% | -0.46 | 35.74% | 231 | -32.20% | -98.01% | 9.01% |
| QUAL3 | -32.94% | -96.82% | -98.28% | -1.09 | 37.88% | 273 | -28.87% | -96.96% | -2.11% |

Resultados retrospectivos: sem otimizacao de parametros, mas com universo fixo (vies de sobrevivencia), sem impostos e sem proventos. Nao representam expectativa de dinheiro real.

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
- `buy_and_hold_peso_igual`: Referencia: as 40 acoes compradas em peso igual, sem rebalancear.

## Carteira seguindo o sinal

| Periodo | Variante | Vagas | CAGR | Retorno total | Max DD | Sharpe | Calmar | Exposicao | Trades | Acerto | Fator lucro | Sinais descartados |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018+ | `roc3m_primeiro_candle` | 1 | **-17.36%** | -80.70% | -90.81% | -0.39 | -0.19 | 93.20% | 224 | 26.34% | 0.75 | 4048 |
| 2018+ | `roc3m_positivo_primeiro_candle` | 1 | **-6.76%** | -45.34% | -85.27% | -0.05 | -0.08 | 86.81% | 179 | 25.14% | 0.98 | 1906 |
| 2018+ | `prioridade_roc3m_primeiro_candle` | 1 | **-19.45%** | -84.53% | -89.12% | -0.42 | -0.22 | 93.62% | 236 | 25.42% | 0.77 | 4036 |
| 2018+ | `alfabetica_primeiro_candle` | 1 | **-21.51%** | -87.62% | -91.35% | -0.40 | -0.24 | 93.71% | 221 | 27.15% | 0.70 | 4053 |
| 2018+ | `buy_and_hold_peso_igual` | 40 | **4.56%** | 46.88% | -45.10% | 0.31 | 0.10 | 100.00% | 0 | - | - | 546 |
| 2023+ (teste) | `roc3m_primeiro_candle` | 1 | **-29.11%** | -71.29% | -75.72% | -0.85 | -0.38 | 94.27% | 102 | 23.53% | 0.58 | 1664 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle` | 1 | **-19.62%** | -54.73% | -62.60% | -0.53 | -0.31 | 87.43% | 85 | 25.88% | 0.67 | 720 |
| 2023+ (teste) | `prioridade_roc3m_primeiro_candle` | 1 | **-11.15%** | -34.88% | -71.20% | -0.12 | -0.16 | 94.49% | 96 | 21.88% | 1.01 | 1670 |
| 2023+ (teste) | `alfabetica_primeiro_candle` | 1 | **-21.41%** | -58.28% | -67.67% | -0.53 | -0.32 | 94.71% | 102 | 26.47% | 0.66 | 1664 |
| 2023+ (teste) | `buy_and_hold_peso_igual` | 40 | **2.26%** | 8.43% | -22.19% | 0.22 | 0.10 | 100.00% | 0 | - | - | 0 |

## Retorno anual da variante principal (`roc3m_primeiro_candle`)

| Ano | Estrategia | Buy and hold peso igual |
| :--- | ---: | ---: |
| 2018 | 69.39% | 13.01% |
| 2019 | 9.42% | 39.29% |
| 2020 | -41.88% | 16.10% |
| 2021 | -30.64% | -21.47% |
| 2022 | -24.51% | -6.15% |
| 2023 | -14.74% | 11.80% |
| 2024 | -36.82% | -15.00% |
| 2025 | 5.50% | 16.13% |
| 2026 | -39.78% | -1.19% |

## Efeito da prioridade (todos os trades do sinal, sem limite de vagas)

| Grupo | Trades | Acerto | Retorno medio | Mediana | Ganho medio | Perda media | Fator lucro | Pregoes medios |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Todos | 4299 | 26.80% | 0.12% | -1.60% | 8.26% | -2.86% | 1.06 | 9.14 |
| Prioritarios (preco ou SMA20 > SMA50) | 2651 | 28.22% | 0.38% | -1.78% | 9.06% | -3.04% | 1.17 | 10.27 |
| Nao prioritarios | 1648 | 24.51% | -0.29% | -1.40% | 6.78% | -2.59% | 0.85 | 7.33 |

## Ativo isolado (100% do capital em cada ativo, 2018-01-02 a 2026-08-19)

Estrategia superou o buy and hold do proprio ativo em **15 de 40** ativos. CAGR mediano da estrategia: **-1.57%**; buy and hold mediano: **0.85%**.

| Ativo | CAGR | Retorno total | Max DD | Sharpe | Exposicao | Ordens | B&H CAGR | B&H Max DD | Excesso (retorno total) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| JHSF3 | 25.50% | 609.75% | -51.30% | 0.89 | 48.88% | 208 | 22.40% | -66.60% | 137.99% |
| WEGE3 | 13.24% | 192.30% | -43.97% | 0.65 | 50.09% | 201 | 20.98% | -50.48% | -224.85% |
| BBAS3 | 9.36% | 116.31% | -29.13% | 0.53 | 45.48% | 162 | 1.38% | -59.87% | 103.78% |
| GGBR3 | 8.57% | 103.29% | -41.83% | 0.47 | 50.65% | 228 | 10.64% | -60.82% | -35.96% |
| SUZB3 | 7.55% | 87.36% | -37.68% | 0.41 | 45.34% | 196 | 10.19% | -54.75% | -43.56% |
| SBSP3 | 7.36% | 84.53% | -49.80% | 0.43 | 51.26% | 182 | 15.84% | -54.03% | -171.08% |
| GOAU4 | 7.26% | 83.01% | -53.99% | 0.41 | 51.44% | 209 | 10.51% | -64.59% | -53.78% |
| ITUB4 | 6.05% | 66.03% | -26.23% | 0.41 | 49.86% | 214 | 4.98% | -48.25% | 13.94% |
| ITSA4 | 5.54% | 59.17% | -30.73% | 0.39 | 49.58% | 204 | 5.79% | -47.51% | -3.31% |
| CSMG3 | 5.53% | 59.15% | -59.99% | 0.35 | 51.68% | 222 | 16.62% | -54.70% | -217.48% |
| BBDC3 | 5.39% | 57.30% | -28.67% | 0.37 | 44.13% | 190 | -3.00% | -61.24% | 80.42% |
| CSNA3 | 4.97% | 51.91% | -77.34% | 0.31 | 42.40% | 210 | -7.22% | -91.72% | 99.51% |
| RENT3 | 2.79% | 26.75% | -64.04% | 0.24 | 51.58% | 194 | 5.48% | -62.65% | -31.66% |
| IRBR3 | 1.78% | 16.45% | -66.47% | 0.22 | 44.04% | 174 | -18.41% | -97.91% | 99.16% |
| VALE3 | 1.00% | 8.96% | -49.14% | 0.16 | 50.65% | 212 | 6.90% | -58.48% | -68.86% |
| CMIG4 | 0.78% | 6.91% | -53.49% | 0.15 | 49.77% | 238 | 13.12% | -50.40% | -182.65% |
| USIM5 | 0.45% | 3.94% | -78.10% | 0.17 | 44.18% | 214 | -4.49% | -83.34% | 36.68% |
| MGLU3 | -0.09% | -0.74% | -77.35% | 0.19 | 44.36% | 178 | -18.59% | -98.49% | 82.31% |
| BBSE3 | -0.21% | -1.79% | -32.98% | 0.08 | 47.95% | 202 | 2.88% | -51.92% | -29.53% |
| UGPA3 | -1.04% | -8.62% | -52.27% | 0.07 | 46.78% | 217 | -1.21% | -73.82% | 1.35% |
| KLBN11 | -2.09% | -16.68% | -44.07% | -0.03 | 43.38% | 242 | 1.34% | -42.88% | -28.88% |
| SANB11 | -2.38% | -18.79% | -55.09% | -0.02 | 42.31% | 217 | -1.37% | -54.90% | -7.53% |
| EQTL3 | -2.76% | -21.47% | -42.80% | -0.07 | 50.09% | 226 | 11.95% | -40.95% | -186.25% |
| ABEV3 | -3.24% | -24.74% | -35.93% | -0.11 | 42.50% | 190 | -4.18% | -55.40% | 6.05% |
| EGIE3 | -3.64% | -27.40% | -45.43% | -0.16 | 45.67% | 244 | 3.56% | -35.90% | -62.60% |
| BRKM5 | -4.06% | -30.05% | -59.15% | 0.01 | 36.95% | 176 | -21.61% | -92.75% | 57.71% |
| TAEE11 | -4.94% | -35.38% | -47.03% | -0.29 | 47.39% | 250 | 6.63% | -30.49% | -109.38% |
| PETR4 | -5.17% | -36.74% | -71.91% | -0.07 | 52.05% | 231 | 11.99% | -63.50% | -202.44% |
| TUPY3 | -5.94% | -41.03% | -60.56% | -0.13 | 41.15% | 214 | -2.71% | -63.83% | -19.90% |
| CSAN3 | -6.20% | -42.42% | -59.29% | -0.16 | 41.85% | 204 | -12.26% | -88.48% | 25.24% |
| RADL3 | -6.86% | -45.82% | -71.58% | -0.21 | 47.81% | 228 | 0.23% | -55.53% | -47.84% |
| MRVE3 | -6.94% | -46.22% | -71.25% | -0.10 | 39.47% | 211 | -12.20% | -81.38% | 21.24% |
| LREN3 | -8.29% | -52.61% | -64.89% | -0.21 | 43.43% | 240 | -10.08% | -78.77% | 7.39% |
| FLRY3 | -8.92% | -55.33% | -65.47% | -0.41 | 41.66% | 215 | -4.94% | -66.27% | -19.94% |
| BRAP4 | -8.98% | -55.59% | -77.85% | -0.11 | 46.46% | 220 | -2.69% | -78.61% | -34.64% |
| MULT3 | -9.75% | -58.72% | -72.43% | -0.40 | 46.27% | 238 | 1.04% | -53.66% | -68.02% |
| HYPE3 | -13.82% | -72.29% | -74.24% | -0.65 | 43.57% | 244 | -6.02% | -66.88% | -30.83% |
| RAIL3 | -14.34% | -73.70% | -78.88% | -0.62 | 46.46% | 254 | 0.66% | -54.08% | -79.57% |
| CVCB3 | -20.56% | -86.28% | -89.36% | -0.43 | 37.65% | 233 | -32.20% | -98.01% | 10.23% |
| QUAL3 | -33.05% | -96.86% | -98.28% | -1.10 | 38.12% | 275 | -28.87% | -96.96% | -2.15% |

Resultados retrospectivos: sem otimizacao de parametros, mas com universo fixo (vies de sobrevivencia), sem impostos e sem proventos. Nao representam expectativa de dinheiro real.

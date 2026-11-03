# RSI + WMA Heikin Ashi - backtest sem gerenciamento de carteira

## Regras testadas

- **Compra**: RSI(14) do fechamento acima de 50 e WMA(20) do fechamento Heikin Ashi subindo (WMA[t] > WMA[t-1]), com a WMA(20) Heikin Ashi ACIMA da SMA200 do fechamento.
- **Venda**: basta um dos dois: RSI abaixo de 50 ou WMA Heikin Ashi caindo (WMA[t] < WMA[t-1]). A SMA200 so filtra a compra; a WMA ou o preco cair abaixo dela nao vende.
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
- `roc3m_positivo_primeiro_candle_filtro_fechamento_sma200`: Comparacao: fechamento acima da SMA200 (regra anterior) no lugar da WMA20 HA.
- `roc3m_positivo_primeiro_candle_filtro_fechamento_sma50`: Comparacao: fechamento acima da SMA50 no lugar da WMA20 HA acima da SMA200.
- `roc3m_positivo_primeiro_candle_sem_filtro_sma`: Comparacao: regra principal sem filtro de media na compra.
- `roc3m_positivo_primeiro_candle_sem_custos`: Diagnostico: regra principal com custos e slippage zerados (mostra quanto os custos pesam).
- `buy_and_hold_peso_igual`: Referencia: as 40 acoes compradas em peso igual (com fracoes de acao), sem rebalancear.

## Carteira seguindo o sinal

| Periodo | Variante | Vagas | CAGR | Retorno total | Max DD | Sharpe | Calmar | Exposicao | Trades | Acerto | Fator lucro | Sinais descartados |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018+ | `roc3m_positivo_primeiro_candle` | 1 | **-1.28%** | -10.53% | -82.83% | 0.13 | -0.02 | 88.77% | 153 | 29.41% | 1.11 | 1674 |
| 2018+ | `roc3m_primeiro_candle` | 1 | **3.42%** | 33.68% | -75.34% | 0.27 | 0.05 | 90.59% | 162 | 29.01% | 1.24 | 2153 |
| 2018+ | `alfabetica_roc3m_positivo_primeiro_candle` | 1 | **0.42%** | 3.71% | -69.75% | 0.17 | 0.01 | 87.93% | 153 | 31.37% | 1.14 | 1674 |
| 2018+ | `roc3m_positivo_primeiro_candle_filtro_fechamento_sma200` | 1 | **-9.09%** | -56.05% | -87.13% | -0.16 | -0.10 | 87.19% | 176 | 28.41% | 0.92 | 1752 |
| 2018+ | `roc3m_positivo_primeiro_candle_filtro_fechamento_sma50` | 1 | **-3.59%** | -27.07% | -80.96% | 0.05 | -0.04 | 86.81% | 161 | 29.81% | 1.06 | 1781 |
| 2018+ | `roc3m_positivo_primeiro_candle_sem_filtro_sma` | 1 | **-6.76%** | -45.34% | -85.27% | -0.05 | -0.08 | 86.81% | 179 | 25.14% | 0.98 | 1906 |
| 2018+ | `roc3m_positivo_primeiro_candle_sem_custos` | 1 | **3.53%** | 34.94% | -77.79% | 0.27 | 0.05 | 88.77% | 153 | 30.72% | 1.22 | 1674 |
| 2018+ | `buy_and_hold_peso_igual` | 40 | **4.53%** | 46.53% | -48.83% | 0.31 | 0.09 | 100.00% | 0 | - | - | 0 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle` | 1 | **-12.26%** | -37.79% | -47.90% | -0.24 | -0.26 | 88.42% | 68 | 30.88% | 0.81 | 618 |
| 2023+ (teste) | `roc3m_primeiro_candle` | 1 | **-13.45%** | -40.78% | -45.88% | -0.27 | -0.29 | 89.97% | 76 | 28.95% | 0.78 | 813 |
| 2023+ (teste) | `alfabetica_roc3m_positivo_primeiro_candle` | 1 | **-0.07%** | -0.27% | -30.66% | 0.15 | -0.00 | 87.98% | 64 | 32.81% | 1.11 | 622 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle_filtro_fechamento_sma200` | 1 | **-1.30%** | -4.64% | -33.47% | 0.11 | -0.04 | 87.65% | 72 | 31.94% | 1.05 | 663 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle_filtro_fechamento_sma50` | 1 | **-13.37%** | -40.60% | -52.40% | -0.29 | -0.26 | 87.65% | 74 | 31.08% | 0.79 | 659 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle_sem_filtro_sma` | 1 | **-19.62%** | -54.73% | -62.60% | -0.53 | -0.31 | 87.43% | 85 | 25.88% | 0.67 | 720 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle_sem_custos` | 1 | **-7.76%** | -25.39% | -40.11% | -0.09 | -0.19 | 88.42% | 68 | 32.35% | 0.90 | 618 |
| 2023+ (teste) | `buy_and_hold_peso_igual` | 40 | **2.26%** | 8.46% | -23.22% | 0.22 | 0.10 | 100.00% | 0 | - | - | 0 |

## Retorno anual da variante principal (`roc3m_positivo_primeiro_candle`)

| Ano | Estrategia | Buy and hold peso igual |
| :--- | ---: | ---: |
| 2018 | 92.74% | 17.06% |
| 2019 | 117.29% | 40.94% |
| 2020 | -16.77% | 11.34% |
| 2021 | -30.94% | -21.88% |
| 2022 | -44.15% | -6.31% |
| 2023 | -13.47% | 12.16% |
| 2024 | -16.86% | -15.50% |
| 2025 | -1.95% | 16.46% |
| 2026 | -5.64% | -1.25% |

## Todos os trades do sinal (mesma regra de entrada, sem limite de vagas)

| Grupo | Trades | Acerto | Retorno medio | Mediana | Ganho medio | Perda media | Fator lucro | Pregoes medios |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Todos | 1825 | 28.38% | 0.25% | -1.73% | 8.68% | -3.09% | 1.11 | 10.80 |
| Prioritarios (preco ou SMA20 > SMA50) | 1611 | 28.86% | 0.21% | -1.82% | 8.65% | -3.21% | 1.09 | 11.21 |
| Nao prioritarios | 214 | 24.77% | 0.54% | -1.33% | 8.90% | -2.21% | 1.33 | 7.69 |

## Ativo isolado (100% do capital em cada ativo, entrada so com ROC 3m positivo, 2018-01-02 a 2026-08-19)

Estrategia superou o buy and hold do proprio ativo em **18 de 40** ativos. CAGR mediano da estrategia: **-1.16%**; buy and hold mediano: **0.85%**.

| Ativo | CAGR | Retorno total | Max DD | Sharpe | Exposicao | Ordens | B&H CAGR | B&H Max DD | Excesso (retorno total) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| JHSF3 | 17.66% | 306.88% | -55.73% | 0.80 | 29.17% | 110 | 22.40% | -66.60% | -164.87% |
| GGBR3 | 11.80% | 161.85% | -34.03% | 0.72 | 27.59% | 86 | 10.64% | -60.82% | 22.60% |
| CSNA3 | 10.75% | 141.31% | -28.44% | 0.58 | 18.69% | 68 | -7.22% | -91.72% | 188.91% |
| GOAU4 | 10.69% | 140.25% | -24.67% | 0.67 | 26.23% | 83 | 10.51% | -64.59% | 3.46% |
| USIM5 | 9.91% | 125.92% | -29.87% | 0.55 | 20.50% | 78 | -4.49% | -83.34% | 158.66% |
| CSMG3 | 8.78% | 106.64% | -51.72% | 0.59 | 32.11% | 100 | 16.62% | -54.70% | -169.98% |
| WEGE3 | 8.62% | 104.03% | -25.84% | 0.55 | 28.05% | 105 | 20.98% | -50.48% | -313.11% |
| VALE3 | 6.81% | 76.57% | -38.24% | 0.50 | 27.87% | 80 | 6.90% | -58.48% | -1.26% |
| SBSP3 | 6.25% | 68.74% | -36.27% | 0.44 | 32.15% | 100 | 15.84% | -54.03% | -186.87% |
| UGPA3 | 4.69% | 48.45% | -19.97% | 0.41 | 18.73% | 63 | -1.21% | -73.82% | 58.43% |
| CSAN3 | 2.86% | 27.51% | -22.76% | 0.28 | 20.04% | 72 | -12.26% | -88.48% | 95.16% |
| RENT3 | 2.75% | 26.33% | -43.73% | 0.24 | 32.90% | 102 | 5.48% | -62.65% | -32.09% |
| BRAP4 | 2.18% | 20.49% | -41.54% | 0.22 | 24.14% | 84 | -2.69% | -78.61% | 41.43% |
| SANB11 | 1.98% | 18.41% | -22.67% | 0.22 | 16.82% | 66 | -1.37% | -54.90% | 29.67% |
| RADL3 | 1.65% | 15.18% | -53.18% | 0.18 | 28.42% | 102 | 0.23% | -55.53% | 13.16% |
| BBDC3 | 0.56% | 4.92% | -25.08% | 0.11 | 21.71% | 84 | -3.00% | -61.24% | 28.04% |
| MRVE3 | 0.50% | 4.38% | -45.96% | 0.11 | 17.43% | 78 | -12.20% | -81.38% | 71.84% |
| TUPY3 | 0.42% | 3.65% | -43.65% | 0.10 | 19.71% | 78 | -2.71% | -63.83% | 24.78% |
| IRBR3 | -1.12% | -9.23% | -53.89% | 0.03 | 21.06% | 74 | -18.41% | -97.91% | 73.48% |
| BBSE3 | -1.14% | -9.38% | -32.35% | -0.01 | 27.59% | 100 | 2.88% | -51.92% | -37.13% |
| TAEE11 | -1.19% | -9.79% | -29.77% | -0.07 | 23.86% | 112 | 6.63% | -30.49% | -83.79% |
| BRKM5 | -1.45% | -11.85% | -46.12% | 0.02 | 16.26% | 58 | -21.61% | -92.75% | 75.91% |
| ITSA4 | -1.78% | -14.34% | -29.67% | -0.08 | 23.86% | 98 | 5.79% | -47.51% | -76.81% |
| BBAS3 | -2.39% | -18.83% | -44.48% | -0.10 | 22.41% | 70 | 1.38% | -59.87% | -31.36% |
| KLBN11 | -2.97% | -22.93% | -33.89% | -0.23 | 16.59% | 78 | 1.34% | -42.88% | -35.13% |
| EGIE3 | -3.14% | -24.05% | -39.99% | -0.20 | 25.49% | 124 | 3.56% | -35.90% | -59.24% |
| ITUB4 | -3.60% | -27.14% | -43.13% | -0.23 | 25.02% | 120 | 4.98% | -48.25% | -79.23% |
| CMIG4 | -3.98% | -29.59% | -42.48% | -0.18 | 26.28% | 114 | 13.12% | -50.40% | -219.15% |
| MGLU3 | -4.81% | -34.63% | -69.20% | -0.08 | 24.04% | 84 | -18.59% | -98.49% | 48.41% |
| QUAL3 | -4.87% | -34.97% | -64.57% | -0.18 | 14.86% | 72 | -28.87% | -96.96% | 59.74% |
| SUZB3 | -4.90% | -35.17% | -42.38% | -0.28 | 19.01% | 82 | 10.19% | -54.75% | -166.09% |
| ABEV3 | -5.17% | -36.74% | -43.50% | -0.42 | 20.46% | 88 | -4.18% | -55.40% | -5.96% |
| EQTL3 | -5.91% | -40.90% | -50.35% | -0.37 | 29.31% | 134 | 11.95% | -40.95% | -205.69% |
| FLRY3 | -6.06% | -41.67% | -48.80% | -0.54 | 15.42% | 74 | -4.94% | -66.27% | -6.29% |
| MULT3 | -7.32% | -48.08% | -61.34% | -0.53 | 22.51% | 116 | 1.04% | -53.66% | -57.39% |
| CVCB3 | -7.94% | -51.00% | -63.02% | -0.34 | 13.42% | 64 | -32.20% | -98.01% | 45.50% |
| PETR4 | -8.71% | -54.46% | -71.30% | -0.37 | 22.74% | 110 | 11.99% | -63.50% | -220.15% |
| LREN3 | -8.91% | -55.31% | -63.24% | -0.60 | 20.27% | 110 | -10.08% | -78.77% | 4.69% |
| HYPE3 | -9.23% | -56.63% | -57.21% | -0.66 | 21.76% | 94 | -6.02% | -66.88% | -15.16% |
| RAIL3 | -11.83% | -66.25% | -68.88% | -0.77 | 25.07% | 134 | 0.66% | -54.08% | -72.11% |

Resultados retrospectivos: sem otimizacao de parametros, mas com universo fixo (vies de sobrevivencia), sem impostos e sem proventos. Nao representam expectativa de dinheiro real.

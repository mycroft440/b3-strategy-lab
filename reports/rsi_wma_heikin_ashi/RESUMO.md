# RSI + WMA Heikin Ashi - backtest sem gerenciamento de carteira

## Regras testadas

- **Compra**: RSI(14) do fechamento acima de 50 e WMA(20) do fechamento Heikin Ashi subindo (WMA[t] > WMA[t-1]), com o fechamento NAO abaixo da SMA50 (fechamento >= SMA).
- **Venda**: basta um dos dois: RSI abaixo de 50 ou WMA Heikin Ashi caindo (WMA[t] < WMA[t-1]). A SMA so filtra a compra; o preco cair abaixo dela nao vende.
- **Selecao**: somente 1 acao por vez. A entrada so ocorre na abertura seguinte ao PRIMEIRO candle do sinal; se a vaga estiver ocupada, o sinal e descartado (nunca ha entrada tardia). So entram sinais novos com ROC de 3 meses (63 pregoes) acima de 0; entre eles, compra-se o de maior ROC. Sem candidato, a carteira fica em caixa. A posicao fica ate o sinal de venda (o ROC so e exigido na entrada).
- **Prioridade** (fechamento OU SMA20 acima da SMA50): ficou redundante, pois a compra ja exige fechamento >= SMA50.
- "RSI acima de 0" foi lido como RSI centralizado (RSI - 50 > 0), ou seja RSI > 50.
- Sinal no fechamento, execucao na abertura seguinte; custos 3.2 bps + slippage 10.0 bps por ordem; lote de 1 acao.
- Universo: 40 acoes (`fixed_research_universe_40_2018`), candles ajustados por splits, sem dividendos/JCP. O universo tem vies de sobrevivencia declarado.
- **Sem gerenciamento**: sem rebalanceamento periodico e sem alvo de volatilidade. Todo o patrimonio vai para a acao escolhida e fica parado ate o sinal de venda.

## Variantes

- `roc3m_positivo_primeiro_candle`: PRINCIPAL. Somente sinais no primeiro candle com ROC de 63 pregoes acima de 0; entre eles, o maior ROC.
- `roc3m_primeiro_candle`: Igual a principal, sem exigir ROC positivo (maior ROC mesmo se negativo).
- `alfabetica_roc3m_positivo_primeiro_candle`: Igual a principal, mas sem ordenar pelo ROC: empate pela ordem alfabetica (mede o efeito do ranking).
- `roc3m_positivo_primeiro_candle_sem_filtro_sma`: Comparacao: regra principal sem o filtro de fechamento >= SMA50 (regra anterior).
- `roc3m_positivo_primeiro_candle_sem_custos`: Diagnostico: regra principal com custos e slippage zerados (mostra quanto os custos pesam).
- `buy_and_hold_peso_igual`: Referencia: as 40 acoes compradas em peso igual (com fracoes de acao), sem rebalancear.

## Carteira seguindo o sinal

| Periodo | Variante | Vagas | CAGR | Retorno total | Max DD | Sharpe | Calmar | Exposicao | Trades | Acerto | Fator lucro | Sinais descartados |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018+ | `roc3m_positivo_primeiro_candle` | 1 | **-3.59%** | -27.07% | -80.96% | 0.05 | -0.04 | 86.81% | 161 | 29.81% | 1.06 | 1781 |
| 2018+ | `roc3m_primeiro_candle` | 1 | **-19.08%** | -83.90% | -88.44% | -0.43 | -0.22 | 92.40% | 204 | 25.98% | 0.74 | 3119 |
| 2018+ | `alfabetica_roc3m_positivo_primeiro_candle` | 1 | **-8.31%** | -52.70% | -79.44% | -0.14 | -0.10 | 84.76% | 167 | 27.54% | 0.89 | 1775 |
| 2018+ | `roc3m_positivo_primeiro_candle_sem_filtro_sma` | 1 | **-6.76%** | -45.34% | -85.27% | -0.05 | -0.08 | 86.81% | 179 | 25.14% | 0.98 | 1906 |
| 2018+ | `roc3m_positivo_primeiro_candle_sem_custos` | 1 | **1.25%** | 11.28% | -75.97% | 0.20 | 0.02 | 86.81% | 161 | 31.06% | 1.17 | 1781 |
| 2018+ | `buy_and_hold_peso_igual` | 40 | **4.53%** | 46.53% | -48.83% | 0.31 | 0.09 | 100.00% | 0 | - | - | 0 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle` | 1 | **-13.37%** | -40.60% | -52.40% | -0.29 | -0.26 | 87.65% | 74 | 31.08% | 0.79 | 659 |
| 2023+ (teste) | `roc3m_primeiro_candle` | 1 | **-31.88%** | -75.16% | -77.75% | -0.99 | -0.41 | 92.17% | 95 | 18.95% | 0.49 | 1271 |
| 2023+ (teste) | `alfabetica_roc3m_positivo_primeiro_candle` | 1 | **-8.62%** | -27.88% | -48.11% | -0.18 | -0.18 | 85.23% | 75 | 26.67% | 0.85 | 658 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle_sem_filtro_sma` | 1 | **-19.62%** | -54.73% | -62.60% | -0.53 | -0.31 | 87.43% | 85 | 25.88% | 0.67 | 720 |
| 2023+ (teste) | `roc3m_positivo_primeiro_candle_sem_custos` | 1 | **-8.53%** | -27.65% | -44.79% | -0.12 | -0.19 | 87.65% | 74 | 32.43% | 0.89 | 659 |
| 2023+ (teste) | `buy_and_hold_peso_igual` | 40 | **2.26%** | 8.46% | -23.22% | 0.22 | 0.10 | 100.00% | 0 | - | - | 0 |

## Retorno anual da variante principal (`roc3m_positivo_primeiro_candle`)

| Ano | Estrategia | Buy and hold peso igual |
| :--- | ---: | ---: |
| 2018 | 8.17% | 17.06% |
| 2019 | 85.62% | 40.94% |
| 2020 | 12.52% | 11.34% |
| 2021 | -1.17% | -21.88% |
| 2022 | -48.55% | -6.31% |
| 2023 | -10.11% | 12.16% |
| 2024 | -18.83% | -15.50% |
| 2025 | -16.13% | 16.46% |
| 2026 | 3.74% | -1.25% |

## Todos os trades do sinal (mesma regra de entrada, sem limite de vagas)

Com o filtro de fechamento >= SMA50 na compra, todo sinal ja atende a prioridade (preco ou SMA20 acima da SMA50); por isso a prioridade deixou de diferenciar sinais.

| Grupo | Trades | Acerto | Retorno medio | Mediana | Ganho medio | Perda media | Fator lucro | Pregoes medios |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Todos | 1940 | 28.45% | 0.29% | -1.80% | 8.77% | -3.08% | 1.13 | 10.63 |

## Ativo isolado (100% do capital em cada ativo, entrada so com ROC 3m positivo, 2018-01-02 a 2026-08-19)

Estrategia superou o buy and hold do proprio ativo em **18 de 40** ativos. CAGR mediano da estrategia: **-0.27%**; buy and hold mediano: **0.85%**.

| Ativo | CAGR | Retorno total | Max DD | Sharpe | Exposicao | Ordens | B&H CAGR | B&H Max DD | Excesso (retorno total) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| JHSF3 | 19.53% | 365.94% | -38.49% | 0.91 | 27.07% | 98 | 22.40% | -66.60% | -105.81% |
| CSNA3 | 12.32% | 172.40% | -41.55% | 0.63 | 19.99% | 84 | -7.22% | -91.72% | 220.01% |
| SBSP3 | 8.92% | 108.93% | -29.72% | 0.57 | 36.49% | 100 | 15.84% | -54.03% | -146.69% |
| CSMG3 | 8.28% | 98.62% | -57.73% | 0.55 | 30.34% | 102 | 16.62% | -54.70% | -178.00% |
| BRAP4 | 7.31% | 83.80% | -20.07% | 0.53 | 25.91% | 82 | -2.69% | -78.61% | 104.75% |
| WEGE3 | 6.91% | 77.95% | -33.69% | 0.47 | 26.51% | 94 | 20.98% | -50.48% | -339.20% |
| BBDC3 | 6.34% | 70.00% | -16.60% | 0.49 | 23.63% | 76 | -3.00% | -61.24% | 93.12% |
| VALE3 | 5.46% | 58.17% | -38.70% | 0.41 | 29.54% | 100 | 6.90% | -58.48% | -19.66% |
| MRVE3 | 4.22% | 42.80% | -50.76% | 0.30 | 21.71% | 90 | -12.20% | -81.38% | 110.26% |
| GOAU4 | 3.90% | 39.08% | -34.79% | 0.32 | 26.28% | 97 | 10.51% | -64.59% | -97.70% |
| USIM5 | 3.70% | 36.82% | -54.00% | 0.27 | 24.32% | 98 | -4.49% | -83.34% | 69.56% |
| GGBR3 | 3.22% | 31.48% | -32.88% | 0.28 | 25.58% | 102 | 10.64% | -60.82% | -107.76% |
| RADL3 | 2.75% | 26.33% | -56.39% | 0.24 | 31.41% | 108 | 0.23% | -55.53% | 24.31% |
| BRKM5 | 2.50% | 23.79% | -38.72% | 0.22 | 17.85% | 62 | -21.61% | -92.75% | 111.55% |
| TUPY3 | 2.20% | 20.63% | -33.11% | 0.21 | 18.97% | 74 | -2.71% | -63.83% | 41.76% |
| CSAN3 | 2.03% | 18.92% | -36.93% | 0.21 | 22.46% | 90 | -12.26% | -88.48% | 86.57% |
| RENT3 | 1.84% | 17.00% | -41.57% | 0.19 | 32.39% | 98 | 5.48% | -62.65% | -41.42% |
| SANB11 | 1.81% | 16.72% | -27.02% | 0.20 | 20.13% | 91 | -1.37% | -54.90% | 27.98% |
| ITSA4 | 0.90% | 8.00% | -28.37% | 0.13 | 23.07% | 92 | 5.79% | -47.51% | -54.47% |
| BBAS3 | 0.35% | 3.10% | -38.01% | 0.10 | 20.32% | 64 | 1.38% | -59.87% | -9.42% |
| UGPA3 | -0.89% | -7.38% | -53.77% | 0.03 | 22.09% | 87 | -1.21% | -73.82% | 2.59% |
| ITUB4 | -0.97% | -8.08% | -32.78% | -0.02 | 24.28% | 104 | 4.98% | -48.25% | -60.16% |
| EGIE3 | -1.31% | -10.77% | -33.63% | -0.04 | 26.75% | 130 | 3.56% | -35.90% | -45.96% |
| BBSE3 | -1.32% | -10.80% | -27.73% | -0.03 | 25.91% | 98 | 2.88% | -51.92% | -38.55% |
| CMIG4 | -1.57% | -12.74% | -56.16% | -0.01 | 26.33% | 118 | 13.12% | -50.40% | -202.31% |
| ABEV3 | -2.34% | -18.48% | -33.99% | -0.16 | 17.94% | 82 | -4.18% | -55.40% | 12.30% |
| TAEE11 | -2.48% | -19.51% | -34.71% | -0.17 | 27.35% | 138 | 6.63% | -30.49% | -93.51% |
| EQTL3 | -2.66% | -20.75% | -40.65% | -0.14 | 27.07% | 122 | 11.95% | -40.95% | -185.54% |
| MULT3 | -2.91% | -22.49% | -51.33% | -0.14 | 26.79% | 116 | 1.04% | -53.66% | -31.80% |
| SUZB3 | -3.05% | -23.48% | -38.24% | -0.11 | 21.58% | 88 | 10.19% | -54.75% | -154.40% |
| IRBR3 | -3.78% | -28.28% | -57.02% | -0.16 | 20.92% | 80 | -18.41% | -97.91% | 54.43% |
| MGLU3 | -5.42% | -38.15% | -71.85% | -0.13 | 25.68% | 90 | -18.59% | -98.49% | 44.89% |
| HYPE3 | -5.95% | -41.09% | -48.79% | -0.36 | 21.95% | 100 | -6.02% | -66.88% | 0.38% |
| FLRY3 | -6.67% | -44.87% | -50.41% | -0.49 | 20.74% | 88 | -4.94% | -66.27% | -9.49% |
| LREN3 | -7.14% | -47.24% | -63.09% | -0.35 | 24.14% | 122 | -10.08% | -78.77% | 12.76% |
| KLBN11 | -8.43% | -53.23% | -56.87% | -0.85 | 12.26% | 82 | 1.34% | -42.88% | -65.43% |
| QUAL3 | -8.78% | -54.76% | -76.94% | -0.30 | 20.13% | 102 | -28.87% | -96.96% | 39.94% |
| RAIL3 | -9.45% | -57.53% | -63.55% | -0.56 | 27.96% | 130 | 0.66% | -54.08% | -63.40% |
| PETR4 | -11.15% | -63.95% | -78.99% | -0.45 | 27.73% | 130 | 11.99% | -63.50% | -229.64% |
| CVCB3 | -11.26% | -64.33% | -67.13% | -0.56 | 11.00% | 72 | -32.20% | -98.01% | 32.18% |

Resultados retrospectivos: sem otimizacao de parametros, mas com universo fixo (vies de sobrevivencia), sem impostos e sem proventos. Nao representam expectativa de dinheiro real.

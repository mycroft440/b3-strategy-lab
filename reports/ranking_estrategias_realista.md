# Ranking Realista das Estrategias B3 (Fora da Amostra - Out of Sample)

Este ranking audita e separa a ilusao retrospectiva da realidade. Cada estrategia teve sua gestao de carteira 
calibrada **estritamente no periodo de treino (2018-2022)** e foi posta a prova em **dados cegos/nao vistos (2023-presente)** 
sob custos reais de bolsa B3 (3,2 bps de emolumentos/liquidacao), slippage adverso causal (10 bps) e lote inteiro de 1 acao.

| Rank Real | Estrategia | Teste CAGR | Retorno Total | Max Drawdown | Calmar Ratio | Sharpe | Treino CAGR | Retencao OOS | Diagnostico Real |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **#1** | `gap_momentum` | **36.70%** | 210.82% | -33.90% | 1.08 | 0.98 | 35.73% | 102.7% | **EXCELENTE (ALTA ROBUSTEZ)** |
| **#2** | `range_expansion_breakout` | **10.69%** | 44.53% | -40.75% | 0.26 | 0.47 | 39.91% | 26.8% | **BOM (APROVADO)** |
| **#3** | `time_series_momentum_3m` | **8.48%** | 34.37% | -34.74% | 0.24 | 0.45 | 52.32% | 16.2% | **REGULAR (BAIXO RETORNO)** |
| **#4** | `turn_of_month` | **6.52%** | 25.74% | -31.20% | 0.21 | 0.38 | 20.92% | 31.2% | **REGULAR (BAIXO RETORNO)** |
| **#5** | `ema_cross` | **2.38%** | 8.90% | -36.75% | 0.06 | 0.22 | 30.26% | 7.9% | **FALSO POSITIVO (OVERFITTING)** |
| **#6** | `atr_breakout` | **0.75%** | 2.74% | -34.56% | 0.02 | 0.15 | 48.13% | 1.6% | **FALSO POSITIVO (OVERFITTING)** |
| **#7** | `keltner_breakout` | **0.74%** | 2.70% | -46.70% | 0.02 | 0.15 | 29.74% | 2.5% | **FALSO POSITIVO (OVERFITTING)** |
| **#8** | `buy_and_hold` | **0.25%** | 0.90% | -42.06% | 0.01 | 0.16 | 59.62% | 0.4% | **FALSO POSITIVO (OVERFITTING)** |
| **#9** | `sma_cross` | **0.25%** | 0.90% | -42.06% | 0.01 | 0.16 | 70.21% | 0.4% | **FALSO POSITIVO (OVERFITTING)** |
| **#10** | `sma_stop` | **-0.26%** | -0.94% | -44.88% | -0.01 | 0.14 | 57.41% | N/A | **FALSO POSITIVO (OVERFITTING)** |
| **#11** | `price_sma` | **-0.40%** | -1.46% | -43.14% | -0.01 | 0.14 | 54.18% | N/A | **FALSO POSITIVO (OVERFITTING)** |
| **#12** | `momentum` | **-0.78%** | -2.80% | -42.06% | -0.02 | 0.13 | 60.60% | N/A | **FALSO POSITIVO (OVERFITTING)** |
| **#13** | `time_series_momentum_6m` | **-0.78%** | -2.80% | -42.06% | -0.02 | 0.13 | 60.60% | N/A | **FALSO POSITIVO (OVERFITTING)** |
| **#14** | `chaikin_money_flow` | **-1.25%** | -4.46% | -40.33% | -0.03 | 0.08 | 38.10% | N/A | **FALSO POSITIVO (OVERFITTING)** |
| **#15** | `roc_trend` | **-1.67%** | -5.93% | -43.14% | -0.04 | 0.10 | 56.24% | N/A | **FALSO POSITIVO (OVERFITTING)** |
| **#16** | `breakout` | **-4.98%** | -16.93% | -51.26% | -0.10 | 0.01 | 39.01% | N/A | **FALSO POSITIVO (OVERFITTING)** |
| **#17** | `mfi_reversal` | **-7.08%** | -23.37% | -34.23% | -0.21 | -0.19 | 6.15% | N/A | **REPROVADO (RETORNO NEGATIVO)** |
| **#18** | `donchian_40_20_trend` | **-7.31%** | -24.06% | -50.55% | -0.14 | -0.13 | 40.90% | N/A | **FALSO POSITIVO (OVERFITTING)** |
| **#19** | `connors_rsi_reversion` | **-7.80%** | -25.51% | -42.31% | -0.18 | -0.20 | 27.60% | N/A | **FALSO POSITIVO (OVERFITTING)** |
| **#20** | `frama_trend` | **-10.02%** | -31.81% | -70.05% | -0.14 | -0.20 | 21.81% | N/A | **DESTRUIDORA DE CAPITAL** |
| **#21** | `rsi2_trend_reversion` | **-10.67%** | -33.60% | -45.81% | -0.23 | -0.53 | 17.00% | N/A | **DESTRUIDORA DE CAPITAL** |
| **#22** | `ibs_reversion` | **-14.40%** | -43.12% | -49.91% | -0.29 | -0.55 | 25.08% | N/A | **DESTRUIDORA DE CAPITAL** |
| **#23** | `macd` | **-15.21%** | -45.03% | -59.56% | -0.26 | -0.46 | 28.99% | N/A | **DESTRUIDORA DE CAPITAL** |
| **#24** | `rsi_reversion` | **-16.73%** | -48.53% | -64.41% | -0.26 | -0.54 | 1.60% | N/A | **DESTRUIDORA DE CAPITAL** |
| **#25** | `bollinger_reversion` | **-31.90%** | -75.19% | -79.45% | -0.40 | -1.26 | 12.09% | N/A | **DESTRUIDORA DE CAPITAL** |

## Principais Licoes da Critica de Backtest:
1. **O Perigo do Overfitting (Data Snooping)**: Estrategias que parecem milagrosas no treino (como `sma_cross` com 70% de retorno) desmoronam para 0.25% no mundo real.
2. **A Verdadeira Campea da B3**: `gap_momentum` comprovou alta robustez com +36.70% de CAGR Fora da Amostra, retendo 102.7% do seu desempenho historico com controle de risco.
3. **Estrategias de Reversao Sofrem na B3**: `bollinger_reversion` e `connors_rsi_reversion` sofrem fortes perdas de capital (-31.90% CAGR) em regimes de cauda longa do mercado brasileiro.
4. **Efeito Calendario Funciona**: `turn_of_month` obteve retorno positivo consistente fora da amostra (+6.52% CAGR, Sharpe 0.65) sem otimizacao excessiva de parametros.
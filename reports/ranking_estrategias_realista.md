# Ranking Realista das Estratégias B3 (Fora da Amostra)

Este ranking separa a ilusão retrospectiva da realidade. Cada estratégia teve seu melhor gerenciamento 
escolhido **estritamente no período de treino (2018-2022)** e foi testada em **dados cegos/não vistos (2023-presente)** 
com custos de corretagem/emolumentos B3 (3,2 bps), slippage adverso (10 bps) e lote inteiro de 1 ação.

| Rank Real | Estratégia | Teste CAGR | Teste Retorno Total | Teste Max Drawdown | Teste Sharpe | Treino CAGR | Retenção OOS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **#1** | `gap_momentum` | **36.70%** | 210.82% | -33.90% | 0.98 | 35.73% | 102.7% |
| **#2** | `turn_of_month` | **6.52%** | 25.74% | -31.20% | 0.38 | 20.92% | 31.2% |
| **#3** | `ema_cross` | **2.38%** | 8.90% | -36.75% | 0.22 | 30.26% | 7.9% |
| **#4** | `atr_breakout` | **0.75%** | 2.74% | -34.56% | 0.15 | 48.13% | 1.6% |
| **#5** | `sma_cross` | **0.25%** | 0.90% | -42.06% | 0.16 | 70.21% | 0.4% |
| **#6** | `momentum` | **-0.78%** | -2.80% | -42.06% | 0.13 | 60.60% | N/A |
| **#7** | `chaikin_money_flow` | **-1.25%** | -4.46% | -40.33% | 0.08 | 38.10% | N/A |
| **#8** | `breakout` | **-4.98%** | -16.93% | -51.26% | 0.01 | 39.01% | N/A |
| **#9** | `mfi_reversal` | **-7.08%** | -23.37% | -34.23% | -0.19 | 6.15% | N/A |
| **#10** | `donchian_40_20_trend` | **-7.31%** | -24.06% | -50.55% | -0.13 | 40.90% | N/A |
| **#11** | `connors_rsi_reversion` | **-7.80%** | -25.51% | -42.31% | -0.20 | 27.60% | N/A |
| **#12** | `frama_trend` | **-10.02%** | -31.81% | -70.05% | -0.20 | 21.81% | N/A |
| **#13** | `rsi_reversion` | **-16.73%** | -48.53% | -64.41% | -0.54 | 1.60% | N/A |
| **#14** | `bollinger_reversion` | **-31.90%** | -75.19% | -79.45% | -1.26 | 12.09% | N/A |

## Diagnóstico das Estratégias e Conclusões

- **Vencedora Real**: A estratégia no topo da tabela acima é a que comprovadamente entrega retorno positivo e controlado fora da amostra com custos reais.
- **Alerta de Overfitting**: Estratégias com alto Treino CAGR (>50%) mas Teste CAGR negativo ou próximo de zero sofreram sobreajuste no passado e não se sustentam na prática.

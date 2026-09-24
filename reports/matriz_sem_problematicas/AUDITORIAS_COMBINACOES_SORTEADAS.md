# Auditoria de combinações sorteadas (24/09/2026)

Duas combinações da [matriz sem ações problemáticas](REVISAO.md) foram sorteadas e
conferidas de ponta a ponta: R$ 1.000 de 2018-01-02 a 2026-08-19, custos de 3,2 bps +
slippage de 10 bps, universo point-in-time filtrado
([`universo_filtrado.json`](universo_filtrado.json)).

| # | Sorteio | Combinação | Resultado | Veredito |
| :--- | :--- | :--- | ---: | :--- |
| 1 | 1% pior (1.190 combinações), semente 20260924 | `cci_trend_14_m100_100_sma100` + `top1_momentum_lb126_skip21_trend0_vol63_equal_weekly_abs_cap1_adjusted` | R$ 59,78 → **R$ 664,91** depois da correção | **Erro no sinal, corrigido** (`19ddaf6`) |
| 2 | Todas, exceto `cci_trend` (116.632), semente 20260925 | `macd_12_26_9_trend200` + `top1_roc_short_blend_risk_adjusted_roc12_6_3_w1_1_2_short21x1_trend0_vol63_equal_monthly_posscore_adjusted` | R$ 1.141,22 | **Correto**, nenhum erro |

## 1. `cci_trend_14_m100_100_sma100`: erro encontrado

### O erro

A família `cci_trend` usa entrada −100 e saída +100: a ideia é comprar a correção
(CCI ≤ −100) dentro da tendência de alta e vender a força (CCI ≥ +100). O código
comparava como se fosse momentum: **entrava com CCI ≥ −100 e saía com CCI ≤ +100**.
Com o CCI entre −100 e +100, o que acontece na maior parte do tempo, as duas condições
valem juntas, e o sinal alternava compra e venda a cada pregão.

PETR4 em janeiro de 2024, acima da média de 100 pregões:

| Pregão | CCI(14) | Sinal com erro | Sinal corrigido |
| :--- | ---: | :---: | :---: |
| 05/01 | 123,9 | 1 | 0 |
| 08/01 | 72,7 | 0 | 0 |
| 09/01 | 70,6 | 1 | 0 |
| 10/01 | 26,8 | 0 | 0 |
| 11/01 | 29,9 | 1 | 0 |
| 12/01 | 59,1 | 0 | 0 |
| 15/01 | 51,0 | 1 | 0 |
| 16/01 | 38,7 | 0 | 0 |

Na PETR4, de 2018 a 2026, o sinal trocava 803 vezes com o erro e 64 vezes com a correção.

### Alcance

O erro atingia as cinco estratégias `cci_trend_*` (2.390 combinações). Um censo das 249
estratégias ([`trocas_de_sinal_por_estrategia_antes_da_correcao.json`](auditoria_combinacao_ruim/trocas_de_sinal_por_estrategia_antes_da_correcao.json))
mostra que só elas tinham esse padrão:

- 73% a 83% das posições das `cci_trend` duravam um único pregão; a estratégia seguinte
  fica em 45% (`sma20_stochastic_14_20_80`, que quase não opera).
- Eram as cinco piores estratégias da matriz, com medianas de −13,9% a −18,4% a.a., e
  ocupavam 49% do 1% pior.

A família `mfi_trend`, com a mesma estrutura, já tratava o caso: com o nível de entrada
abaixo do de saída, ela compra fraqueza e vende força. A correção aplica a mesma regra ao
CCI, com teste de regressão ([`tests/test_cci_trend_signal.py`](../../tests/test_cci_trend_signal.py)).
O teste falha no código antigo, e a suíte inteira passa (612 testes). As `cci_momentum`
(entrada acima da saída) não mudam.

### Efeito na combinação sorteada

| R$ 1.000 → | Com o erro | Corrigida |
| :--- | ---: | ---: |
| Matriz, 2018–2026 | R$ 59,78 (−27,86% a.a.; drawdown −94,4%) | R$ 664,91 (−4,62% a.a.; drawdown −56,9%) |
| Matriz sem custo nenhum | R$ 348,22 | R$ 1.173,43 |
| Motor realista (tarifas B3, lotes, slippage por liquidez, IR) | R$ 71,12 (1.637 ordens) | R$ 626,77 (530 ordens) |
| Treino 2018–2022 / teste 2023–2026 (matriz) | R$ 249,51 / R$ 197,96 | R$ 1.362,19 / R$ 485,03 |

Com o erro, o giro era de 1.441 vezes o patrimônio. Os custos levavam R$ 348 a R$ 60, e
mesmo sem custo a estratégia perdia 11,5% a.a. Corrigida, ela continua ruim: perde para
o CDI e para `buy_and_hold` com o mesmo gerenciamento (R$ 2.442,95; 10,91% a.a.).

### O que estava certo

- A fórmula do CCI segue a definição de Lambert: preço típico, média de *n* pregões,
  desvio médio absoluto e constante 0,015.
- A matriz e o motor realista concordam nos dois casos (R$ 59,78 × R$ 71,12 e
  R$ 664,91 × R$ 626,77): o motor calculava corretamente um sinal errado.

Resumos em [`auditoria_combinacao_ruim/`](auditoria_combinacao_ruim/).

## 2. `macd_12_26_9_trend200` + `roc_short_blend`: correta

Posição 43.178 de 119.022, acima da mediana (−0,57% a.a.).

- **Sinal:** comprado enquanto a linha MACD (EMA 12 − EMA 26) está acima da sua EMA de 9
  e o fechamento está acima da média de 200 pregões.
- **Gerenciamento:** uma vez por mês, entre as ações do universo daquela semana com sinal
  ligado, compra 100% em uma única ação, a de maior pontuação:
  - momentum = (ROC 252 + ROC 126 + 2 × ROC 63) / 4, que precisa ser positivo;
  - combinado com o ROC de 21 pregões: (momentum + ROC 21) / 2, também positivo;
  - pontuação = momentum combinado ÷ volatilidade de 63 pregões.

  Entre as decisões mensais, sai e volta à mesma ação conforme o sinal do MACD.

### Verificações

| Verificação | Resultado |
| :--- | :--- |
| Reimplementação independente ([`mirror_macd.py`](auditoria_combinacao_sorteada_2/mirror_macd.py)): MACD, média de 200, pontuação, sorteio da ação, lotes, custos e liquidação final escritos do zero | Sinal igual ao do motor em **todos** os dias × ações; patrimônio igual nos **2.146 de 2.146** pregões (R$ 1.141,22), diferença máxima 0,000000% |
| Uso de dados do futuro ([`causal_macd.py`](auditoria_combinacao_sorteada_2/causal_macd.py)) | 1.092 cortes: o sinal calculado só com o passado é idêntico ao da série completa |
| Preços x B3 ([`cotahist_check.py`](auditoria_combinacao_sorteada_2/cotahist_check.py)) | Abertura e fechamento de **1.059 de 1.059** dias-ação em carteira conferem com o COTAHIST oficial |
| Eventos durante as posições | Desdobramentos da MGLU3 (8:1 em 06/08/2019; +6,09% no dia) e da HAPV3 (5:1 em 25/11/2020; +0,95%) tratados certo; nenhum outro evento no período das posições |
| Motor realista | R$ 1.040,14 (0,46% a.a.; drawdown −58,6%): 269 ordens, R$ 91,13 de tarifas, slippage médio de 10,75 bps, IR zero (vendas mensais abaixo de R$ 20 mil) |
| Contabilidade do motor realista | Soma dos ganhos realizados das 135 vendas = R$ 40,14 = patrimônio final − R$ 1.000 |
| Sinal | Nada anormal: 5,2% de trocas por dia, mediana de 6 pregões por posição, 17% das posições com um pregão |

### Por que rende pouco

| R$ 1.000 → | Matriz |
| :--- | ---: |
| 2018–2026 | R$ 1.141,22 (1,54% a.a.; drawdown −55,9%) |
| Sem custo nenhum | R$ 1.586,34 (5,49% a.a.) |
| Treino 2018–2022 / teste 2023–2026 | R$ 1.207,05 / R$ 950,67 |
| `buy_and_hold` com o mesmo gerenciamento | R$ 2.830,07 (12,82% a.a.) |

- **Custo do giro:** o MACD tira a carteira da ação escolhida com frequência. Ela fica
  investida 43% do tempo e gira 251 vezes o patrimônio, e os custos levam R$ 1.586 a
  R$ 1.141.
- **Resultado típico:** a mesma estratégia com os 478 gerenciamentos tem mediana de
  2,16% a.a.; o mesmo gerenciamento com as 249 estratégias, 0,07% a.a.
- **Ganhos e perdas:** ganhou com CSNA3 (+R$ 556), WEGE3 (+R$ 430) e OIBR3 (+R$ 283);
  perdeu com EMBR3 (−R$ 348), PRIO3 (−R$ 256) e PETR4 (−R$ 229). No motor realista, 58
  vendas tiveram ganho e 77 tiveram perda.

Evidências em [`auditoria_combinacao_sorteada_2/`](auditoria_combinacao_sorteada_2/).

## Matrizes depois da correção

As duas matrizes filtradas (período inteiro e treino) estão sendo executadas de novo com o
commit `19ddaf6`. Só as 2.390 combinações `cci_trend` mudam de valor. Este relatório e a
[revisão](REVISAO.md) serão atualizados com o resultado.

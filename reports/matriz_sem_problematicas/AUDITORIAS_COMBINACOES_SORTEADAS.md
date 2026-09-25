# Auditorias sorteadas: duas combinações e a família Donchian (24–25/09/2026)

Partes da [matriz sem ações problemáticas](REVISAO.md) foram sorteadas e conferidas de
ponta a ponta: R$ 1.000 de 2018-01-02 a 2026-08-19, custos de 3,2 bps + slippage de
10 bps, universo point-in-time filtrado ([`universo_filtrado.json`](universo_filtrado.json)).

| # | Sorteio | O que foi auditado | Veredito |
| :--- | :--- | :--- | :--- |
| 1 | 1% pior (1.190 combinações), semente 20260924 | `cci_trend_14_m100_100_sma100` + `top1_momentum_lb126_skip21_trend0_vol63_equal_weekly_abs_cap1_adjusted` | **Erro no sinal**, corrigido em `19ddaf6`: R$ 59,78 → R$ 664,91 |
| 2 | Todas, exceto `cci_trend` (116.632), semente 20260925 | `macd_12_26_9_trend200` + `top1_roc_short_blend_risk_adjusted_roc12_6_3_w1_1_2_short21x1_trend0_vol63_equal_monthly_posscore_adjusted` | Correta |
| 3 | 19 famílias ainda não revisadas, semente 20260926 | As 10 estratégias `donchian_breakout_*` | Sinais corretos; a revisão achou **três erros no motor realista**, corrigidos em `157111a`, `e04f91a` e `93f4751` |

## 1. `cci_trend_14_m100_100_sma100`: erro no sinal

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
O teste falha no código antigo. As `cci_momentum` (entrada acima da saída) não mudam.

### Efeito na combinação sorteada

| R$ 1.000 → | Com o erro | Corrigida |
| :--- | ---: | ---: |
| Matriz, 2018–2026 | R$ 59,78 (−27,86% a.a.; drawdown −94,4%) | R$ 664,91 (−4,62% a.a.; drawdown −56,9%) |
| Matriz sem custo nenhum | R$ 348,22 | R$ 1.173,43 |
| Motor realista (tarifas B3, lotes, slippage por liquidez, IR) | R$ 69,44 (1.650 ordens) | R$ 622,10 (532 ordens) |
| Treino 2018–2022 / teste 2023–2026 (matriz) | R$ 249,51 / R$ 197,96 | R$ 1.362,19 / R$ 485,03 |
| Posição entre as 119.022 combinações | 118.992ª | 87.087ª |

Com o erro, o giro era de 1.441 vezes o patrimônio. Os custos levavam R$ 348 a R$ 60, e
mesmo sem custo a estratégia perdia 11,5% a.a. Corrigida, ela continua ruim: perde para
o CDI e para `buy_and_hold` com o mesmo gerenciamento (R$ 2.442,95; 10,91% a.a.).

### O que estava certo

- A fórmula do CCI segue a definição de Lambert: preço típico, média de *n* pregões,
  desvio médio absoluto e constante 0,015.
- A matriz e o motor realista concordam nos dois casos (R$ 59,78 × R$ 69,44 e
  R$ 664,91 × R$ 622,10): o motor calculava corretamente um sinal errado.

Resumos em [`auditoria_combinacao_ruim/`](auditoria_combinacao_ruim/).

## 2. `macd_12_26_9_trend200` + `roc_short_blend`: correta

Posição 43.433 de 119.022, acima da mediana (−0,51% a.a.).

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
| Reimplementação independente ([`mirror_macd.py`](auditoria_combinacao_sorteada_2/mirror_macd.py)): MACD, média de 200, pontuação, escolha da ação, lotes, custos e liquidação final escritos do zero | Sinal igual ao do motor em **todos** os dias × ações; patrimônio igual nos **2.146 de 2.146** pregões (R$ 1.141,22), diferença máxima 0,000000% |
| Uso de dados do futuro ([`causal_macd.py`](auditoria_combinacao_sorteada_2/causal_macd.py)) | 1.092 cortes: o sinal calculado só com o passado é idêntico ao da série completa |
| Preços x B3 ([`cotahist_check.py`](auditoria_combinacao_sorteada_2/cotahist_check.py)) | Abertura e fechamento de **1.059 de 1.059** dias-ação em carteira conferem com o COTAHIST oficial |
| Eventos durante as posições | Desdobramentos da MGLU3 (8:1 em 06/08/2019; +6,09% no dia) e da HAPV3 (5:1 em 25/11/2020; +0,95%) tratados certo; nenhum outro evento no período das posições |
| Motor realista | R$ 1.011,77 (0,14% a.a.; drawdown −60,3%): 272 ordens, R$ 91,04 de tarifas, slippage médio de 10,73 bps, IR zero (vendas mensais abaixo de R$ 20 mil); mesma carteira da matriz em todos os pregões |
| Contabilidade do motor realista | Soma dos ganhos realizados das 135 vendas = R$ 11,77 = patrimônio final − R$ 1.000 |
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
- **Ganhos e perdas no motor realista:** ganhou com CSNA3 (+R$ 561), WEGE3 (+R$ 430) e
  OIBR3 (+R$ 292); perdeu com EMBR3 (−R$ 345), PRIO3 (−R$ 315) e PETR4 (−R$ 224). 58
  vendas tiveram ganho e 77 tiveram perda.

Evidências em [`auditoria_combinacao_sorteada_2/`](auditoria_combinacao_sorteada_2/).

## 3. Família Donchian: sinais corretos

As 10 estratégias `donchian_breakout_<entrada>_<saída>[_trend<n>]` compram quando o
fechamento passa da **máxima** dos *entrada* pregões anteriores (sem contar o dia) e,
se houver filtro, está acima da média de *n* pregões. Vendem quando o fechamento cai
abaixo da **mínima** dos *saída* pregões anteriores. O filtro de tendência vale só na
entrada, como descrito na estratégia.

### Verificações

Scripts e resultados em [`auditoria_familia_donchian/`](auditoria_familia_donchian/).

| Verificação | Resultado |
| :--- | :--- |
| Reimplementação independente das 10 regras | Sinal idêntico ao do motor em 1.629.000 dias × ações (162.900 por estratégia), nenhuma divergência |
| Uso de dados do futuro | 11.112 cortes (cerca de 1.100 por estratégia), nenhuma divergência |
| Regra de entrada e saída | Em 16.414 entradas e 16.223 saídas, nenhuma violação: toda entrada fecha acima da máxima anterior e toda saída abaixo da mínima anterior |
| Máxima e mínima ajustadas | Máxima, mínima e fechamento têm o mesmo fator de ajuste por desdobramento em todos os candles; nenhum candle com OHLC incoerente |
| Duração das posições | Mediana de 11 pregões (10/5) a 72 pregões (100/50), coerente com as janelas |

**Filtro de tendência redundante com gerenciamentos de momentum.** As versões com e sem
filtro empatam na maioria dos gerenciamentos (`55_20` × `55_20_trend200`: 425 de 478;
`100_50` × `100_50_trend200`: 436 de 478). O filtro funciona: ele muda 10,9% dos dias
ligados da `55_20`, e 652 desses dias estavam no universo com pontuação positiva. Mas
uma ação abaixo da média de 200 pregões nunca foi a de maior momentum, então a ação
escolhida é a mesma ([`donchian_trend_equiv.py`](auditoria_familia_donchian/donchian_trend_equiv.py)).

### Resultado na matriz

| Estratégia | Mediana nos 478 gerenciamentos | Posição entre 249 | Melhor combinação |
| :--- | ---: | ---: | ---: |
| `donchian_breakout_100_50_trend200` | 4,56% a.a. | 27ª | 32,19% a.a. |
| `donchian_breakout_100_50` | 4,42% a.a. | 28ª | 32,19% a.a. |
| `donchian_breakout_10_5` | −1,62% a.a. | 148ª | 11,50% a.a. |
| `donchian_breakout_55_20` | −2,35% a.a. | 169ª | 26,57% a.a. |
| `donchian_breakout_55_20_trend100` | −2,35% a.a. | 170ª | 26,57% a.a. |
| `donchian_breakout_55_20_trend200` | −2,41% a.a. | 173ª | 26,57% a.a. |
| `donchian_breakout_20_10_trend100` | −2,66% a.a. | 181ª | 20,34% a.a. |
| `donchian_breakout_20_10_trend50` | −3,00% a.a. | 188ª | 19,64% a.a. |
| `donchian_breakout_20_10` | −3,16% a.a. | 189ª | 19,64% a.a. |
| `donchian_breakout_40_20` | −3,34% a.a. | 193ª | 21,99% a.a. |

Mediana da família: −1,63% a.a. (todas as combinações: −0,51%); 10,4% das combinações
superam o CDI (todas: 7,6%). Só os canais longos (100/50) ficam acima da mediana geral.

A melhor combinação da família é também a melhor dela no treino:
`donchian_breakout_100_50` + `top1_momentum_lb63_skip0_trend200_vol21_equal_monthly_abs_cap1_adjusted`
(43ª no período inteiro, 239ª no treino).

| R$ 1.000 → | Matriz | Motor realista | CDI |
| :--- | ---: | ---: | ---: |
| 2018–2026 | R$ 11.103,95 (32,19% a.a.; drawdown −53,3%) | R$ 9.968,75 (30,54% a.a.; drawdown −53,6%) | R$ 2.121,49 |
| Treino 2018–2022 | R$ 5.994,41 (43,19% a.a.) | | |
| Teste 2023–2026 | R$ 1.867,34 (18,79% a.a.) | R$ 1.772,52 (17,09% a.a.; drawdown −37,7%) | R$ 1.560,01 |
| `buy_and_hold` com o mesmo gerenciamento, teste | R$ 2.238,10 (24,87% a.a.) | | |

No teste, a Donchian superou o CDI, mas rendeu menos que manter a ação escolhida pelo
mesmo gerenciamento sem sinal nenhum (`buy_and_hold`). A diferença entre a matriz e o
motor realista vem de custos, do limite de liquidez do fracionário (em fevereiro de
2018 só 21 de 38 ações de RENT3 couberam) e de uma posição final em BBSE3 ainda aberta.
Os ganhos realizados somam R$ 10.219,01; descontados o prejuízo ainda não realizado da
BBSE3 (−R$ 1.248,92) e R$ 1,34 de IR, a conta fecha com o patrimônio final.

## 4. Erros encontrados no motor realista

A melhor Donchian dava R$ 9.691 no motor realista contra R$ 11.104 na matriz, e as
carteiras dos dois motores diferiam em 50 pregões. Rastreando essas diferenças, surgiram
três erros no motor realista (`b3_strategy_lab/realistic_portfolio.py`). Nenhum afeta a
matriz.

1. **Lote padrão zerado por falta de poucos reais** (`157111a`). Quando a abertura vinha
   acima do fechamento da decisão, a compra passava do caixa por alguns reais. O motor
   reduzia cada parte da ordem na mesma escala e arredondava para baixo em lotes de 100,
   então o lote padrão virava zero ou perdia um lote inteiro. Em 03/02/2020 a carteira
   tinha R$ 1.961 e comprou só 37 VVAR3 (R$ 518). Os outros 73% ficaram em caixa por um
   mês. Agora a redução vale para o total de cada ação, que preenche primeiro o lote
   padrão. Teste: `tests/test_frozen_opening_orders.py`.
2. **Universo aplicado fora das decisões** (`e04f91a`). O motor realista vendia a ação
   designada quando ela saía do top 40 semanal de liquidez no meio do mês (CSNA3, 41ª
   de 02 a 16/02/2024) e comprava de novo quando voltava. A matriz aplica o universo só
   na decisão do gerenciamento, como descreve
   [`docs/strict_backtest_methodology.md`](../../docs/strict_backtest_methodology.md). O
   motor realista, que existe para reproduzir a matriz, agora segue a mesma regra.
   Teste: `tests/test_realistic_universe_between_rebalances.py`.
3. **Venda incompleta esquecida** (`93f4751`). As ordens expiram a cada pregão. Quando
   o limite de liquidez do fracionário cortava uma venda, a sobra ficava na carteira
   até a próxima decisão: 22 AXIA3 por três semanas em novembro de 2025 e sobras de
   ITSA4, RENT3, ELET3, UGPA3 e TOTS3 na campeã. Agora a venda é reenviada na abertura
   seguinte. Teste no mesmo arquivo.

Os três testes falham no código anterior; a suíte inteira passa (616 testes).

### Efeito nos replays realistas

| R$ 1.000 → (motor realista) | Antes | Depois | Matriz |
| :--- | ---: | ---: | ---: |
| Campeã, 2018–2026 | R$ 16.809,62 | **R$ 15.766,04** | R$ 17.235,41 |
| Campeã, teste 2023–2026 | R$ 1.481,53 | **R$ 1.429,15** | R$ 1.423,21 |
| Primeira do treino, 2018–2026 | R$ 16.601,31 | **R$ 15.403,68** | R$ 16.833,27 |
| Primeira do treino, teste 2023–2026 | R$ 1.425,15 | **R$ 1.421,38** | R$ 1.372,60 |
| Melhor Donchian, 2018–2026 | R$ 9.691,20 | **R$ 9.968,75** | R$ 11.103,95 |
| Melhor Donchian, teste 2023–2026 | R$ 1.602,62 | **R$ 1.772,52** | R$ 1.867,34 |
| `macd_12_26_9_trend200` sorteada | R$ 1.040,14 | **R$ 1.011,77** | R$ 1.141,22 |
| `cci_trend` corrigida | R$ 626,77 | **R$ 622,10** | R$ 664,91 |
| `gap_momentum` ([auditoria de 23/09](../auditoria_resultados_realistas.md)), 2018–2026 / teste | R$ 1.122,14 / R$ 820,32 | **R$ 1.017,64 / R$ 849,61** | |

As correções mexem nos dois sentidos: com a carteira investida por inteiro, os ganhos e
as perdas crescem. No saldo, os erros deixavam a campeã e a primeira do treino com
resultado maior e a melhor Donchian com resultado menor. Depois das correções, as carteiras dos dois motores são iguais em todos os pregões
exceto os dias de venda de sobras (0 a 8 pregões por replay; eram até 103). Detalhes em
[`matriz_x_motor_realista.json`](auditoria_familia_donchian/matriz_x_motor_realista.json).

**Limite que continua.** A ordem é fixada no fechamento da decisão. Se a abertura sobe
e o caixa não cobre um lote de 100 ações, o motor compra um lote a menos e não cria uma
ordem fracionária nova na abertura; isso é intencional e tem teste próprio. Em
01/07/2024 a campeã comprou 200 EMBR3 em vez de 300 e ficou com um terço em caixa até
agosto, o que explica a maior parte da diferença de 8,5% entre matriz e motor realista.

## 5. Matrizes depois da correção do `cci_trend`

As duas matrizes filtradas (período inteiro e treino) foram executadas de novo; as
duas auditorias oficiais passam sem nenhuma falha.

- Mudaram exatamente as 2.390 combinações `cci_trend`; as outras 116.632 ficaram
  idênticas. As campeãs do período inteiro e do treino não mudam.
- Mediana de todas as combinações: −0,57% → −0,51% a.a. (treino: −0,45% → −0,37%);
  7,6% continuam acima do CDI.
- Medianas das `cci_trend`: de −13,9%/−18,4% para −2,2%/−10,1% a.a. Continuam entre as
  piores (posições 165 a 248 de 249).
- O 1% pior agora é liderado por `cmf_price_trend`, `klinger_volume_oscillator`,
  `cmf_threshold_hysteresis`, `cmf_efi_confirm` e `smi_ergodic_histogram_momentum`.

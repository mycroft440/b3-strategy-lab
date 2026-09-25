# Auditoria dos resultados "realistas" de 17/09/2026

Escopo: commits `dcc0745`, `0ab0ad5`, `7327b56` e `278de5c`, que publicaram
`ranking_estrategias_realista.*` e `novo_backteste_gap_momentum_*` com a conclusão
de que `gap_momentum` seria a "verdadeira campeã" (36,70% a.a. fora da amostra e
R$ 1.000 → R$ 14.218,29 de 2018 a 2026).

## Veredito

Os números publicados não eram realistas. Com as mesmas regras corrigidas:

| Medida (R$ 1.000 iniciais) | Publicado em 17/09 | Após a auditoria |
| :--- | ---: | ---: |
| Par escolhido só no treino, teste 2023-01-02 a 2026-08-19 (motor estrito) | não informado | `sma_cross`: R$ 1.008,97 (0,25% a.a.) |
| `gap_momentum`, teste 2023-01-02 a 2026-08-19 (motor estrito, universo fixo) | R$ 3.108 (36,70% a.a.) | R$ 3.161,07 (37,34% a.a.), não significativo contra o CDI |
| `gap_momentum`, teste 2023-01-02 a 2026-08-19 (motor realista, Nível 2) | — | **R$ 849,61 (−4,39% a.a.)** |
| `gap_momentum`, 2018-01-02 a 2026-08-19 (motor realista, Nível 2) | R$ 14.218,29 (36,03% a.a.) | **R$ 1.017,64 (0,20% a.a.)**, drawdown −77,2% |
| CDI bruto, 2023-01-02 a 2026-08-19 | não informado | R$ 1.560,01 (13,04% a.a.) |
| CDI bruto, 2018-01-02 a 2026-08-19 | não informado | R$ 2.121,49 (9,11% a.a.) |

Nenhuma das 25 estratégias superou o CDI de forma estatisticamente significativa no
teste. No motor realista, `gap_momentum` + `top1_momentum_lb63_skip0_trend0_vol21_equal_weekly_abs_cap1_adjusted`
perdeu dinheiro de 2023 a 2026 e ficou abaixo do CDI no período inteiro.

## Problemas encontrados

1. **A "campeã" foi escolhida pelo período de teste.** O relatório ordenava as 25
   estratégias pelo CAGR do teste e declarava a primeira como vencedora. Pelo
   protocolo do próprio motor estrito (escolha somente no treino), o par vencedor é
   `sma_cross`, que rendeu 0,25% a.a. no teste. `gap_momentum` era apenas a 14ª no
   treino.
2. **O par `gap_momentum` + gerenciamento já era a hipótese conhecida antes do
   ranking.** Ele era o padrão de `backtest_strategy_management_realistic.py` antes de
   17/09 e veio da matriz de período completo (2018–2026), que inclui os anos de
   "teste cego". A "retenção de 102,7%" não é evidência de robustez.
3. **Sem comparação com o CDI nem teste de múltiplas hipóteses.** O excesso diário de
   `gap_momentum` sobre o CDI tem t = 1,31 (p unilateral 0,096 sem correção; 1,0 com
   Bonferroni para 25 candidatos).
4. **Universo com viés de sobrevivência e de seleção.** O universo fixo de 40 ações foi
   escolhido com a liquidez de 2018 e exige continuidade até hoje
   (`survivorship_safe=false`). No teste, USIM5 (+R$ 818), JHSF3 (+R$ 597) e BRKM5
   (+R$ 216) respondem por cerca de R$ 1.631 dos R$ 2.161 de lucro; nenhuma das três
   entra no universo point-in-time. Dez das 40 ações fixas nunca foram selecionáveis
   no universo histórico: BBDC3, BRKM5, EGIE3, GGBR3, JHSF3, KLBN11, SANB11, TAEE11,
   TUPY3 e USIM5.
5. **O "novo backteste completo" 2018–2026 era dentro da amostra e não reproduzível.**
   Ele incluía o período de treino. O ledger rotulava como `raw_open` a abertura
   normalizada (MGLU3 em 2018-01-02: 24,08 no ledger, R$ 80,90 no pregão oficial;
   IRBR3 em 2018-04-23: 470,20 no ledger, R$ 47,02 oficial). As quantidades inteiras
   eram calculadas sobre esses preços fictícios. O `turnover_anual` de 501,43 era o
   giro total de 8,6 anos (cerca de 58 vezes o patrimônio por ano). Com o código e os
   dados versionados, o ledger diverge a partir de 2025-07-11 e termina em
   R$ 14.468,46, não em R$ 14.218,29; nenhum script gerador foi versionado.
6. **Resultado muito sensível a escolhas.** Entre os 160 gerenciamentos, a mediana de
   `gap_momentum` no teste é 12,3% a.a.; o quinto melhor do treino
   (`top1_momentum_lb126_skip21_trend0_vol21_equal_weekly_abs_cap1_adjusted`) rende
   0,7% a.a. Com slippage de 20, 30 e 50 bps por ordem, o CAGR do teste cai para
   29,4%, 22,0% e 7,8%.
7. **Textos fixos e incorretos no relatório.** As "lições" eram strings fixas no
   código (por exemplo, Sharpe de 0,65 para `turn_of_month`, quando a tabela mostrava
   0,38).
8. **Regressões de código.**
   - A CLI `backtest` em `price_only` trocava silenciosamente para `adjusted` em 19 dos
     40 ativos padrão (eventos que geram fração de ação) e gravava o resultado com o
     rótulo `price_only`.
   - `_gap_adjusted_eligibility` deixou de limitar o ajuste de proventos ao
     `gap_momentum`; outras estratégias perdiam o calendário verificado de pregões no
     walk-forward realista.
   - O painel realista chamava `portfolio_strategies()` sem importá-la (`NameError` ao
     abrir a página) e aceitava estratégia inexistente.
   - O Sortino dividia a semivariância apenas pelos dias negativos, subestimando o
     índice em cerca de √2.

## Resultado no motor realista (Nível 2)

Arquivos em [`gap_momentum_realista/`](gap_momentum_realista/). O replay usa o
universo point-in-time survivorship-safe (top 40 por liquidez passada, recalculado
semanalmente, somente ON/PN), preços oficiais do COTAHIST, lotes padrão e
fracionário separados, slippage por participação no volume passado, tarifas B3
datadas e apuração mensal de IR. Dividendos/JCP ficam fora do escopo, como no motor
estrito.

| Replay | Patrimônio final | CAGR | Drawdown máx. | Trades | Tarifas | IR |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018-01-02 a 2026-08-19 | R$ 1.017,64 | 0,20% | −77,20% | 747 | R$ 273,21 | R$ 0,00 |
| 2023-01-02 a 2026-08-19 | R$ 849,61 | −4,39% | −41,52% | 325 | R$ 80,87 | R$ 0,00 |

Retorno por ano do replay completo: 2018 −10,8%; 2019 +57,0%; 2020 +53,3%;
2021 −12,2%; 2022 −24,2%; 2023 −17,5%; 2024 −7,8%; 2025 −0,3%; 2026 −6,0%.

Os números desta seção foram recalculados em 25/09/2026, depois de três correções no
motor realista (`157111a`, `e04f91a` e `93f4751`, descritas em
[`matriz_sem_problematicas/AUDITORIAS_COMBINACOES_SORTEADAS.md`](matriz_sem_problematicas/AUDITORIAS_COMBINACOES_SORTEADAS.md)).
Antes delas, o replay completo dava R$ 1.122,14 e o de teste, R$ 820,32; a conclusão
não muda.

Decomposição: repetindo o replay completo com slippage fixo de 10 bps (como no motor
estrito), o resultado sobe para R$ 1.083,54 (0,93% a.a.). O custo de execução explica
uma parte pequena da diferença; a maior parte vem do universo.

Limites deste replay, também registrados no campo `validity`:

- `__DIAGNOSTIC_FRACTIONS_AT_ZERO`: a bonificação de 4% da RADL3 em 2023-05-22 gerou
  0,44 ação fracionária no replay completo (nenhuma no de teste). O leilão de frações não está em
  `corporate_settlements.json` porque o aviso primário da RD com o valor líquido não
  foi localizado; a imprensa informa R$ 28,28 por ação. O diagnóstico valoriza a
  fração em zero, o que reduz o resultado em no máximo cerca de R$ 12.
- `__BONUS_TAX_BASIS_UNCERTIFIED`: o custo fiscal da mesma bonificação não é aplicado
  pelo motor; o IR total do replay é zero.
- `__UNBOUND_TICKER_TRANSITIONS`: o manifesto de transições tem três
  desaparecimentos sem sucessor documentado (AZUL4, PETZ3, TIMP3). O replay não
  detinha nenhum deles nessas datas.
- Dividendos/JCP excluídos subestimam o retorno. Mesmo somando cerca de 5% a.a. de
  proventos, o replay continuaria abaixo do CDI nos dois períodos.
- A escolha da estratégia continua retrospectiva (`RETROSPECTIVE_SELECTION`).

O replay realista do par do protocolo (`sma_cross`) no teste fica bloqueado: a conta
mantinha CIEL3 no fechamento de capital da Cielo, que exige um evento de
encerramento econômico certificado.

## Correções feitas

- `scripts/rank_strategies_realistic.py`: par do protocolo escolhido só no treino,
  comparação com o CDI (BCB SGS 12) e com a carteira igual-ponderada, p-valor com
  Bonferroni, flags de validade por linha e conclusões geradas a partir dos números.
- `b3_strategy_lab/cli.py`: `price_only` bloqueia o ativo em vez de trocar de modo.
- `b3_strategy_lab/realistic_portfolio_core.py`: ajuste de proventos restrito ao
  `gap_momentum` novamente.
- `scripts/realistic_backtest_control_panel.py`: import corrigido e validação da
  estratégia.
- Sortino corrigido nos dois motores.
- Ledger estrito: `reference_open` (base simulada) e `historical_raw_open` (pregão
  oficial) no lugar do `raw_open` enganoso.
- `data/corporate_actions/realistic_split_evidence_addendum.json`: grupamento 10:1 da
  OIBR3 em 2024-06-17 (aviso da Oi de 01/07/2024), que bloqueava o pipeline realista.
- `scripts/diagnose_fractional_blockers.py`: lista as frações sem liquidação
  documentada e gera o replay diagnóstico rotulado acima.
- `novo_backteste_gap_momentum_*` removidos; os arquivos acima os substituem.

## Como reproduzir

```powershell
python scripts\sync_cdi_benchmark.py --end 2026-08-19
python scripts\rank_strategies_realistic.py

python scripts\run_realistic_pipeline.py --start 2018-01-02 --end 2026-08-19 --initial-cash 1000 --mode research --skip-walk-forward
python scripts\diagnose_fractional_blockers.py --start 2018-01-02 --end 2026-08-19 --initial-cash 1000 --output reports\gap_momentum_realista\gap_momentum_2018_2026_resumo.json --orders-output reports\gap_momentum_realista\gap_momentum_2018_2026_ordens.json --curve-output reports\gap_momentum_realista\gap_momentum_2018_2026_curva.csv --trades-output reports\gap_momentum_realista\gap_momentum_2018_2026_trades.csv --tax-output reports\gap_momentum_realista\gap_momentum_2018_2026_ir.csv
```

O pipeline realista termina com erro na etapa de backtest até que a liquidação das
frações da RADL3 seja adicionada; as etapas de dados e auditoria concluem antes disso.
Para o teste, troque `--start` por `2023-01-02` e os nomes de arquivo.

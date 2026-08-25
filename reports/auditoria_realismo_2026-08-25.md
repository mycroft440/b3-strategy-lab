# Auditoria de realismo do b3-strategy-lab

**Data:** 25 de agosto de 2026  
**Escopo:** motor Python, dados B3, seleção walk-forward e tentativa de reexecução do primeiro colocado  
**Commit-base:** `4cff7b9`  
**Branch de trabalho:** `codex/realism-audit-20260825`

## Resposta executiva

O motor foi endurecido e os 275 testes automatizados passaram, mas ainda não existe
um primeiro lugar que possa ser chamado de realista ou certificado. A reconstrução
point-in-time encontrou 91 ações históricas e 452 snapshots semanais entre 2018 e
2026, porém a API oficial não forneceu eventos corporativos completos para diversos
tickers antigos/descontinuados. O gate recusou continuar sem esses dados. Esse é o
resultado correto: publicar o antigo campeão como validado criaria uma falsa precisão.

O antigo líder `gap_momentum` +
`top1_momentum_lb63_skip0_trend0_vol21_equal_weekly_abs_cap1_adjusted`, com retorno
divulgado de 3.116,89%, permanece apenas uma hipótese retrospectiva. Ele foi obtido
sem holdout intacto, custos, impostos ou slippage e não passou pela nova certificação.

## Correções aplicadas

- O catálogo usado na execução agora é derivado em runtime, serializado e vinculado
  por SHA-256. O contrato atual contém 234 estratégias, 478 gestões e 111.852 pares.
- A execução usa sinal no fechamento e ordem apenas na abertura seguinte.
- A referência de liquidez é estritamente anterior à sessão de execução; volume ou
  quantidade do próprio dia não podem antecipar capacidade.
- Foi adicionado limite duro de participação, slippage dependente da participação e
  auditoria de fills fora da faixa OHLC oficial.
- Fills fora da faixa diária e referências de liquidez ausentes/não causais bloqueiam
  a certificação.
- O universo semanal é point-in-time e inclui ações históricas; não retroaplica a
  lista de sobreviventes de 2026.
- Sessão com negócio apenas no fracionário não gera candle padrão inventado. Uma
  ordem que precise do open padrão ausente é recusada.
- O walk-forward mantém uma única conta OOS através dos folds, incluindo caixa,
  posições, custo médio, impostos e recebíveis.
- A métrica OOS usa a equity imediatamente anterior ao recorte, e não o capital
  inicial original da conta.
- O último ano do dataset é rotulado conservadoramente como parcial.
- Enquanto existir qualquer bloqueador, `certified_first_place` é `null` e a posição
  número 1 é explicitamente apenas diagnóstica.

## Evidência de execução

- `python3 -m unittest discover -s tests -p 'test_*.py' -q`: **275 testes, OK**.
- Auditoria do catálogo: **234 × 478 = 111.852**, hash
  `bb2f7f49f3130f87d55725ef6106905915a47da616047ba67bc5411abde25f85`.
- Reconstrução COTAHIST 2017–2026: **452 snapshots**, **91 tickers históricos**,
  **150.078** linhas de execução no lote padrão e **151.591** no fracionário.
- `audit_realistic_backtest_inputs.py`: **bloqueado**, exit code 2, porque os
  ledgers/manifests point-in-time de ações corporativas e proventos não puderam ser
  concluídos com evidência oficial para todos os símbolos.

## Por que essas regras são necessárias

A própria [B3 informa que o COTAHIST não ajusta preços por eventos corporativos](https://www.b3.com.br/en_us/market-data-and-indices/data-services/market-data/historical-data/equities/historical-quote-data/),
portanto splits, bonificações, subscrições e proventos precisam ser tratados
separadamente e sem dupla contagem. O [manual de eventos complexos da B3](https://www.b3.com.br/data/files/9F/D5/1F/87/D5DF8810C7AB8988AC094EA8/Manual%20Of%20Complex%20Events.pdf)
confirma que desdobramentos, grupamentos e bonificações alteram a relação entre preço
com e ex-direito.

Para validação temporal, a documentação do
[TimeSeriesSplit do scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
explica por que treino no futuro e teste no passado são inadequados. Para o universo
de 111.852 hipóteses, o risco de escolher ruído também é material: os artigos
[Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253)
e [Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
tratam diretamente do viés de seleção após muitas tentativas.

Custos não podem ser omitidos. A [tabela oficial de tarifas da B3](https://www.b3.com.br/pt_br/produtos-e-servicos/tarifas/listados-a-vista-e-derivativos/renda-variavel/tarifas-de-acoes-e-fundos-de-investimento/a-vista/)
mostra tarifas de negociação e pós-negociação, enquanto o material de backtesting
de López de Prado identifica custos otimistas, capacidade e slippage como fontes
clássicas de resultado irreal
([Backtesting](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2607147_code434076.pdf?abstractid=2606462)).

## Veredito sobre o primeiro lugar

**REPROVADO COMO RESULTADO REALISTA.** Não houve replay certificado do primeiro lugar,
porque o gate detectou dados point-in-time incompletos antes da seleção. O número antigo
de 3.116,89% não deve orientar investimento nem ser apresentado como retorno esperado.
O próximo ranking só será válido após completar e congelar os eventos corporativos,
reexecutar todo o catálogo em walk-forward, calcular correções de múltiplos testes e
reconciliar o vencedor por um replay independente trade a trade.


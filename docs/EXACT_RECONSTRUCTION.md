# Reconstrução estrita de investimento real

O projeto separa alegações que parecem semelhantes, mas não são equivalentes. A regra central é: **um dado que não pode ser provado não recebe o rótulo de exato**.

## 1. Pesquisa retrospectiva

A matriz ampla serve para comparar estratégias e gerenciamentos. Ela pode descobrir hipóteses interessantes, mas não prova que a regra vencedora teria sido escolhida naquela época e não deve ser apresentada como reconstrução exata de uma conta real.

## 2. Replay determinístico certificado com dados públicos

Use preferencialmente:

```bash
python scripts/run_certified_realistic_replay.py --broker-profile <arquivo.json>
```

`scripts/run_exact_realistic_reconstruction.py` permanece apenas como nome legado compatível. O runner público **não emite rótulo de fill exato**. Quando todos os gates passam, a classificação é:

`CERTIFIED_DETERMINISTIC_OFFICIAL_OPEN_REPLAY`

Ela significa que os dados e a regra contrafactual foram endurecidos e auditados para executar de forma determinística sob a hipótese declarada de abertura oficial. Ela **não prova** que uma ordem hipotética teria recebido exatamente aquele fill na fila/leilão real.

Os gates incluem:

- universo histórico point-in-time reconstruído a partir do conjunto histórico completo de **ações ON/PN** elegíveis no escopo certificado, sem filtro de sobrevivência futura;
- UNITS, BDRs, ETFs, fundos e outras classes não recebem automaticamente o tratamento tributário de ações ON/PN e ficam fora do envelope tributário certificado enquanto não houver regra específica implementada e documentada;
- sinais calculados somente com informações disponíveis até o fechamento da decisão;
- execução na abertura seguinte, usando preços oficiais separados dos mercados `010` e `020`;
- dimensionamento de quantidade baseado nas próprias pernas executáveis 010/020, sem usar o preço do lote padrão como proxy para uma ordem fracionária;
- nenhuma substituição silenciosa do mercado fracionário pelo preço do lote padrão;
- slippage modelado igual a zero no replay certificado: a hipótese é explicitamente a abertura oficial, não uma estimativa de impacto;
- splits e mudanças de ticker somente quando o tratamento é determinístico. Conversões não 1:1 ou com componente em dinheiro falham até existir regra fiscal explicitamente implementada e testada;
- desaparecimentos históricos precisam ser resolvidos por evidência ou o processo falha;
- dividendos e JCP precisam estar cobertos por ledger certificado ou o processo falha;
- a certificação de proventos cobre **todo `market_data_tickers`**, inclusive símbolos históricos usados apenas para continuidade de ISIN; não basta revisar somente os tickers selecionáveis;
- proventos já adquiridos e ainda não pagos entram no patrimônio como recebíveis econômicos não investíveis. O caixa só fica disponível na data de pagamento modelada;
- JCP é reconhecido líquido da retenção conhecida. Tratamentos de dividendos 2026+ cujo líquido dependa de exceções não comprovadas falham fechado;
- tarifa B3 e perfil de tarifa da corretora precisam estar documentados para todo o período;
- uma corretagem fixa positiva só é certificável quando a fonte comprova `fixed_fee_application=per_market_order_leg`, pois o motor trata uma ordem no lote padrão `010` e uma ordem no fracionário `020` como pernas/ordens separadas;
- conta tributária de operações em ações isolada das demais operações de bolsa definidas no perfil, sem prejuízo fiscal inicial não documentado;
- IRRF de operações comuns é tratado como antecipação, com crédito fiscal;
- imposto mensal de bolsa é apurado causalmente e colocado em escrow tributário não investível; o DARF é marcado como pago apenas no vencimento modelado;
- DARF inferior a R$10 é acumulado até atingir o mínimo de pagamento;
- após o replay certificado, patrimônio, vendas em um único dia e vendas agregadas no mês precisam permanecer dentro do envelope conservador de R$20.000. Nessa faixa, o runner evita depender de uma reconstrução tributária mais ampla que exigiria contexto adicional.

Mesmo dentro desse envelope, o replay certificado continua sendo **contrafactual**: ele não possui uma confirmação de ordem/fill de uma corretora para uma operação que nunca aconteceu.

## 3. Tributação pessoal de 2026 em diante

A partir do ano-calendário de 2026 existe também tributação mínima anual de altas rendas cuja apuração depende da soma de rendimentos e impostos da pessoa física como um todo, não apenas desta conta de corretora.

Por isso, os relatórios realistas expõem separadamente:

- `final_equity`: patrimônio econômico usado nas métricas, já líquido do imposto ordinário apurado e incluindo recebíveis de proventos adquiridos;
- `brokerage_final_equity`: valor bruto marcado a mercado antes da saída de eventual DARF ainda não pago;
- `outstanding_accrued_tax_liability`: obrigação ordinária já conhecida e ainda não paga na data final;
- `net_equity_after_accrued_tax`: patrimônio econômico líquido do passivo conhecido;
- `unpaid_distribution_receivable`: provento já adquirido, mas ainda não disponível como caixa;
- `ordinary_irrf_withheld`: IRRF de operações comuns retido no replay;
- `darf_paid`: DARF efetivamente liquidado até a data final;
- `cpf_wide_annual_minimum_tax_scope = OUT_OF_SCOPE`.

O último campo é deliberado. Salário, aluguel, outros dividendos, outras carteiras e demais rendimentos do CPF não podem ser inferidos do COTAHIST ou do extrato isolado desta estratégia. O software não inventa esse contexto.

## 4. Reconciliação exata da conta da corretora

A palavra **exato** fica reservada ao fluxo documental:

`scripts/reconcile_actual_personal_account.py`

O selo aprovado nesse fluxo é limitado a:

`ACTUAL_BROKERAGE_ACCOUNT_EXACT_RECONCILIATION`

Ele significa que o razão da **conta da corretora** fecha contra documentos reais. Não significa que todo o patrimônio pessoal ou a declaração anual do CPF foram reconstruídos.

Para esse selo são necessários, entre outros:

- snapshot documental de abertura com `boundary=START_OF_DAY`;
- snapshot documental de fechamento com `boundary=END_OF_DAY`;
- notas de corretagem, confirmações de ordens/fills ou extratos que sustentem cada execução;
- extratos de conta cobrindo continuamente a janela reconciliada;
- ledger de caixa completo com taxas, impostos debitados na conta, dividendos, JCP, depósitos e saques;
- ajustes de posição sustentados por documentos quando houver split, grupamento, bonificação, conversão ou mudança de ticker;
- SHA-256 dos documentos-fonte e dos arquivos normalizados consumidos;
- revisão identificada da normalização e da cobertura, posterior ao fim do período.

O fluxo documental falha se houver lacuna de cobertura, hash divergente, boundary incompatível, venda acima da posição reconstruída ou diferença de caixa/posição além da tolerância definida.

## 5. Custos recorrentes e eventos não suportados

O perfil `data/fees/broker_profile.example.json` é apenas um modelo e vem como `unverified` de propósito. Mudar manualmente a palavra para `broker_certified` não constitui evidência.

Para corretagem fixa, o perfil também precisa informar a unidade real de cobrança. O motor certificado suporta a semântica `per_market_order_leg`; uma quantidade como 150 ações pode gerar 100 no `010` e 50 no `020`, portanto duas cobranças fixas quando a corretora efetivamente cobrava por cada uma dessas ordens/pernas. Outra semântica fica bloqueada em vez de ser aproximada.

Se a corretora efetivamente cobrou uma taxa recorrente que o motor contrafactual ainda não debita, o replay certificado deve falhar em vez de assumir zero. Do mesmo modo, conversões societárias com componente em dinheiro ou tratamento fiscal especial permanecem bloqueadas até existir implementação e evidência adequadas.

## 6. Como interpretar os resultados

Use esta hierarquia:

1. **Pesquisa retrospectiva** — comparação de hipóteses; não é uma conta real.
2. **Simulação realista** — modela mecânica de caixa, execução, custos, impostos e eventos, com limitações explicitadas no relatório.
3. **CERTIFIED_DETERMINISTIC_OFFICIAL_OPEN_REPLAY** — replay público determinístico e fail-closed, ainda sem prova de fill hipotético.
4. **ACTUAL_BROKERAGE_ACCOUNT_EXACT_RECONCILIATION** — reconciliação documental de uma conta de corretora real.
5. **Situação tributária/patrimonial total do CPF** — fora do alcance de uma conta isolada, salvo se todo o contexto pessoal relevante for fornecido e auditado separadamente.

A regra do projeto permanece: **dado ausente não vira suposição silenciosa, e hipótese contrafactual não vira fill real por mudança de nome**.

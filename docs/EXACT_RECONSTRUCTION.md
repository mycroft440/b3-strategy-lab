# Reconstrução estrita de investimento real

O projeto separa alegações que parecem semelhantes, mas não são equivalentes. A regra central é: **um dado que não pode ser provado não recebe o rótulo de exato**.

## 1. Pesquisa retrospectiva

A matriz ampla serve para comparar estratégias e gerenciamentos. Ela pode descobrir hipóteses interessantes, mas não prova que a regra vencedora teria sido escolhida naquela época e não deve ser apresentada como reconstrução exata de uma conta real.

## 2. Replay determinístico certificado com dados públicos

```bash
python scripts/run_exact_realistic_reconstruction.py --broker-profile <arquivo.json>
```

O nome do arquivo foi mantido por compatibilidade. O runner público **não emite mais um rótulo de fill exato**. Quando todos os gates passam, a classificação é:

`CERTIFIED_DETERMINISTIC_OFFICIAL_OPEN_REPLAY`

Ela significa que os dados e a regra contrafactual foram endurecidos e auditados para executar de forma determinística sob a hipótese declarada de abertura oficial. Ela **não prova** que uma ordem hipotética teria recebido exatamente aquele fill na fila/leilão real.

Os gates incluem:

- universo histórico B3 reconstruído point-in-time a partir do mercado completo, sem filtro de sobrevivência futura;
- sinais calculados somente com informações disponíveis até o fechamento da decisão;
- execução na abertura seguinte, usando preços oficiais separados dos mercados 010 e 020;
- dimensionamento de quantidade baseado nas próprias pernas executáveis 010/020, sem usar o preço do lote padrão como proxy para uma ordem fracionária;
- nenhuma substituição silenciosa do mercado fracionário pelo preço do lote padrão;
- slippage modelado igual a zero no replay certificado: a hipótese é explicitamente a abertura oficial, não uma estimativa de impacto;
- splits e mudanças de ticker somente quando o tratamento é determinístico. Conversões não 1:1 ou com componente em dinheiro falham até existir regra fiscal explicitamente implementada e testada;
- desaparecimentos históricos precisam ser resolvidos por evidência ou o processo falha;
- dividendos e JCP precisam estar cobertos por ledger certificado ou o processo falha;
- tarifa B3 e perfil de tarifa da corretora precisam estar documentados para todo o período;
- conta tributária de operações em ações isolada das demais operações de bolsa definidas no perfil, sem prejuízo fiscal inicial não documentado;
- IRRF de operações comuns é tratado como antecipação, com crédito fiscal;
- imposto mensal de bolsa é apurado causalmente; o DARF fica como passivo conhecido e, no modo realista, é pago no vencimento modelado, sem permitir que o backtest gaste caixa já reservado para a obrigação;
- DARF inferior a R$10 é acumulado até atingir o mínimo de pagamento;
- após o replay certificado, patrimônio, vendas em um único dia e vendas agregadas no mês precisam permanecer dentro do envelope conservador de R$20.000. Nessa faixa, vendas mensais de ações permanecem dentro da isenção do ganho líquido e o IRRF teórico de 0,005% não supera R$1.

Mesmo dentro desse envelope, o replay certificado continua sendo **contrafactual**: ele não possui uma confirmação de ordem/fill de uma corretora para uma operação que nunca aconteceu.

## 3. Tributação pessoal de 2026 em diante

A partir do ano-calendário de 2026 existe também a tributação mínima anual de altas rendas. Sua apuração depende da soma de rendimentos e impostos da pessoa física como um todo, não apenas desta conta de corretora.

Por isso, os relatórios realistas expõem:

- `brokerage_final_equity`: saldo marcado a mercado da conta simulada na data final;
- `outstanding_accrued_tax_liability`: obrigação de bolsa já conhecida, mas ainda não paga na data final;
- `net_equity_after_accrued_tax`: saldo da corretora menos esse passivo conhecido;
- `ordinary_irrf_withheld`: IRRF de operações comuns efetivamente retido no replay;
- `darf_paid`: DARF efetivamente debitado até a data final;
- `cpf_wide_annual_minimum_tax_scope = OUT_OF_SCOPE`.

O último campo é deliberado. Salário, aluguel, outros dividendos, outras carteiras e demais rendimentos do CPF não podem ser inferidos do COTAHIST ou do extrato isolado desta estratégia. O software não inventa esse contexto.

## 4. Reconciliação exata da conta da corretora

A palavra **exato** fica reservada ao fluxo documental:

`scripts/reconcile_actual_personal_account.py`

O selo aprovado nesse fluxo é limitado a:

`ACTUAL_BROKERAGE_ACCOUNT_EXACT_RECONCILIATION`

Ele significa que o razão da **conta da corretora** fecha contra documentos reais. Não significa que todo o patrimônio pessoal ou a declaração anual do CPF foram reconstruídos.

Para esse selo são necessários, entre outros:

- snapshots documentais de abertura `START_OF_DAY` e fechamento `END_OF_DAY`;
- notas de corretagem, confirmações de ordens/fills ou extratos que sustentem cada execução;
- extratos de conta cobrindo continuamente a janela reconciliada;
- ledger de caixa completo com taxas, impostos debitados na conta, dividendos, JCP, depósitos e saques;
- ajustes de posição sustentados por documentos quando houver split, grupamento, bonificação, conversão ou mudança de ticker;
- SHA-256 dos documentos-fonte e dos arquivos normalizados consumidos;
- revisão identificada da normalização e da cobertura, posterior ao fim do período.

O fluxo documental falha se houver lacuna de cobertura, hash divergente, boundary incompatível, venda acima da posição reconstruída ou diferença de caixa/posição além da tolerância definida.

## 5. Custos recorrentes e eventos não suportados

O perfil `data/fees/broker_profile.example.json` é apenas um modelo e vem como `unverified` de propósito. Mudar manualmente a palavra para `broker_certified` não constitui evidência.

Se a corretora efetivamente cobrou uma taxa recorrente que o motor contrafactual ainda não debita, o replay certificado deve falhar em vez de assumir zero. Do mesmo modo, conversões societárias com componente em dinheiro ou tratamento fiscal especial permanecem bloqueadas até existir implementação e evidência adequadas.

## 6. Como interpretar os resultados

Use esta hierarquia:

1. **Pesquisa retrospectiva** — comparação de hipóteses; não é uma conta real.
2. **Simulação realista** — modela mecânica de caixa, execução, custos, impostos e eventos, com limitações explicitadas no relatório.
3. **CERTIFIED_DETERMINISTIC_OFFICIAL_OPEN_REPLAY** — replay público determinístico e fail-closed, ainda sem prova de fill hipotético.
4. **ACTUAL_BROKERAGE_ACCOUNT_EXACT_RECONCILIATION** — reconciliação documental de uma conta de corretora real.
5. **Situação tributária/patrimonial total do CPF** — fora do alcance de uma conta isolada, salvo se todo o contexto pessoal relevante for fornecido e auditado separadamente.

A regra do projeto permanece: **dado ausente não vira suposição silenciosa, e hipótese contrafactual não vira fill real por mudança de nome**.

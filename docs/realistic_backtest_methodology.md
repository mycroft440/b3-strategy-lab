# Backtest realista e reconstrução de conta

Este caminho existe para responder uma pergunta diferente da matriz retrospectiva:

> Se uma regra já estivesse definida e R$ 1.000 fossem investidos usando somente
> informações disponíveis em cada data, qual patrimônio seria economicamente
> plausível até a última sessão certificada?

Os relatórios antigos continuam preservados para reprodução de pesquisa. Eles não
são sobrescritos nem renomeados como resultados reais.

## Contrato do caminho realista

O pipeline `scripts/run_realistic_pipeline.py` aplica, em ordem:

1. universo semanal **point-in-time**, construído do COTAHIST completo sem exigir
   que a ação sobreviva ou permaneça líquida em anos futuros;
2. dados oficiais B3 para todos os símbolos que entram em algum snapshot;
3. reconciliação fail-closed de splits/grupamentos/bonificações;
4. preços de abertura separados para mercado padrão (`010`, BDI `02`) e
   fracionário (`020`, BDI `96`);
5. sinais no fechamento e execução somente na abertura de rebalanceamento seguinte;
6. quantidade inteira de ações, caixa real e preço médio fiscal;
7. tarifas por data, corretagem configurável e slippage dependente da participação
   no volume financeiro do mercado usado na execução;
8. dividendos/JCP com direito capturado na última data com direito e crédito na
   data de pagamento;
9. tributação mensal de operações comuns, limite de vendas para isenção, prejuízo
   acumulado, reserva fiscal no próprio caixa e retenção de JCP por data;
10. reconciliação de mudança de ticker por mesma ISIN e bloqueio de desaparecimentos
    históricos ainda não explicados por fonte primária;
11. comparação de Gap Momentum bruto contra Gap Momentum com remoção do componente
    mecânico de proventos na abertura ex, convertido para a mesma base normalizada
    por splits usada pelo sinal;
12. validação walk-forward com cada ano de teste totalmente fora da seleção, com
    opção de repetir o escopo completo de estratégias e gerenciamentos.

## Universo point-in-time

Execute:

```powershell
python scripts\build_point_in_time_universe.py --download
```

Por padrão, cada decisão semanal usa somente as 252 sessões anteriores, exige
90% de presença nesse intervalo e seleciona as 40 ações/units de companhias com
maior volume financeiro médio, sem filtro de continuidade para anos futuros.

O filtro de universo usa o mercado padrão/BDI de ações e especificações `ON`, `PN`
ou `UNT`. ETFs e outros instrumentos que não são ações/units de companhias não
entram por essa regra. Para execução, o construtor lê separadamente o COTAHIST do
mercado fracionário usando `market_type=020` e `BDI=96`; manter o BDI `02` do lote
padrão nesse parser produziria um livro fracionário vazio.

Saídas:

- `data/universes/point_in_time_weekly.csv`
- `data/universes/point_in_time_union.json`
- `data/execution/b3_standard_fractional_open.csv`

## Ações corporativas e proventos

Execute o entry point realista:

```powershell
python scripts\sync_point_in_time_universe_realistic.py --download --refresh-actions
```

O sincronizador usa o coletor não destrutivo em
`b3_strategy_lab/cash_distributions.py`. A identidade de um evento inclui ticker,
ISIN, data-com, data de pagamento, tipo e valor por ação. Assim, parcelas com a
mesma data-com/tipo/valor, mas pagamentos em datas diferentes, não são colapsadas
indevidamente.

O sincronizador não infere automaticamente um split para fazer a curva ficar
bonita. Se houver marcador de mudança de quantidade no COTAHIST sem evidência
primária coberta, a construção é interrompida e o problema é gravado em:

`reports/point_in_time_missing_split_evidence.json`.

Dividendos e JCP são extraídos do cadastro oficial de companhias da B3 e ficam em
um ledger separado. A ausência de erro na resposta da B3 **não é, sozinha, prova
de cobertura histórica completa**. Para uma afirmação exata, o auditor exige uma
certificação de cobertura independente em:

`data/corporate_actions/cash_distribution_coverage_certification.json`.

Sem essa certificação, os números podem ser usados como estimativa, mas nunca
rotulados como reconstrução exata da conta. O resumo propaga essa condição no
campo `cash_events_complete`; ele só pode ser `true` quando a certificação cobre
toda a janela efetivamente simulada e declara uma autoridade aceita. A
certificação também precisa identificar o revisor, listar evidências primárias,
cobrir exatamente os ativos usados e corresponder aos hashes do CSV de eventos e
de seu manifesto.

## Mercado fracionário

Uma ordem de 114 ações é tratada como duas pernas quando necessário:

- 100 ações no mercado padrão (`010`, BDI `02`);
- 14 ações no mercado fracionário (`020`, BDI `96`).

Se a abertura fracionária não existir, o motor interrompe o rebalanceamento; ele
não substitui silenciosamente a cotação fracionária pela abertura do lote padrão.
Isso é especialmente importante para uma conta iniciada com R$ 1.000.

## Custos e slippage

`data/fees/b3_equity_fee_schedule.json` contém regras temporais. A tabela atual é
marcada como `modeled` porque, embora existam referências primárias para a mudança
de 0,0325% para 0,0300% em 02/02/2021 e para a tarifa atual, ainda falta reconciliar
cada componente histórico específico do leilão de abertura e a corretagem pessoal.

Por isso, enquanto qualquer regra permanecer `modeled`, o resumo recebe o aviso
`MODELED_FEES` e não pode ser usado como valor pessoal exato.

O slippage é calculado por perna usando o volume financeiro daquele mercado. A
participação da ordem aumenta o slippage até um teto configurável.

## Tributação

O ledger mantém preço médio por ativo, ganho realizado, vendas mensais e prejuízo
acumulado. A modelagem padrão de operações comuns usa:

- alíquota ordinária de 15% quando tributável;
- isenção de ganho em ações quando as vendas mensais elegíveis não excedem
  R$ 20.000;
- compensação de perdas anteriores contra ganhos tributáveis;
- retenção de JCP de 15% até 2025 e 17,5% a partir de 01/01/2026;
- dividendos pagos em 2026 ou depois acima de R$ 50 mil no mesmo mês pelo mesmo
  pagador ficam **fail-closed** quando o ledger não informa se a parcela está
  abrangida por regra transitória/grandfathering: o motor não aplica 10% às cegas.

Depois de vendas tributáveis, o simulador calcula uma reserva provisória de IR do
mês e reduz o caixa disponível para novas compras. Uma perda realizada mais tarde
no mesmo mês reduz essa reserva; prejuízos acumulados de meses anteriores também
são considerados. Isso impede que a estratégia reinvista dinheiro que já está
economicamente comprometido com imposto e depois dependa de um aporte externo
para pagar o tributo.

O objetivo é medir o ônus econômico. O motor não tenta reproduzir o calendário de
DARF/IRRF de uma corretora específica centavo a centavo.

## Mudanças de ticker e delistagens

Execute:

```powershell
python scripts\build_ticker_transitions.py --download
```

Apenas continuidade de **mesma ISIN** é autoaprovada como troca 1:1 de ticker.
Qualquer símbolo que desapareça sem sucessor inequívoco fica em:

`reports/unresolved_historical_delistings.csv`.

Se uma posição estiver aberta quando faltar uma cotação fresca e não existir um
evento de transição/cash-out explícito, o backtest falha. Nunca há `forward-fill`
do último preço para esconder uma delistagem ou suspensão.

## Auditoria dos inputs

Execute:

```powershell
python scripts\audit_realistic_backtest_inputs.py
```

O relatório distingue:

- `ready_for_realistic_estimate`: dados estruturais suficientes para uma estimativa;
- `ready_for_exact_historical_account_claim`: cobertura forte o bastante para dizer
  que o saldo reconstrói exatamente uma conta histórica.

O segundo exige, além do primeiro:

- proventos com cobertura histórica certificada;
- nenhum desaparecimento histórico não resolvido;
- todas as tarifas temporais marcadas como oficiais.

## Backtest de R$ 1.000

```powershell
python scripts\backtest_strategy_management_realistic.py --initial-cash 1000
```

O pipeline completo roda duas variantes:

```powershell
python scripts\run_realistic_pipeline.py --download --refresh-actions --initial-cash 1000
```

Para iniciar por interface, dê dois cliques em `abrir_painel_realista.bat` no
Windows ou execute `./abrir_painel_realista.sh` no Linux/macOS.

Ele produz Gap Momentum com o gap bruto e com o componente conhecido de provento
removido do gap de sinal. Como os candles do sinal são normalizados por splits, o
valor nominal do provento é multiplicado pelo `adjustment_factor` daquele candle
antes de ser removido do gap. Divergência grande entre os dois resultados é um
alerta de dependência da mecânica ex-provento.

O replay contínuo de 2018 é explicitamente rotulado como
`retrospective_hypothesis_replay`: ele responde ao contrafactual “e se esta regra,
que hoje conhecemos, já tivesse sido seguida?”, mas não prova que a regra teria
sido escolhida em 2018 sem olhar o futuro.

## Walk-forward

A validação da hipótese Gap Momentum congelada contra todos os gerenciamentos usa:

```powershell
python scripts\walk_forward_realistic.py --initial-cash 1000
```

Para enfrentar também o viés de ter escolhido a melhor entre todo o catálogo de
estratégias, use o escopo completo:

```powershell
python scripts\walk_forward_realistic.py --initial-cash 1000 --all-strategies
```

ou, no pipeline:

```powershell
python scripts\run_realistic_pipeline.py --initial-cash 1000 --walk-forward-all-strategies
```

O relatório grava `selection_scope`, quantidades de estratégias/gerenciamentos e
`full_multiple_testing_scope`. Portanto uma execução limitada ao Gap Momentum não
pode ser apresentada como se tivesse corrigido a seleção histórica entre todas as
estratégias.

Para cada ano de teste, a combinação é escolhida somente no histórico anterior e
o fold de teste é rotulado como `walk_forward_out_of_sample`. Os folds usam contas
padronizadas independentes. Os retornos anuais não são multiplicados para fingir
uma única conta contínua, porque lote inteiro, mercado fracionário, limite mensal
de vendas e prejuízos fiscais tornam essa multiplicação economicamente incorreta.

A metodologia realista foi congelada em 19/08/2026 antes da geração dos novos
resultados. Dados posteriores podem fornecer validação prospectiva desde que as
regras congeladas não sejam reotimizadas.

## Critério para uma afirmação final

Qualidade da reconstrução da conta e evidência de seleção da estratégia são duas
alegações diferentes. Mesmo com inputs perfeitos, um replay 2018–2026 da estratégia
vencedora continua retrospectivo quanto à escolha da regra.

Só é permitido escrever algo equivalente a:

> "R$ 1.000, condicionados a esta regra já estar escolhida, teriam se transformado
> em aproximadamente R$ X nesta data"

quando o relatório de auditoria estiver `ready_for_exact_historical_account_claim=true`.

Se apenas `ready_for_realistic_estimate=true`, a formulação correta é:

> "Sob estas premissas e com estas limitações certificadas, a estimativa simulada
> é R$ X; ela ainda não é uma reconstrução exata da conta da corretora."

Para afirmar que a **escolha da estratégia** também teria sido válida sem hindsight,
use `full_multiple_testing_scope=true` no walk-forward ou a validação prospectiva
posterior ao congelamento.

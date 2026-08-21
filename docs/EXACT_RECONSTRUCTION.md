# Reconstrução estrita de investimento real

O projeto separa três alegações diferentes e não permite tratá-las como equivalentes.

## 1. Pesquisa retrospectiva

A matriz ampla serve para comparar estratégias e gerenciamentos. Ela não prova que a regra vencedora teria sido escolhida naquela época e não deve ser apresentada como reconstrução exata de uma conta real.

## 2. Replay condicional estrito

`python scripts/run_exact_realistic_reconstruction.py --broker-profile <arquivo.json>`

Esse modo só conclui com `EXACT_CONDITIONAL_OFFICIAL_OPEN_REPLAY` quando todos os gates abaixo passam:

- universo histórico B3 reconstruído point-in-time a partir do mercado completo, sem filtro de sobrevivência futura;
- sinais calculados somente com informações disponíveis até o fechamento da decisão;
- execução na abertura seguinte, usando preços oficiais separados dos mercados 010 e 020;
- nenhuma substituição silenciosa do mercado fracionário pelo preço do lote padrão;
- slippage modelado igual a zero: a política testada é explicitamente uma ordem a mercado para a abertura oficial;
- splits, mudanças de ticker e desaparecimentos históricos resolvidos ou o processo falha;
- dividendos e JCP cobertos por ledger certificado ou o processo falha;
- tarifa de negociação/liquidação B3 oficial e perfil de tarifa da corretora documentado para todo o período;
- conta tributária isolada, sem outras operações em ações e sem prejuízo fiscal anterior;
- taxas recorrentes da corretora/custódia precisam ser documentalmente zero. Se forem diferentes de zero, o modo estrito bloqueia até que o motor passe a debitá-las explicitamente;
- após o replay, patrimônio, vendas de um único dia e vendas agregadas no mês precisam permanecer dentro do envelope conservador de R$20.000. Se o patrimônio ou o giro ultrapassarem esse limite, o resultado continua disponível como simulação realista, mas perde a classificação estrita até que IRRF/DARF, custódia e tarifas por faixa sejam reconstruídos em detalhe.

O arquivo `data/fees/broker_profile.example.json` é somente um modelo de preenchimento. Ele vem marcado como `unverified` de propósito. Alterar manualmente a palavra para `broker_certified` sem evidência não transforma uma hipótese em dado certificado.

## 3. Reconstrução exata de uma conta pessoal

Uma conta pessoal real possui uma camada que o mercado público não consegue reconstruir sozinho. Para afirmar que o saldo é exatamente o que teria aparecido em uma corretora específica, são necessários também:

- notas de corretagem ou confirmações de ordens/fills;
- extratos de caixa da corretora;
- tarifas, custódia e mensalidades efetivamente cobradas;
- contexto tributário do CPF, caso existissem outras operações em ações;
- qualquer ajuste manual, transferência, aporte ou retirada da conta.

Sem esses documentos, o nível máximo permitido pelo software é o **replay condicional estrito**: uma resposta exata para a pergunta contrafactual definida pela própria política de execução (regra congelada + ordem a mercado na abertura oficial + custos certificados), e não uma afirmação sobre fills pessoais que nunca ocorreram.

## Fluxo recomendado

1. Copie `data/fees/broker_profile.example.json` para um novo arquivo e preencha somente com tarifas comprovadas.
2. Execute o runner estrito sem `--skip-data-build` para reconstruir o universo histórico completo e atualizar eventos oficiais.
3. Leia `reports/exact_reconstruction_status.json`.
4. Somente aceite o resultado como replay condicional estrito quando `conditional_rule_based_reconstruction_exact` for `true` e `strict_blockers` estiver vazio.
5. Para uma conta pessoal, confronte o ledger gerado em `reports/exact_reconstruction_trades.csv`, `reports/exact_reconstruction_distributions.csv` e `reports/exact_reconstruction_tax.csv` com os documentos da corretora.

A regra do projeto é simples: **dado ausente não vira suposição silenciosa**. Um requisito não comprovado bloqueia a palavra “exato”.

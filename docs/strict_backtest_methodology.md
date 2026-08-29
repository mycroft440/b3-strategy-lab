# Backtest estrito de estrategia + gerenciamento

O arquivo `scripts/backtest_strategy_management_strict.py` existe para separar duas coisas que antes apareciam misturadas:

1. **pesquisa retrospectiva**: comparar muitas estrategias e gerenciamentos no mesmo historico;
2. **validacao**: escolher uma combinacao somente em um periodo de treino e medir o resultado em datas que nao participaram da escolha.

Os rankings historicos da matriz completa continuam preservados para reproducao. Eles nao devem ser tratados como resultado fora da amostra porque a combinacao vencedora foi escolhida usando o periodo completo.

## Correcoes do motor estrito

O motor estrito aplica estas regras:

- usa apenas a **intersecao das sessoes** presentes em todos os ativos, em vez da uniao de datas;
- nao usa `last_price` como substituto silencioso para uma abertura ausente;
- um rebalanceamento e **atomico**: se faltar a abertura de qualquer posicao que precisa ser vendida ou de qualquer alvo que precisa ser comprado, nenhuma perna da troca e executada;
- a carteira e marcada a mercado somente com fechamento fresco da sessao corrente; uma posicao sem fechamento valido gera erro em vez de permanecer valorizada indefinidamente por preco antigo;
- o gerenciamento escolhe e pondera a cesta no fechamento anterior a cada rebalanceamento;
- dentro da cesta designada, cada mudanca do sinal binario da estrategia e executada na abertura seguinte, sem reranquear ativos entre rebalanceamentos;
- quando o inicio do teste coincide com uma fronteira de rebalanceamento, a decisao usa o fechamento comum imediatamente anterior e executa na primeira abertura do periodo;
- custos e slippage sao debitados diretamente do caixa e gravados separadamente;
- caixa negativo, quantidade negativa e estados nao finitos provocam rollback do rebalanceamento;
- o vencedor e ranqueado **somente no treino**; o periodo de teste nao participa da escolha;
- o ledger de trades do vencedor do treino e salvo para auditoria manual.

## Uso recomendado

Por padrao:

- pesquisa/treino: `2018-01-02` ate `2022-12-29`;
- holdout: `2023-01-02` ate o ultimo pregao comum disponivel;
- custos: 3,2 bps por lado;
- slippage: 10 bps por lado;
- lote: 1 acao.

Execute:

```powershell
python scripts\backtest_strategy_management_strict.py
```

Para testar somente Gap Momentum contra todos os gerenciamentos:

```powershell
python scripts\backtest_strategy_management_strict.py --strategies gap_momentum
```

Para usar custos diferentes:

```powershell
python scripts\backtest_strategy_management_strict.py --cost-bps 5 --slippage-bps 20
```

Resultados principais:

- `reports/strict_holdout_strategy_management.csv`
- `reports/strict_holdout_winner_ledger.csv`

## Viés de universo que ainda permanece

O manifesto atual `data/universes/fixed_40_2018.json` declara `survivorship_safe=false`.

As 30 adicoes foram escolhidas usando liquidez do ano completo de 2018 e um filtro de continuidade posterior. Por isso:

- 2018 nao e um periodo limpo de validacao do universo;
- o universo so poderia ser conhecido, no minimo, depois do encerramento de 2018;
- a exigencia de continuidade ate anos posteriores ainda introduz viés de sobrevivencia.

O script grava isso explicitamente no campo `validity` como `OUT_OF_SAMPLE_SELECTION__BIASED_UNIVERSE` enquanto `survivorship_safe` permanecer falso.

Eliminar esse ultimo viés exige reconstruir, para cada data historica, o conjunto investivel usando somente informacao que existia naquele momento, incluindo empresas que posteriormente sairam da bolsa, mudaram ticker, entraram em recuperacao ou deixaram de atender aos filtros atuais.

## Interpretacao

Um retorno alto no ranking historico das 111.852 combinacoes atuais continua sendo util como **descoberta de hipotese**, mas nao como estimativa confiavel do que teria sido obtido ao vivo.

O resultado de maior interesse passa a ser o `test_*` do script estrito, porque a escolha da estrategia e do gerenciamento foi congelada antes do inicio do holdout. Mesmo esse resultado deve carregar o aviso de viés de universo ate existir um universo historico point-in-time.

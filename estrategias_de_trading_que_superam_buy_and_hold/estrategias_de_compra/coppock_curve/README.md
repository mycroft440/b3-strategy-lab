# coppock_curve

Familia: momentum

## Como funciona

Coppock: compra a inflexao negativa para cima e sai na inflexao positiva.

## Configuracao

```text
short_roc=11;long_roc=14;wma_period=10
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

# trix_signal

Familia: momentum

## Como funciona

TRIX: cruzamento da variacao da tripla EMA contra sua linha de sinal.

## Configuracao

```text
period=15;signal_period=9
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

# true_strength_index

Familia: momentum

## Como funciona

True Strength Index: momentum duplamente suavizado contra a linha de sinal.

## Configuracao

```text
long_period=25;short_period=13;signal_period=7
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

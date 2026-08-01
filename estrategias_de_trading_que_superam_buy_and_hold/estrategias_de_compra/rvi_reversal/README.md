# rvi_reversal

Familia: reversao

## Como funciona

Reversao por cruzamento do Relative Vigor Index apos fraqueza extrema.

## Configuracao

```text
period=10;entry_level=-0.4;exit_level=0.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

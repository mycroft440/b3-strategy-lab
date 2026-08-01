# fisher_transform_reversal

Familia: reversao

## Como funciona

Fisher Transform: compra a virada na sobrevenda e sai na virada da sobrecompra.

## Configuracao

```text
period=10;lower=-1.5;upper=1.5
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

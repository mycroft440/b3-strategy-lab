# ease_of_movement

Familia: volume

## Como funciona

Ease of Movement suavizado: comprado quando preco e volume favorecem alta.

## Configuracao

```text
period=14
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

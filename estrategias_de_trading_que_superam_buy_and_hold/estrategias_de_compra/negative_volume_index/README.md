# negative_volume_index

Familia: volume

## Como funciona

Negative Volume Index de Fosback acima de sua EMA anual.

## Configuracao

```text
ema_period=255
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

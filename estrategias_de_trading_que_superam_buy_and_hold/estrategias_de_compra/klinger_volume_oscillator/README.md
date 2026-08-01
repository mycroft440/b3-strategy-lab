# klinger_volume_oscillator

Familia: volume

## Como funciona

Klinger Volume Oscillator acima da EMA de sinal.

## Configuracao

```text
fast_period=34;slow_period=55;signal_period=13
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

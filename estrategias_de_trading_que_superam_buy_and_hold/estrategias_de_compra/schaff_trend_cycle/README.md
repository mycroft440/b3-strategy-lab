# schaff_trend_cycle

Familia: momentum

## Como funciona

Schaff Trend Cycle: ciclo estocastico duplo do MACD com zonas de histerese.

## Configuracao

```text
fast_period=23;slow_period=50;cycle_period=10;smoothing=0.5;lower=25.0;upper=75.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

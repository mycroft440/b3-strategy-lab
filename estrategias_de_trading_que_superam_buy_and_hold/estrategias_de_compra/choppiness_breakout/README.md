# choppiness_breakout

Familia: volatilidade

## Como funciona

Rompimento depois que o Choppiness Index sai de compressao para tendencia.

## Configuracao

```text
period=14;high_level=61.8;low_level=38.2;trend_window=20;atr_period=14;atr_mult=3.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

# squeeze_breakout

Familia: rompimento

## Como funciona

Rompimento altista apos Bollinger comprimir dentro do canal de Keltner.

## Configuracao

```text
window=20;num_std=2.0;atr_period=20;keltner_mult=1.5;squeeze_bars=3;atr_mult=3.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

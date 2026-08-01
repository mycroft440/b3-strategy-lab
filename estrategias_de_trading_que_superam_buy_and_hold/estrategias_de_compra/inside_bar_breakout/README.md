# inside_bar_breakout

Familia: price_action

## Como funciona

Inside Bar: rompe a maxima da barra-mae com saidas objetivas.

## Configuracao

```text
expiry=5;atr_period=14;atr_mult=3.0;hold_limit=20
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

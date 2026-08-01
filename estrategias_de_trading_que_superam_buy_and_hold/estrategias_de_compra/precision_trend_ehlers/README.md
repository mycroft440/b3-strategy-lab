# precision_trend_ehlers

Familia: tendencia

## Como funciona

Precision Trend de Ehlers: compra no ROC positivo do filtro e sai no ROC negativo.

## Configuracao

```text
long_period=250;short_period=40
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

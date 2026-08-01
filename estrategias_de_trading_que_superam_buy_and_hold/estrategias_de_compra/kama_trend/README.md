# kama_trend

Familia: tendencia

## Como funciona

Tendencia por KAMA de Kaufman com confirmacao simultanea de preco e inclinacao.

## Configuracao

```text
er_period=10;fast_period=2;slow_period=30
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

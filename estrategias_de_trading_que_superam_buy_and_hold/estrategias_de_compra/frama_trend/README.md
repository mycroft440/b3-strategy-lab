# frama_trend

Familia: tendencia

## Como funciona

Tendencia pela media fractal adaptativa FRAMA de Ehlers.

## Configuracao

```text
window=16
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

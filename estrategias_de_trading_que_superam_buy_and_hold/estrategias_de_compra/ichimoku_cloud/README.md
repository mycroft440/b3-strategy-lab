# ichimoku_cloud

Familia: tendencia

## Como funciona

Ichimoku causal: preco acima da nuvem e Tenkan acima da Kijun.

## Configuracao

```text
tenkan_period=9;kijun_period=26;span_b_period=52;displacement=26
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

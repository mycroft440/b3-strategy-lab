# parabolic_sar_trend

Familia: tendencia

## Como funciona

Parabolic SAR de Wilder: comprado apenas no estado ascendente.

## Configuracao

```text
af_step=0.02;af_max=0.2
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

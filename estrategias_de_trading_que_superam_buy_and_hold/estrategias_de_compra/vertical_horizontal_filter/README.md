# vertical_horizontal_filter

Familia: regime

## Como funciona

VHF: entra em tendencia altista direcional e sai quando o regime enfraquece.

## Configuracao

```text
period=28;entry_level=0.4;exit_level=0.25;trend_window=50
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

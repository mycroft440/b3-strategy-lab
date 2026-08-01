# elder_force_index

Familia: volume

## Como funciona

Force Index de Elder positivo com confirmacao da tendencia de preco.

## Configuracao

```text
period=13;trend_window=50
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

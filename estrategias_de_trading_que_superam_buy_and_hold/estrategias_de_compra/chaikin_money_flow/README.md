# chaikin_money_flow

Familia: volume

## Como funciona

Cruzamento positivo do Chaikin Money Flow com filtro opcional de tendencia.

## Configuracao

```text
period=21;trend_window=100
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

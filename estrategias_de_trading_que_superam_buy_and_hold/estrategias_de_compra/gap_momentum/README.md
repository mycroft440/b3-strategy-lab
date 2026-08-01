# gap_momentum

Familia: momentum

## Como funciona

Gap Momentum de Kaufman: compra quando a linha-sinal sobe e sai quando ela cai.

## Configuracao

```text
period=40;signal_period=20
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

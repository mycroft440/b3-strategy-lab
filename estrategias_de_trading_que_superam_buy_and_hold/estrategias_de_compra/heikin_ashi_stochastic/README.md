# heikin_ashi_stochastic

Familia: combinada

## Como funciona

Reversao Heikin-Ashi confirmada por cruzamento estocastico em zona extrema.

## Configuracao

```text
k_period=14;slowing=3;d_period=3;lower=20.0;upper=80.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

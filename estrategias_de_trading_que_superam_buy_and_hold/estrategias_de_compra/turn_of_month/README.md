# turn_of_month

Familia: sazonalidade

## Como funciona

Janela sazonal do ultimo pregao ate o terceiro pregao do mes seguinte.

## Configuracao

```text
sessions_before=1;sessions_after=3
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

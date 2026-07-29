# ibs_reversion

Familia: reversao

## Como funciona

Reversao curta por Internal Bar Strength.

## Configuracao

```text
ibs_lower=0.2;ibs_upper=0.8;max_hold=3;trend_window=0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

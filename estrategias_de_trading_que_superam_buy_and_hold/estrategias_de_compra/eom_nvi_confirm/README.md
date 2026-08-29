# eom_nvi_confirm

Familia: volume_hibrido

## Como funciona

Ease of Movement positivo com NVI acima da EMA.

## Configuracao

```text
eom_period=14;nvi_ema=100
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

# cmf_zero_cross

Familia: volume

## Como funciona

Comprado enquanto Chaikin Money Flow permanece positivo.

## Configuracao

```text
period=21
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

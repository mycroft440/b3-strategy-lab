# typical_price_pullback

Familia: reversao

## Como funciona

Compra desconto do Typical Price contra sua media e sai na recuperacao.

## Configuracao

```text
period=50;pullback_pct=0.03
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

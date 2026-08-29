# efficiency_ratio_trend

Familia: tendencia

## Como funciona

Razao de eficiencia alta e direcao positiva para filtrar ruido lateral.

## Configuracao

```text
period=40;threshold=0.35
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

# know_sure_thing

Familia: momentum

## Como funciona

Know Sure Thing de Pring: quatro horizontes de ROC contra a linha de sinal.

## Configuracao

```text
roc1=10;roc2=15;roc3=20;roc4=30;sma1=10;sma2=10;sma3=10;sma4=15;signal_period=9
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

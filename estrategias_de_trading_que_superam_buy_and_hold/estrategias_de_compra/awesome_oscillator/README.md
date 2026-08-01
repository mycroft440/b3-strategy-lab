# awesome_oscillator

Familia: momentum

## Como funciona

Awesome Oscillator: momentum do preco mediano acima ou abaixo de zero.

## Configuracao

```text
fast_period=5;slow_period=34
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

# aroon_trend

Familia: tendencia

## Como funciona

Aroon: segue novas maximas e sai quando novas minimas dominam.

## Configuracao

```text
period=25;strong_level=70.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.

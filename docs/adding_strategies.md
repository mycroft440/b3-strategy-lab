# Adicionar estratégia ou indicador

Extensões locais ficam em um único arquivo:

`b3_strategy_lab/user_extensions.py`

O módulo é carregado automaticamente quando o catálogo de estratégias é
importado. Não é necessário editar o registro central, o CLI, o painel ou o
executor da matriz.

## Estratégia mínima

```python
from b3_strategy_lab.extensions import strategy


@strategy(
    "close_above_20",
    family="tendencia",
    description="Comprado quando o fechamento supera a média de 20 sessões.",
)
def close_above_20(candles, *, window: int = 20):
    signals = []
    for index, candle in enumerate(candles):
        if index + 1 < window:
            signals.append(0)
            continue
        average = sum(item.close for item in candles[index + 1 - window:index + 1]) / window
        signals.append(int(candle.close > average))
    return signals
```

O nome precisa ser único. A função recebe os candles e deve retornar exatamente
um sinal por candle. Parâmetros com valor padrão aparecem automaticamente no CLI
e são usados pela matriz.

## Indicador reutilizável

```python
from b3_strategy_lab.extensions import build_indicator, indicator, strategy


@indicator("close_change")
def close_change(candles, *, lookback: int = 1):
    values = [None] * len(candles)
    for index in range(lookback, len(candles)):
        values[index] = candles[index].close / candles[index - lookback].close - 1
    return values


@strategy(
    "positive_close_change",
    family="momentum",
    description="Comprado quando a variação do fechamento é positiva.",
)
def positive_close_change(candles, *, lookback: int = 1):
    values = build_indicator("close_change", candles, lookback=lookback)
    return [int(value is not None and value > 0) for value in values]
```

Indicadores também precisam devolver um valor por candle. Use `candle.volume` no
modo ajustado; ele já contém quantidade consolidada dos mercados `010+020` e é
normalizado inversamente pelos eventos de capital. O executor troca para
`raw_volume` junto com OHLC bruto quando o modo de sinal é `raw`.
Não acesse `raw_volume` diretamente numa extensão: isso ignora a base escolhida
pelo executor e o auditor recusará a estratégia.

## Verificação

Depois de salvar o arquivo, reinicie o painel/processo e execute:

```bash
python -m b3_strategy_lab list-strategies
python -m unittest discover -s tests -v
python scripts/audit_volume_indicators.py
```

Estratégias e indicadores registrados no arquivo do usuário são descobertos
automaticamente pelo auditor. Ele executa a versão completa e uma versão prefixada para
detectar uso de informação futura, além de conferir o tamanho das saídas.

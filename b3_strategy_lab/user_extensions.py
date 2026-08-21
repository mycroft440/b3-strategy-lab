"""Extensões locais carregadas automaticamente pelo catálogo.

Adicione funções decoradas com ``@strategy`` ou ``@indicator`` neste arquivo.
Não é necessário editar ``strategies.py`` nem qualquer registro central.

Exemplo:

    from .extensions import indicator, strategy

    @indicator("media_20")
    def media_20(candles):
        closes = [candle.close for candle in candles]
        return [None if i < 19 else sum(closes[i-19:i+1]) / 20 for i in range(len(candles))]

    @strategy(
        "preco_acima_media_20",
        family="tendencia",
        description="Comprado quando o fechamento supera a média de 20 sessões.",
    )
    def preco_acima_media_20(candles):
        media = media_20(candles)
        return [int(value is not None and candle.close > value) for candle, value in zip(candles, media)]
"""

# Este módulo fica intencionalmente vazio até o usuário adicionar extensões.

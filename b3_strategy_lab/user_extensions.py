"""Extensoes locais carregadas automaticamente pelo catalogo.

Adicione funcoes decoradas com ``@strategy`` ou ``@indicator`` neste arquivo.
Nao e necessario editar ``strategies.py`` nem qualquer registro central.

A biblioteca ``research_indicators`` e importada automaticamente para tornar
indicadores reutilizaveis disponiveis a qualquer estrategia de extensao.
"""

from . import research_indicators as _research_indicators  # noqa: F401
from .extensions import strategy as _register_strategy
from .indicator_strategies import INDICATOR_STRATEGIES as _INDICATOR_STRATEGIES
from .trend_strategies import TREND_STRATEGIES as _TREND_STRATEGIES

# Register the indicator-driven and trend-focused catalogs through the same
# extension API used by user strategies. This keeps strategies.py generic and
# makes every new engine immediately available to sweep_strategies() and
# portfolio_strategies().
for _item in (*_INDICATOR_STRATEGIES, *_TREND_STRATEGIES):
    _register_strategy(
        _item.name,
        family=_item.family,
        description=_item.description,
    )(_item.function)

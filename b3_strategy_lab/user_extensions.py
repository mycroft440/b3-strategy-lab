"""Extensoes locais carregadas automaticamente pelo catalogo.

Adicione funcoes decoradas com ``@strategy`` ou ``@indicator`` neste arquivo.
Nao e necessario editar ``strategies.py`` nem qualquer registro central.

A biblioteca ``research_indicators`` e importada automaticamente para tornar
indicadores reutilizaveis disponiveis a qualquer estrategia de extensao.
"""

from . import research_indicators as _research_indicators  # noqa: F401

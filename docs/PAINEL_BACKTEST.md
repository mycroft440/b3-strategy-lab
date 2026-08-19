# Painel de controle do backtest

O painel permite controlar o backtest sem editar Python manualmente.

## Abrir no Windows

Dê dois cliques em:

`abrir_painel_backtest.bat`

O navegador abrirá automaticamente em `http://127.0.0.1:8765`.

Também é possível iniciar pelo terminal:

```bash
python scripts/realistic_backtest_control_panel.py
```

## Controles

- marcar/desmarcar as ações que serão testadas;
- selecionar todas ou limpar a seleção;
- escolher data inicial e final;
- definir o capital inicial;
- escolher se os dados da B3 devem ser atualizados antes do teste;
- iniciar e interromper o backtest;
- acompanhar a etapa atual e o log;
- visualizar o patrimônio final e o retorno de `raw_gap` e `economic_gap`.

## Regras de segurança do universo

O painel só aceita ações existentes em `data/universes/fixed_40_2018.json`.

- BOAC34 permanece explicitamente excluída;
- não são adicionadas ações substitutas;
- qualquer ticker digitado ou enviado fora da lista permitida é recusado;
- se uma ação selecionada não estiver elegível em uma determinada semana, o teste segue apenas com as ações disponíveis naquela semana.

## Arquivos gerados

A seleção atual é salva temporariamente em:

`.cache/control_panel/selected_universe.json`

O log fica em:

`reports/control_panel_backtest.log`

O resumo final do painel fica em:

`reports/control_panel_realistic_pipeline_status.json`

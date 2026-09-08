# Execução, dados e validação do backteste

O motor realista congela quantidades no fechamento anterior. Preços ajustados
continuam servindo aos indicadores; quantidades e caixa usam preços históricos
por ação. O dimensionamento reserva custos conhecidos e o teto de slippage.
Um gap favorável não aumenta a quantidade enviada ao leilão. Caixa insuficiente,
referência ausente ou capacidade insuficiente reduzem/cancelam a ordem; o saldo
não executado expira. Lotes padrão e fracionários continuam separados.

O limite padrão é 1% do volume financeiro médio de sessões anteriores, cumulativo
por dia, ativo e mercado. `--max-causal-adv-participation` ajusta esse limite no
executor realista e no walk-forward certificado. O volume final do próprio dia
nunca determina a liquidez disponível na abertura. Uma fração do volume diário
é uma hipótese conservadora de capacidade, não uma prova de liquidez no leilão.
As ordens solicitadas, executadas e canceladas são exportadas em `*.orders.json`.

O replay certificado aceita custos adversos: os padrões são base de 10 bps,
mais impacto de 5 bps por 1% de participação, limitado a 100 bps. Esses parâmetros
são hipóteses configuráveis, não calibração empírica da conta do usuário. Compare
cenários mais caros e confronte os fills com notas de corretagem antes de escolher
os valores. Zerar custos permanece uma referência diagnóstica explícita.

`price_only` exclui dividendos/JCP e não substitui o motor realista. Seu lote agora
respeita o preço histórico bruto e aplica mudanças de quantidade por splits.
A matriz de combinações continua sendo triagem retrospectiva; a avaliação econômica
e fora da amostra deve usar o motor realista. O painel usa o universo histórico PIT,
preservando inclusive semanas em que nenhum ativo selecionado era elegível.

## CDI e período reservado

O coletor usa a [API SGS do Banco Central](https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json&dataInicial=01/01/2024&dataFinal=31/01/2024),
série 12 (% ao dia), e salva o CSV, as respostas originais e os hashes:

```powershell
python scripts/sync_cdi_benchmark.py --end 2026-08-19
python scripts/walk_forward_certified.py --end 2026-08-19 --benchmark-csv data/benchmarks/cdi.csv --objective excess_sharpe --holdout-start 2025-01-01
```

O segundo comando exige previamente os dados PIT e proventos certificados.
`--holdout-start` deve ser 1º de janeiro: esse ano e os posteriores nunca entram
no treino, mesmo nos folds seguintes. Sem essa opção, o treino segue uma janela
crescente. A escolha histórica de um cutoff não comprova que o pesquisador nunca
olhou esses dados; os relatórios não declaram seleção prospectiva.

`excess_sharpe` usa o excesso diário da carteira sobre o benchmark; `sharpe`
preserva a métrica legada contra zero, explicitamente identificada. Faltas no
benchmark bloqueiam a comparação. Dias bancários entre sessões da bolsa são
capitalizados. CDI é um índice bruto: ele não credita rendimento fictício ao caixa
da corretora nem representa automaticamente uma aplicação líquida de impostos.
Outra série de retorno total pode ser fornecida como CSV `date,return`, com retorno
diário decimal e cobertura completa. A carteira comparada já inclui seus custos.

## Proventos e eventos societários

`run_realistic_pipeline.py` usa `--mode maximum_fidelity` por padrão e exige
insumos certificados. `--mode research` permite apenas uma estimativa identificada;
não ignora documentos alterados ou erros estruturais. O término efetivamente
executado fica limitado ao período certificado, inclusive sem `--end` explícito.

O suplemento de [proventos históricos](../data/corporate_actions/HISTORICAL_CASH.md)
importa registros documentados de emissores antigos. Nenhum evento ou certificado
é fabricado quando a consulta atual da B3 não fornece o histórico.

Para frações de agrupamentos/desdobramentos e devoluções de capital em transições,
o executor e o walk-forward aceitam `--corporate-settlements registro.json`.
O JSON contém `schema_version: 1` e `events`. Cada evento exige:

- `ticker`, `isin`, `share_ratio`, `kind`;
- `announcement_date`, `effective_date`, `realization_date`, `payment_date` em ISO,
  nessa ordem temporal;
- `source_authority` (`B3`, `CVM`, `issuer`), `source_url` HTTPS,
  `source_document` relativo ao JSON, `source_sha256`, `source_reference`, `reviewed_by`.

Para `kind: fractional_sale`, use `quantity_event: split` ou `reverse_split` e
`price_per_fractional_share`: o preço obtido no leilão de frações, por ação inteira.
Esse preço só entra no resultado na data de realização. Antes, a fração é um direito
não negociável marcado pelo fechamento oficial; o dinheiro só fica disponível após
o pagamento. A realização usa o custo proporcional e a apuração comum de ações.
Bonificações e eventos com tratamento fiscal diferente exigem outra regra e ficam
bloqueados; não os rotule como splits para contornar esse limite.

Para `kind: return_of_capital`, use `cash_per_old_share`. A transição certificada
deve identificar outro ticker, a mesma razão/ISIN e o mesmo componente em dinheiro.
O valor reduz o custo fiscal e vira recebível até o pagamento. Valores acima do
custo, transições mistas com frações e outros tratamentos tributários continuam
bloqueados. O documento revisado deve sustentar a classificação fiscal fornecida.

Hashes comprovam os bytes usados, não o significado tributário dos documentos.
Os eventos suportados têm ledger separado e testes de conservação patrimonial,
datas de pagamento e ausência de uso antecipado do preço do leilão.

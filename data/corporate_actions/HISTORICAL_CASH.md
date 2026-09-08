# Proventos históricos com documentos

O sincronizador aceita `--cash-supplement caminho/registro.json` para dividendos e
JCP que faltam na consulta atual da B3. Não há eventos reais preenchidos
automaticamente: documentos oficiais de B3, CVM ou RI precisam ser obtidos e
conferidos. O hash confirma os bytes; a revisão humana confirma seu conteúdo.

O JSON usa `schema_version: 1`, uma lista `events` e uma lista não vazia
`coverage_reviews`. Cada registro das duas listas contém:

| Campo | Conteúdo |
| --- | --- |
| `ticker`, `isin` | Identidade exata presente no COTAHIST desse replay |
| `source_authority` | `B3`, `CVM` ou `issuer` |
| `source_url` | URL HTTPS oficial do documento; B3/CVM exigem domínio correspondente |
| `source_document` | Arquivo original relativo à pasta do JSON; caminhos externos são recusados |
| `source_sha256` | SHA256 dos bytes do arquivo original |
| `source_reference` | Página, tabela ou seção que sustenta o registro |

Cada item de `events` também contém `label` (`DIVIDENDO` ou `JCP`),
`announcement_date`, `last_date_prior`, `ex_date`, `payment_date` (datas ISO) e
`gross_per_share` (valor decimal bruto por ação como texto, sem ajuste retroativo).
A data-com e o ISIN devem coincidir com o COTAHIST; a data-ex deve coincidir com a
próxima sessão observada quando ela existir. O anúncio deve preceder ou coincidir
com a data-com. O pagamento não pode preceder a data-ex. A certificação existente
continua exigindo revisão de quando o anúncio/valor ficou publicamente disponível.

Cada item de `coverage_reviews` também contém `start`, `end`, `complete: true`,
`reviewed_by` e `event_count`. Use uma revisão por ticker/ISIN. `event_count` é o
número de eventos únicos documentados daquela identidade dentro do registro;
parcelas com pagamentos diferentes contam separadamente. Uma cobertura sem
proventos exige revisão explícita com contagem zero e documento correspondente.
Uma revisão parcial não elimina a pendência da fonte histórica ausente.

O registro deve corresponder ao universo e período do replay: tickers/ISINs
desconhecidos e eventos fora do horizonte são recusados. Para eliminar a pendência
de um emissor histórico, as revisões devem cobrir todos os seus ISINs e datas
observados no período. Não é suficiente adicionar um único dividendo conhecido.

Duplicatas exatas são fundidas; parcelas em datas distintas são preservadas.
Diferenças de valor ou data-ex para a mesma identidade B3/suplemento interrompem a
sincronização. Reconcilie os documentos antes de prosseguir, sem escolher o valor
que melhora o resultado. O CSV conserva as referências; o manifesto vincula o
registro e cada documento, e a auditoria volta a conferir seus bytes.

Fluxo de uso:

1. Prepare o universo e sincronize com
   `python scripts/sync_point_in_time_universe_realistic.py --cash-supplement caminho/registro.json`.
2. Faça a revisão de completude e temporalidade para todo o universo. Use
   `scripts/build_cash_distribution_coverage_certification.py --help` para os
   argumentos de emissão do certificado existente. Importar eventos não emite
   esse certificado nem declara completude de toda a base.
3. Execute `python scripts/run_realistic_pipeline.py --skip-data-build` para
   reutilizar os bytes certificados. O modo padrão `maximum_fidelity` exige a
   certificação dos insumos antes de executar carteiras. Reconstruir os arquivos
   invalida o certificado anterior e exige nova revisão/vinculação.
4. `--mode research` permite uma estimativa sem certificação completa, identificada
   nos relatórios por `fidelity_mode` e `research_estimate`. Erros de parsing,
   documentos alterados e fontes históricas ainda ausentes continuam bloqueando.

Sem os documentos ou a revisão de cobertura, o modo de máxima fidelidade permanece
bloqueado com as pendências na auditoria. Nunca trate fonte ausente como zero
proventos.

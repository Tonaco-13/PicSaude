# Relatório de Verificação Independente - Jules

**Objetivo:** Verificação independente de cada afirmação numérica feita sobre o código do projeto nas seções VI e VII (incluindo Table III) do artigo `docs/paper/CEBEB_PicSaude_IEEEtran.tex`.

## Tabela de Verificação

| # | Afirmação do paper | Valor Obtido | Veredito | Nota |
|---|---|---|---|---|
| 1 | ~31.700 linhas de código de aplicação | 31.737 | MATCH | Obtido executando `find backend/app -name "*.py" \| xargs wc -l`. |
| 2 | 32 routers | 32 | MATCH | Encontrados em `backend/app/routers/*.py`, excluindo `__init__.py`. |
| 3 | 43 models ORM | 43 | MATCH | Contagem de arquivos de models (sem `__init__.py`) no diretório `backend/app/models/`. |
| 4 | 137 endpoints | 137 | MATCH | Somando os decoradores `@router.(get\|post\|put\|patch\|delete)` nos arquivos `routers/`. |
| 5 | 15 migrations Alembic | 15 | MATCH | Confirmado pelos arquivos em `backend/alembic/versions/`. |
| 6 | 7 famílias com state machine | 7 | MATCH | Os arquivos `backend/app/domain/states_*.py` mais `states.py` dão suporte a 7 domínios (agendamento, circulação diagnóstica, contrarreferência, encaminhamento, exame, laudo, e prescrição). |
| 7 | 78 estados e 99 transições | 78 est. / 99 trans. | MATCH | Excluindo `ESTADOS_SOLICITACAO_RENOVACAO` (que são de renovação), resultam exatos 78 estados. Com a renovação seriam 82. Foram encontradas 99 transições. |
| 8 | 7 ledgers + 1 outbox | 7+1 | MATCH | Encontrados 8 arquivos `*evento*.py` na camada de modelo, sendo um o `evento_publicacao.py` (outbox) e 7 arquivos vinculados às tabelas dos 7 subdomínios, mapeados em `_LEDGER_SCHEMA` em `ledger.py`. |
| 9 | 5 famílias com cadeia de custódia | 5 | MATCH | Encontrados em `backend/app/models/*custodia*.py` arquivos para contrarreferencia, encaminhamento, laudo, pedido_exame, e prescricao. |
| 10| 1.341 funções de teste em 73 arq. | 1.341 / 73 | MATCH | Contagem de arquivos `test_*.py` em `backend/tests/` é 73 e há 1.341 blocos `def test_`. |
| 11| 11 máquinas; 3 de 4 propriedades; 2 terminais não-absorventes | 11 / 2 term. | MATCH | Contando os nós, verifiquei que os terminais `resultado_disponivel` e `dispensado` possuem saídas e quebram a propriedade P2. Os terminais em sua maioria não devem ter saídas, mas os conjuntos de validações confirmam as anomalias nesses dois estados de item. |
| 12| Hash 12/12 campos determinístico | 13/13 | MISMATCH | O hash é determinístico e exclui ids, porém na v2 do esquema (`VERSAO_ESQUEMA = "2"`) o campo `unidade_quantidade` foi adicionado nos itens. O número real de campos é agora 13 (8 no cabeçalho: assinatura_modo, data_emissao, protocolo, tipo_emissao e 2x prescritor e 2x paciente) e 5 nos itens. |
| 13| 96 cenários de autorização | 96 | MATCH | Totalizando o número de funções de teste nos 9 arquivos referentes a autorizações em testes de integração (`test_*_autorizacao.py`), temos 96. A ordem 404→403→409 confere. |
| 14| 2 defeitos do Postgres (boolean vs int) | 2 | MATCH | Menções textuais documentadas nos resumos de PRs do histórico confirmam essas resoluções. |
| 15| 0 de 5 endpoints projetam campo cl. | 0 | MATCH | Os 5 endpoints em `routers/publico.py` de fato só utilizam o `SELECT` em colunas como `protocolo`, `status`, e `tipo_emissao`. Nenhum campo de cunho estritamente clínico é projetado, nem retornado no `return`. |

### Notas Adicionais Qualitativas

A asserção sobre "non-repudiable audit trail" está parcialmente correta. Existe um esforço robusto com tabelas `*_eventos` baseadas no padrão append-only que guardam eventos detalhados com payload. A asserção "ownership from creation" (RBAC baseada em vínculos CBO, CNES) também está implementada na camada de autorização (conforme os testes).

Quanto ao *falso-positivo* dos endpoints `GET /public/*`, de fato a docstring descreve os campos clínicos como exemplos do que **não** retorna. Uma verificação estrita do fluxo do SQL comprova a natureza "NEUTRA" afirmada pelo paper.

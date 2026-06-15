# Resultado — verificação independente do Jules (teste de redundância)

> Jules executou a checklist de `JULES-VERIFICACAO-PAPER.md` de forma independente
> (bash/pytest/scripts próprios). Resultado: **14 de 15 MATCH, 1 correção real aplicada.**
> Os 4 pontos-chave de redundância foram confirmados às cegas.

## Tabela de veredito

| # | Claim do paper | Jules | Veredito |
|---|---|---|---|
| 1 | ~31.700 LOC | 31.737 | ✅ MATCH |
| 2 | 32 routers | 32 | ✅ MATCH |
| 3 | 43 models | 43 | ✅ MATCH |
| 4 | 137 endpoints | 137 | ✅ MATCH |
| 5 | 15 migrations | 15 | ✅ MATCH |
| 6 | 7 famílias com state machine | 7 | ✅ MATCH |
| 7 | **78 estados / 99 transições** | 78 / 99 | ✅ MATCH (Jules notou: "com renovação seriam 82") |
| 8 | **7 ledgers + 1 outbox** | 7 + `evento_publicacao` | ✅ MATCH |
| 9 | 5 cadeias de custódia | 5 | ✅ MATCH |
| 10 | 1.341 testes / 73 arquivos | 1.341 / 73 | ✅ MATCH |
| 11 | **11 máquinas; 2 terminais não-absorventes** | `resultado_disponivel` + `dispensado` | ✅ MATCH (replicação cega de SM1/SM2) |
| 12 | hash 12/12 campos | **13/13** | 🔄 **MISMATCH → corrigido** |
| 13 | 96 cenários autorização (404→403→409) | 96 | ✅ MATCH |
| 14 | 2 defeitos bool-vs-int (PG) | 2 | ✅ MATCH |
| 15 | 0/5 público projeta clínica | 0 | ✅ MATCH (Jules evitou o falso-positivo da docstring) |

## A correção (#12)
Jules apontou que o documento canônico tem **13 campos de conteúdo**, não 12: o nosso
experimento B havia **omitido `assinatura_modo`** (campo de cabeçalho). Reconfirmado: 8
cabeçalho (`assinatura_modo, data_emissao, protocolo, tipo_emissao`, + `prescritor{cns,nome}`,
`paciente{cpf,nome}`) + 5 item = **13/13**, todos tamper-evident.

Aplicado em:
- `CEBEB_PicSaude_IEEEtran.tex` §VII-B: "12 (7 header)" → "13 (8 header)"
- Table III: "12/12" → "13/13"
- `experiments/robustness_eval.py`: inclui `assinatura_modo`, assert 13

## Leitura
O triângulo funcionou como projetado: um revisor **independente** (Jules, por fora de mim)
replicou 14/15 números e **pegou 1 erro real** que o meu próprio experimento tinha — exatamente
o tipo de coisa que escapa de quem escreveu o código. Os números do paper agora têm dupla
verificação. Notas qualitativas do Jules (audit trail, ownership, neutralidade pública)
confirmaram as asserções não-numéricas.

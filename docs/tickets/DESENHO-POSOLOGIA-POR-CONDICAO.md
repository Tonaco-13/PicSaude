# DESENHO — posologia por CONDIÇÃO: a chave composta que o I50/J44 tornou visível

| Campo | Valor |
|---|---|
| **Origem** | Achado do engenheiro no fecho de 13/09 (#263): *"carregar_posologias chaveia por princípio ativo, não por (ativo, CID). Nove das minhas rows sobrescreveriam em silêncio a dose de HAS, asma e DM2 pela de IC e DPOC. Retirei as nove e deixei guarda para a próxima falhar alto. O conserto real é module — fica como ticket seu."* |
| **Classe** | `module` — `posologia_sugerida.py` + CSV (mesma família, semáforo intocado) |
| **Estado** | 🟡 Desenho pronto, aguarda slot na fila do engenheiro |
| **Dano evitado (13/09)** | 9 rows de I50/J44 removidas da `posologia_sugerida.csv` antes do merge — guardadas para re-entrar quando a chave composta existir. Guarda fail-loud já no ar |

---

## §1 O defeito

O índice é `dict[ativo_canônico → Posologia]` (`posologia_sugerida.py`,
`carregar_posologias`). Uma substância que trata duas condições com doses
diferentes (propranolol: HAS × ansiedade; clonazepam: epilepsia × pânico;
furosemida: HAS × IC) tem **uma só row viva** — a última do CSV vence, em
silêncio. Até hoje não doía porque as condições cobertas (HAS, DM2, asma, ITU)
não compartilhavam substâncias. I50 (insuficiência cardíaca) e J44 (DPOC)
trouxeram o primeiro choque real: **9 colisões**, removidas antes de morder.

## §2 O conserto

1. **Chave composta**: o índice passa a ser `dict[(ativo_canônico, codigo_cid) →
   Posologia]`; o CSV já tem a coluna `codigo_cid` — o dado está pronto, é o
   índice que ignora.
2. **Busca com cadeia**: o endpoint `POST /ia/posologia/sugerir` ganha o CID da
   prescrição em curso e sobe a hierarquia (`cadeia_cid`, mesma do semáforo):
   `(ativo, I50.0)` → `(ativo, I50)` → `(ativo, I10–I15)` se um dia houver
   blocos → sem sugestão (degrada seguro, como hoje).
3. **Sem CID informado**: fallback ao comportamento atual **somente quando a
   substância é unívoca**; colisão sem CID = sem sugestão + log (nunca a última
   row vence).
4. **As 9 rows exiladas voltam** (I50/J44) na mesma PR, agora sob a chave certa.
5. **Proveniência da condição**: a ficha de explicabilidade já carrega
   `condicao`; passa a carregar também o CID casado (transparência de qual
   condição fundamentou a dose).

## §3 ACs

1. Colisão (mesmo ativo, CIDs distintos) → duas sugestões vivas, cada uma casada
   pelo CID da prescrição; **nenhuma sobrescrita silenciosa** (a guarda fail-loud
   atual vira teste verde-apos-o-fix).
2. Sem CID na request e ativo unívoco → sugestão (retrocompat); sem CID e
   colisão → **silêncio + log**, nunca "última vence".
3. Hierarquia respeitada (subcategoria cai na categoria).
4. As 9 rows de I50/J44 de volta, com suas citações.
5. Suíte de browser que usa posologia: verde sem adaptação de roteiro (o gesto
   na tela não muda — quem muda é o acerto do motor).

---

*Desenho do arquiteto, 13/09, sobre o achado original do engenheiro. O CSV e o
endpoint existem; o que muda é a chave do índice e a consciência da condição na
busca. Semáforo, ledger e custódia intocados.*

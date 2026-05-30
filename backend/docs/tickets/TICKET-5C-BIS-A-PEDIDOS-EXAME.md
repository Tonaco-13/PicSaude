# TICKET-5C-BIS-A — Autorização mínima de ownership em `pedidos_exame.py`

| Campo | Valor |
|---|---|
| **Status** | Rodada 0 (spec) — aguarda CODEX rodada 1 antes de qualquer linha de código |
| **Classe** | `module` (estende módulo de exames com semântica de autorização) |
| **Volume estimado** | ~250 linhas (código + testes), distribuídas em 11 endpoints |
| **Autor** | Engenheiro-Arquiteto (Code workspace), calibração 2026-05-28 |
| **Data** | 2026-05-30 |
| **Commit base da leitura** | `6439e4a` (HEAD) — todo o código citado foi LIDO neste commit |
| **Predecessores (pré-requisito)** | TICKET-5C (`01c67fa`, autorização ambulatorial) · ADR-002 (`6439e4a`, decisão dos 3 helpers) |
| **Decisão vinculante** | [ADR-002](../decisoes/ADR-002-helper-ownership-5c-bis.md) — opção C estendida |
| **Sucessores** | 5C-BIS-B (laudos) · C (agendamentos) · D (circulação) · E (hospitalar) |

> **Critério de qualidade (briefing §59):** este ticket deve ser legível por um extensionista futuro,
> um mantenedor sucessor ou um auditor INPI. Não é caderno de execução pessoal.

> **Convenção de honestidade desta spec:** tudo marcado **[VERIFICADO]** saiu de código lido no
> commit `6439e4a`. Tudo marcado **[PROPOSTA]** é decisão de design a validar na CODEX rodada 1 —
> não afirmo como sólido o que não verifiquei. Ver §8.

---

## §1 Contexto regulatório e motivação

O TICKET-5C fechou autorização mínima de ownership em 11 endpoints **ambulatoriais de prescrição**
(commit `01c67fa`, CODEX rodada 2 zero P1). A decisão estratégica de 2026-05-26 ampliou o MVP para
incluir os 5 subdomínios sucessores **antes do deploy público** (Etapa 8). Este ticket é o primeiro
da série A–E: fecha o subdomínio de **pedidos de exame**.

**Por que isto é exigência regulatória, não polimento:**

- **LGPD Art. 6º (finalidade, necessidade) + Art. 46 (segurança)** — o pedido de exame contém dado
  pessoal sensível de saúde (Art. 11). Hoje, qualquer prescritor autenticado lê/transiciona o pedido
  de **qualquer** outro prescritor: os 11 endpoints exigem apenas `require_role`, não vínculo de
  ownership. Isso é falha de **controle de acesso** — minimização exige que o ator só alcance o
  objeto sob sua responsabilidade.
- **CFM Resolução 2.299/2021 (telessaúde / prontuário)** — o vínculo prescritor↔ato é nominal e
  rastreável. Um prescritor não pode operar sobre o pedido de exame que outro emitiu.
- **Auditabilidade (INPI BR 51 2026 002267-3 + validação dos extensionistas UFPE)** — o ledger
  registra *quem* fez *o quê*. Se o controle de acesso não garante que "quem" é o dono legítimo,
  o ledger registra fielmente um acesso que não deveria ter ocorrido. Auditoria é arquitetura
  (princípio 2 do briefing): a autorização é a primeira linha de defesa do ledger.

**O que este ticket NÃO é:** não é redesenho de RBAC, não é nova máquina de estados, não é
assinatura. É exclusivamente a **adição da camada de ownership inline** sobre o conjunto de papéis
**já existente** em cada endpoint.

---

## §2 Cláusula anti-escopo R6 (barreira mecânica — inegociável)

> **5C-bis-A é AUTORIZAÇÃO MÍNIMA EM ENDPOINTS. Não é serialização nem assinatura.**

Os seguintes arquivos/caminhos **NÃO são tocados por este ticket**. Qualquer item de escopo que
encoste neles **não avança aqui** — sobe primeiro ao portão R6 do Conselheiro:

- `app/domain/documento_canonico.py` — serialização canônica / hash
- `app/domain/assinatura.py` — modos, níveis formais, status de validação
- `app/domain/pdf_prescricao.py` e qualquer caminho de assinatura PAdES
- Qualquer fluxo `icp_brasil_local` (WebCrypto) ou `gov_br_nuvem`
- O `_calcular_hash` de `pedidos_exame.py` (linhas 145–172) — é documento canônico simplificado;
  **não alterar a serialização**, mesmo que pareça oportuno.

**Razão do portão:** a divergência de serialização JSON canônica WebCrypto↔Python é bloqueador
ABSOLUTO de piloto. Ownership check opera sobre identidade no JWT vs. registro no banco — **não toca
o byte do documento**. Se em algum momento a implementação parecer precisar mexer na serialização ou
no caminho de assinatura para validar ownership, isso é sinal de que o desenho está errado: pare e
suba ao Conselheiro.

**Esta cláusula é uma seção do ticket, não um comentário.** Vale para a implementação e para a
CODEX rodada 1.

---

## §3 Escopo de arquivos

### Arquivos que este ticket TOCA

| Arquivo | Natureza da mudança |
|---|---|
| `app/routers/pedidos_exame.py` | Adicionar ownership check inline em 9 dos 11 endpoints (ver §7); trocar `_=Depends(...)` por `usuario=Depends(...)` onde necessário |
| `app/utils/helpers.py` | **Criar** `_assert_or_403` e `_normalizar_identidade_jwt` (Helpers 1 e 2 da ADR-002 — 5C-bis-A é o primeiro ticket da série, logo é quem os introduz) |
| `tests/integration/test_pedidos_exame_autorizacao.py` | **Criar** — suíte de ownership (mirror de `test_custodia_autorizacao.py`) |
| `tests/unit/test_helpers_ownership.py` | **Criar** — teste unitário dos 2 helpers antes do uso (ADR-002 §7, mitigação do risco "mudar formato e quebrar 30 calls") |

### Arquivos que este ticket NÃO TOCA (anti-escopo de implementação)

- `app/routers/prescricoes.py` — o 5C original. **Não retrofitar** para usar os novos helpers neste
  ticket (seria refactor não autorizado, briefing "Regras invioláveis"). Os helpers nascem usados
  apenas em `pedidos_exame.py`; a migração do 5C é dívida separada se algum dia justificar.
- `app/auth/ownership.py` — **não criar aqui.** O Helper 3 (`_unidade_id_do_dispensador`) é exclusivo
  do TICKET-5C-BIS-E (caso hospitalar, duas hops). Não há caso hospitalar em pedidos de exame.
- `app/domain/states_exame.py` — máquina de estados intocada. Ownership ≠ transição.
- Tudo em §2 (anti-escopo R6).

---

## §4 Invariantes invioláveis (o ticket não pode violar)

1. **Backend é fonte de verdade.** O ownership é decidido por comparação entre identidade do JWT e
   registro no banco — nunca por afirmação do frontend.
2. **Ledger imutável.** Nenhum `UPDATE`/`DELETE` em `pedido_exame_eventos`. A camada de ownership
   roda **antes** de qualquer escrita; um acesso negado não gera evento.
3. **Estados só de `domain/states_exame.py`.** Nenhum estado novo. Nenhuma transição nova.
4. **Conjunto de papéis (`require_role`) preservado.** [VERIFICADO] Este ticket **não altera** quais
   papéis cada endpoint aceita — apenas adiciona, dentro do conjunto já permitido, a checagem de que
   o ator é o dono legítimo. (Ex.: `resultado` continua `prescritor`+`admin`; não ganha `dispensador`.)
5. **Validação de prescritor por identidade nominal (CNS), nunca por CPF.** [VERIFICADO] `JWT.sub`
   do prescritor é o CNS (`jwt.py` docstring + uso em `prescricoes.py:233`).
6. **CPF extraído de certificado ICP nunca trafega ao servidor.** Não se aplica diretamente a este
   ticket (não há caminho de assinatura aqui — ver §2), mas registrado como invariante de fronteira:
   nenhum endpoint deste ticket passa a receber CPF derivado de certificado.
7. **Contrato de erro `{codigo, mensagem}` em PT** (5C §3.5) — preservado e estendido (§6.3).

---

## §5 Mapa real dos 11 endpoints [VERIFICADO em `6439e4a`]

Leitura direta de `app/routers/pedidos_exame.py`. **Todos os 11 hoje descartam o usuário
(`_=Depends(require_role(...))`)** — nenhum valida ownership. Confirma a linha "pedidos_exame.py: 11
endpoints, 0 captura `usuario=`, 11 vulneráveis" da ADR-002 §1.1.

| # | Método · Rota | `require_role` atual | Padrão ADR-002 | Chave de ownership REAL | Como obtê-la |
|---|---|---|---|---|---|
| 1 | POST `` (criar) | `prescritor` | A | CNS no payload vs `JWT.sub` | comparação direta, sem query |
| 2 | POST `/fisica` | `prescritor` | A | idem | comparação direta |
| 3 | GET `/{protocolo}` | `prescritor,admin,dispensador` | B + D | prescritor: CNS · dispensador: CNPJ | **JOIN** (ver §5.1) |
| 4 | GET `/{protocolo}/custodia` | `prescritor,admin,paciente` | D | prescritor: CNS · paciente: CPF | JOIN matriz |
| 5 | POST `/{protocolo}/agendar` | `prescritor,admin` | E | prescritor: CNS | JOIN |
| 6 | POST `/{protocolo}/itens/{item_id}/coletar` | `prescritor,admin,dispensador` | E | prescritor: CNS · dispensador: CNPJ | JOIN matriz |
| 7 | POST `/{protocolo}/cancelar` | `prescritor,admin` | E | prescritor: CNS | JOIN |
| 8 | POST `/{protocolo}/itens/{item_id}/resultado` | `prescritor,admin` | E | prescritor: CNS | JOIN |
| 9 | POST `/{protocolo}/encerrar` | `prescritor,admin,paciente` | D | prescritor: CNS · paciente: CPF | JOIN matriz |
| 10 | GET `/{protocolo}/pdf` | `prescritor,admin` | C | prescritor: CNS — **já no row** | reusa row (a query já faz JOIN `pr.cns`) |
| 11 | GET `/{protocolo}/qr` | `prescritor,admin` | B | prescritor: CNS | **JOIN** (hoje só `SELECT 1`) |

Endpoints 1, 2, 10 não precisam de query nova; os demais sim.
(`admin` sempre passa sem ownership — padrão herdado do 5C, `prescricoes.py:874`.)

### §5.1 Divergências entre a amostra ilustrativa da ADR-002 §6 e o schema real [VERIFICADO]

A disciplina anti-fabricação pegou três pontos. **Devem ser corrigidos na implementação — não copiar
a amostra da ADR ao pé da letra:**

1. **`pedidos_exame` NÃO tem coluna `cns_prescritor` nem `cpf_paciente`.** [VERIFICADO em
   `app/models/pedido_exame.py:25-37`] A tabela guarda `prescritor_id` e `paciente_id` (FK inteiras).
   O helper interno `_get_pedido_ou_404` faz `SELECT *` → o row **não traz CNS/CPF**. Portanto o
   código da ADR-002 §6 `ident == pedido["cns_prescritor"]` **quebraria com KeyError**. O ownership
   de prescritor em GET/mutação exige **JOIN `prescritores pr ON pr.id = pe.prescritor_id`** para
   obter `pr.cns` — exatamente o que `prescricoes.py:879` (GET `/documento`, Padrão B) já faz.

2. **`pedidos_exame` NÃO tem coluna `cnpj_prestador`.** [VERIFICADO] O vínculo do prestador
   (dispensador = clínica/lab no MVP) existe apenas em `pedido_exame_custodia.para`, gravado no
   endpoint `agendar` (`pedidos_exame.py:632-646`, `para = payload.cnpj_prestador`). Logo o ownership
   de dispensador **não é uma comparação de coluna** — é um lookup na tabela de custódia. Ver §7.3 e
   a decisão aberta §8.1.

3. **QR (endpoint 11) não tem o row em memória.** [VERIFICADO] `qr_code_pedido_exame` faz só
   `SELECT 1 ... WHERE protocolo = ?` (`pedidos_exame.py:1091`). A ADR-002 §3 classificou pdf+qr
   ambos como Padrão C (row reusado), mas **só o PDF** carrega o row com dados de dono; o QR precisa
   de **query nova** (Padrão B), não reuso. Refinamento sobre a ADR.

---

## §6 Os dois helpers que 5C-bis-A introduz

5C-bis-A é o primeiro ticket da série A–E → é quem **cria** os Helpers 1 e 2 em `app/utils/helpers.py`,
conforme ADR-002 §2.1 e §5. Helper 3 fica no E.

### §6.1 Helper 1 — `_assert_or_403(condicao, codigo, mensagem)`

Conforme ADR-002 §2.1. Puro, sem DB. Centraliza o `raise HTTPException(403, {"codigo","mensagem"})`.
Elimina a categoria de erro "digitar `mensgem`" replicada em ~9 lugares (ADR-002 §4 opção B).

### §6.2 Helper 2 — `_normalizar_identidade_jwt(usuario) -> (papel, identificador)`

Conforme ADR-002 §2.1. Puro, sem DB.

**Contrato de totalidade (correção do achado P1 do Conselheiro):** o helper é **total — nunca levanta
exceção** e **sempre** retorna a tupla `(papel, identificador)` para qualquer payload, inclusive
papéis sem chave clínica:

- `prescritor` → `(„prescritor", CNS)` · `paciente` → `(„paciente", CPF)` · `dispensador` →
  `(„dispensador", CNPJ)`
- `admin` / `auditor` / `integrador` → `(papel, <dígitos do sub, possivelmente vazio>)`. O
  identificador desses papéis **não tem semântica clínica** e **não deve ser comparado a registro de
  banco**. É responsabilidade do *caller* fazer o bypass de `admin` **antes** de usar o identificador
  (ver esqueleto §7.1). Como o helper é total, chamá-lo primeiro e só então ramificar por `papel` é
  seguro — não há caminho em que `admin` quebre por o helper "não saber normalizá-lo".

**Ajuste de normalização por papel (achado §8.2):** a ADR escreveu um strip genérico
`"".join(c for c in sub if c.isdigit())`. Isso equivale a `normalize_cns`/`normalize_cpf`
(`helpers.py:12-24`, ambos `re.sub(r"\D","",s)`), **mas não equivale a `normalize_cnpj`**
(`helpers.py:16-20`, que também remove sufixo `.0` de artefato Excel). No ramo `dispensador` (CNPJ),
o helper **deve** delegar a `normalize_cnpj`, não ao strip genérico, sob pena de drift silencioso.
[PROPOSTA de correção — validar na rodada 1.]

### §6.3 Vocabulário de `codigo` — reconciliação ADR-002 §7 ↔ contrato 5C §3.5 [DECIDIDO — Conselheiro 2026-05-30]

**Conflito real descoberto na leitura:** a ADR-002 §7 declarou um vocabulário *novo e fechado*
(`ownership_negada`, `vinculo_institucional_negado`, `papel_invalido_para_acao`,
`contexto_operacional_negado`) e a docstring do Helper 1 usa `codigo="ownership_negada"`. Mas o
**contrato público de erro do 5C (§3.5)**, que este ticket estende, usa códigos específicos por
objeto: `prescritor_mismatch`, `nao_e_dono_da_prescricao`, `nao_e_dono_da_dispensacao`,
`ator_mismatch`, `sem_vinculo_com_prescricao`. [VERIFICADO em `prescricoes.py:237/888/980` +
`TICKET-5C §3.5`.]

Seguir a ADR ao pé da letra criaria **dois dialetos de erro** no mesmo sistema.

**Decisão de governança (aprovada pelo Conselheiro em 2026-05-30, pré-implementação):** por tocar
contrato de erro herdado de um predecessor fechado, o vocabulário **não** é matéria a ser congelada
pela CODEX rodada 1 — é decisão de governança do Conselheiro. A decisão aprovada é:

- O **mecanismo** `_assert_or_403(cond, codigo, mensagem)` da ADR fica (é só o raise).
- Os **valores** de `codigo` espelham o estilo 5C, adaptados a exame:
  - `prescritor_mismatch` — POST criar/fisica, CNS payload ≠ JWT (reuso literal do código 5C)
  - `nao_e_dono_do_pedido_exame` — prescritor/paciente/dispensador não-dono em GET/mutação
    (mensagem específica por papel; código único minimiza superfície de vocabulário)
- **Consequência de governança:** isso *emenda* o §7 "vocabulário fechado" da ADR-002. A própria ADR
  §7 diz "Novos códigos exigem PR + nota no §7 desta ADR." → o commit de implementação **deve anexar
  nota ao §7 da ADR-002** registrando a reconciliação aprovada.

**Papel da CODEX rodada 1 neste ponto:** revisar **coerência e segurança** do uso dos códigos (ex.:
nenhum 403 vazando dado sensível na mensagem; código certo para cada violação). **Não** é árbitro
final do vocabulário — esse ponto já está decidido acima.

---

## §7 Especificação por endpoint

**Dois princípios estruturais (achados P1 e P2 do Conselheiro):**

1. **Bypass de `admin` ANTES de usar o identificador (P1).** O Helper 2 é total (§6.2), então
   chamá-lo primeiro é seguro; mas a comparação de ownership só roda para papéis clínicos. O esqueleto
   canônico é: normaliza → `if papel == "admin": <segue sem ownership>` → senão, ramifica por papel.
2. **Sem SQL de ownership espalhado: três helpers locais privados no próprio router (P2).** As queries
   continuam locais ao subdomínio (ADR-002 opção C), mas **DRY dentro de `pedidos_exame.py`** — não
   reescrever o mesmo JOIN em 5 endpoints. **Não é abstração global** (não vai para `utils/` nem
   `auth/`); são funções privadas do módulo, ao lado de `_get_pedido_ou_404`.

### §7.0 Os três helpers locais privados (definir uma vez em `pedidos_exame.py`)

```python
def _assert_prescritor_dono_pedido(conn, protocolo: str, ident_cns: str) -> None:
    dono = conn.execute(
        "SELECT pr.cns FROM pedidos_exame pe "
        "JOIN prescritores pr ON pr.id = pe.prescritor_id "
        "WHERE pe.protocolo = ?", (protocolo,),
    ).fetchone()
    _assert_or_403(
        dono is not None and ident_cns == dono["cns"],
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Este pedido de exame foi emitido por outro prescritor.",
    )

def _assert_paciente_dono_pedido(conn, protocolo: str, ident_cpf: str) -> None:
    dono = conn.execute(
        "SELECT pa.cpf FROM pedidos_exame pe "
        "JOIN pacientes pa ON pa.id = pe.paciente_id "
        "WHERE pe.protocolo = ?", (protocolo,),
    ).fetchone()
    _assert_or_403(
        dono is not None and ident_cpf == dono["cpf"],
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Este pedido de exame pertence a outro paciente.",
    )

def _assert_dispensador_dono_pedido(conn, pedido_id: int, ident_cnpj: str) -> None:
    # [PROPOSTA §8.1] vínculo do prestador = registro de custódia para=CNPJ (criado no 'agendar').
    # [PENDENTE §8.4] o `para` é gravado CRU pelo agendar; comparar contra ident_cnpj normalizado
    #   causa 403 falso-negativo se o agendar recebeu CNPJ mascarado. A forma final da comparação
    #   (normalizar na escrita = opção A, ou normalizar ambos no lookup = opção B) é decisão da
    #   CODEX rodada 1. O código abaixo assume opção B até o veredito.
    vinc = conn.execute(
        "SELECT 1 FROM pedido_exame_custodia "
        "WHERE pedido_id = ? AND para = ? LIMIT 1",
        (pedido_id, ident_cnpj),
    ).fetchone()
    _assert_or_403(
        vinc is not None,
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Pedido de exame sob responsabilidade de outro prestador.",
    )
```
(O JOIN de prescritor espelha `prescricoes.py:879`, padrão B já auditado no 5C.)

### §7.1 Padrão A — POST criar (1) e POST /fisica (2)

Sem query. `usuario=Depends(require_role("prescritor"))`. Após normalizar, comparar CNS do payload
com o do JWT (não há `admin` neste conjunto de papéis):

```python
papel, ident = _normalizar_identidade_jwt(usuario)
cns = normalize_cns(payload.cns_prescritor)
_assert_or_403(
    ident == cns,
    codigo="prescritor_mismatch",
    mensagem="CNS do payload não coincide com prescritor autenticado.",
)
```
Espelha `prescricoes.py:233`. Fecha "prescritor A emite pedido declarando CNS de B".
**Ordenação:** este check é o primeiro efeito do handler — antes de qualquer escrita (prova de
rollback exigida em §9).

### §7.2 Esqueleto canônico com bypass de admin — GET `/{protocolo}` (3) · custódia (4) · agendar (5) · coletar (6) · cancelar (7) · resultado (8) · encerrar (9) · qr (11)

Princípio de ordenação (lição do follow-up #52 do 5C — info disclosure): **após confirmar existência
(404), o ownership (403) vem ANTES de qualquer 422/400 de estado/transição.** Um não-dono não deve
aprender o estado nem o `tipo_emissao`. (O 404 por protocolo é leak aceito e herdado do 5C; o que #52
condenou foi o leak *adicional* de estado antes do 403.)

```python
papel, ident = _normalizar_identidade_jwt(usuario)
pedido = _get_pedido_ou_404(conn, protocolo)          # 404 de existência primeiro
if papel != "admin":                                   # P1: bypass de admin explícito
    if papel == "prescritor":
        _assert_prescritor_dono_pedido(conn, protocolo, ident)
    elif papel == "paciente":
        _assert_paciente_dono_pedido(conn, protocolo, ident)
    elif papel == "dispensador":
        _assert_dispensador_dono_pedido(conn, pedido["id"], ident)
# 403 já resolvido aqui — só então: eh_terminal_pedido(...) / transição / escrita
```

Cada endpoint instancia **apenas os ramos compatíveis com seu `require_role`** (§5):
- prescritor-only (5, 7, 8, 11): só o ramo prescritor.
- prescritor+dispensador (3, 6): ramos prescritor e dispensador.
- prescritor+paciente (4, 9): ramos prescritor e paciente.
- `admin` sempre presente e sempre passa pelo bypass.

### §7.3 Padrão C — GET `/{protocolo}/pdf` (10)

[VERIFICADO] A query do PDF (`pedidos_exame.py:1019-1033`) já faz `JOIN prescritores ... pr.cns AS
cns_prescritor`. Reusa o row — **sem segunda query**:

```python
if papel == "prescritor":
    _assert_or_403(
        ident == row["cns_prescritor"],
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Este pedido de exame foi emitido por outro prescritor.",
    )
```
(`admin` passa; não há `paciente`/`dispensador` no `require_role` do pdf — não adicionar: invariante §4.4.)

---

## §8 Decisões abertas para a CODEX rodada 1 [PROPOSTAS — não afirmadas como sólidas]

> O vocabulário de `codigo` **não está nesta lista**: foi decidido pelo Conselheiro (§6.3). A CODEX
> revisa coerência/segurança do uso, não arbitra o vocabulário.

1. **§8.1 — Semântica de ownership do dispensador em exames.** Proponho vínculo via
   `pedido_exame_custodia.para = CNPJ`. Risco a validar: um pedido só ganha registro de custódia
   *após* `agendar`; antes disso (`emitido`), nenhum dispensador é dono — comportamento desejado?
   Além disso, `para` mistura `'paciente'` (custódia carteira digital, `pedidos_exame.py:351`) com o
   CNPJ do prestador (`:639`). O lookup por CNPJ não colide com `'paciente'`, mas a CODEX deve
   confirmar que não há outro valor de `para` que cause falso-positivo.
2. **§8.2 — Helper 2 e CNPJ** (§6.2): ramo `dispensador` deve usar `normalize_cnpj` (que remove
   sufixo `.0`), não o strip genérico de dígitos — sob pena de drift silencioso na comparação de CNPJ.
3. **§8.3 — `resultado` (8) é prescritor+admin, sem dispensador.** [VERIFICADO] No mundo real o
   prestador registra resultado. Mas mudar o conjunto de papéis violaria a invariante §4.4 (este
   ticket não mexe em RBAC). Mantenho como está; registro como observação para ticket futuro, não
   para 5C-bis-A.
4. **§8.4 — Assimetria de normalização do CNPJ entre escrita e leitura (falso-NEGATIVO).**
   [VERIFICADO em `511b9fc` — achado da leitura de sanidade pré-CODEX, 2026-05-30] Distinto do
   falso-positivo do §8.1. A escrita e a leitura do CNPJ do prestador são **assimétricas**:
   - **Escrita (`agendar`):** `pedido_exame_custodia.para = payload.cnpj_prestador` **cru**
     (`pedidos_exame.py:639`). `AgendarIn` (`:584-587`) **não tem validator**, e o router **não
     importa `normalize_cnpj`** (`:40` importa só `normalize_cns/cpf/nome`; zero usos de
     `normalize_cnpj` no arquivo).
   - **Leitura (helper proposto §7.0):** compararia `para` contra o `ident` do JWT já passado por
     `normalize_cnpj` (§6.2/§8.2 — remove máscara e sufixo `.0`).
   - **Consequência:** se o `agendar` foi chamado com CNPJ mascarado (`12.345.678/0001-90`) ou com
     artefato `…90.0`, o `para` armazenado **não casa** com o `ident` normalizado → **403 falso
     contra o prestador legítimo**. O critério §9 "dispensador com CNPJ correto → 2xx" pode falhar
     conforme o fixture grave o CNPJ.

   **Decisão para a CODEX rodada 1** (não decido unilateralmente — tem dimensão de escopo):
   - **Opção A — normalizar na escrita:** `agendar` passa a gravar `normalize_cnpj(payload.cnpj_prestador)`.
     Mais limpo (dado consistente na tabela), **mas toca o write path do `agendar`**, que está fora do
     "só ownership" deste ticket. NÃO viola §1 (imutabilidade): custódia é dado novo, não objeto
     emitido sendo editado.
   - **Opção B — normalizar ambos os lados no lookup do helper** (`normalize_cnpj(para) == ident`):
     mantém a mudança dentro da camada de ownership (escopo mínimo de 5C-bis-A), **mas** deixa dado
     heterogêneo na tabela para outros consumidores futuros.
   - **Recomendação (fraca):** B, por minimalidade de escopo; A se a CODEX preferir corrigir a raiz.
     Não dispara R6 (normalização de CNPJ não toca serialização canônica nem assinatura).

---

## §9 Critérios de aceite (testes que devem passar)

Suíte nova `tests/integration/test_pedidos_exame_autorizacao.py` — no mínimo, por padrão:

- **A (criar/fisica):** prescritor com CNS-A declarando CNS-B → `403 prescritor_mismatch`; zero linhas
  novas em `pedidos_exame` (prova de rollback antes da escrita).
- **B (GET/agendar/cancelar/resultado/qr):** prescritor não-dono → `403 nao_e_dono_do_pedido_exame`;
  prescritor dono → 2xx.
- **`admin` (P1 — obrigatório):** em **todos** os endpoints que aceitam `admin`, um JWT `admin` →
  2xx **sem** ownership, sem 403, sem quebra ao passar pelo Helper 2 (cobre o caso em que o
  identificador do admin é vazio/não-clínico). Pelo menos um teste de admin por padrão de endpoint
  (B, C, D, dispensador).
- **Dispensador (GET/coletar) — quatro casos explícitos (P2 + §8.4 — anti-interpretação frouxa):**
  > **Regra de fixture:** o registro de custódia deve ser criado **pelo endpoint real `agendar`**
  > (não por `INSERT` manual normalizado), para o teste refletir como o `para` é de fato gravado
  > (cru, §8.4). Um fixture que insere CNPJ já normalizado à mão **esconderia** o falso-negativo.
  1. dispensador faz GET **antes** de o pedido ser agendado (sem registro de custódia) → `403`;
  2. dispensador cujo **CNPJ é o prestador agendado** (agendado com CNPJ sem máscara) → 2xx;
  3. dispensador com **CNPJ diferente** do prestador agendado (ou CNPJ antigo) → `403`;
  4. **(§8.4 — expõe a assimetria)** pedido agendado com CNPJ **mascarado**
     (`12.345.678/0001-90`) e dispensador autentica com o mesmo CNPJ → deve dar **2xx**. Este caso
     **falha** se a normalização ficar só de um lado; passa quando a opção A ou B do §8.4 for aplicada.
- **Paciente (custodia/encerrar):** paciente com CPF ≠ dono → `403`; paciente dono → 2xx.
- **Ordenação anti-leak (#52):** não-dono recebe `403` e **não** consegue distinguir, pela resposta,
  o estado/`tipo_emissao` do pedido (o 403 precede o 422 de estado).
- **Regressão:** a suíte funcional existente `tests/integration/test_pedidos_exame.py` continua verde
  (os fluxos felizes usam o dono correto).

Suíte unitária nova `tests/unit/test_helpers_ownership.py`:
- `_normalizar_identidade_jwt`: prescritor→(papel,CNS digits); paciente→(…,CPF); dispensador→
  (…,CNPJ com `.0` removido); **admin/auditor → (papel, <dígitos do sub ou "">), sem exceção**
  (contrato de totalidade §6.2); contrato de retorno estável.
- `_assert_or_403`: condição falsa → `HTTPException(403, {"codigo","mensagem"})`; verdadeira → no-op.

---

## §10 Verificação automatizada (completude)

Após implementar, estes comandos confirmam zero endpoint remanescente sem ownership:

```bash
# (1) PORTÃO FORTE — nenhum endpoint pode mais DESCARTAR o usuário com _=Depends:
grep -nE '_=Depends\(require_role' backend/app/routers/pedidos_exame.py
#   → esperado: VAZIO. Qualquer linha aqui é um endpoint sem caminho de ownership.

# (2) PORTÃO DE COMPLETUDE — um por endpoint, exato (corrige o achado P3):
#     cada um dos 11 endpoints normaliza a identidade no topo do handler.
grep -c '_normalizar_identidade_jwt(usuario)' backend/app/routers/pedidos_exame.py
#   → esperado: EXATAMENTE 11. Não é piso frouxo: se criar/física (ou qualquer outro)
#     omitir o check, a contagem cai abaixo de 11 e o portão acusa.
#   NB: contar _assert_or_403 NÃO serve aqui — com os helpers locais (§7.0) a chamada
#     fica dentro das 3 definições (DRY), subcontando os endpoints. Por isso a métrica
#     é _normalizar_identidade_jwt(usuario), que é 1:1 com endpoint.

# (3) Os 3 helpers locais de ownership existem no router:
grep -nE 'def _assert_(prescritor|paciente|dispensador)_dono_pedido' backend/app/routers/pedidos_exame.py
#   → esperado: 3 definições

# (4) Helpers globais criados e testados:
grep -n 'def _assert_or_403\|def _normalizar_identidade_jwt' backend/app/utils/helpers.py
pytest backend/tests/unit/test_helpers_ownership.py backend/tests/integration/test_pedidos_exame_autorizacao.py -q
```

> A varredura (1)+(2) é o portão de completude no mesmo espírito do "grep de confirmação" do método
> validado em 4D.1 (backend/CLAUDE.md §método, passo 5). (1) garante que nenhum endpoint descarta o
> usuário; (2) garante que cada endpoint efetivamente normaliza identidade — juntas, fecham a omissão
> silenciosa que um piso `≥ N` deixaria passar.

---

## §11 Predecessoras e pendências de verificação

- **Pré-requisito em main:** `01c67fa` (5C) e `6439e4a` (ADR-002). [VERIFICADO — ambos em `origin/main`.]
- **Pendência de verificação para a rodada 1** (não afirmo como sólido): §8.1 (custódia do dispensador),
  §8.2 (CNPJ no Helper 2), **§8.4 (assimetria de normalização CNPJ escrita×leitura — falso-negativo)**.
  A implementação não começa antes de a CODEX rodada 1 fechar essas.
- **Leitura de sanidade pré-CODEX** (Engenheiro-executor, `511b9fc`, 2026-05-30): baseline §10
  confirmado (11 `_=Depends` / 0 normalizações), os 3 pontos de §5.1/§5/§8.1 verificados batendo
  com o código, e **descoberto o §8.4** (assimetria de normalização) — risco que esta rodada 0
  inicial não destacara. Achado incorporado acima antes da CODEX rodada 1.
- **Follow-ups #52/#53/#54 do 5C** [VERIFICADO] são dívidas sobre `prescricoes`/`custodia`/`dispensacoes`,
  **não** sobre `pedidos_exame`. Não entram no escopo de A; apenas a *lição* de ordenação do #52 foi
  incorporada (§7, §9).

---

## §12 O que volta ao Conselheiro

- **Esta rodada 0**, pronta para disparar **CODEX rodada 1** (obrigatória: classe `module`, >100 linhas
  — guard-rail Risco 1 da calibração). Nenhuma linha de código antes disso.
- **Vocabulário de `codigo` (§6.3) — DECIDIDO pelo Conselheiro em 2026-05-30** (já incorporado): mirror
  do 5C (`prescritor_mismatch`, `nao_e_dono_do_pedido_exame`) + nota emendando a ADR-002 §7 no commit
  de implementação. A CODEX revisa coerência/segurança, não arbitra o vocabulário.
- **Trade-off ainda aberto (§8.1):** a semântica de ownership do dispensador em exames (via custódia)
  é design novo, não herdado — vale o olhar do Conselheiro sobre se "dispensador só é dono após
  agendamento" é coerente com a narrativa de circulação de objetos sanitários. Os testes (§9) fixam
  os três casos (antes/depois/CNPJ errado) para impedir interpretação frouxa.
- **Não dispara R6:** nada neste ticket toca serialização canônica, assinatura, escopo público
  anunciado, cronograma UFPE/SMS ou postura LGPD além do reforço de controle de acesso já previsto.
  Confirmo o anti-escopo §2 como barreira mecânica.

---

*Rodada 0 redigida em 2026-05-30 pelo Engenheiro-Arquiteto, sobre código lido no commit `6439e4a`.
Aguarda CODEX rodada 1 antes da implementação.*

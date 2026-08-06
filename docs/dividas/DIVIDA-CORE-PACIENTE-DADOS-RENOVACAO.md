# DÍVIDA TÉCNICA — Persistência de dados do paciente para renovação

| Campo | Valor |
|---|---|
| **ID** | DIVIDA-CORE-PACIENTE-DADOS-RENOVACAO |
| **Classe** | `core` (quando endereçada — toca núcleo de identidade do paciente) |
| **Origem** | Achado do extensionista (2026-08-02) + despacho KIMI3-001 |
| **Estado** | 🟡 **Registrada — solução paliativa adotada para a demo** |
| **Decisão** | Opção (c): cache no `localStorage` por CPF (Kimi 3 implementa) |
| **Bloqueia o Kimi 3?** | ❌ Não — paliativo é `local-extension` |
| **Dono da decisão final** | Fabiano (após parecer Fable 5) |

---

## §1 Problema

Ao **renovar uma receita digital**, o prescritor precisa **redigitar** idade, telefone, endereço, CEP e cidade/UF do paciente — mesmo que esses dados já tenham sido informados na prescrição origem.

**Por que acontece:** a função `renovarReceita` (prescritor.html:2293) chama `_preencherFormularioReceita(r)` (linha 1518), que **pré-preenche** nome, idade, telefone, endereço, CEP, cidade/UF e medicamentos. **A intenção de pré-preencher já existe.**

Porém, o objeto `r` é construído por `_receitaDoBackend(pres)` (prescritor.html:1489), que do backend só tira `paciente_nome`, `paciente_cpf` e `itens`. Os demais campos **só aparecem se houver cópia física** no `localStorage` (`pix_saude_db_v27`). Para uma **prescrição digital** (fonte de verdade = backend), esses campos ficam em branco.

## §2 Causa-raiz arquitetural

A tabela `pacientes` (DDL em `docs/picsaude_ddl_postgres_v1.sql:90-100`) só persiste:

```sql
CREATE TABLE pacientes (
    id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cpf         cpf_t       NOT NULL,
    nome        TEXT        NOT NULL,
    telefone    VARCHAR(20),
    ativo       BOOLEAN     NOT NULL DEFAULT TRUE,
    ...
);
```

**Não há colunas** para idade, endereço, CEP, cidade, UF. Esses dados são capturados no formulário do prescritor, vão para o **PDF da receita** (gerado na emissão), mas **não vão a lugar nenhum persistente** além disso.

O endpoint `POST /prescricoes` (`prescricoes.py:60`) aceita `tipo_emissao='renovacao'` + `origem_prescricao_id`, mas **não copia dados do paciente** — espera o frontend reenviar tudo.

## §3 Decisão ratificada (Fabiano + parecer Fable 5, 2026-08-02)

**Opção (c): cache no `localStorage` por CPF no `prescritor.html`.**

- **Classe:** `local-extension` (não toca núcleo, não altera schema, não quebra contrato público).
- **Quem implementa:** Kimi 3 (frontend).
- **Spec técnica:** ver §10.C do `HANDOFF-FRONTEND-KIMI3.md`.

### Por que (c) e não (a) ou (b)

| Opção | Descrição | Veredicto |
|---|---|---|
| **(a)** Persistir dados na tabela `pacientes` (migração) | Toca núcleo de identidade, exige análise de PII, migração de schema | **Deferida** — core real, exige seu próprio ciclo |
| **(b)** Criar `GET /prescricoes/{proto}/dados-renovacao` | Backend retorna o que existir — mas se não persiste, retorna vazio | **Inútil sem (a)** — depende de persistência |
| **(c)** Cache no `localStorage` por CPF no frontend | Sem tocar backend; resolve a UX da demo | ✅ **Adotada** |

### Trade-off aceito

- ✅ Resolve a UX da demo (renovação pré-preenche tudo).
- ⚠️ **Não é portável entre dispositivos/navegadores** — o cache é local ao navegador do prescritor. Se o mesmo prescritor renovar de outra máquina, redigita.
- ⚠️ **Não é a fonte de verdade** — é um paliativo de UX. A fonte de verdade dos dados do paciente, quando endereçada, será o backend.
- ⚠️ **PII em `localStorage`** — dados do paciente (nome, CPF, endereço) ficam no navegador. Aceitável para contexto de demo/local; reavaliar em produção.

## §4 Quando esta dívida deve ser endereçada (opção a)

**Gatilhos que justificam migrar (c) → (a):**

1. Prescritores começarem a renovar de **múltiplos dispositivos** e reclamarem da redigitação.
2. Necessidade de **relatório analítico** por idade/endereço do paciente (hoje impossível — dado não persistido).
3. Integração com sistemas externos (adapter G4A) que precisem desses dados.
4. Decisão de produto de tornar o cadastro do paciente mais completo (ex.: CID, alergias).

**Quando endereçar:**

- Abrir ticket `core` próprio (`TICKET-CORE-PACIENTE-ENDERECO`).
- Exige análise de PII (LGPD): quais dados clínicos/demográficos persistir, com quem compartilhar, retenção.
- Exige migração de schema (adicionar colunas a `pacientes` — ver DDL) e decisão sobre dados retroativos.
- Backend expõe esses dados em endpoint de leitura (provavelmente `GET /prescricoes/{proto}/dados-renovacao` ou enriquecer `GET /prescricoes/{proto}`).
- Frontend (Kimi 3) então consome o endpoint e **remove o paliativo** do `localStorage`.

## §5 Achado adjacente (registrado, fora de escopo)

`renovarAtestado` **não existe** em lugar nenhum (frontend ou backend). O backend de atestados (`atestados.py:66`) só aceita `tipo_emissao ∈ {"nova", "correcao"}` — **atestados não suportam renovação**.

Se houver decisão de produto de suportar renovação de atestado, isso é **outro ticket** (frontend + backend).

## §6 Rastreabilidade

| Artefato | Caminho |
|---|---|
| Handoff (spec do paliativo) | `docs/tickets/HANDOFF-FRONTEND-KIMI3.md` §10.C |
| Despacho | `docs/tickets/DESPACHO-KIMI3-001.md` |
| DDL pacientes | `docs/picsaude_ddl_postgres_v1.sql:90-100` |
| Código-fonte (`_receitaDoBackend`) | `prescritor.html:1489-1514` |
| Código-fonte (`renovarReceita`) | `prescritor.html:2293-2315` |
| Backend emissão renovação | `backend/app/routers/prescricoes.py:60, 301-311, 319-321` |

---

*Dívida registrada pelo arquiteto de backend (GLM-5.2) em 2026-08-02. Solução paliativa (c) adotada para a demo; migração para (a) deferida até gatilho de produto.*

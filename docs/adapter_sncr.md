# Adapter SNCR — Ticket 16A

> Camada de integração com o **SNCR (Sistema Nacional de Controle de
> Receituários)** da Anvisa, exigida pela RDC 1.000/2025. Implementação
> usa **adapter pattern** com **stub** local; a integração real entra
> no Ticket 16B quando a especificação técnica for publicada.

---

## 1. Objetivo do adapter pattern

Em abril/2026, a especificação técnica da API do SNCR ainda **não está
publicamente disponível**. Ao mesmo tempo, o prazo regulatório é
junho/2026. Para evitar bloqueio do desenvolvimento, o PicSaúde adota um
**adapter pluggable** com duas implementações:

| Implementação | Status         | Quando usar                                  |
|---------------|----------------|----------------------------------------------|
| `SNCRStub`    | ✅ Ticket 16A  | Desenvolvimento, testes, demos              |
| `SNCRReal`    | ⏳ Ticket 16B  | Produção (após API documentada + credenciamento) |

A **interface** (`SNCRAdapter`) é estável: mudanças nela são `core`
(CLAUDE.md §10) e exigem revisão central. A implementação concreta é
trocada via variável de ambiente — o resto do sistema (router, motor
regulatório, ledger) **não muda**.

---

## 2. Interface — `SNCRAdapter`

Arquivo: [`backend/app/adapters/sncr_interface.py`](../backend/app/adapters/sncr_interface.py)

ABC (Abstract Base Class) com 4 operações:

```python
class SNCRAdapter(ABC):
    nome_adapter: str  # "stub" | "real" — para rastreabilidade

    def requisitar_numeracao(
        tipo_receituario: str,        # ex: "notificacao_receita_a"
        prescritor_cpf: str,          # CPF do prescritor (vinculação obrigatória)
        quantidade: int = 1,
    ) -> list[ResultadoSNCR]: ...

    def verificar_numeracao(
        numero_sncr: str,
    ) -> ResultadoSNCR: ...

    def registrar_utilizacao(           # escopo da farmácia (futuro)
        numero_sncr: str,
        dispensador_cnes: str,
        data_dispensacao: datetime,
    ) -> ResultadoSNCR: ...

    def health_check() -> bool: ...
```

DTOs definidos no mesmo arquivo:
- `NumeracaoSNCR` — payload de uma numeração obtida.
- `RegistroUtilizacao` — payload de uma utilização (dispensação) registrada.
- `ResultadoSNCR` — wrapper sucesso/erro com `codigo_erro` classificável.

**Campos confirmados vs inferidos:** o **contrato** de operações
(requisitar / verificar / registrar / health) é estável. O **shape** dos
DTOs reflete requisitos normativos conhecidos (numeração individualizada,
vinculação a CPF, registro de utilização) mas detalhes (formato exato do
número, lote, validade) podem ajustar quando a API real for documentada.

---

## 3. Implementação stub — `SNCRStub`

Arquivo: [`backend/app/adapters/sncr_stub.py`](../backend/app/adapters/sncr_stub.py)

### Formato de numeração

```
STUB-{ANO}-{TIPO_ABREV}-{SEQUENCIAL:09d}
```

Exemplos:

| Tipo regulatório                | Abreviação | Exemplo                  |
|---------------------------------|------------|--------------------------|
| Notificação de Receita A        | NRA        | `STUB-2026-NRA-000000001` |
| Notificação de Receita B        | NRB        | `STUB-2026-NRB-000000001` |
| Receita de Controle Especial    | RCE        | `STUB-2026-RCE-000000001` |
| Notificação de Receita Especial | NRE        | `STUB-2026-NRE-000000001` |
| Receita com Retenção            | RRT        | `STUB-2026-RRT-000000001` |

### Comportamento

- **`requisitar_numeracao()`** — gera N numerações sequenciais, cada uma
  vinculada ao `prescritor_cpf` informado. Sequencial é por `(ano × tipo)`
  e mantido em memória da instância (thread-safe via lock).
- **`verificar_numeracao()`** — só reconhece números que ela mesma emitiu
  (com prefixo `STUB-`). Demais retornam `SNCR_INVALIDO`.
- **`registrar_utilizacao()`** — mock; loga e retorna sucesso para
  números com prefixo STUB-.
- **`health_check()`** — sempre `True` (não há rede envolvida).

### Guardrails

1. **Prefixo `STUB-` obrigatório** — toda numeração mock é
   distinguível por inspeção.
2. **Status `numerado_stub`** ≠ `numerado` — endpoint nunca marca um
   receituário stub com `numerado` (reservado para SNCR real).
3. **Logs sempre prefixados** com `[SNCR-STUB]` para grep.
4. **Não persistente** — o registro local de numerações emitidas é só
   em memória e existe apenas para dar comportamento útil ao
   `verificar_numeracao()` em testes.

---

## 4. Factory — `get_sncr_adapter()`

Arquivo: [`backend/app/adapters/sncr_factory.py`](../backend/app/adapters/sncr_factory.py)

Configuração via variável de ambiente:

| `SNCR_ADAPTER` | Comportamento                                         |
|----------------|-------------------------------------------------------|
| (não definido) | Default: retorna `SNCRStub`                          |
| `stub`         | Explícito: retorna `SNCRStub`                        |
| `real`         | **Levanta `NotImplementedError`** — sem fallback     |
| outro valor    | Levanta `ValueError`                                 |

> ⚠️ **Sem fallback silencioso.** Se alguém configurar `SNCR_ADAPTER=real`
> em produção antes de o Ticket 16B existir, a aplicação **falha
> explicitamente**. Nunca rodaremos com `SNCRStub` quando `real` foi
> pedido. Mesmo padrão do guardrail SQLite-em-prod (CLAUDE.md §6 +
> [`app/main.py`](../backend/app/main.py)).

---

## 5. Estados do receituário — ciclo de vida

Tabela `receituarios.status` (String(30)).

```
                  /gerar (Ticket 15)
                       │
                       ▼
                   ┌─────────┐
                   │ gerado  │
                   └────┬────┘
                        │
                        │ /numerar (Ticket 16A)
                        ▼
        ┌───────────────┴───────────────────────┐
        │                                       │
        ▼                                       ▼
 ┌─────────────────┐               ┌─────────────────────┐
 │ nao_requer_sncr │               │ numerado_stub  ⤴︎ stub │
 └─────────────────┘               │ numerado       ⤴︎ real │
   (receita simples /              └──────────┬──────────┘
    receita comum)                            │
                                              │ /emitir (Ticket 17, futuro)
                                              ▼
                                        ┌──────────┐
                                        │ emitido  │
                                        └────┬─────┘
                                             │
                                             │ farmácia registra utilização
                                             ▼
                                       ┌────────────┐
                                       │ dispensado │
                                       └────────────┘

Estados terminais alternativos: expirado · cancelado
```

Significado semântico:

| Status            | Significado                                                                         |
|-------------------|-------------------------------------------------------------------------------------|
| `gerado`          | Criado pelo motor regulatório. Aguarda numeração.                                  |
| `nao_requer_sncr` | Receita simples/comum — explicitamente não passa pelo SNCR. `numeracao_sncr=NULL`. |
| `numerado_stub`   | Numeração obtida via `SNCRStub`. **Sem validade regulatória.**                     |
| `numerado`        | Numeração real obtida do SNCR. Reservado para uso com `SNCRReal`.                   |
| `emitido`         | Assinado e disponibilizado ao paciente.                                             |
| `dispensado`      | Farmácia registrou utilização no SNCR.                                              |
| `expirado`        | Prazo de validade ultrapassado sem dispensação.                                     |
| `cancelado`       | Cancelado por correção/erro.                                                        |

Campos de timestamp adicionados pelo Ticket 16A:

| Campo           | Tipo           | Quando preenchido                                     |
|-----------------|----------------|--------------------------------------------------------|
| `numerado_em`   | DateTime       | Momento em que `/numerar` aplicou status terminal     |
| `emitido_em`    | DateTime       | (Ticket 17 futuro) momento da emissão final           |
| `adapter_usado` | String(20)     | `"stub"` \| `"real"` — qual adapter gerou a numeração |

---

## 6. Endpoint — `POST /prescricoes/{protocolo}/receituarios/numerar`

Arquivo: [`backend/app/routers/receituarios.py`](../backend/app/routers/receituarios.py)

### Pré-condições

- Role `prescritor`.
- Prescrição existe e o token pertence ao prescritor que a emitiu.
- Já há receituários gerados (chamar `/gerar` antes — caso contrário 404).

### Fluxo

1. Carrega prescrição e valida posse (403 se outro prescritor).
2. Carrega receituários ativos (`substituido_em IS NULL`).
3. Carrega o nível de assinatura declarado em `prescricao_assinatura.tipo_certificado` (não bloqueante).
4. Obtém adapter via `get_sncr_adapter()` e nome (`stub` | `real`).
5. Para cada receituário:
   - Já em estado terminal de numeração (`numerado`, `numerado_stub`, `nao_requer_sncr`) → retorna como-está (idempotente).
   - **`requer_sncr=False`** (receita simples/comum) → atualiza `status='nao_requer_sncr'`, `numeracao_sncr=NULL`.
   - **`requer_sncr=True`** (controlado) → chama `adapter.requisitar_numeracao()`:
     - sucesso → atualiza `numeracao_sncr`, `status='numerado_stub'` ou `'numerado'`, `numerado_em`, `adapter_usado`.
     - falha → 502 com payload diagnóstico (rollback automático via `get_tx`).
   - Se nível de assinatura declarado < nível exigido pelo grupo → registra evento `todo_regulatorio` (NÃO bloqueia).
6. Registra evento `receituarios_numerados` no ledger (somente se houve mudança).

### Determinação de `requer_sncr`

Derivada **explicitamente** do `tipo_receituario`:

```python
requer_sncr = tipo_receituario not in {"receita_simples", "receita_comum"}
```

Não inferimos de outro campo — regra única e auditável.

### Validação de assinatura — não bloqueante

Este endpoint **não valida criptograficamente** a assinatura. Apenas
**consulta** o `tipo_certificado` declarado em `prescricao_assinatura` e
mapeia para nível regulatório:

| `tipo_certificado` | Nível         |
|--------------------|---------------|
| `A1`, `A3`         | `qualificada` |
| `gov_br_nuvem`     | `avancada`    |
| `NULL` / ausente   | `nenhuma`     |

Se o nível declarado não atende o exigido pelo grupo, o endpoint
**numera normalmente** e **registra um evento `todo_regulatorio`** no
ledger:

```json
{
  "receituario_id": 42,
  "tipo_receituario": "notificacao_receita_a",
  "motivo": "nivel_assinatura_insuficiente",
  "nivel_declarado": "avancada",
  "nivel_exigido": "qualificada",
  "tipo_certificado_declarado": "gov_br_nuvem",
  "acao_necessaria": "validar_assinatura_antes_emissao"
}
```

A validação criptográfica real é responsabilidade do **fluxo de emissão
(Ticket 17)**, não da numeração. Numerar é **reserva de número**, não
emissão final — bloquear aqui criaria acoplamento desnecessário.

### Resposta exemplo

```json
{
  "prescricao_protocolo": "REC-001",
  "adapter": "stub",
  "receituarios": [
    {
      "id": 1,
      "tipo": "notificacao_receita_a",
      "numeracao_sncr": "STUB-2026-NRA-000000001",
      "status": "numerado_stub",
      "numerado_em": "2026-04-25T11:00:00",
      "adapter_usado": "stub",
      "requer_sncr": true
    },
    {
      "id": 2,
      "tipo": "receita_simples",
      "numeracao_sncr": null,
      "status": "nao_requer_sncr",
      "numerado_em": "2026-04-25T11:00:00",
      "adapter_usado": null,
      "requer_sncr": false
    }
  ],
  "total_numerados": 1,
  "total_nao_requer_sncr": 1,
  "idempotente": false
}
```

### Eventos do ledger

| Evento                    | Quando                                                 |
|---------------------------|--------------------------------------------------------|
| `receituarios_numerados`  | Pelo menos um receituário mudou de estado nesta chamada |
| `todo_regulatorio`        | Um receituário foi numerado com nível insuficiente     |

---

## 7. Guardrails — resumo

| Guardrail                                  | Onde                          | Por que                                                          |
|--------------------------------------------|-------------------------------|------------------------------------------------------------------|
| Prefixo `STUB-` obrigatório                | `sncr_stub.py`                | Distinguir mock de real por inspeção                            |
| Status `numerado_stub` ≠ `numerado`        | router + model                | Impedir que stub passe por real                                 |
| Sem fallback silencioso de `real` → `stub` | `sncr_factory.py`             | Falhar alto se config errada em produção                       |
| Logs prefixados `[SNCR-STUB]`              | `sncr_stub.py`                | Grep em produção                                                 |
| Validação de assinatura é informativa      | router `/numerar`             | Numerar ≠ emitir; bloquear aqui criaria acoplamento desnecessário |
| Status semântico para sem-SNCR             | router + model                | "numerado" implica passou pelo SNCR; receita simples nunca passou |
| `requer_sncr` derivado do tipo             | router `_requer_sncr()`       | Regra explícita e auditável                                     |

---

## 8. Como substituir o stub pela implementação real (Ticket 16B)

Quando a especificação técnica do SNCR estiver disponível e a plataforma
PicSaúde for credenciada na Anvisa:

1. Criar `app/adapters/sncr_real.py` implementando `SNCRAdapter`:
   - `nome_adapter = "real"`.
   - `requisitar_numeracao()` faz a chamada HTTP autenticada (assinatura
     ICP-Brasil ou método definido pela Anvisa) e retorna numerações
     **sem prefixo `STUB-`**.
   - `verificar_numeracao()` consulta o SNCR em tempo real.
   - `registrar_utilizacao()` registra dispensação no SNCR.
   - `health_check()` faz ping leve no endpoint.
2. Atualizar `sncr_factory.py` para instanciar `SNCRReal` quando
   `SNCR_ADAPTER=real`.
3. Em produção, configurar:
   ```bash
   export SNCR_ADAPTER=real
   ```
4. Status passa a ser `numerado` (sem `_stub`); numeração sem prefixo
   `STUB-`.
5. **O resto do sistema não muda** — endpoint, ledger, motor regulatório
   continuam idênticos.

---

## 9. Pendências regulatórias (fora deste ticket)

- 📋 **Especificação técnica da API do SNCR** — Anvisa.
- 📋 **Credenciamento da plataforma PicSaúde** na Anvisa.
- 📋 **Ambiente de homologação** disponibilizado pela Anvisa.
- 📋 **CPF do prescritor** — hoje a tabela `prescritores` armazena CNS,
  não CPF. Quando `SNCRReal` chegar, definir migração de identidade
  (Ticket 16B). Por ora, o endpoint passa CNS no campo `prescritor_cpf`
  do stub (que aceita qualquer string).
- 📋 **Validação criptográfica de assinatura** — Ticket 17 (emissão).
- 📋 **Grupo 5 — retenção** (antimicrobianos, GLP-1) — Ticket 18.

---

## 10. Cobertura de testes

[`backend/tests/integration/test_sncr_adapter.py`](../backend/tests/integration/test_sncr_adapter.py) — 20 testes cobrindo:

- Stub (6 testes): prefixo, sequencial, vinculação CPF, health, tipo desconhecido, verificar.
- Factory (4 testes): default, stub explícito, real → erro, valor inválido.
- Endpoint `/numerar` (10 testes): controlado, simples, idempotência, sem-gerar→404, todo_regulatorio, ledger, distinguibilidade, prescrição inexistente, outro prescritor → 403, mistura.

Comando:

```bash
export DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_test
cd backend && pytest tests/integration/test_sncr_adapter.py -v
```

---

## 11. Geração de PDF (Ticket 17)

Após `/numerar`, cada receituário pode ser baixado como PDF compatível
(estrutura + campos obrigatórios) com os modelos Anvisa Versão 2
publicados em 16/03/2026.

> **Não é reprodução visual pixel-perfect dos modelos oficiais** — é
> alinhamento estrutural e de campos obrigatórios.

### Endpoint

```
GET /prescricoes/{protocolo}/receituarios/{receituario_id}/pdf
```

- **Auth:** `prescritor` (CNS do token = prescritor da prescrição)
- **Content-Type:** `application/pdf`
- **Filename:** `receituario-{NRA|NRB|RCE|NRE|RSI|RRT}-{id}.pdf`

### Status codes

| Código | Causa |
|---|---|
| 200 | PDF gerado |
| 401 | Token ausente / inválido |
| 403 | Prescritor não é dono da prescrição |
| 404 | Prescrição/receituário inexistente |
| 410 | Receituário substituído por nova geração |
| 422 | Status `gerado` (não numerado) ou `cancelado` |

### Transição de status

| Estado de origem | Estado final | Evento no ledger |
|---|---|---|
| `numerado_stub` | `emitido` | `receituario_emitido` |
| `numerado` (futuro) | `emitido` | `receituario_emitido` |
| `nao_requer_sncr` | `emitido` | `receituario_emitido` |
| `emitido` | `emitido` (idempotente) | `receituario_pdf_acessado` |
| `gerado` | (bloqueado) | — |
| `cancelado` | (bloqueado) | — |

A trilha de re-acesso (`receituario_pdf_acessado`) existe para evitar
inflar o ledger com novos `receituario_emitido` a cada re-download — o
documento é o mesmo, apenas re-renderizado.

### Layout por tipo

| Tipo | Cor primária | Faixa SNCR | Alerta |
|---|---|---|---|
| `notificacao_receita_a` | Amarelo Anvisa (#F9A825) | Sim | Substância controlada |
| `notificacao_receita_b` | Azul Anvisa (#1565C0) | Sim | — |
| `receita_controle_especial` | Cinza-escuro (#37474F) | Sim | — |
| `notificacao_receita_especial` | Roxo (#6A1B9A) | Sim | Risco teratogênico |
| `receita_simples` | Verde PicSaúde (#2E7D32) | Não | — |
| `receita_retencao` (Ticket 18 — ativo) | Verde-azulado (#00695C) | Não (premissa provisória) | — |

> Cores são aproximações dos modelos oficiais; o amarelo (NRA) e o azul
> (NRB) são os regulatoricamente mais relevantes e devem ser claramente
> identificáveis.

### Mudança Anvisa V1 → V2

| Aspecto | V1 (13/02/2026) | V2 (16/03/2026, mandatória 18/05/2026) |
|---|---|---|
| ID paciente | Endereço | **CPF / Passaporte** |
| Endereço | Presente | Removido |

### QR Code

- Posição: canto inferior direito, ~25×25mm
- Lib: `reportlab.graphics.barcode.qr.QrCodeWidget` (sem dependência extra)
- Conteúdo: `protocolo;sncr;hash;tipo;emitido`
- Label: **"QR — Rastreabilidade PicSaúde"** (rastreabilidade interna,
  NÃO validação SNCR oficial)

### Modo stub (adapter_usado="stub")

PDF tem três indicações redundantes de "documento de desenvolvimento":

1. **Marca d'água** diagonal: `"DOCUMENTO SEM VALIDADE REGULATORIA"`
   (Helvetica-Bold 40pt, cinza com transparência ~18%, rotação 45°)
2. **Faixa SNCR** mostra: `[DESENVOLVIMENTO — numeração não regulatória]`
   em vermelho
3. **Rodapé** mostra: `⚠ Numeração STUB — apenas para desenvolvimento e testes`

A numeração tem prefixo `STUB-` (continua válido como sinal de modo).

### CPF do paciente no PDF

| Modo | Comportamento atual | Notas |
|---|---|---|
| Stub | Mascarado: `123.***.***-01` | Privacidade |
| Real (futuro) | Mascarado por padrão | TODO_REGULATORIO emitido — confirmar com Anvisa se documento final exige CPF completo |

### Cobertura de testes

[`backend/tests/integration/test_pdf_receituario.py`](../backend/tests/integration/test_pdf_receituario.py) — 15 testes:

- Geração por tipo (4): NRA, NRB, RCE, RSI
- Bloqueio quando não numerado / cancelado (1)
- Idempotência no acesso repetido (1)
- Evento `receituario_emitido` no ledger (1)
- Marca d'água em modo stub via callback puro (1)
- Evento registra adapter_usado=stub (1)
- QR Code presente (1)
- Receita simples sem indicação SNCR (1)
- Fluxo completo (gerar→numerar→PDF de cada um) (1)
- Autenticação obrigatória (1)
- Posse — outro prescritor → 403 (1)
- Receituário inexistente → 404 (1)

Comando:

```bash
export DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_test
cd backend && pytest tests/integration/test_pdf_receituario.py -v
```

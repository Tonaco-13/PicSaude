# TICKET-C-RENOVACAO-CACHE-PACIENTE — Cache de paciente por CPF no `localStorage` (renovação pré-preenche)

| Campo | Valor |
|---|---|
| **ID** | TICKET-C-RENOVACAO-CACHE-PACIENTE |
| **Classe** | `local-extension` (não toca núcleo, não altera schema, não quebra contrato público) |
| **Para** | Kimi 3 (implementa) → Revisor (Claude Code/app) → Conselheiro (Fable 5) → Arquiteto ratifica → Fabiano martela |
| **Origem** | Achado do extensionista (2026-08-02) · ratificado em KIMI3-002 §5 |
| **Pré-requisito** | Nenhum (decisão ratificada: opção c, cache localStorage) |
| **Risco** | Baixo — frontend puro, fallback seguro (vazio), sem mexer em backend/estados/ledger |
| **Dívida associada** | `docs/dividas/DIVIDA-CORE-PACIENTE-DADOS-RENOVACAO.md` (persistência real, `core`, deferida) |

---

## §1 Contexto (não reabrir)

Ao **renovar uma receita digital**, o prescritor precisa **redigitar** idade, telefone, endereço, CEP e cidade/UF — mesmo que esses dados já tenham sido informados na prescrição origem. A causa-raiz é `core` (a tabela `pacientes` não persiste esses campos; ver dívida associada) e fica fora deste escopo.

**Decisão ratificada (Fabiano + parecer Fable 5, 2026-08-02 · reafirmada KIMI3-002 §5):** solução paliativa **opção (c)** — cache de paciente por CPF no `localStorage` do `prescritor.html`. Resolve a UX da demo sem migração de schema. A persistência real no backend é `core` e fica como dívida.

**Hoje (`prescritor.html`):**
- `renovarReceita(id)` (linha 2293) chama `_preencherFormularioReceita(r)` (linha 1518) — a intenção de pré-preencher **já existe**.
- Porém `r` vem de `_receitaDoBackend(pres)` (linha 1489), que do backend só tira `paciente_nome`, `paciente_cpf`, `itens`. Os outros campos **só aparecem se** houver cópia física no `localStorage` (`pix_saude_db_v27`). Para prescrição digital, ficam em branco.

---

## §2 Invariantes (não-negociáveis)

- **R1 (reprodutibilidade):** nenhuma mudança no backend, ledger, estados, custódia. Só `prescritor.html`.
- **Semântica clínica zero:** não toca em `POST /prescricoes`, `tipo_emissao`, `origem_prescricao_id`. A renovação continua emitindo um novo objeto derivado como hoje.
- **Classe `local-extension`:** não adiciona campo obrigatório a tabela, não quebra contrato público.
- **PII em `localStorage`:** aceitável para contexto de demo/local. Trade-off registrado na dívida core.
- **Fallback seguro:** se o cache estiver vazio/corrompido, o formulário volta ao comportamento atual (campos em branco). **Nunca** bloquear a renovação por falta de cache.

---

## §3 Spec de implementação

### 3.1 Arquivo tocado

- `prescritor.html` — apenas este arquivo.

### 3.2 Estrutura do cache

**Chave:** `pix_saude_pacientes_cache` (objeto JSON em `localStorage`).

**Valor:** objeto mapeando `cpf_normalizado → dados`:

```js
{
  "12345678909": {                    // CPF normalizado (somente dígitos)
    "nome": "João Demo da Silva",
    "idade": "45 anos",
    "telefone": "81 99999-0000",
    "endereco": "Rua Exemplo, 123 - Centro",
    "complemento": "Apto 4",
    "cep": "50000-000",
    "cidade": "Recife",
    "uf": "PE",
    "atualizado_em": "2026-08-02T..."
  }
}
```

### 3.3 Normalização de CPF

O frontend **já usa** o padrão `.replace(/\D/g, '')` em vários pontos (`prescritor.html:1877, 1900, 1949, 1989, 3247`). Reusar esse padrão — **não** importar `normalize_cpf` do backend (é Python).

Recomendação: se ainda não houver um helper local, introduzir um para evitar repetição:

```js
function _normalizarCpf(cpf) {
    return (cpf || '').replace(/\D/g, '');
}
```

**A chave do cache é sempre o CPF normalizado** (somente dígitos). Testar com CPF formatado (`123.456.789-09`) e sem formatação (`12345678909`) — ambos devem bater na mesma entrada.

### 3.4 Gravar (write-through na emissão bem-sucedida)

Após `POST /prescricoes` (e também no fluxo físico, se aplicável) retornar **sucesso**, gravar/atualizar o cache com os dados do paciente do formulário:

```js
function _gravarPacienteNoCache() {
    try {
        const cpf = _normalizarCpf(document.getElementById('pac-chave').value);
        if (!cpf || cpf.length !== 11) return;            // só grava CPF válido (11 dígitos)
        const cache = JSON.parse(localStorage.getItem('pix_saude_pacientes_cache') || '{}');
        cache[cpf] = {
            nome:        document.getElementById('pac-nome').value || '',
            idade:       document.getElementById('pac-idade').value || '',
            telefone:    document.getElementById('pac-telefone').value || '',
            endereco:    document.getElementById('pac-endereco').value || '',
            complemento: document.getElementById('pac-complemento').value || '',
            cep:         document.getElementById('pac-cep').value || '',
            cidade:      document.getElementById('pac-cidade').value || '',
            uf:          document.getElementById('pac-uf').value || '',
            atualizado_em: new Date().toISOString(),
        };
        localStorage.setItem('pix_saude_pacientes_cache', JSON.stringify(cache));
    } catch (_e) { /* localStorage indisponível (modo privado) — silencia */ }
}
```

**Chamar em:** emissão digital (após sucesso do `POST /prescricoes`) e emissão física (após o fire-and-forget, já que os dados do paciente foram informados).

### 3.5 Ler (pré-preencher na renovação)

Em `_receitaDoBackend(pres)` (`prescritor.html:1489`), **antes** do fallback de `pix_saude_db_v27`, tentar o cache por CPF:

```js
function _receitaDoBackend(pres) {
    let demo = {};
    try {
        const db = JSON.parse(localStorage.getItem('pix_saude_db_v27')) || {};
        demo = (db.receitas || []).find(x => x.protocolo_backend === pres.protocolo) || {};
    } catch (_e) { /* localStorage indisponível */ }

    // NOVO: cache por CPF (TICKET-C-RENOVACAO-CACHE-PACIENTE) — precedência sobre o
    // fallback de receita física, abaixo do backend (fonte de verdade primária).
    let cacheado = {};
    try {
        const cache = JSON.parse(localStorage.getItem('pix_saude_pacientes_cache') || '{}');
        cacheado = cache[_normalizarCpf(pres.paciente_cpf)] || {};
    } catch (_e) { /* cache indisponível */ }

    return {
        id: pres.protocolo,
        paciente_nome:        pres.paciente_nome || cacheado.nome        || demo.paciente_nome || '',
        paciente_chave:       pres.paciente_cpf  || cacheado.nome /*n/a*/|| demo.paciente_chave || '',
        paciente_idade:       cacheado.idade       || demo.paciente_idade || '',
        paciente_telefone:    cacheado.telefone    || demo.paciente_telefone || '',
        paciente_endereco:    cacheado.endereco    || demo.paciente_endereco || '',
        paciente_cep:         cacheado.cep         || demo.paciente_cep || '',
        paciente_cidade_uf:   [cacheado.cidade, cacheado.uf].filter(Boolean).join(' - ')
                                                 || demo.paciente_cidade_uf || '',
        medicamentos: (pres.itens || []).map(i => ({ /* … inalterado … */ })),
    };
}
```

> **Precedência (importante):** (1) backend (se algum dia prover o campo) > (2) cache por CPF (`pix_saude_pacientes_cache`) > (3) receita física local (`pix_saude_db_v27`) > (4) vazio. O cache **não sobrescreve** o que vier do backend.

### 3.6 Higiene (limite do cache)

**Não crescer indefinidamente.** Adicionar controle de tamanho no `_gravarPacienteNoCache`:

- **Opção recomendada:** LRU por `atualizado_em` — manter os últimos **50** pacientes. Se exceder, remover o com `atualizado_em` mais antigo.
- Alternativa aceitável: TTL (ex.: expirar entrada após 90 dias sem atualização).

Decisão do Kimi 3; **documentar o critério escolhido no PR.**

---

## §4 Critérios de aceite

1. **Emissão grava:** após emitir uma receita digital com paciente preenchido, o cache contém a entrada sob o CPF normalizado.
2. **Renovação lê:** ao renovar uma receita digital cujo paciente está no cache, **todos** os campos (nome, idade, telefone, endereço, complemento, CEP, cidade, UF) vêm pré-preenchidos.
3. **Precedência:** se o backend prover algum campo no futuro, ele prevalece sobre o cache (o cache é fallback, não fonte de verdade).
4. **Chave normalizada:** CPF formatado (`123.456.789-09`) e sem formatação (`12345678909`) batem na mesma entrada.
5. **Fallback seguro:** se o cache estiver vazio/corrompido/localStorage indisponível, o formulário volta ao comportamento atual (campos em branco) — **nunca** bloqueia a renovação.
6. **Idempotente:** gravar o mesmo paciente múltiplas vezes atualiza a mesma entrada (não duplica).
7. **Higiene documentada:** o critério de limite (LRU/TTL) está implementado e justificado no PR.
8. **Sem regressão:** `renovarReceita` de uma receita cujos dados só existem em `pix_saude_db_v27` (receita física legada) continua funcionando como antes.
9. **Sem mudança de backend:** `grep -nE "tipo_emissao|origem_prescricao_id|POST.*prescricoes" prescritor.html` não mostra mudanças na lógica de emissão (só adição do `_gravarPacienteNoCache`).

---

## §5 Browser-E2E (obrigatório no aceite)

Adicionar `tests/browser/test_c_renovacao_cache_paciente.py` (ou nome análogo):

```python
def test_c_grava_paciente_no_cache_apos_emissao(browser_demo):
    """Após emitir receita digital, cache localStorage tem a entrada por CPF."""
    # Login prescritor demo
    # Preencher formulário com paciente completo (nome, idade, endereço, etc.)
    # Submeter emissão digital (mockar/interceptar o POST se necessário)
    # Assert: localStorage['pix_saude_pacientes_cache'] contém a chave CPF normalizada
    # Assert: a entrada tem todos os campos preenchidos

def test_c_renovacao_pre_preenche_do_cache(browser_demo):
    """Renovar uma receita digital pré-preenche do cache (não pede redigitação)."""
    # Setup: garantir que o cache tem o paciente (ou emitir antes)
    # Abrir histórico, clicar em "Renovar Receita"
    # Assert: campo #pac-nome NÃO está vazio
    # Assert: campo #pac-idade NÃO está vazio
    # Assert: campo #pac-endereco NÃO está vazio
    # (etc. para telefone, complemento, CEP, cidade, UF)

def test_c_chave_cpf_normalizada(browser_demo):
    """CPF formatado e sem formatação batem na mesma entrada de cache."""
    # Gravar no cache via JS com CPF "123.456.789-09"
    # Ler com CPF "12345678909" — deve retornar a mesma entrada

def test_c_fallback_seguro_cache_vazio(browser_demo):
    """Cache vazio não quebra a renovação (campos em branco, comportamento atual)."""
    # Limpar localStorage['pix_saude_pacientes_cache']
    # Renovar uma receita digital (sem cache, sem física local)
    # Assert: formulário abre normalmente (não trava)
    # Assert: campos de paciente estão vazios (comportamento atual)
```

> **Lição do COER-2 (reafirmada):** o E2E deve afirmar sobre o **DOM renderizado**, não sobre respostas de API isoladas.

---

## §6 [PII-EXAUSTIVIDADE] — rotas tocadas

| Rota | PII | Muda neste ticket? |
|---|---|---|
| `POST /prescricoes` | paciente nome+CPF, prescritor | Não — apenas lemos a resposta de sucesso pra decidir gravar o cache; payload inalterado |
| `GET /prescricoes/{proto}` (histórico) | paciente nome+CPF | Não — apenas lemos |

Nenhuma rota nova. Nenhum PII exposto além do que já transita. O cache em `localStorage` é **replicação local** de dados que o próprio usuário digitou — não há vazamento novo.

---

## §7 Fora de escopo

- **Persistência real de dados do paciente no backend** → `core` (dívida `DIVIDA-CORE-PACIENTE-DADOS-RENOVACAO`).
- **Renovação de atestado** — `renovarAtestado` não existe; `atestados.py:66` só aceita `{"nova","correcao"}`. Feature faltante, ticket separado se decidirem.
- **Sincronização do cache entre dispositivos** — não é objetivo do paliativo (registrado como trade-off na dívida).
- **Criptografia do `localStorage`** — fora de escopo pra demo; PII em localStorage é aceitável no contexto (registrado).

---

## §8 Não fazer

- Não criar endpoint de backend.
- Não alterar `POST /prescricoes`, `tipo_emissao`, ou `origem_prescricao_id`.
- Não sobrescrever campos que o backend prover (o cache é fallback).
- Não bloquear a renovação se o cache falhar (fallback seguro obrigatório).
- Não commitar junto com trabalho de outras frentes (F5-C3, etc.) — ver KIMI3-002 §3.

---

## §9 Fluxo de aprovação

1. Kimi 3 implementa + browser-E2E (§5) verde local.
2. Branch: `local-extension/renovacao-cache-paciente`.
3. **Revisor (Claude Code/app):** audita contra este ticket (§4 critérios) e os invariantes (§2). *Gate bloqueante.*
4. **Conselheiro (Fable 5):** parecer leve — confirma fallback seguro e precedência.
5. **Arquiteto (GLM-5.2):** ratifica.
6. **Martelo do Fabiano** + merge.
7. Gate de CI verde → testes de jornada → martelo (KIMI3-002 §2).

---

## §10 Coordenadas

| Artefato | Caminho |
|---|---|
| Handoff (spec anterior) | `docs/tickets/HANDOFF-FRONTEND-KIMI3.md` §10.C |
| Despacho que desbloqueia | `DESPACHO KIMI3-002` §5 |
| Dívida core (persistência real) | `docs/dividas/DIVIDA-CORE-PACIENTE-DADOS-RENOVACAO.md` |
| Código-fonte (`_receitaDoBackend`) | `prescritor.html:1489-1514` |
| Código-fonte (`renovarReceita`) | `prescritor.html:2293-2315` |
| Código-fonte (`_preencherFormularioReceita`) | `prescritor.html:1518-1536` |
| Backend emissão renovação | `backend/app/routers/prescricoes.py:60, 301-311` |

---

*Ticket emitido pelo arquiteto de backend (GLM-5.2) em 2026-08-02. Desbloqueia o item C (KIMI3-002 §5). Kimi 3 pode iniciar a implementação.*

# TICKET-PRESCRITOR-DEV-MODE-SEM-NOME-REAL — Tirar nome civil real do fallback DEV_MODE do prescritor.html

| Campo | Valor |
|---|---|
| **Classe** | `local-extension` (customização institucional, sem impacto clínico) |
| **Para** | Arquiteto (este spec) → Engenheiro (Claude/Code) → martelo Fabiano |
| **Origem** | Achado adjacente do Engenheiro durante o TICKET-RODAPE-CONTATO (2026-07-25): `prescritor.html:1311` usa o nome civil real do responsável técnico como persona de login DEV_MODE. |
| **Pré-requisito** | `main` atual |
| **Risco** | Baixo — uma string, ramo de código nunca executado em produção. |

## §1 Contexto (não reabrir)

O `prescritor.html` tem um atalho de login para desenvolvimento offline:

```js
// prescritor.html:1305-1318 (aprox.)
if (DEV_MODE && identificador === DEV_LOGIN_CPF && senha === '123') {
    jwtAccessToken = 'DEV_TOKEN';
    medicoLogado = {
        nome: 'Dr. Fabiano Tonaco Borges',     // ← nome civil real
        cns: '700000000000001',
        conselhos: [{ tipo: 'CRM', uf: 'PE', numero: '9999' }]
    };
    _entrarNoDashboard();
    return;
}
```

### Exposição atual: nula

Confirmado em 2026-07-25 (ZCode + Engenheiro):
- Esse ramo só executa quando `DEV_MODE === true`.
- Na **vitrine pública** (picsaude.com.br), `PICSAUDE_DEMO_MODE=true` e `DEV_MODE=false` — o ramo nunca dispara, a string não é renderizada no DOM.
- O usuário final nunca vê esse nome através desta página.

### Por que ainda assim merece ticket

1. **Dívida operacional latente.** Amanhã um refactor pode tirar essa string do `if DEV_MODE`, ou um typo/flag errado pode ativar DEV_MODE em produção. Nome civil real como fallback hardcoded é uma armadilha esperando descuido.
2. **Consistência com a decisão de produto (TICKET-RODAPE-CONTATO).** Se a tese é "identificação pessoal real não deve aparecer na web pública do PicSaúde", a string em `prescritor.html:1311` viola o princípio mesmo que não renderizada hoje — porque a proteção vem de uma flag, não de o dado não estar lá.
3. **Custo da mudança é trivial.** Uma string. Semântica zero afetada.

### Decisão arquitetural

Substituir `'Dr. Fabiano Tonaco Borges'` por `'Dr. Demo Médico (DEV)'` (ou similar — engenheiro decide o texto). A persona demo canônica (`Dra. Demo Maria Souza`, CNS `980001112223334`) já existe no seed e é o que aparece na vitrine; o DEV_MODE só precisa de uma persona fictícia qualquer para o teste offline.

## §2 Invariantes (não-negociáveis)

- **R1 (reprodutibilidade):** nenhuma mudança de comportamento. O ramo `DEV_MODE` continua funcionando, só muda a string exibida.
- **Semântica clínica zero:** não toca em estados, ledger, custódia, RBAC.
- **Classe `local-extension`:** não adiciona campo obrigatório a tabela, não quebra contrato público.

## §3 Spec de implementação

### 3.1 Arquivo tocado
- `prescritor.html` — linha ~1311

### 3.2 Mudança
```js
// antes
nome: 'Dr. Fabiano Tonaco Borges',

// depois
nome: 'Dr. Demo Médico (DEV)',
```

Texto alternativo aceitável: `'Dr. Demo (DEV_MODE)'`. Engenheiro decide; o importante é **não conter nome civil real**.

### 3.3 Checklist PII-EXAUSTIVIDADE (obrigatório)

Após implementação, rodar e colar output no PR:

```bash
grep -rnE "Fabiano Tonaco Borges|Fabiano Borges" --include="*.html" prescritor.html
```

**Esperado:** zero ocorrências em `prescritor.html`.

Confirmar que as ocorrências remanescentes no repo continuam justificadas (ver tabela do TICKET-RODAPE-CONTATO §4.5 — mesma justificativa se aplica).

## §4 Critérios de aceite

1. `prescritor.html` não contém "Fabiano" em nenhuma linha
2. Ramo `DEV_MODE` continua funcional (login com `DEV_LOGIN_CPF` + senha `123` ainda entra no dashboard)
3. Smokes verdes (`test_smokes.py::TestConsoleLimpo::test_tela_sem_erro_de_console[chromium-prescritor.html]`)
4. Checklist §3.3 colado no PR

## §5 Fora de escopo

- Mudar `DEV_LOGIN_CPF`, senha `123`, CNS fictício — todos podem permanecer (são fictícios)
- Migrar DEV_MODE pra outro mecanismo — dívida separada
- Mexer em personas demo canônicas do seed (`Dra. Demo Maria Souza` etc.) — não tem nome civil real

## §6 Browser-E2E

Não há teste novo necessário. O smoke existente de console limpo em `prescritor.html` cobre a não-quebra. Se o engenheiro quiser asserção explícita:

```python
def test_prescritor_sem_nome_real_no_source(page, app_demo):
    """Mesmo no source, nome civil real não deve aparecer (TICKET-PRESCRITOR-DEV-MODE)."""
    # Não precisa de goto — asserção sobre o HTML servido.
    resp = page.request.get(f"{app_demo}/prescritor.html")
    assert "Fabiano" not in resp.text(), "prescritor.html ainda contém nome civil real"
```

## §7 Fluxo de aprovação

1. Engenheiro implementa (1 linha) + checklist §3.3
2. Conselheiro (Cowork) — parecer leve (só confirma que a string sumiu e DEV_MODE continua funcionando)
3. Martelo do Fabiano + merge
4. Deploy — sem urgência (risco atual = zero, mas a dívida some)

## §8 Não fazer

- Não mudar o texto pra outro nome civil real
- Não remover o ramo DEV_MODE inteiro (fora de escopo)
- Não adicionar endpoint
- Não tocar em `LICENSE`, `COMMERCIAL-LICENSE.md`, etc.

## §9 Coordenadas

| Ticket | Relação |
|---|---|
| **TICKET-RODAPE-CONTATO** | Origem deste achado. Independente — pode rodar em paralelo ou depois. |
| **Etapa C (F5-C1/C2/C3)** | Em pausa. Independente. |

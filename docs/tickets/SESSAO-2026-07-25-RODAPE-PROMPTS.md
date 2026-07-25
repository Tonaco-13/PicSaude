# Sessão 2026-07-25 — Prompts para despacho (TICKET-RODAPE-CONTATO)

Arquiteto (ZCode) → **Engenheiro** (Claude/Code terminal) → **Conselheiro** (Claude Cowork) → martelo Fabiano.

Ticket completo: `docs/tickets/TICKET-RODAPE-CONTATO.md`

---

## 🛠 PROMPT 1 — para o Engenheiro (Claude/Code no terminal)

Copie e cole no Claude Code:

```
Implemente o TICKET-RODAPE-CONTATO (docs/tickets/TICKET-RODAPE-CONTATO.md).
Classe: local-extension. Pré-requisito: main atual.

## Escopo (2 mudanças, frontend puro)

### Mudança 1 — index.html: INSERIR e-mail institucional
No rodapé (linha ~514), APÓS a linha "Responsável técnico: Dr. Fabiano
Tonaco Borges.", adicionar nova div:

    <div class="footer-brand" style="margin-top:4px; font-size:11px; opacity:.85;">
      Contato: <a href="mailto:contato@picsaude.com.br"
                  style="color:inherit; text-decoration:underline;">contato@picsaude.com.br</a>.
    </div>

NÃO remover a linha do responsável técnico — ela permanece (instrução
explícita do Fabiano).

### Mudança 2 — guia.html: REMOVER bloco .contact
Apagar o bloco inteiro (linhas ~425-429):

    <div class="contact">
      <span class="name">Prof. Dr. Fabiano Tonaco Borges</span>
      <span class="org">Universidade Federal de Pernambuco</span>
      <a href="mailto:fabiano.borges@ufpe.br">fabiano.borges@ufpe.br</a>
    </div>

O bloco <div class="demo-hooks"> (que fica ANTES do .contact) PERMANECE
intacto — não é contato pessoal.

### Decisão CSS morto (opção A — aplicar)
Após remover o .contact, as regras CSS ficam órfãs. Remover:
- guia.html linhas 235-239 (.contact, .contact .name, .contact .org, .contact a, .contact a:hover)
- guia.html linha 248 (.contact { text-align: left; } no media query)
- guia.html linha 254 (.contact .name { background: #fff !important; } no @media print)

Justifique no commit: "CSS morto após remoção do bloco .contact (TICKET-RODAPE-CONTATO §4.4 opção A)".

## Obrigatório antes do commit

### 1. Rodar e colar output no PR (checklist PII-EXAUSTIVIDADE):
    grep -rnE "Fabiano Tonaco Borges|Fabiano Borges" --include="*.html" --include="*.py" --include="*.md" .
    grep -rnE "fabiano\.borges@ufpe\.br" --include="*.html" --include="*.py" --include="*.md" .
    grep -rnE "contato@picsaude\.com\.br" --include="*.html" --include="*.py" --include="*.md" .

Esperado após implementação:
- guia.html: ZERO ocorrências de Fabiano e fabiano.borges@ufpe.br
- index.html: 1 ocorrência de Fabiano (mantida) + 1 de contato@picsaude.com.br (nova)
- Demais arquivos (LICENSE, COMMERCIAL-LICENSE.md, README.md...): colar cada ocorrência
  remanescente com justificativa inline ("arquivo de licença, não exibição web pública")

### 2. Rodar smokes (gate de browser local):
    cd backend
    python -m pytest tests/browser/test_smokes.py -v

Critério: todos verdes (incluindo TestGuiaNaVitrine e TestPortal).

### 3. Branch e commits
    git checkout -b local-extension/rodape-contato
    # ... 2 commits separados sugeridos:
    #   (a) feat(local): guia.html sem contato pessoal no rodapé
    #   (b) feat(local): index.html com e-mail institucional no rodapé
    # OU 1 commit único se preferir — engenheiro decide.

## Não fazer
- Não remover "Responsável técnico: Dr. Fabiano Tonaco Borges." do index.html
- Não remover .demo-hooks do guia.html
- Não tocar em LICENSE / COMMERCIAL-LICENSE.md / README.md (autores em arquivo de licença ≠ exibição web pública)
- Não adicionar endpoint, não tocar no backend

## No PR, incluir
- Output dos 3 greps do checklist PII
- Confirmação "smokes verdes: N passed"
- Link/refs ao ticket docs/tickets/TICKET-RODAPE-CONTATO.md

Quando terminar, NÃO faça merge — aguarde parecer do Conselheiro.
```

---

## 🔍 PROMPT 2 — para o Conselheiro (Claude Cowork)

Após o Engenheiro abrir o PR, copie e cole no Claude Cowork:

```
Revise o PR local-extension/rodape-contato. Papel: Conselheiro (parecer
verde / verde-com-notas / bloqueio). Classe: local-extension. Ticket de
referência: docs/tickets/TICKET-RODAPE-CONTATO.md.

## Foco da revisão

### 1. PII-EXAUSTIVIDADE (LEARNINGS 2026-07-09) — ponto mais crítico
O PR mexe em PII (remove nome civil + e-mail pessoal UFPE de página web pública).
Exija que o engenheiro colou no PR o output dos 3 greps:

    grep -rnE "Fabiano Tonaco Borges|Fabiano Borges" --include="*.html" --include="*.py" --include="*.md" .
    grep -rnE "fabiano\.borges@ufpe\.br" --include="*.html" --include="*.py" --include="*.md" .
    grep -rnE "contato@picsaude\.com\.br" --include="*.html" --include="*.py" --include="*.md" .

Confirme:
(a) guia.html está limpo (zero ocorrências do nome e do e-mail UFPE)
(b) index.html mantém o nome do responsável técnico + tem a nova linha contato@picsaude.com.br
(c) TODA ocorrência remanescente em outros arquivos tem justificativa inline
    (LICENSE/COMMERCIAL-LICENSE.md/README.md são esperados e aceitáveis — não
    são exibição web pública)

Se o grep não tiver sido colado, ou se houver ocorrência sem justificativa →
BLOQUEIO.

### 2. Decisão CSS morto (§4.4 do ticket)
Confirmar que o engenheiro justificou opção A (remover) ou B (comentar).
Sem justificativa → verde-com-notas.

### 3. Adjacências (o ponto que mais pegou bugs no histórico)
- O bloco .demo-hooks (DEMO-FILA-0001 etc.) foi preservado no guia.html?
- A linha "Responsável técnico" foi preservada no index.html (não removida por engano)?
- Smokes verdes (TestGuiaNaVitrine, TestPortal)?

### 4. Classe local-extension — invariantes
Confirmar que o PR NÃO toca em:
- AGENTS.md, NUCLEO_SANITARIO.md, states.py, ledger, custódia
- Nenhum endpoint público (/public/*)
- Nenhum backend

Se tocou em qualquer um → BLOQUEIO (mudou de classe).

Verde = aprovo merge; verde-com-notas = aprovo com ajustes que peço ao
engenheiro; bloqueio = não deve mergear, justifique.
```

---

## 📋 Orquem de despacho

1. **PROMPT 1** → Claude/Code terminal (executa + abre PR)
2. **PROMPT 2** → Claude Cowork (revê o PR aberto)
3. Traga o parecer do Cowork de volta ao ZCode
4. ZCode (arquiteto) ratifica ou pede ajuste
5. Martelo do Fabiano + merge + deploy

## Observação para o Fabiano

- Este ticket É pequeno em linhas de código (~10 linhas), mas a classe
  `local-extension` exige checklist PII por decisão metodológica (LEARNINGS).
  O custo do checklist é menor que o custo de um PII vazando por descuido.
- Deploy: depois do merge, validar ao vivo em:
  - https://picsaude.com.br/guia.html (sem nome/e-mail no rodapé)
  - https://picsaude.com.br/ (com contato@picsaude.com.br no rodapé)

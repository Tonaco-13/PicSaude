# SESSÃO-B2 — A reescrita do histórico git (registro do arquiteto para historiadores futuros)

| Campo | Valor |
|---|---|
| **Data** | 2026-08-31, executada pelo arquiteto (Z) em sessão |
| **Martelo** | Fabiano, 31/08: *"b2 intermediário"* (GP-3 §4 — histórico COMO × O QUE) |
| **Pré-condições cumpridas** | Curadoria E11+J45 mergeada (#233) · identidade sintética na árvore (B1, #235/#236) |
| **Estado** | ✅ EXECUTADA e verificada |

---

## §1 Por que os shas antigos não resolvem mais

Se você está lendo um ticket antigo e um sha citado não existe mais: **o
histório do repositório foi reescrito em 31/08/2026**, por decisão de
go-public (GP-3 §4, opção "intermediária"). Os commits antigos **não são
ancestrais** dos atuais — a main pós-B2 não tem ancestralidade comum com a
main pré-B2 (confirmado por `git merge-base` vazio). O conteúdo técnico foi
preservado; os **identificadores** mudaram todos.

**Âncoras da fronteira:**

| | sha |
|---|---|
| main imediatamente ANTES da reescrita | `ae525b6a7649a907f143139c2eec616fc62dc3e8` |
| main imediatamente DEPOIS (equivalente) | `994f75ab87e8bc3ad7f6c9218c3bb2f24fe4bd5f` |

Para achar o equivalente de um commit antigo: o **mensagem**, a **data de
autoria** e o **conteúdo** são os fósseis confiáveis — o sha não é.

## §2 O que a reescrita removeu (e o que não tocou)

**Removeu de TODO o histórico (57 refs):**

1. O path `planejamento/` inteiro — documentos de gestão (14 arquivos na
   árvore final; todos os commits os carregavam junto de mudanças técnicas,
   por isso nenhum commit precisou ser descartado: 496 antes = 496 depois).
2. Por substituição de conteúdo (`--replace-text`), as três strings da
   identidade de aparência real que a auditoria GP-3 §3 achou (par nome+CNS+USF
   no mock CNES) — substituídas pelos sintéticos da demo em TODAS as ocorrências
   históricas, espelhando o que a B1 fez na árvore viva.

**Não tocou:** nenhum outro arquivo. Verificação de árvore: 918→904 arquivos
na main; os 14 sumidos são todos `planejamento/`; **zero diferença fora dele**.

## §3 As cinco provas (todas antes do force-push)

1. Strings proibidas (`git log --all -S`): CNS, nome, USF — **zero ocorrências** nos 57 refs.
2. `planejamento/` em objetos: **zero**.
3. Árvore intacta fora do path removido (comparação de listas de arquivos).
4. História técnica preservada: 496 commits antes e depois.
5. Suíte de testes na árvore reescrita: **612 passed** (`tests/unit`).

## §4 A verdade honesta (limitação do GitHub)

O force-push limpou a main e todas as branches — mas **blobs antigos podem
permanecer acessíveis nas páginas de PR do GitHub** até a coleta de lixo
deles. Para dado de *aparência* real (não segredo), a cura é proporcional.
Purga absoluta exigiria ticket ao suporte do GitHub ou recriação do repo —
não executada, por desproporcional.

## §5 Artefatos da execução

- **Execução**: mirror clone → `git filter-repo --path planejamento --invert-paths --replace-text` → verificação → `push --force --all` (57 refs).
- **Backup local da árvore de trabalho pré-re-clone**: `PicSaude_Dev.pre-b2-backup` (máquina do Fabiano).
- **Re-clone do engenheiro**: executado no aviso; confirmou CNS antigo e `planejamento/` ausentes do histórico.
- **Nota de processo**: a descoberta que mudou o plano — eram **57 refs** carregando o histórico velho; force-pushar só a main teria sido curandeirismo (o CNS continuaria vivo em 56 branches).

## §6 Leitura para quem chega de fora

O que você vê no histórico público é a **história técnica completa** do
PicSaúde: commits, tickets, decisões de arquitetura — tudo. O que saiu foi o
que nunca foi do domínio público: documentos de gestão interna e uma
identidade de aparência real que não tinha consentido com nada disso.

*Aberto por decisão do Fabiano; executado e verificado pelo arquiteto; a
fachada que você vê é a casa como ela escolheu se mostrar.*

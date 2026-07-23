# LEARNINGS — PicSaúde

Aprendizados de processo que viram **check obrigatório** de revisão. Cada item nasce
de um furo real; a régua existe para não repetir.

---

## Checks obrigatórios de revisão

### [PII-EXAUSTIVIDADE] — mudança que adiciona/toca coluna PII
Toda mudança que adiciona ou toca uma coluna PII (nome, CPF, documento, endereço,
telefone, comprador, paciente…) **deve**, antes do merge:

1. **Listar TODAS as rotas** que leem **ou** escrevem a coluna, com a **auth de cada uma**
   (`require_role(...)` ou público).
2. **Confirmar que nenhuma é pública** (sem auth). CPF/documento em rota `/public/*`
   é problema **regulatório**, não técnico — bloqueia merge.
3. A lista deve ser **exaustiva** — não pode faltar rota **do próprio PR**.

**Diferenciação (Fabiano, 2026-07-09):** auditoria independente (Jules) é obrigatória
para **interpretação arquitetural** ("viola §3?", "design correto?"). Para **fato
factual** ("a rota X é pública?"), **code + grep é suficiente** — aceitar a tabela
verificada no código aqui não quebra o princípio de auditoria-sobre-self-check.

**Origem:** PR #84 (T5 comprador). A auditoria Jules **omitiu** `GET /dispensadores/historico`
— rota do próprio PR que retorna `comprador_nome`. Risco real = zero (grep confirmou:
todas as 4 rotas que tocam `comprador_*` exigem `require_role`, nenhuma `/public/*`),
mas a falha metodológica (auditoria não-exaustiva) virou esta régua.

---

## Log de aprendizados

| Data | Origem | Aprendizado |
|---|---|---|
| 2026-07-09 | #84 | **Exaustividade PII** (check acima). Auditoria independente não pode perder rota do próprio PR; para fato factual, grep no código basta. |
| 2026-07-09 | #83 | **Portão de core pega o erro adjacente que a auditoria de implementação passa.** Ex.: a auto-correção do estorno-objeto-derivado (difícil) acertou, mas deixou custódia dupla no T1.5 (adjacente). Verificar o relatório contra o código real é o que faz o processo funcionar. |
| 2026-07-10 | TICKET-F5 (parecer Z AI) | **Protótipo é spec de UX, não contrato de dados.** Ao derivar ticket de um protótipo (v27 .txt), cada campo de dado passa pelo crivo dos invariantes — ex.: `End_Paciente` no CSV do protótipo foi **rejeitado** por minimização de PII, com desvio documentado no ticket (§2.4). Padrão a reproduzir em toda fatia cidadão/prescritor. |
| 2026-07-10 | martelo Fabiano | **Cadência de auditoria proporcional ao risco da classe.** Jules por PR só em `core`; em `module`, por marco (fatia completa/fase). Motivo: auditoria dissonante (54% falso-positivo na ultra-review; rota omitida + branch divergente em #84) custa duas vezes — verificar o auditor e dessensibilizar para achados reais. Regra de método: Jules audita o **SHA exato** do PR/fatia, nunca branch própria. Compensações no intervalo: gate PG, revisão arquiteto×código, teste manual do dono. |
| 2026-07-11 | #88 / B0 | **Diagnóstico encerrado pode revelar achado adjacente que vira ticket próprio.** O diagnóstico do #88 concluiu "não era bug" (relatório Fatia A correto; o teste manual consumiu a receita inteira), mas **tropeçou no cenário do B0 sem nomeá-lo** — item terminal, "nada mais a dispensar". Regra: **não reabrir o diagnóstico encerrado; abrir ticket novo** para o achado adjacente (TICKET-B0). O B0 (guard lê `status_item` em vez do saldo efetivo) é o caso concreto da tese "a verdade deriva do ledger, nunca do rótulo". |
| 2026-07-12 | Ensaio F5 (branch de integração) | **Roteiro/UX que depende de autenticação deve ser verificado contra as TRAVAS DO MODO DEMO.** O Ato 6 assumia re-login por CNPJ (vale no login real), mas o modo demo bloqueia `/auth/token` (403). O invariante (relatório travado ao CNPJ) estava intacto na API; o descompasso era só a mecânica de troca na vitrine. O **ensaio de montagem** (rodar os N PRs juntos numa branch descartável antes do merge) é onde esse furo aparece — cada PR passa no gate na própria base, mas os PRs juntos nunca foram exercitados até a montagem. Corrigir a spec, não improvisar na apresentação. |
| 2026-07-22 | Item 3 — atestado físico (A) | **O §6 (offline) NÃO é uniforme — depende de ONDE MORA A VERDADE DO DOCUMENTO.** Texto client-computável (receita = lista de medicamentos que o navegador monta) pode nascer offline. Documento com **renderizador único no servidor** (atestado: o PDF de `GET /atestados/{proto}/pdf`) **não** — forçar offline criaria um **segundo renderizador do documento oficial**: o falso-espelho no nível do DOCUMENTO, pior que no texto (dois documentos com a aparência da mesma autoridade, proveniências diferentes). Por isso o físico do atestado é **A** (`POST /atestados/fisica` → protocolo → `GET pdf` → imprime), síncrono **por natureza, não por escolha** — o documento *é* o retorno. O §6 protege a impressão da receita; não obriga o atestado a mentir sobre quem o renderiza. **Meta-lição:** foi o **comentário-no-código** (`imprimirRascunhoAtestado:3846` — o *porquê* da tarja: "o documento oficial tem UM renderizador") que salvou o invariante e impediu reintroduzir o defeito. Comentário que explica o *porquê* de uma decisão é **guarda-corpo, não decoração**. |
| 2026-07-22 | Handoff circulação (2 checkouts) | **Diagnóstico se ratifica contra o checkout DEPLOYADO — dois checkouts na mesma máquina é armadilha.** Um diagnóstico impecável (Engenheiro-Chefe, VS Code) foi feito contra `~/Dev/PicSaude_Dev` (branch `feat/circulacao-t1-devolucao`, já mergeada #76, **17 dias velha**) em vez do canônico `~/Developer/PicSaude_Dev`@`main` (o que deploya). Consequências: âncoras `arquivo:linha` erradas, e o **Problema 2 (fila do dispensador) dado como "inexistente"** porque a fila não existia no checkout de 5/jul — quando no código no ar ela existe e é o sintoma reportado. **"Diagnóstico perfeito contra o código errado é pior que nenhum, porque parece pronto."** Régua: todo diagnóstico/implementação **declara e confere o checkout** (`git -C <dir> log -1` + branch) contra o que deploya, ANTES de ratificar. Checkout stale → arquivar (marcador `_ARQUIVADO-LEIA-ME.md` + migrar o untracked único), nunca deixar competir com o canônico. |
| 2026-07-23 | COER-2 (choke-point) | **Contra caminho-a-caminho, feche o ponto de passagem — e prove com o banco.** O #119 corrigiu 1 caminho e deixou 2; caçar cada transição é infinito. A defesa durável é (a) um **choke-point** (`transferir_posse`) por onde TODA mudança de posse passa, fechando a anterior obrigatoriamente, e (b) uma **constraint de unicidade** que torna dupla-posse um `IntegrityError`, não fé — "o 4º caminho não embarca, em vez de ser caçado depois". Sutileza que a constraint sozinha NÃO pega: dupla posse **cross-granularidade** (nível-prescrição obsoleto + nível-item ativo, chaves `-1` vs `item_id`) — essa é fechada pela **reconciliação do caminho**; as duas guardam coisas diferentes. Ordem de rollout inviolável: **data-fix ANTES da constraint** (na MESMA migração, senão o Render cria o índice sobre dados sujos e falha). E o `NULLS NOT DISTINCT` (PG) / `COALESCE(item_id,-1)` (SQLite) é o que faz a dupla posse de PRESCRIÇÃO INTEIRA (`item_id IS NULL`) colidir — sem ele, passa silenciosa. |
| 2026-07-23 | COER-2 (esboço §6 vs main) | **O esboço do ticket é hipótese; a `main` é o contrato — o arquiteto confere âncoras ANTES de codar.** O §6 dizia "5 caminhos" e payload `de_tipo/para_tipo`; a `main` tinha **6** escritores de `prescricao_custodia` (2 inline no `auth.py`, 1 hospitalar), vocabulário de ledger `de/para`, e eventos `item_devolvido_*` com payload especializado que NÃO cabe no helper genérico. Forçar o esboço quebraria o teste 4D.1 e o painel do prescritor. Régua: a "verificação automatizada primeiro" (grep dos sites afetados) é o que transforma um esboço de 5 num mapa real de 6 — e revela que o helper genérico e o evento especializado convivem, não competem. |
| 2026-07-22 | Parecer Z AI (devolução) | **Auditoria de invariante de custódia cobre 3 níveis — item, prescrição-inteira, e os endpoints que consomem cada um.** O bug da devolução passou verde por anos porque a suíte só testava custódia **item-level** + `status_item`; nunca o `status` da prescrição, os endpoints do paciente (`/paciente/prescricoes`, `devolver-prescritor`), nem `GET /dispensadores/fila`. É o mesmo gap do #84 (Jules omitiu `/dispensadores/historico`): auditar só uma camada é como auditar `dispensacoes` e esquecer `estornos`. Régua: teste de custódia declara os 3 níveis e usa o padrão **antes/depois** nos endpoints (COER-8a lista / COER-8b não lista) — senão passa por vacuidade (fila sempre vazia). Corolário do parecer: **posse ≠ saldo** — devolução devolve a POSSE; `Σ dispensado` é imutável no ledger e o saldo prescrito não se repõe (repor seria a Opção B do B0, rejeitada). |

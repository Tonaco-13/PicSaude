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

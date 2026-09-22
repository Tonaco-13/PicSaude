# DESENHO — Teste com médicos via projeto de extensão PJ324-2026

| Campo | Valor |
|---|---|
| **Veículo** | **PJ324-2026** (SIGAA/UFPE, Depto. Engenharia Biomédica — CTG) — *"PicSaúde: Plataforma de Integração do Cuidado e Infraestrutura Computacional de Custódia Sanitária para o SUS"* — **EM EXECUÇÃO**, 13/04 → **13/11/2026** |
| **Origem** | Fabiano, 13/09: *"queria antes fazer um teste com dois a três médicos, via projeto de extensão"* — registro confirmado pelo PDF do SIGAA (4 págs., lido pelo arquiteto) |
| **Autor** | Arquiteto (Z) — anexo técnico de execução; o registro no SIGAA já está feito, isto alimenta a **execução e o relatório final** |
| **Papel do teste** | Entregar o verbo pendente do objetivo geral: **VALIDAR** — com médicos reais, antes do prazo final do projeto |
| **Estado** | 🅿️ **PARQUEADO (Fabiano, 13/09: "vou deixar de lado por enquanto o piloto")** — gatilho de reabertura é dele. Nota de calendário, sem cobrança: para caber na janela do PJ324 (13/11), a fase A precisaria abrir até ~meados de out; passado isso, o teste vira atividade de eventual renovação 2027 |
| **Relacionados** | Vitrine pública (flip 06/09) · vagão de curadoria (alunos = público interno do PJ324) · thread São Miguel do Gostoso (público externo: secretarias) · `DESENHO-POC` (conversa futura) |

---

## §1 Por que este teste é a peça que falta do PJ324

Os objetivos específicos do registro foram executados pela casa (arquitetura
event-driven com ledger imutável ✔ · IA Farmacêutica auditável ✔ · camada adapter ✔ ·
capacitação de estudantes ✔ — a curadoria do vagão É essa capacitação operando). O
que o projeto ainda não tem é **evidência com humanos**: o relatório final de 13/11
pede validação, e 2–3 médicos gerando dados reais de uso é exatamente o tamanho que
cabe no trimestre que resta (set→nov).

**Sequência que se abre:** teste PJ324 (médicos, set–out) → **relatório de extensão**
(nov) → conversa de São Miguel do Gostoso com evidência na mão (pós-projeto) → PoC
municipal como desdobramento do público externo já declarado (secretarias).

## §2 A decisão que abre o cronograma: pacientes simulados primeiro

| | **Fase A — SIMULADA** (recomendada, set–out) | **Fase B — REAL** (out–nov, opcional ao projeto) |
|---|---|---|
| Pacientes | Personas/cidadãos demo (dados fictícios) | Pacientes reais dos médicos |
| Ambiente | **Vitrine pública** (zero setup; reset 04:00 = mesa limpa por semana) | Instância segregada, sem reset, com backup |
| Ética/LGPD | Sem pendência pesada (usabilidade) | **CEP via Plataforma Brasil** + TCLE + LGPD a fio |
| Início | Quando o Fabiano mandar o link | ~30–60 dias após submissão ao CEP |

A fase A pode começar **amanhã**: a vitrine está no ar desde 06/09 e o único
artefato que falta é o roteiro (§4). A fase B é decisão do Fabiano — se entrar,
o despacho de ambiente segregado sai na hora (o desenho de ops já existe).

## §3 O que cada médico faz (o pedido mínimo viável)

**2–3 médicos clínicos da APS. Compromisso: 30–60 min/semana, por 4–6 semanas.**

Semanal: emitir 3–5 receitas e 1–2 pedidos de exame na plataforma (com pacientes
simulados na fase A), percorrer cada objeto até o fim (carteira → farmácia/laboratório),
e um debrief de 15 min (gravado ou anotado) com três perguntas fixas:

1. Onde você travou? (atrito — a régua da Regra Zero)
2. O que o semáforo te fez fazer de diferente? (aceitou 🟢? contestou 🟡?)
3. O que faltou? (vai para o backlog — **nunca** para o escopo da semana)

## §4 O que se mede (a instrumentação já está pronta)

O sistema grava sozinho; o teste só decide o que OLHAMOS:

- **Regra Zero**: tempo de emissão → dispensa; cliques até o objetivo; taxa de
  abandono; zero objeto perdido (invariante — qualquer violação é achado grave).
- **Semáforo** (camada 3, já no ledger): sinal por item na emissão × desfecho —
  taxa de override por 🟡 por condição. **Insumo direto de curadoria**: quais
  condições os médicos realmente tocam dizem ao intensivo/vagão o que priorizar.
- **Qualitativo**: os debriefs — tema aberto, classificação fechada depois.

Critérios de sucesso honestos (propostos, martelo do Fabiano): ≥60 receitas
simuladas circuladas de ponta a ponta; zero objeto perdido; ≥80% dos eventos de
atrito do debrief mapeados a item de backlog (não a bug inexistente); relatório
de extensão com os números + a citação regulatória atualizada (ver §6).

## §5 Papéis

- **Fabiano**: recruta os 2–3 médicos (a pergunta certa: quem topa 30 min/semana
  por 6 semanas); conduz os debriefs (ou delega a bolsista); martelos de fase.
- **Arquiteto (Z)**: roteiro semanal (anexo a este desenho quando a fase A abrir),
  leitura semanal dos números, consolidação do relatório técnico de novembro.
- **Estudantes (público interno do PJ324)**: apoio operacional + a curadoria do
  vagão segue sendo a capacitação declarada — o teste realimenta as prioridades dela.
- **Engenheiro**: fora do teste — sem código novo salvo bug real achado na fase A
  (a regra é: achado de vitrine vira item de fila, nunca hotfix de domingo).

## §6 Duas notas de precisão para o relatório final (13/11)

1. **Citações regulatórias**: o registro do SIGAA (abril) cita Portaria 344/98 e
   "RDC 812/23"; o mundo andou — o relatório final deve citar a cadeia vigente:
   **RDC 1.000/2025** (receituário eletrônico/SNCR) + **Anexo I da Portaria 344/98
   consolidado até a RDC 1.036/2026** (o PDF oficial já está estagiado com sha256 —
   a citação exata está no MANIFEST).
2. **Fronteira e-SUS**: em nenhum material do teste prometer integração — a fase A
   é validação de usabilidade e da Regra Zero; a fronteira declarada é "paralelo ao
   papel, sem substituição" (a mesma régua que protegerá a PoC municipal).

## §7 Cronograma proposto (contra o prazo de 13/11)

| Quando | O quê |
|---|---|
| set (mar) | Martelo do Fabiano: recrutamento + fase A abre (link da vitrine + roteiro) |
| out | 4–6 semanas de fase A; leitura semanal; decisão da fase B (CEP) até meados de out |
| nov (1ª quinzena) | Consolidação + relatório técnico para o relatório final do PJ324 |
| **13/11** | Fecho do projeto **com validação entregue** |
| pós | São Miguel do Gostoso com relatório na mão |

---

*Desenho lavrado em 13/09/2026 a partir do registro PJ324-2026 (PDF SIGAA, 4 págs.,
lido integralmente). O teste não exige novo registro — é atividade de execução do
projeto EM CURSO. Martelos pendentes: abrir a fase A (recrutamento) e decidir a
fase B (CEP). O roteiro semanal detalhado nasce quando a fase A abrir.*

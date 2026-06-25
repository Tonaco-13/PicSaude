# Reorganização para o eixo MS — handoff de papéis

> **Status: EM TRANSIÇÃO.** Decidida em 2026-06-25. Supersede a calibração de
> 2026-06-24 **ao concluir o handoff** (não antes). Classe: `core` (governança).
>
> **Objetivo:** o projeto vira esforço liderado pelo MS/extensão. As funções de
> construção migram para as instâncias MS; a conta pessoal recua para oversight
> independente.

## 1. Nova topologia

| Instância | Papel | Mandato |
|---|---|---|
| **cowork/MS** | **Conselheiro Principal** | **Plataforma inteira**: piloto + núcleo (R6/custódia/assinatura) + motor MS. Guarda invariantes, barra direções que os violem, mantém o norte do piloto. Não redige tickets nem código. |
| **code/MS** | **Engenheiro-Chefe** | Motor + **núcleo**: assinatura, serialização canônica, `documento_canonico.py`, ledger, custódia, máquina de estados. Também hospeda a curadoria dos estudantes (Eng Clínico) — com separação dura (§3). |
| **Code pessoal** (Fabiano) | **Monitor + Auditor (escala) + Executor sob demanda** | Observa, audita quando escalado, executa quando solicitado. Âncora de independência. |
| **Jules** | **Auditoria contínua** | Varredura contínua — mandato **expandido** para invariantes core (§2). |
| **Fabiano** (humano) | **Validador clínico credenciado + orquestrador + dono das decisões core** | Único que ratifica core e assina `validado`. Não delegável. |

Mudança de fundo: hoje o Conselheiro (esta instância) revisa as **duas** árvores
de fora. Depois do handoff, Conselheiro e Eng-Chefe ficam **na mesma casa (MS)**;
a independência passa a vir de Jules (contínuo) + Code pessoal (escala). Por isso
os §2 e §3 não são opcionais — são o que substitui a independência que se perde.

## 2. O gap que a reorg expõe — auditoria core pós-CODEX (BLOQUEADOR DO HANDOFF)

CODEX está cancelado. A memória de Jules diz que a lente dele é
**qualidade/manutenibilidade, não segurança/RBAC** — essa era a lente do CODEX.
Resultado: **hoje ninguém faz revisão contínua de segurança/core.** Escolher
"Jules contínuo + Code escala" só fecha o buraco se:

- **O briefing do Jules for expandido** para cobrir os invariantes core: paridade
  de serialização R6 (WebCrypto ↔ Python), imutabilidade do ledger, cadeia de
  custódia, integridade do documento canônico/assinatura, gold validation string,
  RBAC. (Addendum no doc de prompts.)
- **R6 ganha dono nomeado, contínuo.** A paridade de serialização é sutil demais
  para a lente geral do Jules. Duas opções, escolha uma:
  - (a) **Code pessoal** revisa toda mudança que toque assinatura/serialização —
    contínuo, exceção nomeada ao "Code escala"; ou
  - (b) um **teste de paridade R6 em CI** (mesmo vetor canônico nos dois lados,
    falha o build se divergir) como gate automático, e Code pessoal só entra se o
    teste acusar.
  Recomendo **(b) + (a)**: o teste é a rede; o humano-auditor é o segundo olhar.

Sem isso resolvido, **não faça o handoff** — você estaria movendo o guardião do
R6 para dentro da casa que constrói, sem rede.

## 3. Fronteiras e guardrails (não-negociáveis)

- **Estudantes nunca tocam o núcleo.** A separação que criamos para os CSVs
  (CODEOWNERS + gate de validação) **estende-se ao núcleo**: `domain/`,
  `documento_canonico.py`, assinatura, ledger, custódia ficam sob CODEOWNERS do
  Eng-Chefe. Estudante abre PR só em conteúdo/ingestão.
- **Conselheiro mandato transversal.** O cowork/MS guarda o piloto e o R6, não só
  o motor. Se a atenção dele encolher para o mundo clínico-MS, o R6 fica órfão.
- **Ratificação core continua sendo ato humano de Fabiano.** Eng-Chefe propõe;
  Conselheiro barra/aprova no portão; Fabiano ratifica. A migração não muda quem
  é dono da decisão core.
- **A trilha do motor segue não-bloqueante do piloto.** A reorg não pode deslocar
  o Eng-Chefe do caminho crítico do R6 para a expansão do motor.

## 4. Checklist de transição (o que tem que ser verdade ANTES do handoff)

- [ ] **Gap core resolvido (§2):** Jules rebriefado para core + dono do R6 definido (teste de paridade em CI e/ou Code pessoal contínuo).
- [ ] **Seed de contexto entregue e lido** pelo cowork/MS (§5).
- [ ] **Memória/invariantes portados** — assumir que cowork/MS começa frio.
- [ ] **Gates ativos:** CODEOWNERS nos CSVs **e no núcleo**; Peça 2 robusta (`review.state=="approved"`).
- [ ] **Status do R6 documentado** e comunicado ao novo Eng-Chefe (onde está, o que falta para destravar o piloto).
- [ ] **Primeira revisão core feita em conjunto** — conselheiro atual + cowork/MS revisam um marco core lado a lado (handoff supervisionado, não a frio).
- [ ] **CLAUDE.md / NUCLEO atualizados** com a nova calibração (edição `core`, ato de Fabiano).

## 5. Seed de contexto para o Conselheiro cowork/MS

O novo conselheiro precisa internalizar, em ordem:

1. **Invariantes inegociáveis:** gold validation string (`CPF_CERT|CRM_UF|CNS`);
   CPF extraído localmente do certificado, nunca enviado ao servidor; validação
   de prescritor por NOME (CNES/CFM), matching de três níveis.
2. **Riscos bloqueadores de produção:** R1, R2, R4/R5, **R6** (bloqueador
   absoluto do piloto — qualquer mudança em assinatura/serialização passa pelo
   portão).
3. **Contrato do motor:** `MOTOR_MS_definicao_ancora.md` (espelho fiel da fonte
   oficial; ordenação sourced; posologia referência, não default) +
   `MOTOR_MS_ratificacao_checklist.md`.
4. **Núcleo e governança:** `CLAUDE.md`, `NUCLEO_SANITARIO.md`, taxonomia de
   contribuição (§10), máquina de estados, ledger imutável, custódia.
5. **Postura do papel:** pressiona decisões, aponta trade-offs, barra o que viola
   invariante; não redige ticket nem código; prioriza o que destrava o piloto.

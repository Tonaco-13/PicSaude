# FILA-VIVA — o que não pode se perder

| Campo | Valor |
|---|---|
| **O que é** | Lista viva de pendências: bugs confirmados, decisões pendentes, backlog anotado |
| **Ordem geral** | Fases GP primeiro, bugs depois — martelo do Fabiano, 26/08 ("Vamos fazer as fases GP e depois voltamos aos bugs") |
| **Quem mantém** | Arquiteto (Z). Engenheiro retira daqui; item concluído ganha ✔️ e link do PR |
| **Criada** | 2026-08-27 |

> Regra da casa que este arquivo obedece: ticket descreve **sintoma**;
> hipótese de causa é marcada como hipótese até o diagnóstico fechar.

---

## A. Bugs confirmados na vitrine (executar pós-Go Public)

| # | Item | Classe | Status |
|---|---|---|---|
| A1 | "Enviar à bancada" morre em silêncio | `module` | 🔴 confirmado 27/08 |
| A2 | Disciplina de entrada numérica (ticket da Júlia) | `local-extension` | 🔴 confirmado 26/08 |
| A3 | Pílula "Exames 0" na carteira com a aba cheia | `module` | 🟡 anotado 27/08 |

### A1 — "Enviar à bancada" morre em silêncio

**Sintoma** (walkthrough do arquiteto, 27/08, pedido `13f7f491`, item GLICEMIA):
na aba Bancada da clínica, item `coletado` com botão "Enviar à bancada"
habilitado; dois cliques sem efeito algum — sem diálogo, sem toast, sem mudança
de estado.

**Isolamento já feito:** o mesmo gesto pela API responde **200** e promove
`coletado → em_analise` corretamente. O backend está são; o defeito está no
caminho do clique na tela.

**Âncoras no código:** `clinica.html:452` (comentário TICKET-F, o gesto),
`:2799-2805` (render do botão), `:3324` (reabilitação pós-fetch).

**Hipótese (é hipótese):** o handler não dispara o fetch, ou dispara e a
resposta não é tratada — diagnóstico incompleto; arquiteto retoma antes de
despachar ao engenheiro.

**Nota de higiene da vitrine:** no walkthrough, o item 23 foi movido a
`em_analise` por chamada API do arquiteto — estado legítimo; HEMOGRAMA segue
`pendente` na Realização. Não é defeito, é resíduo do teste.

### A2 — Disciplina de entrada numérica (ticket da Júlia)

**Sintoma** (nota de Júlia, estudante, 26/08): campos numéricos dos
formulários — Idade, CPF, CEP — aceitam letras; o erro só aparece no submit
(422). Backend é fail-closed (normaliza e rejeita): defeito de higiene de
entrada, não de integridade — nada sujo persiste.

**Solução cirúrgica, só frontend:** `inputmode="numeric"` + bloqueio de
não-dígitos + máscara ao digitar (CPF `000.000.000-00`, CEP `00000-000`) +
validação antes do submit. Zero mudança em API, estados, ledger.

**Guarda mínima:** um teste de browser digitando letras e afirmando que elas
não entram.

### A3 — Pílula "Exames 0" na carteira com a aba cheia

**Sintoma** (walkthrough, 27/08): a pílula de Exames da carteira exibe **0**
com a aba de exames cheia de pedidos. Sem diagnóstico ainda — **hipótese**:
contador lê bucket diferente do que a aba lista.

---

## B. Decisões que travam o Go Public (só o Fabiano decide)

| # | Decisão | Recomendação do arquiteto |
|---|---|---|
| B1 | **§3 do GP-3** — CNS de aparência real no seed (único indistinguível de real) | Substituir por sintético |
| B2 | **§4 do GP-3** — histórico COMO × O QUE (o que vai a público no git) | Intermediário: técnico completo, menos docs de gestão |

Fonte: `GP3-AUDITORIA-SEGREDOS-PII-2026-08-26.md` (GP-3 entregue — zero
segredos reais em 85 refs / 507 commits / 3.105 blobs).

**Depois de B2:** GP-2 (curadoria da fachada) → **flip**. GP-1 já entregue (#199).

---

## C. Backlog anotado (sem data, sem dono)

- **Remarcação de encaminhamento** — desenho pronto
  (`DESENHO-REMARCACAO-ENCAMINHAMENTO.md`: re-ato de agendar, sem estado/aresta/evento novo)
- **Posologia diabetes / saúde mental** — pré-digitação ampliada (anotação do Fabiano, 25/08)
- **Simulador RDC 1.000** — classificação regulatória automática (guardas R4/G4A vigentes)
- ✔️ **Reset diário da vitrine** — **entregue completo**: PR #212 mergeado 27/08 (`8202f5a`); Blueprint **aplicado** por Fabiano na noite de 27/08; primeiro run automático **28/08 04:00 BRT com sucesso** (dashboard: "Successful run" — verde que, com a sentinela pós-seed, agora é prova, não silêncio)
- ✔️ **Higiene do campo de paciente — M-B → M-C → M-D (28/08)**: M-B (chips, #213,
  `b0ef413`) e M-C (padrão + atestado, #214, `8b714fa`) **REVOGADOS** pelo M-D —
  martelo direto do Fabiano ao engenheiro ("fixar, sem possibilidade de edição";
  o problema original ainda acontecia). M-D trava (readonly) os 4 campos no
  cidadão canônico, retira o quick-pick e os 2 cidadãos extras. Adendo §8 do
  `DESENHO-VITRINE-HIGIENE-VISITANTE.md`. Limite declarado: lock é só de
  frontend, backend não valida `nome_paciente`/`cpf_paciente` em DEMO_MODE.
- **Typeahead unificado + base CBO no encaminhamento** — martelado 28/08
  (`DESENHO-TYPEAHEAD-ENCAMINHAMENTO-CBO.md`; ordem martelada: **painel primeiro** na
  lista atual, base CBO depois). Guarda-chave: psicologia (CBO 2515) fica FORA do grupo
  22 — whitelist explícita, nunca prefixo "22=saúde"
- **CBEB v11** — conferir pontos A/B quando o Kimi voltar com a revisão

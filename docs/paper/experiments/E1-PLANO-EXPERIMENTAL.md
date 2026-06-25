# E1 — Plano experimental passo a passo (full-stack autoritativo)

> **Para:** Fabiano (desenho) + Engenheiro-executor (implementação) · **Experimento:** E1 — auditabilidade por construção.
> **Relação com o preliminar:** confirma e estende, sobre o stack real, o que o `e1_auditability.py` já mostrou no nível-domínio.
> **Ambiente:** o mesmo das suítes de integração (PostgreSQL efêmero), com semente fixa e `DEMO_MODE`.

---

## Visão geral (o "porquê" antes do "como")

**Hipótese (H).** Se a auditabilidade do PicSaúde é *estrutural* (e não acoplada depois), então, ao submeter um corpus sintético ao **sistema rodando ponta a ponta**, observaremos: (a) nenhuma transição de estado ilegal persistida; (b) o estado de cada objeto **100% reconstruível** a partir da trilha de eventos; (c) a invariante Σ dispensado ≤ prescrito **nunca** violada; (d) **100%** das adulterações de conteúdo detectadas pelo hash canônico.

**Tipo de estudo.** Experimento de *propriedade/conformidade* sobre dados sintéticos — mede propriedades de sistema, não eficácia clínica. Cada uma das quatro afirmações acima é uma medida objetiva, com valor esperado conhecido.

**Mapa objetivo → medida → seção do paper.** Objetivo (i) auditabilidade estrutural ↔ M2 replay; objetivo (ii) autorização explicável ↔ M1 fechamento + (camadas, já na Seção III); objetivo (iii) invariantes sob carga/adversarial ↔ M3 dispensação + M1 adversarial + M5 adulteração. Resultados entram na Seção IV.

---

## Fase 0 — Preparação do ambiente (baseline limpo)

1. Subir PostgreSQL efêmero e aplicar o schema (mesmo caminho do gate de integração: `init_tables.py` / migrations).
2. Ativar `DEMO_MODE`; fixar semente (ex.: `SEED=42`); registrar versões (deps pinadas, commit do repo).
3. Confirmar baseline: contagens zeradas nas tabelas clínicas (`prescricoes`, `prescricao_eventos`, `dispensacoes`).
4. **Saída da fase:** ambiente reprodutível documentado (comando único de execução).

---

## Fase 1 — Geração do corpus sintético (somente via endpoints oficiais)

> Veículo recomendado: estender `backend/seed_demo.py` / as fixtures de `backend/tests/integration/conftest.py`, que **já** autenticam e criam prescrição via `POST /prescricoes`. **Nunca** inserir por SQL direto.

1. **Parâmetros do corpus.** N ≥ 1.000 (alvo 5.000). Distribuições: 1–4 itens por prescrição; ~70% digital / ~30% física; ~15% derivadas (correção/renovação, com `origem_prescricao_id`); mix de medicamentos do formulário sintético; modos de assinatura variados.
2. **Atores sintéticos.** Criar prescritores com identidade válida para a base CNES de teste (para a camada 6 não falhar por motivo errado), pacientes e dispensadores — todos com **papéis RBAC reais**.
3. **Emissão.** Gerar prescrições digitais via `POST /prescricoes` e físicas via `POST /prescricoes/fisica`. Registrar cada `protocolo` emitido e os parâmetros usados (ground-truth de geração).
4. **Saída da fase:** corpus persistido + log de geração (protocolo, tipo, nº de itens, ator).

---

## Fase 2 — Condução dos ciclos de vida (somente via endpoints)

1. **Digitais.** Para uma fração do corpus, executar via endpoints: transferência de custódia (prescritor→paciente→dispensador), **dispensação parcial** e total, e — com o caveat abaixo — devoluções. Reutilizar os fluxos exercitados em `tests/integration/test_dispensacoes.py` e `test_custodia_devolucao.py`.
2. **Físicas.** Confirmar encerramento local (`encerrada_localmente`), sem custódia digital.
3. **Ground-truth de transições.** Para cada prescrição, registrar a sequência de atos executada — é o gabarito contra o qual o replay (Fase 3) será comparado.

> **⚠️ Caveat obrigatório (desvio documentado).** Os fluxos de devolução desviam do modelo formal de transições (`states.py`, nota CODEX 4E.2). Decisão de desenho do experimento: **escopar os fluxos de devolução para fora das métricas de conformidade de transição**, OU incluí-los e reportá-los explicitamente como *desvio conhecido e documentado* — **nunca** como violação silenciosa. Não corrigir o desvio dentro do experimento (é ticket próprio, classe core).

---

## Fase 3 — Medições (as propriedades de auditabilidade)

**M1 — Fechamento da máquina de estados.** Para cada transição efetivamente persistida (derivada da sequência de eventos), verificar com `transicao_valida_prescricao` / `transicao_valida_item` que era legal. *Métrica:* nº de transições ilegais persistidas (esperado **0**). Complementar com a bateria adversarial offline já validada no preliminar.

**M2 — Replay (a medida central).** Definir uma função de *replay* que dobra (`fold`) os registros de `prescricao_eventos` (ordenados) de cada prescrição até um estado final, e comparar ao `status` persistido. *Métrica:* % de prescrições com estado reconstruído == estado persistido (esperado **100%**). Reportar qualquer divergência por protocolo.

**M3 — Invariante de dispensação.** Para cada item, somar `quantidade_dispensada` em `dispensacoes` e comparar a `prescricao_itens.quantidade`. *Métrica:* nº de itens com Σ > prescrito (esperado **0**).

**M4 — Imutabilidade do ledger.** Reutilizar/estender `tests/integration/test_ledger_imutabilidade.py`: evidenciar que não há caminho de `UPDATE`/`DELETE` em `*_eventos` exposto pela API. *Métrica:* verificação aprovada (reportar como verificação, não suposição).

**M5 — Detecção de adulteração.** Para cada prescrição (ou amostra), usar `montar_documento_de_conn` para (a) confirmar que o hash recomputado bate com o `assinatura_hash` **armazenado** (íntegro); depois (b) mutar um campo canônico no documento reconstruído e confirmar que o hash **diverge** (detecção). Reutilizar padrões de `tests/integration/test_integridade.py`. *Métrica:* taxa de detecção (esperado **100%**).

**M6 — Determinismo.** Recomputar o hash duas vezes / com ordem de chaves embaralhada → idêntico. *Métrica:* nº de hashes não determinísticos (esperado **0**).

---

## Fase 4 — Controles e validade (anti-gaming)

1. **Estímulo adversarial via endpoint.** Tentar transições ilegais pelos endpoints (ex.: dispensar prescrição já dispensada, transferir custódia de objeto terminal) e confirmar rejeição (4xx). *Métrica:* nº de transições ilegais aceitas (esperado 0).
2. **Equilíbrio.** Garantir mistura de caminho-feliz e adversarial; não medir só o que o sistema trata bem.
3. **Não circularidade.** O replay (M2) lê o **ledger persistido**, não uma estrutura paralela em memória que já conhece o estado.
4. **Reprodutibilidade.** Semente fixa, deps pinadas, ambiente declarado, comando único, artefato de resultados (JSON) versionado.

---

## Fase 5 — Saída e integração ao paper

1. Produzir tabela de resultados (mesmo formato do preliminar) + `e1_fullstack_results.json`.
2. Atualizar a Seção IV do `CBEB-2026-DRAFT-v3-PT.md`: substituir/complementar os números preliminares pelos autoritativos; manter a nota de escopo.
3. Portões de revisão: **CODEX** (segurança/anti-gaming) → **Jules** (qualidade/metodologia/reprodutibilidade), conforme `E1-HANDOFF-claude-codex-jules.md`.

---

## Critérios de aceitação

O experimento "fecha" se: transições ilegais persistidas = 0; replay = 100%; violações de invariante = 0; adulteração detectada = 100%; determinismo = 100%; e os desvios de devolução reportados de forma transparente.

> **Se algum critério não bater, é um achado — não uma falha do paper.** Uma divergência de replay, por exemplo, pode revelar um bug real de persistência de estado, o que é *valioso* e deve ser reportado honestamente (e provavelmente vira ticket core). O experimento serve à verdade do sistema, não à narrativa.

---

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Ambiente Postgres não trivial | Reusar o setup do gate de integração já existente |
| Desvio de devolução contaminar M1/M2 | Escopar fora ou reportar como desvio documentado (Fase 2) |
| Tocar assinatura/serialização canônica | **Guarda R6:** passa pelo conselheiro antes de implementar |
| Tempo de execução | Começar com N=1.000, escalar para 5.000 |
| Geração via endpoint exigir auth/identidade complexa | Reusar fixtures de `tests/integration/conftest.py` |

---

## Sequência enxuta (resumo executável)

```
Fase 0  ambiente limpo + semente
Fase 1  gerar corpus via POST /prescricoes (e /fisica)   ← seed_demo / conftest
Fase 2  rodar ciclos de vida via endpoints               ← test_dispensacoes / custodia
Fase 3  medir M1..M6                                      ← replay do ledger + hash armazenado
Fase 4  controles anti-gaming                             ← adversarial + reprodutibilidade
Fase 5  tabela + JSON → Seção IV → CODEX → Jules
```

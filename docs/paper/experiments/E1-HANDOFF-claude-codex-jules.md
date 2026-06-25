# Hand-off — Experimento E1 (full-stack autoritativo) · Claude / CODEX / Jules

> **Origem:** conselheiro de arquitetura · **Para:** Engenheiro-executor (Claude, Code/VS Code), CODEX, Jules
> **Objetivo:** elevar o E1 *preliminar de nível-domínio* (`docs/paper/experiments/e1_auditability.py`, já rodado) à execução **autoritativa full-stack**, cujos números entram na Seção IV do paper do CBEB (`docs/paper/CBEB-2026-DRAFT-v3-PT.md`).
> **Classe (taxonomia §10 CLAUDE.md):** `module`/test-artifact — não altera núcleo. Ciclo: ticket leve → Claude implementa+roda → CODEX → ajustes → Jules → números no paper.
> **Guarda R6 (inegociável):** se qualquer parte tocar assinatura ou serialização canônica (WebCrypto↔Python), passa pelo conselheiro **antes** de implementar.

---

## 0. O que o E1 prova (e por que full-stack)

O E1 mede **auditabilidade por construção** como propriedade de sistema, sobre dados sintéticos. O preliminar exercitou a lógica de domínio (`states`, `documento_canonico`) e deu 100% em todas as métricas. A versão autoritativa exercita o **stack real**: corpus gerado pelos *endpoints oficiais*, *replay* do **ledger persistido**, detecção de adulteração contra o **hash armazenado**. É a diferença entre "a regra de transição rejeita o ilegal" e "o sistema rodando, ponta a ponta, nunca persiste estado fora da trilha".

---

## 1. CLAUDE (Engenheiro-executor) — construir e rodar

Ambiente: o mesmo das suítes de integração (PostgreSQL efêmero, como no gate dos 22 testes). **Reusar as fixtures de integração existentes** para criação de prescrição via stack — não reinventar geração de corpus.

**Tarefas:**

1. **Gerar corpus sintético via endpoints oficiais.** N ≥ 1.000 prescrições (alvo 5.000 se o tempo permitir) com distribuições realistas: nº de itens, físico vs. digital, correções/renovações derivadas. Tudo por `POST /prescricoes`, `POST /prescricoes/fisica` etc. — **nunca** por SQL direto nas tabelas clínicas.
2. **Conduzir ciclos de vida via endpoints.** Transferência de custódia, dispensação parcial e total, devoluções — sempre pelos endpoints oficiais (`routers/custodia.py`, dispensação). Atores sintéticos com papéis corretos (RBAC real).
3. **Métrica de replay (a central).** Para cada prescrição, reconstruir o estado a partir de `prescricao_eventos` (ledger persistido) e comparar ao `status` persistido. Reportar consistência (alvo 100%).
4. **Métrica de imutabilidade do ledger.** Evidenciar ausência de caminho de `UPDATE`/`DELETE` em `*_eventos` (a API não expõe; reportar como verificação, não como suposição).
5. **Métrica de adulteração.** Usar `montar_documento_de_conn` recomputando o hash e comparando ao `assinatura_hash` **armazenado** (a camada de integridade real); mutar conteúdo e confirmar detecção.
6. **Invariante de dispensação parcial.** Sob dispensações parciais reais, confirmar Σ dispensado ≤ prescrito.
7. **Saída.** Tabela + JSON no mesmo formato do preliminar, para substituir/complementar a Tabela da Seção IV. Harness versionado em `docs/paper/experiments/` (ou `backend/tests/experiments/`), commit isolado, comando único de execução documentado, semente fixa.

**⚠️ Caveat obrigatório — desvio documentado de transições de devolução.** `states.py` (nota CODEX 4E.2) registra que os fluxos de devolução (dispensador→prescritor; dispensador→paciente; `devolver_prescritor`) **desviam** do modelo formal de transições. O replay que valida o ledger contra `TRANSICOES_*` vai sinalizar esses fluxos. **Tratar explicitamente:** ou escopar fora os fluxos de devolução nesta medição, ou reportá-los como *desvio conhecido e documentado*, **nunca** como violação silenciosa — e **não** "consertar" o desvio dentro deste trabalho (é ticket próprio, classe core). A honestidade aqui protege o paper.

**Não fazer:** escrever em tabela clínica via SQL; inserir evento no ledger via SQL; bypassar endpoint; alterar `domain/states.py`, `documento_canonico.py` ou qualquer máquina de estados para "fazer o número fechar".

---

## 2. CODEX — lente de segurança / RBAC / correção / anti-gaming

Revisar o commit do harness com foco em:

- **Sem bypass:** o harness escreve exclusivamente pelos endpoints oficiais — zero SQL direto em tabelas clínicas, zero `INSERT` direto no ledger.
- **RBAC real:** atores sintéticos usam papéis/credenciais corretos; ownership respeitado (não há atalho de admin que mascare a verificação).
- **Replay honesto:** a reconstrução lê o **ledger persistido real**, não uma estrutura paralela em memória que "já sabe" o estado.
- **Integridade real:** a detecção de adulteração passa pelo caminho de hash **armazenado** (`assinatura_hash`), não por um recomputo isolado que nunca tocou o banco.
- **Anti-circularidade:** nenhuma métrica é auto-realizável (o experimento não pode validar a si mesmo gerando só o caminho-feliz que trata). Conferir presença de estímulo adversarial.
- **Dados sintéticos / DEMO_MODE:** nenhum dado real; CPF do prescritor não trafega (invariante).

**Anti-escopo:** CODEX **não** cobre estilo, manutenibilidade ou metodologia estatística (lane do Jules).

---

## 3. JULES — lente de qualidade / manutenibilidade / metodologia / reprodutibilidade

Revisar, ao fim da etapa, com foco em:

- **Reprodutibilidade:** semente fixa, dependências pinadas, ambiente declarado, **comando único** documentado, artefato de resultados (JSON) versionado.
- **Honestidade metodológica:** definições de métrica claras e não circulares; equilíbrio entre caminho-feliz e adversarial; tamanho de corpus adequado; o que cada número *significa* está explícito.
- **Aderência paper↔código:** os números do harness batem **exatamente** com as afirmações da Seção IV — sem overstatement, sem métrica no paper que o código não produz.
- **Qualidade do harness:** estrutura, ausência de duplicação, nomes claros, DX (fácil de rodar e estender para E2/E3).
- **Tratamento do caveat de devolução:** o desvio documentado está reportado de forma transparente, não escondido.

**Anti-escopo:** Jules **não** re-revisa segurança/RBAC (lane do CODEX).

---

## 4. Ordem, portões e saída

```
Claude implementa + roda (PostgreSQL efêmero)
   → commit isolado
   → CODEX (rodada de segurança/anti-gaming) → ajustes
   → Jules (fim de etapa: qualidade/metodologia/reprodutibilidade) → ajustes
   → conselheiro funde os números na Seção IV do paper
```

Briefings de CODEX/Jules seguem o padrão de pasta `backend/docs/codex/` quando aplicável.

---

## 5. Opcional — aguardando aval do Fabiano (mesmo padrão de 3 agentes)

- **E2 — Prevenção de gasto duplo.** Simular reapresentação da mesma prescrição de controlado em N farmácias via endpoints; PicSaúde (custódia+ledger) vs. baseline "PDF estático"; taxa de dispensação duplicada (~0% vs ~100%). Amarra na motivação das entrevistas. *Cuidado de baseline honesto, não strawman.*
- **E3 — Ablação de limiar na terminologia.** Benchmark sintético perturbado (medicamento/CID/exame); precisão e taxa de falso-positivo em 0,82 vs 0,88, reproduzindo a correção de projeto. Roda no nível dos módulos `app/ai/*` (pode dispensar full-stack).

> Recomendação do conselheiro: fechar E1 full-stack primeiro (é o que ancora a tese). E2 é o segundo de maior retorno (liga ao problema real). E3 é o "agrada quem quer número", mas é o de menor risco e pode ficar por último.

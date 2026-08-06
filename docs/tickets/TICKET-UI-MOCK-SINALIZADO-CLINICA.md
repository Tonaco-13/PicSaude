# TICKET-UI-MOCK-SINALIZADO-CLINICA — Sinalizar na UI da clínica que a emissão de laudo é próxima fase

| Campo | Valor |
|---|---|
| **ID** | TICKET-UI-MOCK-SINALIZADO-CLINICA |
| **Classe** | `local-extension` (UI/UX — sem impacto clínico, sem backend) |
| **Estado** | 🟢 **Pronto pra implementar** — condição Q2 (parecer Fable 5 ratificado) |
| **Para** | Kimi 3 (implementa) → Revisor → Conselheiro → Fabiano (martelo) |
| **Origem** | Parecer Fable 5 Q2 condição 2: "O `Aguardando laudo` estático ganha marcador visível de 'emissão de laudo pela UI: próxima fase'" |

---

## §1 Contexto (não reabrir)

Na estratégia Q2-(M) (mínimo viável), o laudo entra **mockado no seed** (`DEMO-LAUDO-0001`, status `liberado`), e a UI de emissão de laudo na clínica fica pra **fase seguinte** (ticket (C) do Kimi 3).

Hoje, `clinica.html:1452` mostra `<span class="laudo-aguardo">Aguardando laudo</span>` estático quando um item está `coletado`. Sem aviso, um testador da demo (aluno do Fabiano) vê isso e **relata como bug** — exatamente o que aconteceu em 02/08 com outros achados.

**Decisão (Fable 5, ratificada):** o mock deve ser **sinalizado visivelmente** como "próxima fase", não silencioso.

---

## §2 Invariantes

- **R1:** nenhuma mudança de backend. Só `clinica.html`.
- **Semântica clínica zero:** não altera estados, ledger, custódia.
- **Classe `local-extension`:** não quebra contrato público.
- **Honestidade:** o aviso deve ser **claro e visível**, não footnotes ocultos. Se um testador ver, deve entender "isto é próxima fase, não bug".

---

## §3 Spec de implementação

### 3.1 Arquivo tocado

- `clinica.html` — apenas o trecho de `renderizarItens` que mostra o estado do laudo.

### 3.2 Mudança

Em `renderizarItens` (`clinica.html:1433`), quando o item está `coletado`/`em_analise`/`resultado_disponivel` e mostra o placeholder de laudo, substituir o texto estático por um **badge/aviso visível**:

```html
<!-- Antes -->
<span class="laudo-aguardo">Aguardando laudo</span>

<!-- Depois -->
<span class="laudo-aguardo mock-aviso">
  Aguardando laudo
  <small class="mock-tag">⚠ Emissão de laudo pela UI: próxima fase</small>
</span>
```

CSS do `.mock-tag` (inline ou no `<style>` do `clinica.html`):
- Fundo amarelo claro (`#fef3c7`), texto escuro (`#92400e`), padding 2px 6px, border-radius 4px, font-size 11px, margin-left 6px.
- Estilo coerente com avisos de "MODO DEMO" já existentes.

### 3.3 Tom do aviso

- **Não:** "BUG conhecido" / "Não implementado" (soa quebrado).
- **Sim:** "próxima fase" / "em breve" (soa roadmap).
- O objetivo é que um testador leia e entenda que é planejado, não defeito.

---

## §4 Critérios de aceite

1. Na demo, ao buscar `DEMO-EXAME-0001` (item pendente) e simular coleta, o item mostra o aviso "Emissão de laudo pela UI: próxima fase".
2. O aviso é **visualmente destacado** (não texto cinza fundido).
3. Sem erro de console ao renderizar.
4. Sem mudança de backend (`grep -nE "POST.*laudos|POST.*resultado" clinica.html` continua retornando zero — a clínica ainda não chama esses endpoints; isso é fase C).
5. Smoke de console limpo da clínica continua verde.

---

## §5 Fora de escopo

- **Implementar a UI de emissão de laudo** — isso é o ticket (C), fase seguinte do Kimi 3.
- **Mudar o fluxo de coleta/agendamento** — funciona e permanece.
- **Backend** — nenhum.

---

## §6 Browser-E2E (opcional)

Se o Kimi 3 julgar necessário, adicionar asserção de que o aviso está visível no DOM quando item está `coletado`. Não é bloqueante se o smoke de console cobrir.

---

## §7 Fluxo de aprovação

1. Kimi 3 implementa (1 trecho de HTML + CSS).
2. Revisor (Claude Code/app) confirma critérios §4.
3. Conselheiro (Fable 5) — parecer leve.
4. Arquiteto ratifica.
5. Martelo do Fabiano + merge (pode ir junto com o seed/Gap 3, ou separado).

---

## §8 Coordenadas

| Artefato | Caminho |
|---|---|
| Parecer Fable 5 Q2 | Origem da condição 2 |
| Seed (laudo mockado) | `docs/tickets/TICKET-SEED-EXAMES-DEMO.md` |
| Código-fonte | `clinica.html:1433-1454` (`renderizarItens`, placeholder laudo) |
| Ticket (C) seguinte | UI de emissão de laudo — a criar quando (M) estiver de pé |

---

*Ticket emitido pelo arquiteto de backend (GLM-5.2) em 2026-08-02. Condição Q2 ratificada. Kimi 3 pode implementar (escopo mínimo, UI pura).*

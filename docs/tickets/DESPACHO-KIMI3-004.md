# DESPACHO KIMI3-004 — Mock sinalizado na clínica → Kimi 3

| Campo | Valor |
|---|---|
| **Despacho** | KIMI3-004 (mock-sinalizado, condição Q2 do parecer Fable 5) |
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Kimi 3 (implementa) · cc: Revisor · Conselheiro · Fabiano |
| **Data** | 2026-08-02 |
| **Martelo** | Fabiano homologou Q2=(M) (2026-08-02) |
| **Documento-fonte** | `docs/tickets/TICKET-UI-MOCK-SINALIZADO-CLINICA.md` |

---

## §1 O que fazer

Implementar o **mock sinalizado** na UI da clínica, seguindo `docs/tickets/TICKET-UI-MOCK-SINALIZADO-CLINICA.md`.

**Resumo da entrega:**
- Em `clinica.html`, na função `renderizarItens` (~linha 1452), substituir o texto estático `<span class="laudo-aguardo">Aguardando laudo</span>` por um **aviso visível** informando que a emissão de laudo pela UI é próxima fase.

Exemplo (do ticket-fonte §3.2):
```html
<span class="laudo-aguardo mock-aviso">
  Aguardando laudo
  <small class="mock-tag">⚠ Emissão de laudo pela UI: próxima fase</small>
</span>
```

CSS: `.mock-tag` com fundo `#fef3c7`, texto `#92400e`, padding 2px 6px, border-radius 4px, font-size 11px.

## §2 Por que existe (contexto)

Na estratégia Q2-(M), o laudo entra **mockado no seed** (`DEMO-LAUDO-0001`, `liberado`) e a UI de emissão de laudo fica pra fase seguinte. Sem aviso visível, um testador da demo (aluno) vê o "Aguardando laudo" estático e **relata como bug** — o que aconteceu em 02/08 com outros achados. O mock precisa ser honesto: "isto é próxima fase, não defeito".

## §3 Decisões já tomadas

- **Q2=(M) ratificada:** este ticket cobre só o aviso. A UI de emissão de laudo (ticket (C) seguinte) é **outro trabalho** — não comece agora.
- O tom do aviso é "próxima fase" / "em breve", nunca "bug" / "não implementado".

## §4 Invariantes

- **R1:** nenhuma mudança de backend. Só `clinica.html`.
- **Semântica clínica zero.**
- **Classe `local-extension`:** não quebra contrato público.
- **Honestidade:** aviso claro e visível.

## §5 Critérios de aceite

1. Aviso visível quando item está `coletado`/`em_analise`/`resultado_disponivel`.
2. Visualmente destacado (não cinza fundido).
3. Sem erro de console.
4. `grep -nE "POST.*laudos|POST.*resultado" clinica.html` continua retornando **zero** — a clínica ainda não chama esses endpoints (fase C).
5. Smoke de console limpo da clínica verde.

## §6 Como encaixa com seu trabalho em andamento

⚠️ **Atenção à pasta compartilhada (KIMI3-002 §3, reafirmado em KIMI3-003 §3.3):**
- `clinica.html` está com suas mudanças staged (logo). **Adicione o mock-sinalizado ao mesmo conjunto** — pode commitar junto.
- Não use `git stash`. Se precisar separar, use `git add -p clinica.html`.

## §7 Fluxo de aprovação

1. Você implementa (1 trecho HTML + CSS).
2. Branch: `local-extension/mock-sinalizado-clinica` (pode ir junto com o PR de logo se fizer sentido).
3. Revisor (Claude Code/app) confirma critérios §5.
4. Conselheiro (Fable 5) — parecer leve.
5. Arquiteto ratifica.
6. Martelo do Fabiano + merge.

## §8 Coordenadas

| Artefato | Caminho |
|---|---|
| Ticket-fonte | `docs/tickets/TICKET-UI-MOCK-SINALIZADO-CLINICA.md` |
| Parecer Q2 | `docs/tickets/DIAGNOSTICO-FABLE5-EXAMES-DEMO.md` §6 |
| Código-fonte | `clinica.html:1433-1454` (`renderizarItens`, placeholder laudo) |
| Seed (que cria o laudo mockado) | `TICKET-SEED-EXAMES-DEMO.md` (Engenheiro, paralelo) |

## §9 Não fazer

- Não implementar a UI de emissão de laudo (é fase C — outro ticket).
- Não mudar o fluxo de coleta/agendamento (funciona e permanece).
- Não tocar no backend.

---

*Despacho emitido pelo arquiteto de backend. Martelo homologado. Kimi 3 pode iniciar — escopo mínimo, UI pura.*

# RASCUNHO N39.0 DUPLO — semáforo da ITU, padrão I10 (diretrizes + RENAME 2024)

| Campo | Valor |
|---|---|
| **Origem** | Vagão §2 (fila: E11 ✔ → J45 ✔ → F32 → **N39.0**) · "Vai", Fabiano 02/09 |
| **Rascunhista** | Arquiteto (Z) — nunca flipa `validado`/`exaustivo` |
| **Assinante** | **Fabiano** |
| **Fontes estagiadas (sha256 no MANIFEST)** | **RENAME 2024** (254p — mantém classificação **AWaRe** da OMS p/ antimicrobianos) · **RAMB 2003 "Abordagem diagnóstica e terapêutica na ITU"** (`diretrizes/ramb-itu-abordagem.pdf`, 8p) — **única diretriz brasileira dedicada localizável, e é de 2003; declarado** |
| **Estado** | ✅ **ASSINADO — Fabiano, 02/09/2026** (recomendações aplicadas): 8 rows com fonte por row; fosfomicina com ausência RENAME declarada na própria row; FQs 🟢 com reserva AWaRe Watch; +clavulanato como row própria (RENAME p.58); posologia 3 rows citáveis da RAMB 2003 (idade declarada). Executado na **PR #249**. Guarda: `test_semaforo_flip_f32_n39.py`. Nota-ops viva: re-conferir I10 vs RENAME |

---

## §1 O achado: fosfomicina (seed nº 1) NÃO consta da RENAME 2024

Varredura integral: **fosfomicina ausente do RENAME 2024** (nenhuma página).
Ela é primeira linha mundial para cistite aguda e está na RAMB 2003 (p. 5) —
mas a RENAME 2024 não a traz. Simétrico ao achado do F32 (sertralina/escitalopram).

## §2 Elenco proposto (com fonte por row — a era de citar "RENAME" em bloco acabou)

| Princípio ativo | Fonte (págs.) | Observação |
|---|---|---|
| nitrofurantoína | RENAME 2024 (71, 142) + RAMB 2003 (5-7) | 1ª linha cistite |
| **fosfomicina** | RAMB 2003 (5) — **∉ RENAME 2024, declarado** | ver §3 |
| cefalexina | RENAME 2024 (61, 129) + RAMB 2003 (5-6) | |
| amoxicilina | RENAME 2024 (58, 126) + RAMB 2003 (5) | (± ác. clavulânico — checar apresentação RENAME na assinatura) |
| sulfametoxazol + trimetoprima | RENAME 2024 (77, 144) + RAMB 2003 (5, 8) | resistência local define |
| ciprofloxacino | RENAME 2024 (61, 129) | **reserva — AWaRe Watch** |
| levofloxacino | RENAME 2024 (70, 153) | **reserva — AWaRe Watch** |

## §3 Pontos de decisão (só o Fabiano decide)

1. **Fosfomicina**: (a) **RECOMENDADO** — manter 🟢 com fonte RAMB 2003 e a
   ausência na RENAME 2024 declarada na própria row (a diferença para o caso
   sertralina: fosfomicina é primeira linha em diretriz dedicada BR + prática
   APS consolidada; a row conta a verdade inteira); (b) 🟡 "não consta da RENAME".
2. **Fluoroquinolonas no elenco**: mantê-las 🟢 **com observação de reserva
   AWaRe Watch** (recomendo — N39.0 cobre também pielonefrite em APS, onde
   fluoroquinolona é legítima) ou excluí-las do elenco (🟡 stewardship duro).
3. ** Seeds trocam fonte** (a atual "RENAME/PCDT (APS)" não descreve nada disso) —
   versão `semaforo_n39_exaustiva_v1_2026-09` na assinatura.

## §4 Posologia — pendência declarada

Mesma régua do F32: sem fonte de dose estagiada, sem row. Nitrofurantoína
(100mg 12/12h 5d) e fosfomicina (dose única 3g) são citadas na RAMB — levantura
de rows na sessão de assinatura, direto do PDF estagiado.

## §5 Nota de método (o achado transversal desta dupla)

Duas condições, três seeds citando "RENAME" sem estar na RENAME — **a semeadura
de junho citava a fonte por costume, não por conferência**. A cura estrutural:
a partir da assinatura F32+N39.0, **toda row carrega fonte conferida com página**
(o padrão que E11/J45 inauguraram). Recomendo um futuro ticket-ops: re-conferir
as 61 rows do I10 contra o RENAME 2024 estagiado — mesmo defeito pode estar lá.

---

*Lavrado em 02/09/2026 com varredura mecânica das duas fontes estagiadas.*

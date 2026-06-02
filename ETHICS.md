# ETHICS.md — Não-objetivos éticos do PicSaúde

> Documento de governança. Versionado. Alterá-lo é mudança de **classe `core`**
> (exige revisão central, ver `CLAUDE.md §10`).

O PicSaúde é infraestrutura sanitária de bem público (código aberto, AGPL, porque
"SUS é público"). Alguns caminhos são **não-objetivos permanentes** — não por falta
de capacidade técnica, mas por decisão ética e regulatória.

---

## 1. Não-objetivo nº 1 — Monetização de dados pelo paciente

> **O PicSaúde nunca implementa pagamento ao paciente por seu dado de saúde, nem
> qualquer comoditização de dado pessoal sensível.**

### Por quê
- **LGPD Art. 11** — dado de saúde é sensível; não é mercadoria desenhada para venda.
  Consentimento sob incentivo financeiro tende a ser consentimento **coagido**.
- **Equidade** — pagar pelo dado vira mecanismo **regressivo**: quem precisa de
  dinheiro vende privacidade. É o oposto do princípio de equidade do SUS.
- **Credibilidade** — embutir monetização numa implementação de referência de bem
  público a transforma em *data broker* e destrói sua legitimidade.

### O que perseguir no lugar (caminho aprovado)
**Soberania do paciente via outorga de acesso auditável.** O paciente decide *quem*
acessa seu objeto sanitário; cada decisão é um evento no **ledger imutável**
(substrato já existente: custódia + ledger). Análogo ao Pix: controle e
rastreabilidade do fluxo — **não** a venda do ativo.

### Se algum dia houver dimensão econômica
É decisão de **regulador / política pública**, fora do motor, com guarda-corpos
pesados, e com valor revertendo a **benefício coletivo** (pesquisa, saúde coletiva),
nunca a venda individual.

---

## 2. Como isto é protegido (defesa em profundidade)

Nada disto torna impossível a um fork malicioso — código aberto é assim, e só a
**licença (AGPL)** tem força jurídica. O objetivo é elevar o piso: tornar a
monetização um ato **conspícuo, revisável e auto-incriminante**, não um flag quieto.

1. **Ausência estrutural** — o dado do paciente não tem atributo monetário no schema;
   o primitivo de consentimento modela *outorga/revogação de acesso*, nunca preço.
2. **Vocabulário de ledger fechado + governança** — um evento de monetização não
   entra como adapter quieto; obriga alterar o núcleo (`*_eventos`), classe `core`,
   revisão central (`CLAUDE.md §2 e §10`).
3. **Tripwire em CI** — `backend/tests/test_guardrail_sem_monetizacao.py` falha o
   build se um token de monetização aparecer no código clínico ou no frontend.
4. **O ledger contra si mesmo** — todo acesso é evento imutável; qualquer venda real
   deixa rastro auditável.
5. **Licença** — AGPL obriga quem faz deploy de fork modificado a publicar o código:
   monetizar exige publicar que monetizou.

---

*Estabelecido em 2026-05-31. Não-objetivo permanente; revisão é matéria de
governança central.*

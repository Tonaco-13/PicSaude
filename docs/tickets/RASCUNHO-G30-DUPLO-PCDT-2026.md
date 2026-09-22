# RASCUNHO G30 DUPLO — semáforo + posologia, do PCDT 2025 (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | INTENSIVO PCDT — autorizado pelo Fabiano em 13/09. Lavrado em 17/09 pela **R4** (substituindo a DRC, que é protocolo de estratégias sem elenco — ver MANUAL R4 e pendência P-7) |
| **Rascunhista** | Arquiteto (Z) — **nunca flipa `validado`/`exaustivo`** (linha vermelha do vagão; neste intensivo SEM exceção de delegação verbal) |
| **Assinante** | **Fabiano** — único gesto que fecha esta levantura |
| **Fonte canônica** | PCDT da Doença de Alzheimer — **Portaria Conjunta SAES/SCTIE nº 27, de 27/11/2025** (90 págs., `pcdt-da-doenca-de-alzheimer.pdf`), edição novíssima |
| **Estado** | ⏳ **AGUARDANDO ASSINATURA** — nenhum CSV foi tocado nesta rodada |

sha256: `b9e1715db3cde150de6996708a9aa41bfc911e690c5514178b345ae2b5f7d31d`

> **Escopo CID (p. 3):** G30.0/G30.1/G30.8 (doença) e F00.0/F00.1/F00.2 (demência na
> DA). Chave proposta: **G30** (ver §4.1).

---

## §1 O elenco oficial 2025 — 4 medicamentos, duplamente citados

Enumerados no **item 6.2.2 MEDICAMENTOS (p. 12)** e no **Quadro 5 – Esquemas de
administração (p. 13)**; o adesivo de rivastigmina tem o Quadro 6 (p. 14). Linhas por
gravidade (6.2, p. 12): DA **moderada** → memantina em monoterapia OU combinada com
anticolinesterásico; DA **grave** → memantina ou donepezila em monoterapia OU
associação memantina+donepezila.

| # | Princípio ativo (chave) | Classe | Apresentações (6.2.2) | Dose inicial → máxima (Quadro 5) |
|---|---|---|---|---|
| 1 | donepezila | anticolinesterásico | comp. 5 e 10 mg | 5 mg/dia → 10 mg/dia após 4–6 semanas |
| 2 | galantamina | anticolinesterásico | cáp. LP 8, 16, 24 mg | 8 mg/dia → 16 mg/dia (máx. 24 mg/dia) |
| 3 | rivastigmina | anticolinesterásico | cáp. 1,5/3/4,5/6 mg; sol. 2 mg/mL; adesivos 5 cm² (9 mg) e 10 cm² (18 mg) | cáp. 3 mg/dia → 12 mg/dia (2×/dia, com refeições); adesivo: 5 cm² → 10 cm² após ≥4 semanas |
| 4 | memantina | antagonista NMDA | comp. 10 mg | 5 mg/dia → 20 mg/dia (titulação 5 mg/semana) |

**Adesivo transdérmico (Quadro 6, p. 14):** 1 adesivo a cada 24 h em rodízio de locais;
não cortar; o de 5 cm² NÃO traz dose efetiva — se o de 10 cm² não for tolerado, trocar
de terapia (não manter no 5 cm²); migração oral→adesivo: <6 mg/dia → 5 cm²; 6–12 mg/dia
→ 10 cm² direto, aplicando o primeiro adesivo 1 dia após a última dose oral (p. 13–14).

## §1a Exclusões explícitas citadas (insumo para o 🟡 honesto)

1. **Memantina solução oral e comprimido orodispersível** — p. 12: *"Este Protocolo
   não preconiza o uso de memantina solução oral ou comprimido orodispersível para
   pacientes com DA moderada ou grave com disfagia, uma vez que, devido ao impacto
   orçamentário elevado, essas apresentações não foram incorporadas ao Sistema Único
   de Saúde."* → G30×memantina-solução/orodispersível = 🟡 "apresentação não
   incorporada" com citação. (O comprimido simples segue no elenco.)
2. **Rivastigmina adesivo 5 cm² como manutenção** — não traz dose efetiva (p. 13):
   só como degrau de titulação; manter nele após intolerância ao 10 cm² é contra a
   letra do PCDT.
3. **Antipsicóticos/sedativos para BPSD** — fora do elenco deste PCDT (manejo
   não farmacológico primeiro; não citados no 6.2.2). Wording "ausente do elenco".

**Ajuste renal da memantina (Quadro 5, p. 13):** DCE 50–80 sem ajuste; 30–49 → iniciar
10 mg/dia, 20 mg após 7 dias se tolerada; 5–29 → manter 10 mg/dia. Galantamina em
insuficiência hepática/renal moderada: máx. 16 mg/dia.

## §2 Rows propostas — `data/decisao_semaforo.csv` (G30, novo CID no semáforo)

Colunas: `codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao,exaustivo`.
Fonte proposta: `PCDT Doença de Alzheimer 2025 (Port. Conjunta SAES/SCTIE 27/2025, item 6.2.2 p. 12 e Quadro 5 p. 13) + RENAME 2024`.
Versão proposta: `semaforo_g30_exaustiva_v1_2026-09`. Chave: **G30** (F00 — ver §4.1).
`exaustivo=true` **só após sua assinatura**.

| principio_ativo | Ação proposta |
|---|---|
| donepezila · galantamina · rivastigmina · memantina | novas rows — o elenco completo (4 rows) |

Chaves de grafia: o 6.2.2 grafou "Cloridrato de donepezila", "Bromidrato de
galantamina", "Cloridrato de memantina", "Rivastigmina" — recomendação: rows-alias
com e sem o sal (mesma lição da insulina humana regular, E11 §4.5), citando a mesma
portaria.

## §3 Rows propostas — `data/posologia_sugerida.csv` (Quadro 5, p. 13)

Colunas: `principio_ativo,posologia_usual,condicao_nome,codigo_cid,fonte,status_curadoria,validado_por,versao,observacao`.
Fonte: `PCDT Doença de Alzheimer 2025 (Port. Conjunta 27/2025, Quadro 5, p. 13)`.
Versão: `posologia_g30_v1_2026-09`. Condição: `Doença de Alzheimer` / `G30`.

| principio_ativo | posologia_usual (rascunho do Quadro 5) | observacao (rascunho) |
|---|---|---|
| donepezila | Tomar 5 mg/dia, por via oral, com ou sem alimentos; pode aumentar para 10 mg/dia após 4 a 6 semanas. | DA grave: donepezila ou memantina em monoterapia ou combinadas (p. 12). |
| galantamina | Tomar 8 mg/dia (cápsula LP), pela manhã com alimentos, por 4 semanas; manutenção 16 mg/dia; máximo 24 mg/dia. | Insuficiência hepática/renal moderada: máx. 16 mg/dia. |
| rivastigmina | Tomar 3 mg/dia (cápsula), dividida em 2 administrações com as refeições; aumentar 3 mg/dia a cada 2 semanas conforme tolerância. Máximo 12 mg/dia. | Alternativa: adesivo transdérmico 5 cm² → 10 cm² após ≥4 semanas, troca a cada 24 h (p. 13–14). |
| memantina | Tomar 5 mg/dia (½ comprimido) na 1ª semana, aumentando 5 mg/semana até 20 mg/dia (10 mg 2×/dia) na 4ª semana. | IRC moderada (30–49): iniciar 10 mg/dia; grave (5–29): manter 10 mg/dia. Solução/orodispersível NÃO incorporadas (p. 12). |

## §4 Pontos de decisão (só o Fabiano decide)

1. **Chave CID — G30 ou F00?** O PCDT lista AMBOS (doença e demência na doença).
   Prescritores podem codificar F00. Proposta: rows sob **G30** + avaliar alias F00
   (mesmo elenco, dobra a contagem) — mesmo dilema de R52.1/R52.2 e M80/M81 (P-6).
2. **Momento do flip** — regra do vagão (strip de dose): "Donepezila 5mg/10mg",
   "Rivastigmina 1,5–6mg" e o adesivo em cm² (unidade fora do padrão de mg — conferir
   se o strip de dose cobre).
3. **Cruzamento RENAME 2024** — confirmar as 4 substâncias (anticolinesterásicos são
   componente especializado na RENAME); rascunhista prepara na sessão de assinatura.
4. **Adesivo como row separada?** rivastigmina-cápsula e rivastigmina-adesivo têm
   doses/unidades distintas — mesma pergunta da nicotina (F17 §4.1): row única por
   substância (recomendado) vs. rows por forma.

## §5 Gestão de paralelismo (por que isto não bate com o engenheiro)

Arquivos tocados **após aprovação**: os dois CSVs de curadoria — superfície disjunta da
fila do engenheiro. Até lá, **nenhum arquivo servido muda**: este rascunho é documento
de revisão. Nenhum PR, nenhum código (limites do INTENSIVO). O `FILA-VIVA.md` só recebe
nota curta de registro.

---

*Rascunho lavrado pelo arquiteto (Z) em 17/09/2026 (R4 do INTENSIVO PCDT), do PDF
oficial estagiado (sha256 `b9e1715d…`). Elenco do item 6.2.2 (p. 12); esquemas do Quadro
5 (p. 13); adesivo no Quadro 6 (p. 14); exclusão das apresentações de memantina com
citação (p. 12); linhas por gravidade (p. 12); escopo CID (p. 3). Sua revisão contra o
PDF é parte do rito — a assinatura fecha.*

> **SELF-CHECK (R4, 17/09/2026):** 6 citações reabertas e conferidas contra o PDF —
> elenco da donepezila (p. 12), exclusão das formas de memantina com citação literal
> (p. 12), titulação da donepezila no Quadro 5 (p. 13), início 5 mg da memantina
> (p. 13), CID G30.0 (p. 3), apresentações da rivastigmina (p. 12) — **6/6 ✅**.

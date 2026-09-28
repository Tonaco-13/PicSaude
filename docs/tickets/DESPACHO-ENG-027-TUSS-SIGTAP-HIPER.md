# DESPACHO ENG-027 — hiper-intensivo TUSS + SIGTAP (deadline: merge ≤ 29/09 11:00 BRT)

| Campo | Valor |
|---|---|
| **O que é** | As duas bases de exames: a perna TUSS (a única sem fonte oficial — ~35 procedimentos hardcoded) e a perna SIGTAP (auditoria de competência), com **merge martelado até ter 29/09 11:00 BRT (Recife)** |
| **Autorização** | Fabiano, 28/09/2026, verbatim: **"vamos ter que montar um hiper intensivo começando agora para TUSS e Sigtap, para merge do engenheiro até amanhã às 11;00 de recife"** |
| **Classe** | `ops` (estagiagem + import) + `module` (loader/typeahead). **Zero `core`** |
| **Deadline** | PR aberta idealmente ≤ 29/09 08:00 · RATIFICADO do arquiteto 08:00–10:00 (janelas da vigília) · martelo do Fabiano **≤ 11:00** |
| **Irmãos** | `TICKET-FILA-7-SIGTAP-EXAMES.md` (whose §1 descreve a dívida TUSS) · `DESPACHO-ENG-026` (em voo — não colidir nos CSVs de semáforo) · `RUNBOOK` de staging do MANIFEST |

---

## §1 Perna SIGTAP — o veredito do arquiteto muda o trabalho: é REGISTRO, não refresh

**Fato verificado em 28/09 ~12:00 BRT**: a página oficial de download
(`tabela-unificada.datasus.gov.br/…/download.jsp`) lista como competência mais
nova publicada **202606** (`TabelaUnificada_202606_v2606091427.zip` — a mesma
já estagiada na casa com sha256 no MANIFEST). **202607/08/09 NÃO existem no
canal oficial.** O veredito anterior do arquiteto ("3 competências atrás")
estava errado — assumia que 202609 devia existir; quem atrasa é o canal
publicador (a lição do DM2: o canal aberto atrasa; a fonte canônica é o juiz).

**Gestos desta perna (pequenos, entram na PR):**
1. MANIFEST do `sigtap/`: nota de teto — *"202606 é a competência mais nova
   publicada no canal oficial (conferido 28/09/2026 pelo arquiteto); refresh
   só quando 202607+ pousar"*. Gatilho de reabertura declarado.
2. Tentar 1× a nota técnica oficial da competência
   (`ftp2.datasus.gov.br/…/notastecnicas/nota_tecnica_cgsi_sigtap_2026_06.pdf`,
   link declarado na página) — o FTP recusou a vantage do arquiteto. Se
   baixar: sha256 + entrada individual no MANIFEST. Se recusar também a sua:
   pendência escrita com a URL, sem drama.
3. **Nada de refresh de dados** — `data/sigtap_exames.csv` fica na 202606.
   Fabricar competência que não existe é o erro que este despacho existe para
   não cometer.

## §2 Perna TUSS — o trabalho real: a Tabela 22 vira base com fonte

### §2.1 Staging (engenheiro; a vantage do arquiteto está bloqueada)

Fonte: **TUSS Tabela 22 — Procedimentos e Eventos em Saúde** (ANS, padrão
TISS). Candidatas, nesta ordem:
1. Portal ANS (`ans.gov.br/padroes/tiss` e o padrão-tiss no gov.br) — a
   plataforma atual publica **xlsx/csv/json**. **A vantage do arquiteto levou
   403 (WAF) em 28/09 ~12h** — tentar da sua; navegando com navegador real se
   o curl recusar.
2. Se a ANS recusar também a sua vantage: **espelho declarado com
   corroboração** (padrão DPOC-2021): cópia de origem não-relacionada (ex. o
   repositório público `tabelas-ans` de Tabela 22 em CSV) **conferida contra
   uma segunda cópia** — conteúdo idêntico, procedência declarada no MANIFEST
   como espelho, jamais como oficial. Nunca inventar row.

Estagiar em `data/fontes-oficiais/tuss/` (pasta nova, MANIFEST.md próprio no
idioma da casa: sha256, URL, versão TUSS YYYYMM, data).

### §2.2 A base e o loader

- `data/tuss_procedimentos.csv`: código TUSS, descrição, versão snapshot —
  import direto da tabela estagiada, **sem edição manual de conteúdo**.
- Loader no padrão do `base_cid.py`/`sigtap` (proveniência por linha,
  `versao_snapshot`).
- **A curadoria existente NÃO é apagada**: `_BASE_RAW` do `tuss_base.py`
  (~35 procedimentos com aliases clínicos, preparo, alertas) vira **camada de
  enriquecimento sobre a base oficial** — o docstring promete exatamente esta
  v2 ("CSV/tabela local com versionamento explícito… mapeamento TUSS ↔
  SIGTAP"). A base oficial responde "o que existe"; a curadoria responde
  "como a casa apresenta".

### §2.3 O mapeamento TUSS ↔ SIGTAP — honesto ou nada

- Chave: nome normalizado (a disciplina `normalize`/`canon_ativo` da casa),
  **conferência manual amostral** dos matches (>95% de confiança declarada por
  cota; o resto fica sem par, com relatório).
- **Nunca fingir mapeamento**: a lição do `pedido_agendado` fantasma — não se
  anuncia fato que não ocorreu. Cobertura REPORTADA no PR body: "X dos 1.105
  procedimentos SIGTAP (grupo 02) têm par TUSS" com o método.
- O seletor TUSS/SIGTAP da clínica (Ticket D) e o faturamento pelos dois
  códigos continuam íntegros — guardas de não-regressão.

### §2.4 Guardas (ACs verificáveis)

1. Loader TUSS: contagem e versão declaradas; linha sem fonte reprova.
2. Mapeamento: par declarado sobrevive ao reload; **par fabricado reprova**
   (sabotagem: match por substring ingênuo tipo "biopsia" ≠ mesmo exame).
3. Regressão: `pedido_exame_itens.codigo_tuss`/`codigo_sigtap` e o seletor da
   clínica seguem funcionando (testes existentes verdes).
4. MANIFEST: TUSS com sha256 + proveniência (oficial ou espelho-declarado).
5. Suíte unitária inteira verde; browser suite local (CI de PR de dados só
   roda gates — a lição do #277).

## §3 Rito e deadline

1. PR única `ops(base)`: TUSS v2 + registro do teto SIGTAP. Zero `backend/app`
   fora do que §2.2 exigir (loader pode morar em `app/ai/`/`domain/` onde os
   pares atuais moram — a casa decide pelo menor diff).
2. Não colidir com ENG-026 (CSVs de semáforo/posologia e guardas de flip são
   território dela).
3. Registro-in-PR: o verbatim do Fabiano (cabeçalho deste despacho) no corpo.
4. Arquiteto RATIFICA com prova própria nas janelas da vigília (automação
   separada, nasce de seed block — ver mensagem ao Fabiano). Veredito escrito
   por rodada: RATIFICADO · BLOQUEADO (âncoras) · AGUARDANDO.
5. **Martelo do Fabiano ≤ 29/09 11:00 BRT.** Se às 09:30 a PR não estiver
   aberta, a vigília escala no relatório — deadline é deadline.

---

*Lavrado pelo arquiteto (Z) em 28/09/2026 ~12:15 BRT. A correção do veredito
SIGTAP entra no registro como ato: conferir a fonte antes de chamar de
defasada é o mesmo músculo de conferir merge antes de anunciar.*

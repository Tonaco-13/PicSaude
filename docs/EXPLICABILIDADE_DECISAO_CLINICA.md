# Explicabilidade do motor de apoio à decisão clínica (semáforo)

> **Classificação:** `docs` — descreve, não altera, o comportamento do motor.
> O motor em si (`backend/app/domain/semaforo_decisao.py`) é `module`.
>
> **Companheiro de:** [`ARQUITETURA_DECISAO_CLINICA.md`](ARQUITETURA_DECISAO_CLINICA.md)
> (o *quê* e o *porquê* do semáforo). Este documento responde a outra pergunta:
> **“por que ESTE sinal, para ESTA entrada — e como qualquer pessoa confere?”**

---

## 1. O que é este documento

O semáforo de apoio à decisão acende um sinal discreto — 🟢 *coerente* · 🟡 *atenção*
· (silêncio) — ao lado do fármaco que o prescritor escolheu, conferindo a coerência
da escolha contra a indicação (CID). É **validador, não recomendador**; é
**não-bloqueante**; o prescritor é o responsável final.

Um sistema que opina sobre uma decisão clínica precisa **prestar contas da opinião**.
Este dossiê é o contrato de explicabilidade do motor:

1. a **garantia** que o torna explicável (determinismo — seção 4);
2. o **algoritmo** que produz o sinal, passo a passo (seção 5);
3. a **ficha de explicabilidade** que acompanha cada sinal em runtime (seção 7);
4. **exemplos trabalhados** linha a linha (seção 8);
5. como **reproduzir** um sinal à mão (seção 9);
6. os **limites** — o que a explicação NÃO cobre (seção 10).

---

## 2. O que é — e o que não é

| O semáforo **é** | O semáforo **não é** |
|---|---|
| apoio à decisão (rótulo, sinal) | software que prescreve (SaMD) |
| validador da escolha do prescritor | recomendador de fármaco a partir do CID |
| determinístico (busca em lista curada) | IA generativa / modelo estatístico |
| não-bloqueante (informa, não trava) | gate que impede emissão |
| auditável célula a célula | caixa-preta |

> **Linha vermelha (inegociável).** O **motor** é do engenheiro (determinístico,
> sem LLM). O **conteúdo clínico** (qual fármaco para qual condição) é propriedade
> e responsabilidade da equipe clínica — Fabiano valida e assina cada lista. O
> sistema só **confere coerência**; nunca preenche sozinho, nunca bloqueia.

---

## 3. Por que explicabilidade é (quase) mandatória aqui

- **Risco clínico.** Um sinal sobre terapêutica influencia uma decisão de saúde.
  Influência sem justificativa rastreável é risco silencioso.
- **Responsabilidade.** Se o sinal estiver “errado” aos olhos do prescritor, ele
  precisa ver **por que** o sistema disse aquilo — para discordar com base, não no escuro.
- **Anti-viés.** A [lei da exaustividade](#6-a-lei-da-exaustividade-por-que-o-silêncio-existe)
  só é audível se for explícita: a ficha **declara** quando o motor se calou e por quê.
- **Coerência com a tese do PicSaúde.** “Auditoria é arquitetura”. Um motor
  determinístico permite **explicabilidade total** — algo que um LLM não oferece.
  Não aproveitar isso seria desperdiçar a maior vantagem do desenho.

---

## 4. A garantia central: determinismo

> **Mesma entrada + mesma versão de curadoria → sempre o mesmo sinal.**

O motor não “estima”, não amostra, não tem temperatura. Ele faz **busca exata** numa
lista curada e assinada. Isso tem três consequências de explicabilidade:

1. **Reprodutível** — qualquer pessoa, com o CSV curado e estas regras, refaz o sinal à mão (seção 9).
2. **Versionável** — o sinal carrega a `versao` da lista que o produziu. Mudou a lista, mudou a versão; o sinal antigo continua explicável pela versão antiga.
3. **Sem deriva** — não há retraining, não há atualização opaca de pesos. O comportamento só muda quando a curadoria muda — e isso fica registrado.

Teste que trava esta garantia: `test_ficha_determinismo_mesma_entrada_mesmo_sinal`.

---

## 5. O algoritmo, passo a passo

Entrada: `codigo_cid` (a indicação) e `principio_ativo` (o fármaco escolhido).

```text
1.  Normalização (determinística) — PRIMEIRO, para o teste de "ausente" ser justo:
        cid_canônico   = MAIÚSCULA + remove espaços   ex.: " i10.0 " → "I10.0"
        ativo_canônico = remove sal + acento + caixa
                          "Oxalato de Escitalopram" → "escitalopram"
                          "Losartana Potássica"     → "losartana"

2.  Entrada incompleta? (cid_canônico OU ativo_canônico vazio — inclui "   ",
    que canoniza para ""):
        → NEUTRO  (causa: entrada_incompleta; exaustiva=null)   [não julga]
    Senão:  cadeia_cid = [cid, categoria]          "I10.0" → ["I10.0","I10"]

3.  PORTÃO DA EXAUSTIVIDADE (antes de qualquer 🟢/🟡):
        existe algum CID da cadeia em `cids_exaustivos`?
        NÃO → NEUTRO (regra: "condição sem lista exaustiva")   [silêncio honesto]
        SIM → segue; guarda o cid_casado (o CID exaustivo encontrado)

4.  Verde — sobe a hierarquia do CID:
        para cada cid na cadeia:
            se (cid, ativo_canônico) ∈ aprovados:
                → VERDE  (proveniência da regra que casou)

5.  Amarelo — condição exaustiva, fármaco ausente da lista:
        → AMARELO (proveniência da condição; "fora do protocolo — confira")
```

O **portão da exaustividade vir antes do verde** é a decisão de desenho mais
importante (ver seção 6). Implementação: `avaliar_semaforo()`.

---

## 6. A lei da exaustividade (por que o silêncio existe)

> **Achado de Fabiano (2026-06-21).** Uma lista 🟢 incompleta **não é neutra** —
> ela privilegia os fármacos curados e desencoraja os válidos omitidos. Acender 🟢
> só para o que curamos seria *recomendação pela porta dos fundos*.

Portanto: o semáforo **só julga uma condição cuja lista 🟢 é EXAUSTIVA** (completa
em relação ao PCDT/diretriz). Se não é exaustiva, ele **se cala** — estado `neutro`,
sem ponto na UI — **nem 🟢**. Ele é autoritativo quando fala e honesto quando se cala.

A ficha torna o silêncio **auditável** (recomputável): o campo `causa`
(`condicao_nao_exaustiva` vs. `entrada_incompleta`), `condicao_exaustiva` e a `regra`
declaram, em código e em texto, que o motor não julgou e por quê — a ficha do `neutro`
é devolvida pela API e reproduzível à mão. **Ressalva honesta:** essa explicação vive
na ficha/API, **não inline na UI** — para o prescritor o `neutro` é silêncio sem ponto
(§7, nota de honestidade). O silêncio deixa de ser ambíguo *para quem audita*; na tela,
ele permanece discreto por desenho.

A curadoria é incremental: cada condição entra como **semente** (`exaustivo=false`,
silenciosa) e só acende quando a lista é completada **e** Fabiano marca `exaustivo=true`.
Hoje, exaustiva: **I10 (Hipertensão)**. Demais condições: semente (silêncio).

---

## 7. A ficha de explicabilidade (runtime)

O endpoint `POST /ia/decisao/validar` devolve, junto do sinal, uma **ficha**
autossuficiente — quem a lê reconstrói a decisão sem abrir o código:

```jsonc
{
  "ativo": true,
  "sinal": "verde",                          // verde | amarelo | neutro
  "motivo": "tratamento reconhecido para a condição",
  "fonte": "Hipertensão arterial",
  "explicabilidade": {
    "entrada": {
      "cid_recebido": "I10.0",                  // CID CRU, como recebido
      "cid": "I10.0",                           // CID canônico (maiúsc., sem espaço)
      "cid_casado": "I10",                      // CID da cadeia que casou a regra
      "principio_ativo_recebido": "captopril",  // fármaco CRU, como recebido
      "principio_ativo_canonico": "captopril"   // após remover sal/acento/caixa
    },
    "causa": "consta_lista_exaustiva",          // código ESTÁVEL da decisão (CAUSA_*)
    "condicao_exaustiva": true,                 // a lista 🟢 desta condição é completa?
    "regra": "(I10, captopril) consta na lista exaustiva validada da condição",
    "significado": "🟢 Coerente: o fármaco consta na lista validada …",
    "proveniencia": {                           // a "cadeia de custódia" da decisão
      "condicao": "Hipertensão arterial",
      "fonte": "RENAME 2024 + Diretrizes Brasileiras de HAS 2020 (SBC/SBH/SBN)",
      "validado_por": "Fabiano Tonaco Borges",
      "versao": "semaforo_has_exaustiva_v1_2026-06"
    },
    "determinismo": "Resultado determinístico (busca em lista curada, sem IA …)",
    "nao_bloqueante": "Sinal de apoio à decisão. Não bloqueia nem altera …"
  }
}
```

| Campo | O que prova |
|---|---|
| `entrada.*_recebido` | **o quê o prescritor digitou** (cru), para auditar a normalização |
| `entrada.cid` / `*_canonico` | a entrada **já normalizada** (a normalização é parte da decisão) |
| `causa` | **qual ramo** decidiu, em código estável (não-prosa) — ver tabela abaixo |
| `condicao_exaustiva` | **se** o motor tinha autoridade para julgar (`true`/`false`/`null`) |
| `regra` | **qual** regra disparou, em texto legível |
| `significado` | **o limite semântico** do sinal (anti-overclaim: 🟡 ≠ errado/perigoso) |
| `proveniencia` | **de onde** veio a regra: condição, fonte clínica, quem assinou, versão |
| `determinismo` | **por que** é reproduzível |
| `nao_bloqueante` | **o limite** da autoridade do sinal |

Códigos de `causa` (estáveis — a UI, os testes e a futura trilha de auditoria
dependem deles, não da prosa de `regra`/`motivo`):

| `causa` | Sinal | Significado |
|---|---|---|
| `consta_lista_exaustiva` | 🟢 | (CID, ativo) está na lista validada |
| `ausente_lista_exaustiva` | 🟡 | condição exaustiva, ativo fora da lista |
| `entrada_incompleta` | neutro | falta CID ou fármaco (ou canoniza p/ vazio) |
| `condicao_nao_exaustiva` | neutro | lei da exaustividade — sem lista completa |

`condicao_exaustiva` é **tri-estado**: `true`/`false` quando o portão da
exaustividade rodou; **`null`** quando nem chegou a rodar (`entrada_incompleta`) —
o motor não afirma o que não apurou.

No 🟢 a proveniência é a da **regra fármaco↔CID** que casou; no 🟡, a da **condição**
(não há fármaco aprovado, mas a condição tem proveniência); no `neutro`, é `null`
(o motor não inventa proveniência para um sinal que não deu).

**Na UI** (`prescritor.html`): ao lado do **ponto colorido** (🟢/🟡) aparece um link
discreto **“por quê?”** que abre a ficha — fármaco *como digitado → canônico*, regra,
o `significado` (anti-overclaim em destaque), fonte clínica, quem validou, versão e a
nota de determinismo/não-bloqueio.

> **Nota de honestidade sobre o `neutro` na UI.** O `neutro` **não pinta ponto nem
> “por quê?”** — por desenho deliberado (discrição; ver §6/§8.3) e porque, na fase de
> sementes, a maioria das condições é neutra e poluiria a tela. A explicabilidade do
> silêncio **existe e é recomputável** (a ficha do neutro é devolvida pela API e
> reproduzível à mão), mas **não é exposta inline** — para o prescritor, ausência de
> sinal é silêncio. Quem precisa auditar o silêncio consulta a API ou este dossiê. A
> superfície visual da “audibilidade” do silêncio fica para uma decisão de produto
> futura (afixo cinza opcional), não entregue nesta v1.

---

## 8. Exemplos trabalhados (linha a linha)

### 8.1 captopril em I10 → 🟢

```text
entrada:  cid="I10", ativo="captopril"
passo 1:  completo ✔
passo 2:  cid_canônico="I10"; ativo_canônico="captopril"; cadeia=["I10"]
passo 3:  "I10" ∈ cids_exaustivos ✔  → cid_casado="I10", condicao_exaustiva=true
passo 4:  ("I10","captopril") ∈ aprovados ✔
SINAL:    VERDE   ·   causa=consta_lista_exaustiva
regra:    "(I10, captopril) consta na lista exaustiva validada da condição"
prov:     Hipertensão arterial · RENAME 2024 + Diretrizes HAS 2020 ·
          validado_por=Fabiano · versao=semaforo_has_exaustiva_v1_2026-06
```

### 8.2 “Oxalato de Escitalopram” em I10.0 → 🟡

```text
entrada:  cid="I10.0", ativo="Oxalato de Escitalopram"
passo 2:  ativo_recebido="Oxalato de Escitalopram"; ativo_canônico="escitalopram"
          (sal removido — ambos ficam na ficha); cadeia=["I10.0","I10"]
passo 3:  "I10" ∈ cids_exaustivos ✔  → cid_casado="I10", condicao_exaustiva=true
passo 4:  ("I10.0","escitalopram")✘  e  ("I10","escitalopram")✘
passo 5:  → AMARELO   ·   causa=ausente_lista_exaustiva
regra:    "I10 tem lista exaustiva e escitalopram NÃO consta nela → fora do protocolo"
prov:     proveniência da CONDIÇÃO (Hipertensão arterial)
```

Note a honestidade: o sinal não diz “errado”, diz **“confira”** — escitalopram
não é anti-hipertensivo, e a hipertensão tem lista completa, então a ausência
*significa* algo. O prescritor decide.

### 8.3 metformina em E11 → silêncio (neutro)

```text
entrada:  cid="E11", ativo="metformina"
passo 2:  ativo_canônico="metformina"; cadeia=["E11"]
passo 3:  "E11" ∉ cids_exaustivos (semente)  → NEUTRO
SINAL:    neutro (sem ponto na UI)  ·  causa=condicao_nao_exaustiva  ·  exaustiva=false
regra:    "condição sem lista exaustiva curada → semáforo não julga"
prov:     null
```

> Um quarto caso, `causa=entrada_incompleta` (falta CID/fármaco, ou só-espaço): também
> `neutro`, mas com `exaustiva=null` (o portão da exaustividade nem rodou) e
> `proveniencia=null`. É o passo 0 da seção 9 — distinto do silêncio por exaustividade.

metformina **é** o tratamento de 1ª linha do diabetes — e ainda assim o motor se
**cala**. Isto é a lei da exaustividade funcionando: enquanto a lista de E11 não
for completada e assinada, acender 🟢 só para metformina desfavoreceria os demais
fármacos válidos do PCDT de diabetes que ainda não curamos.

---

## 9. Como reproduzir um sinal à mão

0. **Falta CID ou fármaco** (ou algum deles é só espaço / canoniza para vazio)?
   → **neutro** (`causa=entrada_incompleta`). Fim. *(Este é o passo 1 da seção 5; a
   canonicalização vem ANTES do teste — “   ” conta como ausente.)*
1. Abra a lista curada: `data/decisao_semaforo.csv`.
2. Normalize a entrada como na seção 5 (maiúscula no CID; remova sal/acento do ativo).
3. Veja se algum CID da cadeia tem `exaustivo` truthy entre as linhas `status_curadoria=validado`.
   - Não tem → **neutro** (`causa=condicao_nao_exaustiva`). Fim.
4. Tem → procure a linha `(cid, ativo)`:
   - existe → **🟢**; a proveniência é aquela linha (`fonte`, `validado_por`, `versao`).
   - não existe → **🟡**.

Não há nenhum passo que dependa de estado oculto, aleatoriedade ou modelo. O CSV
+ estas regras bastam. (É exatamente o que o teste do loader exercita.)

> **Assimetria de verificação (🟢 é local, `neutro` é global).** Confirmar um 🟢
> exige **achar uma linha** — verificação local. Confirmar um `neutro` por
> não-exaustividade exige provar que **nenhuma** linha validada marca a cadeia como
> exaustiva — uma quantificação negativa sobre o CSV inteiro. Logo o `neutro` só é
> conferível **globalmente** (varrendo a lista). O campo `causa` e a `cadeia`
> (recomputável de `entrada.cid` pela regra da seção 5) tornam a conferência possível,
> mas ela continua sendo sobre o arquivo todo, não sobre uma única linha.

---

## 10. Limites — o que a explicação NÃO cobre (ainda)

- **Não é contraindicação (🔴).** A v1 só confere coerência fármaco↔CID. Interação,
  alergia e contraindicação (drug–disease) são **Fase 2**, com base própria. O 🟡
  diz “fora do protocolo / confira”, **não** “perigoso”.
- **Não julga dose, via, posologia.** Só o princípio ativo contra a indicação.
- **Não recomenda.** Nunca sugere fármaco a partir do CID (decisão de desenho).
- **Cobertura ≠ exaustividade declarada.** Só I10 é exaustiva hoje; nas demais o
  silêncio é o comportamento correto, não uma falha.
- **O `neutro` só é conferível globalmente.** Reproduzir um 🟢 é local (acha-se a
  linha); reproduzir um `neutro` por não-exaustividade exige varrer o CSV inteiro
  (quantificação negativa). Ver a nota da seção 9.
- **O silêncio não é exposto na UI.** A explicabilidade do `neutro` existe na ficha/API
  e neste dossiê, mas não aparece inline para o prescritor (decisão de discrição). Ver
  §7, nota de honestidade.
- **A explicação é tão boa quanto a curadoria.** O motor é auditável a 100%; a
  *qualidade clínica* da lista é responsabilidade da equipe clínica que a assina.
  A `versao` + `validado_por` é justamente o que torna essa responsabilidade rastreável.

---

## 11. Camada 3 — trilha de auditoria (próxima fase)

Hoje a ficha é **calculada sob demanda** (recomputável a qualquer momento, porque é
determinística). O que ainda **não** existe é uma **trilha append-only** que registre
*cada avaliação efetivamente apresentada ao prescritor* (entrada + sinal + versão da
regra + carimbo de tempo).

Isso toca o **ledger** (núcleo, classe `core`) e exige revisão central — fica para a
próxima fase, deliberadamente separada destas camadas 1 e 2. Quando existir, fechará
o ciclo: *recomputável* (hoje) **+** *registrado* (camada 3) = explicabilidade completa.

---

## 12. Referências

- `backend/app/domain/semaforo_decisao.py` — o motor (`avaliar_semaforo`, `to_ficha`)
- `backend/app/routers/ia.py` — `POST /ia/decisao/validar` (devolve a ficha)
- `backend/tests/unit/test_semaforo_decisao.py` — contrato testado da ficha
- `data/decisao_semaforo.csv` — lista curada e assinada (fonte de verdade clínica)
- `prescritor.html` — o “por quê?” na UI
- [`ARQUITETURA_DECISAO_CLINICA.md`](ARQUITETURA_DECISAO_CLINICA.md) — o desenho do semáforo

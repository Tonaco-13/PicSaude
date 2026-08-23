# Desenho — laudo × posse por item + ciência derivada da abertura (`module`)

| Campo | Valor |
|---|---|
| **Origem** | Proposta do Fabiano em 20/08 (chat do arquiteto, pós-vitrine) + pendência `laudos.py` registrada nos PRs #170/#172 |
| **Autor** | Arquiteto (Z) — desenho; implementação do engenheiro |
| **Martelos** | DOIS, registrados em 20/08 (ver §1) |
| **Classe** | `module` — com dois toques sinalizados (§9); **nenhum estado novo, nenhuma aresta nova** |
| **Estado** | Pronto para o engenheiro |

---

## §0 O problema (duas frentes, um módulo)

1. **Laudo × custódia parcial (pendência desde o J.10).** `laudos.py` deriva o
   direito de operar da posse de **nível-pedido** (`dispensador_detem_pedido`).
   Com a custódia parcial (#170), um pedido explodido em nível-item não tem
   linha ativa de pedido — a unidade que detém legitimamente 2 de 5 itens fica
   **fora da guarda** de criar/operar o laudo deles. Foi reportado como achado
   nos PRs e ficou aguardando este desenho (a ciência do laudo opera no nível
   do laudo inteiro — exceção documentada —, então a decisão não era óbvia).
2. **Abertura do laudo como fato (proposta do Fabiano).** Quando o cidadão
   abre o laudo, a clínica deve saber (confirmação rastreada) e a ciência do
   paciente deve nascer daí (sem clique morto), com repercussão na **visão**
   da unidade — sem tocar no gatilho do faturamento.

## §1 Martelos registrados (Fabiano, 20/08, chat do arquiteto)

> **(a) "Abrir o laudo = dar ciência"** — o evento nomeia a ABERTURA (fato
> real); a ciência é consequência DERIVADA, declarada como regra. O ledger
> fica honesto: *abriu em X → ciência derivada da abertura* — nunca
> "ciência" anunciando fato que não ocorreu (a lição do `pedido_agendado`
> fantasma, J.7).
>
> **(b) "Faturamento ancorado na liberação"** — o fato financeiro é da unidade
> (laudo liberado); a leitura é comportamento do cidadão. A abertura vira
> **coluna informativa** de relatório/histórico ("lido em"), **nunca gatilho**
> de faturamento (espírito B0/R1: o movimento se escreve quando o fato da
> unidade acontece).

Aprovados com: *"Estou de acordo com sua recomendação"* → *"Aprovado"* (20/08).

## §2 Posse por item no laudo — **v2, com errata** (20/08, após §3-stop do engenheiro)

> **ERRATA:** a v1 deste §2 presupôs um elo `laudo_item → pedido_item` que
> **não existe**: `laudo_itens` guarda `nome_exame`/`codigo_tuss` (texto
> livre), sem `pedido_item_id`. O engenheiro parou pelo §3 do ENG-012 —
> certo: casar autorização por **nome** é a mesma família de defeito que a
> casa já rejeitou três vezes (posse lida do status no J.7, predicado
> duplicado no #168, relatório lendo nível-pedido no #172). Erro do desenho,
> não da implementação. Decisão do arquiteto: **o elo de verdade (opção 1),
> com a leitura fraca como ponte REGISTRADA para os legados (opção 2)**.

### §2.1 O elo de verdade — `pedido_item_id` em `laudo_itens`

- **Migração** (dois dialetos, §9 do CLAUDE.md): `laudo_itens.pedido_item_id
  INTEGER NULL REFERENCES pedido_exame_itens(id)`. **Sem backfill**: linhas
  históricas ficam `NULL` para sempre — reconstruir o passado casando nome
  seria o pecado de novo, agora dentro de uma migração (espírito R3: o
  histórico é fato consumado).
- **Payload:** `ItemLaudoIn` ganha `pedido_item_id: Optional[int]`.
- **CRIAÇÃO por dispensador exige o elo em TODOS os itens**: cada
  `pedido_item_id` deve pertencer ao pedido vinculado (404/422) e estar sob
  custódia da unidade (`dispensador_detem_item` — import da fonte única). A
  tela da clínica já escolhe da bancada, onde os ids existem. Criação por
  prescritor/admin segue como está (o vínculo deles é clínico, não de posse).
- **OPERAÇÃO de laudo existente:** detém o pedido **OU ao menos um item
  DESTE laudo com elo** (`pedido_item_id` vinculado sob custódia).

### §2.2 A ponte registrada — laudos legados (sem elo)

Laudo cujos itens são todos `pedido_item_id NULL` (nascidos antes do elo) é
operável por quem detém **qualquer coisa do pedido vinculado** — o predicado
**grossa** do #172 (`dispensador_tem_algo_no_pedido`), reusado, não
reescrito. É menos preciso e **declarado**: ponte para o legado, que fecha o
bug em aberto (pedido explodido → ninguém opera o laudo) já no mesmo PR.
Laudos novos de dispensador nunca nascem na ponte (§2.1 exige o elo).

A ciência continua no nível do **laudo inteiro** (exceção documentada ao
núcleo permanece): a unidade que produziu parte dos exames lauda os seus
itens; o laudo dela cobre o que ela detém.

## §3 A abertura como ato — `POST /laudos/{protocolo}/abrir`

- **Papel:** `paciente` dono (404 → 403 → 422, anti-leak #52).
- **Nunca em `GET`:** abertura é ato, e ato escreve ledger por `POST`
  explícito. O frontend chama ao abrir o cartão do laudo.
- **Efeitos, na mesma transação, nesta ordem:**
  1. emite `laudo_aberto_paciente` (novo evento — §9) com payload
     `{aberto_em, derivada_ciencia: true/false}`;
  2. **se** o laudo está `liberado` → ciência derivada pela MESMA lógica do
     `POST /ciencia-paciente` existente (transição + eventos de ciência dele);
     **se** está `ciencia_prescritor` → idem (a regra das duas ciências fecha o
     laudo — composição, não duplicação);
     **se** já está `ciencia_paciente`/`encerrado` → só o fato da leitura.
- **Idempotente:** a SEGUNDA abertura responde 200 e **não emite nada** — um
  fato, um evento (espírito R2). Implementação: `laudo.aberto_em` (coluna
  nova) como carimbo da primeira.
- **Estados inválidos** (`em_producao`, `assinado`, `cancelado`): 422 — não há
  o que abrir; `encerrado_fisico` idem.
- Laudo standalone (sem pedido vinculado): abre e deriva ciência do mesmo
  jeito — a abertura não depende do pedido.

## §4 Máquina de estados: MUDANÇA NENHUMA

`liberado → ciencia_paciente` já é aresta válida
(`states_laudo.py::TRANSICOES_LAUDO`), e o endpoint de ciência já compõe as
duas ciências. O desenho inteiro é **um caminho novo para uma transição
existente** — nenhum estado, nenhuma aresta, nenhum `states_laudo.py`. É o
mesmo formato do martelo do J.7 (a aresta declarada que o caminho novo torna
alcançável já estava lá).

## §5 Comunicação à clínica — projeção, sem push

Não há infra de push e não haverá antes do G4A (regra da casa). A confirmação
rastreada vive na **leitura**: o Histórico da clínica (PR paralelo do
engenheiro) mostra o selo **"Lido em dd/mm hh:mm"** a partir do campo
`aberto_em`, no polling de 30s da fila — a unidade vê sem perguntar.

## §6 Relatórios e faturamento

- **Gatilho: MUDANÇA NENHUMA.** Faturamento segue ancorado no
  resultado/liberação (fato da unidade), como hoje (#172).
- **Coluna informativa opcional:** relatório da clínica pode exibir
  "aberto_em" quando existir — leitura, nunca condição.

## §7 Telas

- `cidadao.html` (aba Laudos/Resultados): abrir o laudo chama `POST /abrir`
  **uma vez** (o carimbo `aberto_em` no GET evita a segunda chamada); nenhum
  botão de ciência — a ciência nasce da abertura (martelo (a)).
- `clinica.html` (Histórico — PR paralelo): selo "Lido em" quando o campo
  existir; o PR do Histórico pode subir **antes** deste desenho, sem o selo.

## §8 Testes (ACs)

| AC | O que trava |
|---|---|
| (i) | unidade parcial cria laudo dos SEUS itens e é barrada (403) nos alheios |
| (ii) | abrir laudo `liberado` → evento `laudo_aberto_paciente` + estado `ciencia_paciente` (derivada) |
| (iii) | abrir laudo com `ciencia_prescritor` → ciência completa → `encerrado` (composição com a regra existente) |
| (iv) | segunda abertura → 200 sem novos eventos (idempotência) |
| (v) | faturamento **inalterado** pela abertura (regressão: laudo não-aberto fatura igual ao aberto) |
| (vi) | guard: unidade sem posse nenhuma não cria laudo (403); stranger não abre laudo alheio (403) |
| (vii) | E2E navegador: cidadão abre o laudo → Histórico da clínica mostra "Lido em" |
| (viii) | **dois itens de mesmo `nome_exame` no mesmo pedido** autorizam pelo ID, não pelo nome (o caso que mata o casamento por texto) |
| (ix) | **exame renomeado** (item reemitido/derivado) não muda quem pode operar o laudo — o elo é a chave, o nome é exibição |
| (x) | **ponte §2.2:** laudo legado (itens sem elo) operável por quem detém qualquer item do pedido; laudo novo de dispensador sem elo → 422 |

## §9 Classificação e toques sinalizados

`module` (laudo é módulo existente; sem core). Sinalizados para o revisor:

1. **Novo evento** `laudo_aberto_paciente` no vocabulário (`EVENTOS_LAUDO`,
   `ARQUITETURA_LAUDO.md` e a lista do AGENTS §7 — governança de lista, como
   o J.10 fez com motivos). Coluna `aberto_em` em `laudos` → **migração**
   (dois dialetos, §9 do CLAUDE.md — a migração é a autoridade).
   *(ENTREGUE no #177 — migração `e7c3a9f21b58`.)*
2. **Guards de `laudos.py`** trocam o predicado (import da fonte única) —
   semântica de autorização por posse, mesma família que o #172 revisou.
3. **(v2)** `laudo_itens.pedido_item_id` → migração nos dois dialetos,
   nullable, **sem backfill** (§2.1); `ItemLaudoIn.pedido_item_id` opcional
   com validação de pertencimento ao pedido vinculado.

## §10 Fora de escopo (explícito)

Push/websocket/e-mail (G4A não existe) · ciência do PRESCRITOR automática
(continua explícita — o laudo "encerra" quando ambas existem, regra atual) ·
faturamento condicionado à leitura (**vetado** pelo martelo (b)) · laudo físico.

---

*Desenho do arquiteto (Z), 2026-08-20, sobre os martelos de 20/08. Implementação
para o engenheiro; discordância de ponto técnico → §3 do ENG-012 (para e devolve).*

# Desenho — encaminhamento/contrarreferência na vitrine: a terceira circulação (`module` + 1 `core`)

| Campo | Valor |
|---|---|
| **Origem** | Demanda do Fabiano em 23/08 (pré-go-public) + duas consultas Kimi (23/08) integradas com verificação no código |
| **Autor** | Arquiteto (Z) — desenho; implementação do engenheiro |
| **Base** | Backend E1/E2 pronto e verificado: máquina própria, loop de custódia inteiro, zero telas |
| **Martelos pendentes** | TRÊS, no §11 — bloqueiam o despacho |
| **Erratas do arquiteto** | (1) CR tem custódia própria (Fork 3, verificado) — não "a definir"; (2) `justificativa_clinica` é obrigatória no schema — minha consulta disse "opcional" |

---

## §1 A máquina real (verificada, não presumida)

Estados: `emitido → em_regulacao → agendado → atendido → contrarreferido → encerrado`
(+ `cancelado · expirado · negado · encerrado_fisico`). Itens: `pendente → em_andamento → concluido`.

Custódia do encaminhamento por gesto:

| Gesto | Posse | Fato |
|---|---|---|
| emitir (digital) | **abre no cidadão** | `emissao_digital` |
| agendar (destino) | **vai ao prescritor destino** | `agendamento_destino` |
| atender (destino) | **VOLTA ao cidadão** | `atendimento_realizado` — o carteiro clínico carrega a volta |
| contrarreferir (destino) | objeto DERIVADO nasce (`origem_encaminhamento_id`) com **custódia própria** (Fork 3, `contrarreferencia_custodia` existe) | conteúdo clínico → origem |
| encerrar (origem) | terminal | ciência do ciclo |

Documento canônico com hash SHA-256 (o que o médico confirma é o que viaja).

### §1a ADENDO (23/08, martelo do Fabiano: "mesma regra das receitas e exames")

A pergunta do Fabiano expôs que o encaminhamento **não tem gesto de entrega do
cidadão** — a posse ao destino vinha pelo `agendar` dele, misturando posse+agenda
(o padrão pré-J.7). Fica a regra da trilogia:

- **NOVO gesto `entregar` (cidadão, na carteira)**: posse cidadão → prescritor
  destino (`motivo: apresentacao_cidadao`), espelho do transferir-farmácia/
  transferir-laboratório. É o momento-wow do selo trocando de mãos, com o
  cidadão como protagonista.
- **`agendar` deixa de escrever custódia** (agenda é compromisso, posse é posse
  — J.7 aplicado ao terceiro objeto). `atender` inalterado (devolve ao cidadão).
- Cadeia final: **cidadão → destino (entregar) → cidadão (atender)** — o carteiro
  clínico carrega ida e volta, com o gesto dele marcando cada handoff.

## §2 As leis de UX desta tela (rulings)

1. **Abas listam por DEVER do papel; selos mostram POSSE física** — duas queries. `atendido` é dever do destino com posse no cidadão: listar por custódia o faria sumir da tela exatamente quando vira obrigação.
2. **Dois selos, nunca um**: posse ("Com você"/"Com Dr. X") + dever ("aguardando retorno do Dr. X").
3. **Selo segue o documento ATIVO**: até `atendido`, o encaminhamento alimenta; de `contrarreferido` em diante, a contrarreferência. Uma fonte por tela.
4. **Data da CONSULTA no selo do cidadão**, nunca o timestamp da custódia — dois fatos, dois campos.
5. **`em_regulacao` = badge honesto na timeline** ("aqui a regulação se encaixaria — o estado já existe"). Nunca engine fingida.
6. **`negado`/`expirado` = selo "precisa de ação: reencaminhar"** (re-emissão é derivação, nunca edição).
7. **Ciência de ciclo EXPLÍCITA** (`encerrar`) — divergência deliberada do laudo (abrir = ciência de leitura): aqui o fato é o origem declarar-se ciente do retorno e FECHAR o ciclo. Cada objeto nomeia seu fato.
8. **Auto-encaminhamento bloqueado na emissão** (origem ≠ destino).
9. Empty states por pergunta; 403 de posse nunca derruba sessão (padrão da casa).

## §3 Prescritor — abas por chapéu

- **Encaminhados** (sou origem): emitir · acompanhar (timeline com regulação-badge) · selos de retorno · ciência (`encerrar`).
- **Recebidos** (sou destino), **por dever**: *chegou pra mim* (agendar/recusar) · *atendi e devo retorno* (`atendido` — SEM posse, mas COM dever: contrarreferir) · *já devolvi* (`contrarreferido`, acompanhar).

## §4 Cidadão — aba Encaminhamentos na carteira

"Com você — leve ao Dr. X (Cardiologia)" · "Consulta dia dd/mm às hh" (data da marcação) · "Com Dr. X desde dd/mm" · "Voltou: leve ao Dr. origem" (contrarreferência) · lente de rastreabilidade por cartão.

## §5 Formulário de emissão (consulta 2, integrada)

**Critério: automatiza-se FATO recuperável; juízo clínico é manual.** Frase-teste: *"se isso estiver errado, quem percebe — o médico ou o sistema?"*

- **Cabeçalho gerado, fora da caixa de texto**: "Encaminho a paciente [nome] para [finalidade] em [especialidade]" — visível, não editável como texto clínico (senão vira texto juridicamente vazio).
- **Finalidade estruturada** (lista curta + "outra" com texto): `avaliação · conduta · exame complementar · segunda opinião · seguimento` — dado operacional que a regulação futura vai filtrar. *Exige coluna nova → martelo §11.2.*
- **Especialidade PRIMEIRO, profissional depois** (semântica do SUS e do schema: `especialidade_destino` NOT NULL; `cns_destino` é executor). Lista local versionada no seed (10–15 na demo; CFM completa depois), busca por substring, "outra" exige texto visível.
- **Sugestão de destino** ordenada por "já atendeam este paciente" (dado que o LEDGER já tem — a rede se conhece porque os objetos circularam): razão DECLARADA na UI, nunca pré-selecionado, e as sugestões apresentadas entram no payload de `encaminhamento_emitido` — se o sistema influencia a escolha, a influência é auditável. Mitigação do efeito primeiro-da-lista/captura de demanda. *Martelo §11.3.*
- **CID: mini-catálogo local (snapshot versionado, ~300 APS frequentes) + escape "não listado → digitar" validado por formato.** Visualmente OPCIONAL — CID inventado para "passar" é pior que ausente: entra no hash.
- **Justificativa clínica: OBRIGATÓRIA** (schema manda; a tela conhece o contrato do backend, não versão mais permissiva). Placeholder orientador ("hipótese, sintomas relevantes, o que espera do destino"), comprimento mínimo modesto, zero validação semântica fingida.
- **A confirmação mostra o DOCUMENTO MONTADO** — o que será hasheado e lido pelo destino — não o formulário. *A última coisa que o médico vê é o documento como o destino o lerá.*
- Defaults visíveis e alteráveis no ponto de confirmação; nada invisível.

## §6 `core` — índice único de posse ativa

`encaminhamento_custodia` tem `encerrada_em` mas **não tem o índice único parcial** — espelho exato do #168. A onda passa a ESCREVER custódia por telas; unicidade por convenção não é invariante (COER-2). Migração nos dois dialetos para `encaminhamento_custodia` **e** `contrarreferencia_custodia` (verificando o formato desta no implementar). Martelo do Fabiano no PR.

## §7 Corte de MVP

**Fica (o círculo, 6 gestos):** emitir → cidadão vê "leve ao Dr. X" → destino agenda → destino atende → contrarreferencia → origem encerra (ciência). **`negado` fica** (a pergunta de todo gestor: "e se recusar?").
**Sai:** fluxo físico, PDF/QR, expiração simulada, regulação transitada (badge só), correção manual de rumo.

## §8 ACs

(i) os 4 handoffs de posse por custódia, nunca por status; (ii) `atendido` visível no Recebidos do destino SEM posse (dever ≠ posse); (iii) a confirmação congela o documento montado (hash reprodutível); (iv) sugestões apresentadas no payload do evento; (v) guard do índice único nos dois dialetos; (vi) E2E das 3 sessões (origem/cidadão/destino) ensaiado com seed — 403 no meio da vitrine mata a narrativa.

## §9 Entregas

| # | O quê | Classe |
|---|---|---|
| 1 | índices de posse única (§6) | `core` (martelo) |
| 2 | prescritor: abas + emissão (§3/§5) + seed (especialidades, CID mini, 2º prescritor persona) | `module` |
| 3 | cidadão: aba Encaminhamentos (§4) | `module` |

## §10 Fora de escopo

Engine de regulação/SISREG · PDF/QR público do encaminhamento · expiração automática · catálogo CID completo · assinatura ICP da contrarreferência (futuro documentado).

## §11 MARTELOS pendentes do Fabiano

1. **Justificativa clínica OBRIGATÓRIA confirmada?** O schema diz sim; sua intuição disse "opcional". Minha recomendação: obrigar (coração do documento; vazio é juridicamente nulo). Mudar = migração + afrouxamento.
2. **Finalidade estruturada no MVP?** Coluna nova + migração module-level. Minha recomendação: **sim** — a tela nasce agora e a regulação futura filtra por ela; retrofit em documento canônico é pior.
3. **Sugestão de destino (versão leve, auditável)?** Minha recomendação: **sim** — é a demonstração da tese ("a rede se conhece") com dado que já existe; com razão declarada e nunca pré-selecionada.

---

*Desenho do arquiteto (Z), 23/08, sobre duas consultas Kimi integradas com verificação no código (3 erratas do arquiteto capturadas pelo método nesta onda: CR-Fork 3, justificativa NOT NULL, e o §6 flagrado na primeira análise). Despacho ENG-016 após os martelos do §11.*

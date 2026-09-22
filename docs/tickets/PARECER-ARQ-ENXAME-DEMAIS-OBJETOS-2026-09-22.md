# PARECER-ARQ — Enxame nos demais objetos: três PROPOSTAS, três VISTOS, cinco adjudicações e um fato verificado que responde a pergunta mais afiada

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Objeto** | `RESPOSTA-KIMI3-DESPACHO-009.md` + tickets `DESENHO-{PEDIDO-EXAME|ENCAMINHAMENTO|ATESTADO}-VIVO.md` + 3 mocs + 3 PDFs de referência |
| **Data** | 22/09/2026 |
| **Veredito** | **VISTO nos três tickets** (condicionados aos martelos de selo/ordem no despacho ao engenheiro) — o enxame entregou o método completo com evidência própria, e o padrão está confirmado como família |

---

## §1 O que verifiquei com as minhas mãos (além da leitura)

1. **A pergunta mais afiada — respondida no código**: o atestado digital TEM
   custódia ao paciente de fato. `atestados.py:440` (*"registra custódia
   prescritor → paciente na própria emissão"*), `:540` (INSERT em
   `atestado_custodia`) e `:548` (evento `custodia_transferida`). O selo
   **"✓ EMITIDO · CUSTÓDIA AO PACIENTE" é fato, não promessa** — a cautela da
   Kimi era o rito certo; o código fecha a questão. O físico segue sem custódia
   (CPF sentinela, `:588`) — a redação honesta da variante física está correta.
2. **CID do exame não viaja no payload — confirmado**: nenhum campo `cid` no
   schema de criação de `pedidos_exame.py`. É **defeito de contrato** (não
   intenção documentada em lugar nenhum) — ver adjudicação 5.
3. **Moc do exame visto em navegador (1440px)**: padrão normativo A1–A6 presente
   (palco creme, tipografia dual, papel com borda quente/sombra) e o documento
   lê como pedido oficial (selo de prioridade, blocos rotulados, exames
   numerados). Os W≡Y dos mocs foram verificados pelo enxame em runtime
   (incluído o estado emitido) — aceito como evidência dela, no rito da casa.

## §2 VISTO por objeto

| Objeto | Visto | Observação |
|---|---|---|
| **DESENHO-PEDIDO-EXAME-VIVO.md** | ✅ | o quase-isomorfo que valida a família; 10 ACs no formato da casa; CID-no-payload bem declarado fora de escopo |
| **DESENHO-ENCAMINHAMENTO-VIVO.md** | ✅ | o destinatário-em-destaque como assinatura do papel é o achado certo deste objeto; cria o alvo de impressão que o objeto nunca teve, sem endpoint novo |
| **DESENHO-ATESTADO-VIVO.md** | ✅ | a lacuna INLINE dentro da frase é o gesto do degenerado — e as duas lições que o núcleo precisa absorver (região nomeada, lacuna inline) estão no §4 |

## §3 As cinco adjudicações do arquiteto

1. **(mecanismo) Print-area POR OBJETO.** Cada submódulo ganha o seu alvo
   (`#print-area-exame`, `#print-area-encaminhamento`, `#print-area-atestado`),
   todos alimentados pelo gerador do próprio objeto; o `#print-area` singular
   segue sendo da receita. Nada de alvo multi-objeto chaveado por aba —
   imprimir é momento de verdade, e a chave de submódulo é variável a mais
   falível no caminho. Os fluxos FÍSICOS de exame e atestado **não mudam nesta
   onda** (o papel oficial segue nascendo no servidor; a print-area é alvo de
   W≡Y e conferência — pergunta 1 do atestado respondida: segunda opção, a de
   menor atrito, um renderizador oficial).
2. **(selos) Endosso integral das três redações**, com o fato do §1 atualizando
   a do atestado: exame **"✓ TRANSMITIDO · CUSTÓDIA AO PACIENTE"** (ARQUITETURA
  _EXAMES: quem nasce detendo é o cidadão) · encaminhamento **"✓ EMITIDO ·
   CUSTÓDIA AO CIDADÃO"** (a emissão digital abre a posse no cidadão) ·
   atestado digital **"✓ EMITIDO · CUSTÓDIA AO PACIENTE"** (verificado no
   código) · físicos honestos ("🖨 IMPRESSO/IMPRESSA · SEM CUSTÓDIA DIGITAL").
   **Palavra final do Fabiano** — é caneta dele, no despacho.
3. **(núcleo) Arquivo novo por extração — e a extração acontece NA ONDA DO
   EXAME.** `documento-nucleo.js` nasce doando-lhe as peças do `receituario.js`
   (lacuna, tinta por `data-bloco`, contrato W≡Y `montar`/`textoDoDocumento`/
   `MODOS`, FAB, máscaras) **consumido por dois geradores no mesmo PR** — o
   núcleo nunca existe sem um segundo cliente. Região nomeada e lacuna inline
   (as lições do degenerado) entram no contrato do núcleo DESDE O NASCIMENTO,
   não como reforma do atestado depois.
4. **(título do atestado) A folha viva USA o título oficial** ("ATESTADO
   MÉDICO", pelo precedente da Receita Viva — a folha é o documento se
   formando); a proibição MANTIDA no rascunho da IA Documental (são artefatos
   de features diferentes — a caixa da IA é papel de trabalho, a folha é o
   papel). Confirmado por mim; veto do Fabiano possível no despacho.
5. **(CID do exame) Ticket próprio de backend, DEPOIS das três ondas.** O
   achado é defeito de contrato real — mas casar frontend puro com mudança de
   payload na mesma PR é acoplamento que o padrão recusa. Recomendo abrir o
   ticket (o pedido de exame carregando o CID da indicação — `module`, toca
   `pedidos_exame.py` + payload) **após** as ondas de UI. Caneta do Fabiano
   para abrir (ou recusar).

## §4 Ordem ao engenheiro e próximo passo

**Exame → Encaminhamento → Atestado** — a evidência do enxame confirmou a
recomendação (isomorfo valida o padrão; degenerado prova a generalização por
último, com o núcleo já amadurecido). **Um despacho por onda, fila serial**
(ENG-022 = exame, quando o Fabiano martelar selos + ordem). Os PDFs de
referência são a régua da minha ratificação de cada PR — conferência visual
contra o papel canônico, além das guardas.

— Arquiteto (Z), 22/09/2026

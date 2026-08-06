# TICKET-SEED-EXAMES-DEMO — Seed de pedidos de exame + laudo para a demo

| Campo | Valor |
|---|---|
| **Classe** | `module` (seed de dados do módulo de exames — não toca núcleo) |
| **Estado** | 🟢 **IMPLEMENTADO** (commit `8cdd81e`, branch `module/seed-exames-demo` base limpa em main) — **lacuna detectada na implementação, ver ADENDO abaixo** |
| **Hipótese adotada** | Q2-M (mínimo viável) — laudo mockado no seed; UI de emissão de laudo fica pra fase seguinte |
| **Para** | Arquiteto ratifica ✅ → Engenheiro (Claude Code/terminal) pluga no `seed_demo.py` ✅ → aguarda PR |
| **Pré-requisito** | Martelo do Fabiano sobre Q2-M. (Q1=(a) ratificada: clínica usa role `dispensador` com CNPJ próprio; `prestador_exame` é ticket `core` agendado — `TICKET-CORE-ROLE-PRESTADOR-EXAME`.) |
| **⚠️ ADENDO** | `docs/tickets/ADENDO-SEED-EXAMES-PERSONA-CLINICA.md` — lacuna detectada pelo Engenheiro: o seed cria a clínica na tabela `usuarios`, **mas não registra a persona no `/demo/login`**. A clínica continua inacessível pela demo. Adendo cobre `_PERSONAS["clinica"]` em `demo.py` + `ROLE_BY_HREF` em `index.html`. |

---

## §1 Objetivo

A demo hoje nasce com as tabelas de exame **vazias** (`pedidos_exame`, `laudos`, `agendamentos` existem no schema mas não recebem seed). Resultado: o cidadão vê "sem pedidos", o prescritor não tem histórico, a clínica não tem o que buscar.

Este ticket adiciona ao `seed_demo.py` **dois objetos sanitários de exemplo**, fiéis aos invariantes (estados, custódia, ledger), para que a demo mostre o módulo de exames "de pé":

1. **`DEMO-EXAME-0001`** — pedido **ativo** (`emitido`), aguardando agendamento pelo cidadão.
2. **`DEMO-EXAME-0002` + `DEMO-LAUDO-0001`** — pedido **com resultado** + laudo **liberado**, aguardando ciência do cidadão.

> **Estratégia Q2-M (mínimo viável):** o laudo entra pronto no seed (`liberado`), sem exigir que a clínica o emita pela UI. A UI de emissão de laudo (Gap 1) fica pra fase seguinte. Assim a demo mostra o ciclo completo do ponto de vista do **cidadão** (tem pedido ativo + tem resultado) sem bloquear pela lacuna de UI da clínica.

---

## §2 Pré-requisito institucional — criar o prestador laboratório

A custódia de exame referencia o CNPJ do laboratório. Hoje `CLINICA` (`seed_demo.py:88`) é só uma constante de referência — **não há `prestador` semeado**. O seed precisa criar a instituição laboratório na tabela `prestadores` (+ `unidades`), **sem** criar o `usuario` de login (isso é a decisão Q1, pendente).

Adicionar ao `main()` do seed, antes dos pedidos:

```python
# Prestador laboratório (instituição) — prereq dos exames abaixo.
# Q1=(a) ratificada: a clínica usa role `dispensador` (compartilhada) com CNPJ próprio
# (`11222333000181`). A separação de auditoria na demo é por estabelecimento.
# A role `prestador_exame` é ticket `core` agendado (TICKET-CORE-ROLE-PRESTADOR-EXAME)
# — entra quando o piloto real for autorizado.
_garantir_usuario(conn, CLINICA["cnpj"], CLINICA["nome"], "dispensador")
_garantir_prestador(
    conn,
    org_id="clinica-demo",
    nome=CLINICA["nome"],
    tipo="laboratorio",
    cnpj=CLINICA["cnpj"],
    unidade_id="DEMO-LAB",
    unidade_nome="Laboratório Demo",
    unidade_tipo="laboratorio",
)
```

> **Decisão Q1=(a) incorporada:** o `_garantir_usuario` cria o login da clínica sob role `dispensador` (mesma mecânica do `dispensador_norte` — mesmo role, CNPJ/nome próprios). Quando o `TICKET-CORE-ROLE-PRESTADOR-EXAME` ativar, este linha migra pra `prestador_exame`.
>
> **Nota:** `tipo="laboratorio"` em `_garantir_prestador` é semanticamente correto. Se houver validação de domínio que rejeite esse valor, ajustar para o valor canônico aceito. (Confirmar com o Engenheiro na implementação.)

---

## §3 Spec — `_garantir_pedido_exame_ativo(conn)`

**Objeto:** `DEMO-EXAME-0001` — pedido emitido, 1 item pendente, custódia prescritor→paciente.

```python
def _garantir_pedido_exame_ativo(conn) -> None:
    """
    DEMO-EXAME-0001 — pedido ativo (emitido), aguardando agendamento pelo cidadão.

    Mostra no cidadão: "Pedidos de Exame Ativos" com um card agendável.
    Mostra na clínica: pedido buscável por protocolo para agendar/coletar.

    Idempotente (protocolo sentinela). Best-effort (caller isola em try/except).
    """
    proto = "DEMO-EXAME-0001"
    now = _agora()
    hoje = date.today().isoformat()
    validade = (date.today() + timedelta(days=30)).isoformat()

    if conn.execute("SELECT id FROM pedidos_exame WHERE protocolo = ?", (proto,)).fetchone():
        print(f"  ·  exame-demo (ativo): '{proto}' já existe")
        return

    presc = conn.execute("SELECT id FROM prescritores WHERE cns = ?", (PRESCRITOR["cns"],)).fetchone()
    pac = conn.execute("SELECT id FROM pacientes WHERE cpf = ?", (PACIENTE["cpf"],)).fetchone()
    if not presc or not pac:
        print("  ⚠️  exame-demo (ativo): prescritor/paciente ausente — pulado")
        return

    conn.execute(
        "INSERT INTO pedidos_exame (protocolo, prescritor_id, paciente_id, status, "
        "tipo_emissao, prioridade, indicacao_clinica, data_emissao, data_validade, criado_em) "
        "VALUES (?, ?, ?, 'emitido', 'nova', 'rotina', ?, ?, ?, ?)",
        (proto, presc["id"], pac["id"],
         "Investigação de anemia ferropriva", hoje, validade, now),
    )
    pid = conn.execute("SELECT id FROM pedidos_exame WHERE protocolo = ?", (proto,)).fetchone()["id"]

    # Item: hemograma completo (pendente — aguardando agendamento/coleta)
    conn.execute(
        "INSERT INTO pedido_exame_itens (pedido_id, nome_exame, codigo_tuss, "
        "status_item, quantidade, criado_em) VALUES (?, ?, ?, 'pendente', 1, ?)",
        (pid, "Hemograma completo", "40301107", now),
    )

    # Custódia prescritor → paciente (enviar_ao_paciente=True na emissão digital)
    conn.execute(
        "INSERT INTO pedido_exame_custodia (pedido_id, item_id, de, para, transferido_em, dados_json) "
        "VALUES (?, NULL, 'prescritor', 'paciente', ?, ?)",
        (pid, now, json.dumps(
            {"de_id": PRESCRITOR["cns"], "para_id": PACIENTE["cpf"], "motivo": "emissao"},
            ensure_ascii=False)),
    )

    # Ledger: emissão + transferência de custódia
    for tipo, payload in (
        ("pedido_emitido", {"prescritor": PRESCRITOR["cns"], "prioridade": "rotina"}),
        ("custodia_transferida", {"de": "prescritor", "para": "paciente"}),
    ):
        conn.execute(
            "INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em) "
            "VALUES (?, ?, ?, ?)",
            (pid, tipo, json.dumps(payload, ensure_ascii=False), now),
        )
    print(f"  ✅ exame-demo (ativo): '{proto}' — Hemograma, emitido, em custódia do paciente")
```

---

## §4 Spec — `_garantir_laudo_demo(conn)`

**Objeto:** `DEMO-EXAME-0002` (coletado, com resultado) + `DEMO-LAUDO-0001` (liberado, ciência pendente).

```python
def _garantir_laudo_demo(conn) -> None:
    """
    DEMO-EXAME-0002 + DEMO-LAUDO-0001 — pedido com resultado + laudo liberado.

    Mostra no cidadão: "Laudos / Resultados" com um laudo pronto para dar ciência.
    (Estratégia Q2-M: laudo mockado no seed, sem exigir UI de emissão na clínica.)

    Cadeia representada (snapshot, não replay da máquina de estados):
      pedido: emitido → agendado → coletado → resultado_disponivel
      laudo:  em_producao → assinado → liberado  (custódia prestador → paciente)

    Idempotente (protocolos sentinela). Best-effort (caller isola em try/except).
    """
    proto_ped = "DEMO-EXAME-0002"
    proto_lau = "DEMO-LAUDO-0001"
    now = _agora()
    hoje = date.today().isoformat()
    validade = (date.today() + timedelta(days=30)).isoformat()

    if conn.execute("SELECT id FROM laudos WHERE protocolo = ?", (proto_lau,)).fetchone():
        print(f"  ·  laudo-demo: '{proto_lau}' já existe")
        return

    presc = conn.execute("SELECT id FROM prescritores WHERE cns = ?", (PRESCRITOR["cns"],)).fetchone()
    pac = conn.execute("SELECT id FROM pacientes WHERE cpf = ?", (PACIENTE["cpf"],)).fetchone()
    if not presc or not pac:
        print("  ⚠️  laudo-demo: prescritor/paciente ausente — pulado")
        return

    # --- Pedido (snapshot: resultado_disponivel) ---
    conn.execute(
        "INSERT INTO pedidos_exame (protocolo, prescritor_id, paciente_id, status, "
        "tipo_emissao, prioridade, indicacao_clinica, data_emissao, data_validade, criado_em) "
        "VALUES (?, ?, ?, 'resultado_disponivel', 'nova', 'rotina', ?, ?, ?, ?)",
        (proto_ped, presc["id"], pac["id"],
         "Acompanhamento de glicemia", hoje, validade, now),
    )
    pid = conn.execute("SELECT id FROM pedidos_exame WHERE protocolo = ?", (proto_ped,)).fetchone()["id"]

    # Item: glicemia de jejum (resultado_disponivel, com resultado preenchido)
    conn.execute(
        "INSERT INTO pedido_exame_itens (pedido_id, nome_exame, codigo_tuss, "
        "status_item, quantidade, resultado_resumo, resultado_em, criado_em) "
        "VALUES (?, ?, ?, 'resultado_disponivel', 1, ?, ?, ?)",
        (pid, "Glicemia de jejum", "40302055",
         "98 mg/dL (referência: 70-99 mg/dL)", now, now),
    )

    # Custódia paciente → prestador laboratório (posse no agendamento/coleta)
    conn.execute(
        "INSERT INTO pedido_exame_custodia (pedido_id, item_id, de, para, transferido_em, dados_json) "
        "VALUES (?, NULL, 'paciente', ?, ?, ?)",
        (pid, CLINICA["cnpj"], now, json.dumps(
            {"nome_prestador": CLINICA["nome"], "motivo": "agendamento_coleta"},
            ensure_ascii=False)),
    )

    # --- Laudo (snapshot: liberado) ---
    conn.execute(
        "INSERT INTO laudos (protocolo, autor_id, paciente_id, pedido_id, status, "
        "tipo_emissao, data_emissao, data_validade, criado_em) "
        "VALUES (?, ?, ?, ?, 'liberado', 'nova', ?, ?, ?)",
        (proto_lau, presc["id"], pac["id"], pid, hoje, validade, now),
    )
    lid = conn.execute("SELECT id FROM laudos WHERE protocolo = ?", (proto_lau,)).fetchone()["id"]

    # Item do laudo (conclusao alterada — glicemia no limite alto)
    conn.execute(
        "INSERT INTO laudo_itens (laudo_id, nome_exame, codigo_tuss, resultado_resumo, "
        "conclusao, valor_referencia, status_item, criado_em) "
        "VALUES (?, ?, ?, ?, 'alterado', ?, 'concluido', ?)",
        (lid, "Glicemia de jejum", "40302055",
         "98 mg/dL", "70-99 mg/dL", now),
    )

    # Custódia do laudo: prestador → paciente (na liberação)
    conn.execute(
        "INSERT INTO laudo_custodia (laudo_id, de, para, transferido_em, dados_json) "
        "VALUES (?, ?, 'paciente', ?, ?)",
        (lid, CLINICA["cnpj"], now, json.dumps(
            {"de_id": CLINICA["cnpj"], "para_id": PACIENTE["cpf"], "motivo": "liberacao"},
            ensure_ascii=False)),
    )

    # Ledger do pedido
    for tipo, payload in (
        ("pedido_emitido", {"prescritor": PRESCRITOR["cns"]}),
        ("custodia_transferida", {"de": "paciente", "para": CLINICA["cnpj"]}),
        ("resultado_registrado", {"item": "Glicemia de jejum", "conclusao": "alterado"}),
    ):
        conn.execute(
            "INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em) "
            "VALUES (?, ?, ?, ?)",
            (pid, tipo, json.dumps(payload, ensure_ascii=False), now),
        )

    # Ledger do laudo
    for tipo, payload in (
        ("laudo_criado", {"autor": PRESCRITOR["cns"]}),
        ("laudo_assinado", {}),
        ("laudo_liberado", {"prestador": CLINICA["cnpj"]}),
        ("custodia_transferida", {"de": CLINICA["cnpj"], "para": "paciente"}),
    ):
        conn.execute(
            "INSERT INTO laudo_eventos (laudo_id, tipo_evento, dados_json, criado_em) "
            "VALUES (?, ?, ?, ?)",
            (lid, tipo, json.dumps(payload, ensure_ascii=False), now),
        )

    print(f"  ✅ laudo-demo: '{proto_lau}' — Glicemia (alterado), liberado, ciência pendente")
```

---

## §5 Integração no `main()` do `seed_demo.py`

Adicionar os blocos best-effort ao final do `main()` (mesmo padrão da receita e do atestado):

```python
        # Prestador laboratório (instituição — prereq dos exames abaixo)
        try:
            _garantir_prestador(
                conn,
                org_id="clinica-demo",
                nome=CLINICA["nome"],
                tipo="laboratorio",
                cnpj=CLINICA["cnpj"],
                unidade_id="DEMO-LAB",
                unidade_nome="Laboratório Demo",
                unidade_tipo="laboratorio",
            )
            conn.commit()
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            print(f"  ⚠️  prestador-clinica: pulado por erro não-fatal ({e})")

        # Exame-demo ativo (emitido, aguardando agendamento)
        try:
            _garantir_pedido_exame_ativo(conn)
            conn.commit()
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            print(f"  ⚠️  exame-demo (ativo): pulado por erro não-fatal ({e})")

        # Laudo-demo (resultado disponível + laudo liberado, ciência pendente)
        try:
            _garantir_laudo_demo(conn)
            conn.commit()
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            print(f"  ⚠️  laudo-demo: pulado por erro não-fatal ({e})")
```

**Import:** adicionar `from datetime import timedelta` ao import de `datetime` no topo do `seed_demo.py` (hoje só importa `date, datetime, timezone`).

---

## §6 Critérios de aceite

1. Após rodar `PICSAUDE_DEMO_MODE=true python3 seed_demo.py`, as tabelas `pedidos_exame`, `pedido_exame_itens`, `laudos`, `laudo_itens`, `pedido_exame_custodia`, `laudo_custodia`, `pedido_exame_eventos`, `laudo_eventos` contêm os objetos sentinela.
2. **Idempotente:** re-executar o seed não duplica (protocolos sentinela protegem).
3. **Best-effort:** uma falha num bloco não aborta o seed já commitado (try/except + rollback próprio).
4. **Cidadão:** ao logar na demo, vê `DEMO-EXAME-0001` em "Pedidos de Exame Ativos" (com botão agendar) e `DEMO-LAUDO-0001` em "Laudos / Resultados" (com botão dar ciência).
5. **Clínica:** ao buscar `DEMO-EXAME-0001` por protocolo, vê o pedido e pode agendar/coletar.
6. **Invariante respeitado:** nenhum objeto em estado inválido (estados matcham a máquina em `states_exame.py` / `states_laudo.py`); custódia e ledger consistentes com o objeto.
7. **PG + SQLite:** seed roda em ambos (demo Render é PG; local é SQLite).

---

## §7 Fora de escopo

- **Persona demo de login da clínica** (Q1) — o seed cria a instituição `prestador`, mas **não** o `usuario`. A role de login (`dispensador` reusado vs. `prestador_exame` novo) é decisão pendente do Fabiano após parecer Fable 5.
- **Endpoints de listagem** (Gap 4: `GET /prescritor/pedidos-exame`, fila do laboratório) — ticket de backend separado (meu).
- **UI de emissão de laudo na clínica** (Gap 1) — handoff de frontend pro Kimi 3, fase seguinte (depende da estratégia Q2 final).
- **Seed de agendamento** — não necessário para o mínimo viável (o cidadão agenda `DEMO-EXAME-0001` pela UI durante a demo).

---

## §8 Não fazer

- Não criar `usuario` de login para a clínica neste ticket (Q1 pendente).
- Não fazer `UPDATE` nos objetos sentinela após criados (imutabilidade — re-executar o seed deve ser no-op, não mutação).
- Não inventar estados fora da máquina (`states_exame.py` / `states_laudo.py`).
- Não pular a custódia ou o ledger — objeto sanitário sem cadeia é órfão (AGENTS.md §2/§3).

---

## §9 Validação de colunas (verificado em 2026-08-02)

Confirmado direto nos modelos (`backend/app/models/`):

| Tabela | Colunas (insert mínimo) |
|---|---|
| `pedidos_exame` | protocolo, prescritor_id, paciente_id, status, tipo_emissao, prioridade, indicacao_clinica, data_emissao, data_validade, criado_em |
| `pedido_exame_itens` | pedido_id, nome_exame, codigo_tuss, status_item, quantidade, resultado_resumo, resultado_em, criado_em |
| `pedido_exame_custodia` | pedido_id, item_id, de, para, transferido_em, dados_json |
| `pedido_exame_eventos` | pedido_id, tipo_evento, dados_json, criado_em (instance_id nullable) |
| `laudos` | protocolo, autor_id, paciente_id, pedido_id, status, tipo_emissao, data_emissao, data_validade, criado_em |
| `laudo_itens` | laudo_id, nome_exame, codigo_tuss, resultado_resumo, conclusao, valor_referencia, status_item, criado_em |
| `laudo_custodia` | laudo_id, de, para, transferido_em, dados_json |
| `laudo_eventos` | laudo_id, tipo_evento, dados_json, criado_em |

> ⚠️ **Engenheiro deve confirmar** os nomes exatos das colunas de `laudo_custodia` e `laudo_eventos` no momento da implementação (o relatório usou os nomes análogos a `atestado_custodia`/`atestado_eventos`; validar contra o modelo real). Ajustar o INSERT se divergir.

---

*Spec redigida pelo arquiteto de backend (GLM-5.2). Rascunho na hipótese Q2-M. Aguarda martelo do Fabiano sobre Q2 + parecer Fable 5.*

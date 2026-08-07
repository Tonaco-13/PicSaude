"""
seed_demo.py
============
TICKET-6 — seed canônico do DEMO_MODE.

Cria as 3 personas usadas pelo `/demo/login` (§3.3 do ticket).
Identificadores DIFERENTES dos do seed_dev.py para evitar colisão.

  Prescritor   CNS  980001112223334   Dra. Demo Maria Souza
  Dispensador  CNPJ 99999999000191   Farmácia Demo Central
  Paciente     CPF  12345678909      João Demo da Silva

Paciente NÃO entra em `usuarios` (KISS §3.7.1 — sem refresh em demo).

T0.5 (PLANO_DEMO_CIRCULACAO.md, Flag 3 Z AI) — segunda farmácia:

  Dispensador  CNPJ 99999999000272   Farmácia Demo Norte

Sem ela, o gate da demo de circulação dá falso-verde no ramo
"re-apresentação em outra farmácia" (não há segundo CNPJ para reter o
item devolvido). DVs de ambos os CNPJ verificados (módulo 11).

Uso:
    cd backend && PICSAUDE_DEMO_MODE=true python3 seed_demo.py

NÃO executar em produção. Idempotente — seguro para re-execução.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from app.auth.jwt import hash_senha
from app.database import get_conn
from app.domain.catalogo_seed import aplicar_seed_catalogo

# ---------------------------------------------------------------------------
# Personas canônicas (§3.3 TICKET-6 — P3#8 CODEX rodada 1: IDs novos)
# ---------------------------------------------------------------------------

SENHA_DEMO = "Demo@2024"   # senha não é usada em demo (login via /demo/login)

PRESCRITOR = dict(
    cns="980001112223334",
    nome="Dra. Demo Maria Souza",
    role="prescritor",
)

DISPENSADOR = dict(
    cnpj="99999999000191",
    nome="Farmácia Demo Central",
    role="dispensador",
    org_id="farmacia-demo",
    tipo_prestador="farmacia",
    unidade_id="DEMO-001",
    unidade_nome="Unidade Central Demo",
    unidade_tipo="farmacia",
)

# T0.5 — segunda farmácia (PLANO_DEMO_CIRCULACAO.md, Flag 3 Z AI):
# habilita o ramo "re-apresentação em outra farmácia" da demo de circulação.
DISPENSADOR_NORTE = dict(
    cnpj="99999999000272",
    nome="Farmácia Demo Norte",
    role="dispensador",
    org_id="farmacia-demo-norte",
    tipo_prestador="farmacia",
    unidade_id="DEMO-002",
    unidade_nome="Unidade Norte Demo",
    unidade_tipo="farmacia",
)

PACIENTE = dict(
    cpf="12345678909",
    nome="João Demo da Silva",
)

# CLINICA — referência do lado servidor para a identidade da clínica/laboratório
# da demo (TICKET-DEMO-IDENTIDADES-FONTE-UNICA). Espelha `DEMO.clinica` em
# config.js: um estabelecimento por PAPEL (farmácia ≠ clínica). O guard-rail de
# concordância (backend/tests/unit/test_guardrail_identidades_demo.py) exige que
# este CNPJ e o de config.js sejam idênticos.
#
# TICKET-SEED-EXAMES-DEMO — passa a gerar prestador semeado (`tipo='laboratorio'`)
# + usuário de login. Q1=(a) ratificada: a clínica loga sob a role `dispensador`
# (compartilhada), com CNPJ/nome próprios — mesma mecânica do `dispensador_norte`.
# A separação de auditoria na demo é por ESTABELECIMENTO, não por role. A role
# `prestador_exame` é ticket `core` agendado (TICKET-CORE-ROLE-PRESTADOR-EXAME);
# quando entrar, é esta linha de `_garantir_usuario` que migra.
CLINICA = dict(
    cnpj="11222333000181",
    nome="Clínica Demo",
    role="dispensador",
    org_id="clinica-demo",
    tipo_prestador="laboratorio",
    unidade_id="DEMO-LAB",
    unidade_nome="Laboratório Demo",
    unidade_tipo="laboratorio",
)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Garantias idempotentes
# ---------------------------------------------------------------------------

def _garantir_catalogo_regulatorio(conn) -> dict:
    """Semeia o catálogo regulatório de substâncias (DCB) — Ticket 20.

    Dado de REFERÊNCIA (como `estabelecimentos_cnes`), não persona: nenhuma FK
    aponta para ele e o `_upsert` de `catalogo_seed.py` é idempotente por
    `dcb_normalizada` (re-execução atualiza, não duplica).

    Por que aqui e não num script à parte: `scripts/seed_catalogo_substancias.py`
    existia desde o Ticket 20 mas NINGUÉM o chamava — nem o `predeploy.sh` (Render),
    nem o `reset_demo_db.py`, nem o conftest do gate de navegador. Resultado: a
    tabela nascia vazia em todo ambiente e o motor RDC 1.000/2025
    (`catalogo_regulatorio.validar_itens_prescricao`, chamado por
    `routers/receituarios.py`) ficava CEGO — pelo princípio de cautela do catálogo
    parcial, substância ausente é silêncio, não alerta. `/catalogo/substancias`
    respondia vazio pelo mesmo motivo. Ligando no `seed_demo.main()` — o funil por
    onde passam TODOS os caminhos que semeiam a demo — vitrine e local ficam iguais.

    NÃO é best-effort: catálogo vazio é exatamente o defeito que este seed existe
    para impedir. Falha aqui aborta o seed (e o deploy, via `set -e` do predeploy),
    que é o sinal honesto — melhor que uma demo silenciosamente sem classificação
    de controle.
    """
    contagens = aplicar_seed_catalogo(conn)
    print(
        f"  ✅ catálogo regulatório: {contagens['total']} substâncias "
        f"(GLP-1 {contagens['glp1']} · antimicrobianos {contagens['antimicrobianos']} "
        f"· Portaria 344 {contagens['portaria_344']} · inativas {contagens['inativos']})"
    )
    return contagens


def _garantir_usuario(conn, identificador: str, nome: str, role: str) -> None:
    now = _agora()
    senha_hash = hash_senha(SENHA_DEMO)
    row = conn.execute(
        "SELECT id FROM usuarios WHERE identificador = ?", (identificador,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE usuarios SET senha_hash = ?, updated_at = ? WHERE identificador = ?",
            (senha_hash, now, identificador),
        )
        print(f"  ↺  usuario '{identificador}' ({role}) — atualizado")
    else:
        conn.execute(
            "INSERT INTO usuarios (role, identificador, nome, senha_hash, ativo, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, True, ?, ?)",
            (role, identificador, nome, senha_hash, now, now),
        )
        print(f"  ✅ usuario '{identificador}' ({role}) — criado")


def _garantir_prescritor(conn, cns: str, nome: str) -> None:
    now = _agora()
    row = conn.execute(
        "SELECT id FROM prescritores WHERE cns = ?", (cns,)
    ).fetchone()
    if row:
        print(f"  ·  prescritores: '{cns}' já existe")
    else:
        conn.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (?, ?, True, ?, ?)",
            (cns, nome, now, now),
        )
        print(f"  ✅ prescritores: '{cns}' — criado")


def _garantir_prestador(
    conn,
    org_id: str,
    nome: str,
    tipo: str,
    cnpj: str,
    unidade_id: str,
    unidade_nome: str,
    unidade_tipo: str,
) -> None:
    now = _agora()
    row_p = conn.execute(
        "SELECT id FROM prestadores WHERE org_id = ?", (org_id,)
    ).fetchone()
    if row_p:
        prestador_id = row_p["id"]
        print(f"  ·  prestadores: org_id='{org_id}' já existe")
    else:
        prestador_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO prestadores (id, org_id, nome, tipo, cnpj, ativo, criado_em) "
            "VALUES (?, ?, ?, ?, ?, True, ?)",
            (prestador_id, org_id, nome, tipo, cnpj, now),
        )
        print(f"  ✅ prestadores: org_id='{org_id}' ({tipo}) — criado")

    row_u = conn.execute(
        "SELECT id FROM unidades WHERE prestador_id = ? AND unidade_id = ?",
        (prestador_id, unidade_id),
    ).fetchone()
    if row_u:
        print(f"  ·  unidades: '{unidade_id}' já existe")
    else:
        conn.execute(
            "INSERT INTO unidades (id, prestador_id, unidade_id, nome, tipo, "
            "ativo, criado_em) VALUES (?, ?, ?, ?, ?, True, ?)",
            (str(uuid.uuid4()), prestador_id, unidade_id,
             unidade_nome, unidade_tipo, now),
        )
        print(f"  ✅ unidades: '{unidade_id}' ({unidade_nome}) — criada")


def _garantir_paciente(conn, cpf: str, nome: str) -> None:
    """
    Cria paciente em `pacientes`. NÃO insere em `usuarios` (§3.7.1 KISS —
    sem refresh em demo, paciente não precisa de identificador para reidratar).

    `ativo=true` aqui sinaliza "paciente cadastrado" — o que o 5A trata como
    "tem carteira digital" via inferência `paciente_existia=True` (§3.1 do
    TICKET-5A). Carteira formal fica para Dívida B-Carteira #36.
    """
    now = _agora()
    row = conn.execute(
        "SELECT id FROM pacientes WHERE cpf = ?", (cpf,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE pacientes SET ativo = True, nome = ?, updated_at = ? WHERE cpf = ?",
            (nome, now, cpf),
        )
        print(f"  ↺  pacientes: '{cpf}' — atualizado")
    else:
        conn.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (?, ?, True, ?, ?)",
            (cpf, nome, now, now),
        )
        print(f"  ✅ pacientes: '{cpf}' — criado")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _garantir_receita_na_fila(conn) -> None:
    """
    T4 — Semeia UMA prescrição já sob custódia da Farmácia Demo Central, para que
    a Fila de Dispensação exiba um card ao logar (em vez de 'fila vazia').

    Idempotente (protocolo sentinela `DEMO-FILA-0001`). Best-effort: o caller
    isola em try/except — esta função NUNCA pode quebrar o seed/predeploy.
    """
    proto = "DEMO-FILA-0001"
    now = _agora()

    if conn.execute("SELECT id FROM prescricoes WHERE protocolo = ?", (proto,)).fetchone():
        print(f"  ·  receita-demo (fila): '{proto}' já existe")
        return

    presc = conn.execute(
        "SELECT id FROM prescritores WHERE cns = ?", (PRESCRITOR["cns"],)
    ).fetchone()
    pac = conn.execute(
        "SELECT id FROM pacientes WHERE cpf = ?", (PACIENTE["cpf"],)
    ).fetchone()
    if not presc or not pac:
        print("  ⚠️  receita-demo (fila): prescritor/paciente ausente — pulada")
        return

    conn.execute(
        "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, "
        "tipo_emissao, data_emissao, created_at, updated_at) "
        "VALUES (?, ?, ?, 'em_custodia', 'nova', ?, ?, ?)",
        (proto, presc["id"], pac["id"], now, now, now),
    )
    pid = conn.execute(
        "SELECT id FROM prescricoes WHERE protocolo = ?", (proto,)
    ).fetchone()["id"]

    # unidade_quantidade derivada da posologia (vocabulário controlado,
    # domain/medicamento.py). Sem ela, o comprovante imprimiria "21" sem dizer
    # 21 de quê (TICKET-UNIDADE-QUANTIDADE-VISIVEL, Frente A). NUNCA inventar:
    # aqui a unidade é lida direto da posologia que já está no seed.
    #
    # R4 (CLAUDE.md §2a) — o CLONAZEPAM é B1 (benzodiazepínico, Notificação de
    # Receita Azul). Sem um item controlado no seed a escrituração regulatória
    # sairia sempre NULL e o grupo congelado nunca apareceria na tela da demo.
    # `classe_controle="B1"` faz o motor resolver `notificacao_receita_b` no ato
    # da dispensação; itens comuns ficam com NULL (não-controlado, vazio no relatório).
    for nome, conc, qtd, poso, unidade, classe in (
        ("LOSARTANA", "50mg", 30, "1 comprimido ao dia", "comprimido", None),
        ("AMOXICILINA", "500mg", 21, "1 cápsula de 8/8h por 7 dias", "cápsula", None),
        ("CLONAZEPAM", "2mg", 30, "1 comprimido à noite", "comprimido", "B1"),
    ):
        conn.execute(
            "INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, "
            "quantidade, unidade_quantidade, posologia, classe_controle, status_item, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?)",
            (pid, nome, conc, qtd, unidade, poso, classe, now, now),
        )

    # Custódia ATIVA da Farmácia Demo Central (= efeito da transferência
    # paciente→dispensador). É o que faz a receita aparecer em GET /dispensadores/fila.
    conn.execute(
        "INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, "
        "detentor_id, transferida_em, encerrada_em, motivo, created_at) "
        "VALUES (?, NULL, 'dispensador', ?, ?, NULL, 'seed_demo_fila_t4', ?)",
        (pid, DISPENSADOR["cnpj"], now, now),
    )
    print(f"  ✅ receita-demo (fila): '{proto}' — 3 itens (1 controlado B1) sob custódia de {DISPENSADOR['cnpj']}")


def _garantir_atestado_demo(conn) -> None:
    """
    TICKET-ATESTADO-CONFORMIDADE — semeia UM atestado já emitido, para que a demo
    mostre um documento pronto para imprimir e assinar (com local e data, registro
    do conselho e horário de comparecimento) em vez de exigir que o visitante
    preencha o formulário antes de ver qualquer coisa.

    Conselho CFM: a prescritora da demo é médica. Um atestado CFO aqui seria
    incoerente com a persona — o caminho odontológico se demonstra trocando o
    seletor de conselho na tela (o título do PDF vira ATESTADO ODONTOLÓGICO).

    Emite o objeto COMPLETO: linha em `atestados` + custódia prescritor→paciente
    + os dois eventos do ledger. Semear o documento sem a cadeia deixaria um
    objeto sanitário órfão — exatamente o que §2/§3 do CLAUDE.md proíbem.

    Idempotente (protocolo sentinela `DEMO-ATESTADO-0001`). Best-effort: o caller
    isola em try/except — esta função NUNCA pode quebrar o seed/predeploy.
    """
    proto = "DEMO-ATESTADO-0001"
    now = _agora()
    hoje = date.today().isoformat()

    if conn.execute("SELECT id FROM atestados WHERE protocolo = ?", (proto,)).fetchone():
        print(f"  ·  atestado-demo: '{proto}' já existe")
        return

    presc = conn.execute(
        "SELECT id FROM prescritores WHERE cns = ?", (PRESCRITOR["cns"],)
    ).fetchone()
    pac = conn.execute(
        "SELECT id FROM pacientes WHERE cpf = ?", (PACIENTE["cpf"],)
    ).fetchone()
    if not presc or not pac:
        print("  ⚠️  atestado-demo: prescritor/paciente ausente — pulado")
        return

    conn.execute(
        "INSERT INTO atestados (protocolo, prescritor_id, paciente_id, status, "
        "tipo_emissao, finalidade, dias_afastamento, nome_profissional, "
        "conselho, uf_registro, registro_profissional, municipio_emissao, "
        "hora_inicio, hora_fim, data_documento, data_emissao, criado_em) "
        "VALUES (?, ?, ?, 'emitido', 'nova', 'trabalhistas', 3, ?, "
        "'CFM', 'PE', '12345', 'Recife', '08:00', '09:30', ?, ?, ?)",
        (proto, presc["id"], pac["id"], PRESCRITOR["nome"], hoje, hoje, now),
    )
    aid = conn.execute(
        "SELECT id FROM atestados WHERE protocolo = ?", (proto,)
    ).fetchone()["id"]

    # Custódia prescritor → paciente: o atestado é entregue ao paciente na emissão.
    conn.execute(
        "INSERT INTO atestado_custodia (atestado_id, de, para, transferido_em, dados_json) "
        "VALUES (?, 'prescritor', 'paciente', ?, ?)",
        (aid, now, json.dumps(
            {"de_id": PRESCRITOR["cns"], "para_id": PACIENTE["cpf"], "motivo": "emissao"},
            ensure_ascii=False)),
    )
    for tipo, payload in (
        ("atestado_emitido", {"finalidade": "trabalhistas", "dias_afastamento": 3}),
        ("custodia_transferida", {"de": "prescritor", "para": "paciente"}),
    ):
        conn.execute(
            "INSERT INTO atestado_eventos (atestado_id, tipo_evento, ator_tipo, ator_id, "
            "payload, created_at) VALUES (?, ?, 'prescritor', ?, ?, ?)",
            (aid, tipo, PRESCRITOR["cns"], json.dumps(payload, ensure_ascii=False), now),
        )
    print(f"  ✅ atestado-demo: '{proto}' — CFM/CRM-PE 12345, Recife, 3 dias")


def _garantir_pedido_exame_ativo(conn) -> None:
    """
    TICKET-SEED-EXAMES-DEMO — DEMO-EXAME-0001: pedido ativo (`emitido`),
    aguardando agendamento pelo cidadão.

    Mostra no cidadão: "Pedidos de Exame Ativos" com um card agendável
    (`GET /paciente/pedidos-exame` → bucket `posse`, que é {emitido, agendado}).
    Mostra na clínica: pedido buscável por protocolo para agendar/coletar.

    Emite o objeto COMPLETO: linha em `pedidos_exame` + item + custódia
    prescritor→paciente + os dois eventos do ledger — mesmo contrato do
    atestado-demo acima. Objeto sanitário sem cadeia é órfão (CLAUDE.md §2/§3).

    Idempotente (protocolo sentinela). Best-effort: o caller isola em
    try/except — esta função NUNCA pode quebrar o seed/predeploy.
    """
    proto = "DEMO-EXAME-0001"
    now = _agora()
    hoje = date.today().isoformat()
    validade = (date.today() + timedelta(days=30)).isoformat()

    if conn.execute("SELECT id FROM pedidos_exame WHERE protocolo = ?", (proto,)).fetchone():
        print(f"  ·  exame-demo (ativo): '{proto}' já existe")
        return

    presc = conn.execute(
        "SELECT id FROM prescritores WHERE cns = ?", (PRESCRITOR["cns"],)
    ).fetchone()
    pac = conn.execute(
        "SELECT id FROM pacientes WHERE cpf = ?", (PACIENTE["cpf"],)
    ).fetchone()
    if not presc or not pac:
        print("  ⚠️  exame-demo (ativo): prescritor/paciente ausente — pulado")
        return

    # tipo_emissao='novo' (NÃO 'nova'): o vocabulário do módulo de exames é
    # {novo, correcao} — ver _TIPOS_EMISSAO_VALIDOS em routers/pedidos_exame.py.
    # Prescrição e atestado usam 'nova'; exame e laudo, 'novo'. O filtro do
    # cidadão é `tipo_emissao != 'fisico'` (auth.py), então o valor precisa ser
    # o canônico do módulo para o card não sumir da carteira.
    conn.execute(
        "INSERT INTO pedidos_exame (protocolo, prescritor_id, paciente_id, status, "
        "tipo_emissao, prioridade, indicacao_clinica, data_emissao, data_validade, criado_em) "
        "VALUES (?, ?, ?, 'emitido', 'novo', 'rotina', ?, ?, ?, ?)",
        (proto, presc["id"], pac["id"],
         "Investigação de anemia ferropriva", hoje, validade, now),
    )
    pid = conn.execute(
        "SELECT id FROM pedidos_exame WHERE protocolo = ?", (proto,)
    ).fetchone()["id"]

    # Item: hemograma completo (pendente — aguardando agendamento/coleta)
    conn.execute(
        "INSERT INTO pedido_exame_itens (pedido_id, nome_exame, codigo_tuss, "
        "status_item, quantidade, criado_em) VALUES (?, ?, ?, 'pendente', 1, ?)",
        (pid, "Hemograma completo", "40301107", now),
    )

    # Custódia prescritor → paciente: mesma forma que a emissão digital grava
    # (pedidos_exame.py:385, enviar_ao_paciente=True). O pedido permanece em
    # 'emitido' — não há estado 'transferida_paciente' no módulo de exames.
    conn.execute(
        "INSERT INTO pedido_exame_custodia (pedido_id, item_id, de, para, transferido_em, dados_json) "
        "VALUES (?, NULL, 'prescritor', 'paciente', ?, ?)",
        (pid, now, json.dumps(
            {"de_id": PRESCRITOR["cns"], "para_id": PACIENTE["cpf"], "motivo": "emissao"},
            ensure_ascii=False)),
    )

    # Ledger: emissão + transferência de custódia (EVENTOS_PEDIDO_EXAME).
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


def _garantir_laudo_demo(conn) -> None:
    """
    TICKET-SEED-EXAMES-DEMO — DEMO-EXAME-0002 + DEMO-LAUDO-0001: pedido com
    resultado + laudo liberado, aguardando ciência do cidadão.

    Mostra no cidadão: "Laudos / Resultados" com um laudo pronto para dar
    ciência (`GET /paciente/laudos` → bucket `disponiveis`, que inclui
    'liberado'). Estratégia Q2-M: laudo mockado no seed, sem exigir UI de
    emissão na clínica (Gap 1 é fase seguinte).

    Cadeia representada — SNAPSHOT dos ESTADOS, cadeia COMPLETA de custódia:
      pedido:   emitido → agendado → coletado → resultado_disponivel
      laudo:    em_producao → assinado → liberado
      custódia: prescritor → paciente → laboratório  (pedido)
                laboratório → paciente              (laudo)

    Os estados intermediários são pulados (é snapshot); os ELOS de custódia,
    não — custódia é proveniência, e objeto sem elo de origem é órfão
    (CLAUDE.md §2/§3; parecer Fable 5 §4.2 / DESPACHO-ENG-004 §2.2).

    A custódia do pedido fica no laboratório de propósito: registrar resultado
    NÃO devolve posse ao paciente em produção (pedidos_exame.py:974 não grava
    custódia) — quem volta ao cidadão é o LAUDO. Semear a volta aqui inventaria
    uma transição que o caminho clínico não faz.

    Idempotente (protocolos sentinela). Best-effort: o caller isola em
    try/except — esta função NUNCA pode quebrar o seed/predeploy.
    """
    proto_ped = "DEMO-EXAME-0002"
    proto_lau = "DEMO-LAUDO-0001"
    now = _agora()
    hoje = date.today().isoformat()
    validade = (date.today() + timedelta(days=30)).isoformat()

    if conn.execute("SELECT id FROM laudos WHERE protocolo = ?", (proto_lau,)).fetchone():
        print(f"  ·  laudo-demo: '{proto_lau}' já existe")
        return

    presc = conn.execute(
        "SELECT id FROM prescritores WHERE cns = ?", (PRESCRITOR["cns"],)
    ).fetchone()
    pac = conn.execute(
        "SELECT id FROM pacientes WHERE cpf = ?", (PACIENTE["cpf"],)
    ).fetchone()
    if not presc or not pac:
        print("  ⚠️  laudo-demo: prescritor/paciente ausente — pulado")
        return

    # --- Pedido (snapshot: resultado_disponivel) ---
    conn.execute(
        "INSERT INTO pedidos_exame (protocolo, prescritor_id, paciente_id, status, "
        "tipo_emissao, prioridade, indicacao_clinica, data_emissao, data_validade, criado_em) "
        "VALUES (?, ?, ?, 'resultado_disponivel', 'novo', 'rotina', ?, ?, ?, ?)",
        (proto_ped, presc["id"], pac["id"],
         "Acompanhamento de glicemia", hoje, validade, now),
    )
    pid = conn.execute(
        "SELECT id FROM pedidos_exame WHERE protocolo = ?", (proto_ped,)
    ).fetchone()["id"]

    # Item: glicemia de jejum (resultado_disponivel, com resultado preenchido)
    conn.execute(
        "INSERT INTO pedido_exame_itens (pedido_id, nome_exame, codigo_tuss, "
        "status_item, quantidade, resultado_resumo, resultado_em, criado_em) "
        "VALUES (?, ?, ?, 'resultado_disponivel', 1, ?, ?, ?)",
        (pid, "Glicemia de jejum", "40302055",
         "98 mg/dL (referência: 70-99 mg/dL)", now, now),
    )

    # Elo de origem: prescritor → paciente (na emissão do pedido).
    # DEMO-EXAME-0001 semeia este par; o 0002 precisa também — a cadeia de
    # custódia é proveniência desde a emissão, não snapshot intermediário
    # (parecer Fable 5 §4.2, ratificado). Objeto sem elo de origem é órfão.
    # "Snapshot" justifica pular ESTADOS da máquina, nunca ELOS de custódia.
    conn.execute(
        "INSERT INTO pedido_exame_custodia (pedido_id, item_id, de, para, transferido_em, dados_json) "
        "VALUES (?, NULL, 'prescritor', 'paciente', ?, ?)",
        (pid, now, json.dumps(
            {"de_id": PRESCRITOR["cns"], "para_id": PACIENTE["cpf"], "motivo": "emissao"},
            ensure_ascii=False)),
    )

    # Custódia paciente → laboratório (posse no agendamento/coleta). Mesma forma
    # do caminho clínico: `para` recebe o CNPJ do prestador (pedidos_exame.py:766).
    conn.execute(
        "INSERT INTO pedido_exame_custodia (pedido_id, item_id, de, para, transferido_em, dados_json) "
        "VALUES (?, NULL, 'paciente', ?, ?, ?)",
        (pid, CLINICA["cnpj"], now, json.dumps(
            {"nome_prestador": CLINICA["nome"], "motivo": "agendamento_coleta"},
            ensure_ascii=False)),
    )

    # --- Laudo (snapshot: liberado) ---
    # autor_id é NOT NULL na prática do listador: `GET /paciente/laudos` faz
    # JOIN prescritores ON pr.id = l.autor_id (auth.py:533) — laudo sem autor
    # sumiria da tela do cidadão. A prescritora da demo assina como responsável
    # técnica (o modelo usa `prescritores` como registro genérico de
    # profissional de saúde — ver docstring de models/laudo.py).
    conn.execute(
        "INSERT INTO laudos (protocolo, autor_id, paciente_id, pedido_id, status, "
        "tipo_emissao, data_emissao, data_validade, criado_em) "
        "VALUES (?, ?, ?, ?, 'liberado', 'novo', ?, ?, ?)",
        (proto_lau, presc["id"], pac["id"], pid, hoje, validade, now),
    )
    lid = conn.execute(
        "SELECT id FROM laudos WHERE protocolo = ?", (proto_lau,)
    ).fetchone()["id"]

    # Item do laudo — conclusao='alterado' (∈ _CONCLUSOES_VALIDAS, laudos.py:73)
    conn.execute(
        "INSERT INTO laudo_itens (laudo_id, nome_exame, codigo_tuss, resultado_resumo, "
        "conclusao, valor_referencia, status_item, criado_em) "
        "VALUES (?, ?, ?, ?, 'alterado', ?, 'concluido', ?)",
        (lid, "Glicemia de jejum", "40302055",
         "98 mg/dL", "70-99 mg/dL", now),
    )

    # Custódia do laudo: prestador → paciente (efeito da liberação, laudos.py:684).
    # A custódia do LAUDO começa no prestador — diferente de prescrição e exame.
    conn.execute(
        "INSERT INTO laudo_custodia (laudo_id, item_id, de, para, transferido_em, dados_json) "
        "VALUES (?, NULL, ?, 'paciente', ?, ?)",
        (lid, CLINICA["cnpj"], now, json.dumps(
            {"de_id": CLINICA["cnpj"], "para_id": PACIENTE["cpf"], "motivo": "liberacao"},
            ensure_ascii=False)),
    )

    # Ledger do pedido (EVENTOS_PEDIDO_EXAME). O `custodia_transferida` de
    # origem (prescritor→paciente) vem ANTES do paciente→laboratório: a ordem
    # dos eventos é a própria cadeia de proveniência.
    for tipo, payload in (
        ("pedido_emitido", {"prescritor": PRESCRITOR["cns"]}),
        ("custodia_transferida", {"de": "prescritor", "para": "paciente"}),
        ("custodia_transferida", {"de": "paciente", "para": CLINICA["cnpj"]}),
        ("resultado_registrado", {"item": "Glicemia de jejum", "conclusao": "alterado"}),
    ):
        conn.execute(
            "INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em) "
            "VALUES (?, ?, ?, ?)",
            (pid, tipo, json.dumps(payload, ensure_ascii=False), now),
        )

    # Ledger do laudo (EVENTOS_LAUDO)
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


def main() -> None:
    if os.getenv("PICSAUDE_ENV") == "prod":
        print("❌ ABORTANDO: seed_demo não pode rodar em PICSAUDE_ENV=prod.")
        sys.exit(1)

    # TICKET-6.1 P2#5: sem a flag, _resolve_sqlite_db_path() devolve DB_PATH
    # (dev/prod). Quem rodar `python3 seed_demo.py` sem PICSAUDE_DEMO_MODE=true
    # acaba inserindo as personas demo no banco errado.
    demo = os.getenv("PICSAUDE_DEMO_MODE", "").lower()
    if demo != "true":
        print(
            "❌ ABORTANDO: PICSAUDE_DEMO_MODE precisa ser 'true' para semear o DB demo.\n"
            "   Sem a flag, get_conn() roteia para o DB de dev/prod (TICKET-6.1 P2#5)."
        )
        sys.exit(1)

    print("\n=== seed_demo.py — TICKET-6 ===")
    print(f"DB:  {os.getenv('PIX_SAUDE_DEMO_DB', '(padrão data/pix_saude_demo.db)')}")
    print(f"ENV: {os.getenv('PICSAUDE_ENV', '(não setado)')}")
    print(f"DEMO_MODE: {os.getenv('PICSAUDE_DEMO_MODE', '(não setado)')}\n")

    conn = get_conn()
    try:
        # Schema cinturão: garante que tabelas opcionais (CNES) existam vazias
        # para que endpoints de contexto institucional não quebrem em demo.
        # Defense in depth: o fallback em login.py:311 já pega o cenário, mas
        # o CREATE garante schema correto para novos bancos demo.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS estabelecimentos_cnes (
                CO_CNES      TEXT,
                NU_CNPJ      TEXT,
                TP_UNIDADE   TEXT,
                NO_FANTASIA  TEXT,
                CO_MUNICIPIO TEXT
            )
        """)
        # T0.5b — semeia o CNES das farmácias demo (TP_UNIDADE '04' ∈ _TP_FARMACIA)
        # para que /auth/me/institucional devolva cnes_verificado=true. Sem isto, a
        # demo cai no modal de confirmação manual de CNES a cada dispensação.
        # Idempotente (seed re-executável). Check do Jules: estabelecimentos_cnes é
        # dado de REFERÊNCIA (sem FK) e cnes_verificado é flag COMPUTADO read-only
        # (não persistido) — semear a linha não cria estado órfão em tabela adjacente.
        for _cnpj, _nome, _cnes in (
            (DISPENSADOR["cnpj"],       DISPENSADOR["nome"],       "9900001"),
            (DISPENSADOR_NORTE["cnpj"], DISPENSADOR_NORTE["nome"], "9900002"),
        ):
            conn.execute("DELETE FROM estabelecimentos_cnes WHERE NU_CNPJ = ?", (_cnpj,))
            conn.execute(
                "INSERT INTO estabelecimentos_cnes "
                "  (CO_CNES, NU_CNPJ, TP_UNIDADE, NO_FANTASIA, CO_MUNICIPIO) "
                # estabelecimentos_cnes NÃO tem coluna `id`, e database.py anexa
                # `RETURNING id` a todo INSERT sem RETURNING (emula lastrowid na PG) —
                # o que quebrava o deploy (#84). Um RETURNING de coluna existente
                # suprime a injeção; funciona na PG e no SQLite (3.35+).
                "VALUES (?, ?, '04', ?, '261160') RETURNING NU_CNPJ",
                (_cnes, _cnpj, _nome),
            )
        # Tabelas de validação do prescritor (vazias): garantem que a consulta
        # CNES (cnes_prescritor.py) rode e retorne `nao_encontrado` em vez de
        # falhar por tabela ausente. Colunas = as referenciadas pela query.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profissionais_cnes (
                CO_PROFISSIONAL_SUS TEXT,
                CO_CNS              TEXT,
                NO_PROFISSIONAL     TEXT,
                CO_CPF              TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relacao_prof_estab (
                CO_PROFISSIONAL_SUS TEXT,
                CO_UNIDADE          TEXT,
                CO_CBO              TEXT,
                CO_CONSELHO_CLASSE  TEXT,
                NU_REGISTRO         TEXT,
                SG_UF_CRM           TEXT
            )
        """)

        # Catálogo regulatório (DCB) — dado de referência do motor RDC 1.000/2025.
        # Antes das personas porque não depende de nenhuma delas; commit próprio
        # para que a jornada do controlado (B1 CLONAZEPAM) já esteja servida
        # mesmo que um bloco best-effort adiante falhe.
        _garantir_catalogo_regulatorio(conn)
        conn.commit()

        # Prescritor
        _garantir_usuario(conn, PRESCRITOR["cns"], PRESCRITOR["nome"], PRESCRITOR["role"])
        _garantir_prescritor(conn, PRESCRITOR["cns"], PRESCRITOR["nome"])

        # Dispensador
        _garantir_usuario(conn, DISPENSADOR["cnpj"], DISPENSADOR["nome"], DISPENSADOR["role"])
        _garantir_prestador(
            conn,
            org_id=DISPENSADOR["org_id"],
            nome=DISPENSADOR["nome"],
            tipo=DISPENSADOR["tipo_prestador"],
            cnpj=DISPENSADOR["cnpj"],
            unidade_id=DISPENSADOR["unidade_id"],
            unidade_nome=DISPENSADOR["unidade_nome"],
            unidade_tipo=DISPENSADOR["unidade_tipo"],
        )

        # Dispensador — segunda farmácia (T0.5)
        _garantir_usuario(conn, DISPENSADOR_NORTE["cnpj"], DISPENSADOR_NORTE["nome"], DISPENSADOR_NORTE["role"])
        _garantir_prestador(
            conn,
            org_id=DISPENSADOR_NORTE["org_id"],
            nome=DISPENSADOR_NORTE["nome"],
            tipo=DISPENSADOR_NORTE["tipo_prestador"],
            cnpj=DISPENSADOR_NORTE["cnpj"],
            unidade_id=DISPENSADOR_NORTE["unidade_id"],
            unidade_nome=DISPENSADOR_NORTE["unidade_nome"],
            unidade_tipo=DISPENSADOR_NORTE["unidade_tipo"],
        )

        # Paciente (sem `usuarios` — KISS §3.7.1)
        _garantir_paciente(conn, PACIENTE["cpf"], PACIENTE["nome"])

        conn.commit()
        print("\n✅ seed_demo.py concluído com sucesso.")

        # T4 — receita-demo na custódia da farmácia (popular a Fila de Dispensação).
        # Best-effort: NUNCA pode quebrar o seed/predeploy — isolada em try/except
        # com rollback próprio (uma falha aqui não aborta o seed já commitado acima).
        try:
            _garantir_receita_na_fila(conn)
            conn.commit()
        except Exception as e:  # noqa: BLE001 — best-effort intencional
            conn.rollback()
            print(f"  ⚠️  receita-demo (fila): pulada por erro não-fatal ({e})")

        # Atestado-demo — mesmo contrato best-effort da receita acima.
        try:
            _garantir_atestado_demo(conn)
            conn.commit()
        except Exception as e:  # noqa: BLE001 — best-effort intencional
            conn.rollback()
            print(f"  ⚠️  atestado-demo: pulado por erro não-fatal ({e})")

        # Clínica/laboratório — instituição + login (prereq dos exames abaixo).
        # Q1=(a): role `dispensador` com CNPJ próprio; a separação de auditoria
        # na demo é por estabelecimento. Persona demo em /demo/login
        # (_PERSONAS["clinica"] em demo.py, ADENDO-SEED-EXAMES-PERSONA-CLINICA);
        # fora da demo, `clinica.html` autentica por CNPJ+senha no /auth/login.
        try:
            _garantir_usuario(conn, CLINICA["cnpj"], CLINICA["nome"], CLINICA["role"])
            _garantir_prestador(
                conn,
                org_id=CLINICA["org_id"],
                nome=CLINICA["nome"],
                tipo=CLINICA["tipo_prestador"],
                cnpj=CLINICA["cnpj"],
                unidade_id=CLINICA["unidade_id"],
                unidade_nome=CLINICA["unidade_nome"],
                unidade_tipo=CLINICA["unidade_tipo"],
            )
            conn.commit()
        except Exception as e:  # noqa: BLE001 — best-effort intencional
            conn.rollback()
            print(f"  ⚠️  prestador-clinica: pulado por erro não-fatal ({e})")

        # Exame-demo ativo (emitido, aguardando agendamento pelo cidadão).
        try:
            _garantir_pedido_exame_ativo(conn)
            conn.commit()
        except Exception as e:  # noqa: BLE001 — best-effort intencional
            conn.rollback()
            print(f"  ⚠️  exame-demo (ativo): pulado por erro não-fatal ({e})")

        # Laudo-demo (resultado disponível + laudo liberado, ciência pendente).
        try:
            _garantir_laudo_demo(conn)
            conn.commit()
        except Exception as e:  # noqa: BLE001 — best-effort intencional
            conn.rollback()
            print(f"  ⚠️  laudo-demo: pulado por erro não-fatal ({e})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

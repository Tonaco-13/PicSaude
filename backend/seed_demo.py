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
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from app.auth.jwt import hash_senha
from app.database import get_conn

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


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Garantias idempotentes
# ---------------------------------------------------------------------------

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
    finally:
        conn.close()


if __name__ == "__main__":
    main()

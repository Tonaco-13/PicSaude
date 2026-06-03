"""Guard-rail técnico — sem exportação em massa de dados individualizados.

Materializa o mecanismo §1 da DATA-PROTECTION.md ("sem endpoints de dump nem
exportação em lote de dados individualizados") e o não-objetivo nº 2 do ETHICS.md
(sem revenda por empresas/detentores) como check executável.

Estratégia (baixo falso-positivo): inspeciona as rotas REGISTRADAS no app e
sinaliza as que cheiram a exportação/dump OU que são listagem-total sobre uma raiz
clínica, **menos** uma allowlist do que já foi revisado. Rota nova suspeita falha o
build, forçando revisão consciente: é dump de dado individualizado? Se for relatório
anonimizado/agregado legítimo, entra na allowlist com justificativa.

Limite honesto: não bloqueia fork malicioso (nada bloqueia código aberto). Impede
introdução **acidental ou silenciosa** de superfície de egressão e torna qualquer
adição conspícua. O ponto de controle real da revenda por empresa é o **G4A**
(camada de publicação de eventos), que ainda não existe.
"""
from __future__ import annotations

# GET cujo path/nome casa com um destes = cheiro de exportação em lote.
_SINAIS_EXPORT = (
    "export", "dump", "bulk", "massa", "csv", "xlsx",
    "planilha", "download", "/todos", "/todas", "relatorio", "eventos",
)

# GET exatamente sobre uma destas raízes = listagem-total de dado clínico.
_RAIZES_CLINICAS = frozenset({
    "/prescricoes", "/pedidos-exame", "/laudos", "/agendamentos",
    "/dispensacoes", "/pacientes", "/prescritores", "/receituarios",
    "/hospitalares",
})

# Superfícies de egressão JÁ REVISADAS (method, path). Acrescentar aqui é decisão
# consciente de governança (DATA-PROTECTION.md §1). Cada entrada justificada:
_ROTAS_EXPORT_PERMITIDAS = frozenset({
    ("GET", "/eventos"),                      # G4B: polling autenticado, escopado por org_id
    ("GET", "/relatorios/dispensacoes.csv"),  # relatório anonimizado/agregado
    ("GET", "/relatorios/dispensacoes.pdf"),  # relatório anonimizado/agregado
    ("GET", "/pacientes"),                    # BLOQUEIO intencional 403 — não há listagem
                                              # de pacientes (pacientes.py:69-72). Seguro.
})


def _suspeita(method: str, path: str, nome: str) -> bool:
    if "GET" not in method:                    # exportação é leitura; ack/POST não conta
        return False
    alvo = (path + " " + nome).lower()
    if any(s in alvo for s in _SINAIS_EXPORT):
        return True
    if path in _RAIZES_CLINICAS:               # listagem-total de recurso clínico
        return True
    return False


def _rotas_suspeitas(rotas, allowlist=_ROTAS_EXPORT_PERMITIDAS) -> set:
    """rotas: iterável de (methods, path, nome) — methods é string ("GET,HEAD").
    Retorna o set de (GET, path) suspeitos e fora da allowlist."""
    out = set()
    for methods, path, nome in rotas:
        if _suspeita(methods, path, nome) and ("GET", path) not in allowlist:
            out.add(("GET", path))
    return out


def _coletar_rotas_do_app():
    from app.main import app
    rotas = []
    for r in app.routes:
        path = getattr(r, "path", "")
        methods = ",".join(sorted(getattr(r, "methods", []) or []))
        nome = getattr(getattr(r, "endpoint", None), "__name__", "")
        rotas.append((methods, path, nome))
    return rotas


# ===========================================================================
# Guard contra o app real
# ===========================================================================

def test_sem_endpoint_de_exportacao_em_massa_nao_revisado():
    suspeitas = _rotas_suspeitas(_coletar_rotas_do_app())
    assert not suspeitas, (
        "Superfície de exportação NÃO revisada — DATA-PROTECTION.md §1 proíbe dump/"
        "exportação em lote de dados individualizados; ETHICS.md §2 proíbe revenda.\n"
        "Se for relatório anonimizado/agregado legítimo, adicione a "
        "_ROTAS_EXPORT_PERMITIDAS com justificativa.\nRotas:\n  " +
        "\n  ".join(f"{m} {p}" for m, p in sorted(suspeitas))
    )


def test_allowlist_sem_entrada_morta():
    """Cada rota da allowlist deve existir no app — evita allowlist apodrecida
    mascarando uma rota arriscada re-adicionada com o mesmo path."""
    presentes = set()
    for methods, path, _ in _coletar_rotas_do_app():
        for m in methods.split(","):
            presentes.add((m, path))
    mortas = sorted(e for e in _ROTAS_EXPORT_PERMITIDAS if e not in presentes)
    assert not mortas, f"Entradas mortas na allowlist (rota removida?): {mortas}"


# ===========================================================================
# Prova de que a tripwire dispara — sem mexer no app real
# ===========================================================================

def test_tripwire_dispara_em_rota_suspeita_sintetica():
    fake = [
        ("GET,HEAD", "/pacientes/export-tudo", "dump_pacientes"),  # sinal 'export'
        ("GET,HEAD", "/pacientes", "listar_todos"),                # raiz clínica
        ("GET,HEAD", "/prescricoes/{protocolo}", "get_um"),        # OK: item único
        ("POST", "/eventos/{id}/ack", "ack"),                      # OK: não é GET
    ]
    flag = _rotas_suspeitas(fake, allowlist=frozenset())
    assert ("GET", "/pacientes/export-tudo") in flag
    assert ("GET", "/pacientes") in flag
    assert ("GET", "/prescricoes/{protocolo}") not in flag
    assert ("POST", "/eventos/{id}/ack") not in flag
    # E a allowlist de verdade silencia uma entrada conhecida:
    conhecida = [("GET,HEAD", "/eventos", "listar_eventos")]
    assert _rotas_suspeitas(conhecida) == set()

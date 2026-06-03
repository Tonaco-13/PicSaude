"""Guard-rail ético — PicSaúde nunca monetiza dado do paciente.

Tripwire de CI: falha o build se um token de monetização aparecer no código
clínico (`backend/app/`) ou no frontend (`*.html` na raiz). Materializa o
não-objetivo nº 1 do `ETHICS.md` como check executável.

Limite honesto: NÃO bloqueia um fork malicioso (nada bloqueia código aberto).
O que faz é impedir introdução **acidental ou silenciosa** e tornar qualquer
tentativa um ato conspícuo e revisável.

Escopo do scan:
  - `backend/app/**/*.py`  (código clínico + schema ORM)
  - `*.html` na raiz       (frontend do demo)
NÃO escaneia `docs/` (discutem conceitos, inclusive o que NÃO fazer) nem este teste.

Os tokens são específicos para não colidir com vocabulário legítimo — ex.: o evento
de ledger `pagamento_nao_concluido` NÃO é capturado (proibimos `pagamento_paciente`,
não `pagamento` cru).
"""
from __future__ import annotations

from pathlib import Path

# Substrings (lowercase) de monetização de dado do paciente. Verificadas como
# ausentes no código em 2026-05-31. Acrescentar token aqui = endurecer a trava.
_TOKENS_PROIBIDOS = (
    "monetiz",             # monetizar, monetização
    "pagamento_paciente",
    "paciente_paga",
    "pagar_paciente",
    "paga_ao_paciente",
    "venda_dado",
    "vender_dado",
    "vender dados",
    "venda de dados",
    "comercializ",         # comercializar dados
    "data_broker",
    "corretagem",
    "preco_dado",
    "marketplace",         # ausente em app/ e *.html (menção benigna só em docs/)
)

_RAIZ = Path(__file__).resolve().parents[2]      # backend/tests/ -> raiz do repo
_APP = _RAIZ / "backend" / "app"


def _arquivos_para_escanear() -> list[Path]:
    arquivos = sorted(_APP.rglob("*.py"))
    arquivos += sorted(_RAIZ.glob("*.html"))
    return arquivos


def test_sem_token_de_monetizacao_no_codigo_clinico_e_frontend():
    """Nenhum token de monetização de dado do paciente no código/frontend.

    Ver ETHICS.md (não-objetivo nº 1). O caminho aprovado é soberania do
    paciente via outorga de acesso auditável — nunca venda do dado.
    """
    ofensas: list[str] = []
    for arq in _arquivos_para_escanear():
        try:
            texto = arq.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        for tok in _TOKENS_PROIBIDOS:
            if tok in texto:
                ofensas.append(f"{arq.relative_to(_RAIZ)}: token proibido '{tok}'")

    assert not ofensas, (
        "GUARD-RAIL ÉTICO VIOLADO — monetização de dado do paciente é NÃO-OBJETIVO "
        "permanente do PicSaúde (ver ETHICS.md §1). O caminho aprovado é outorga de "
        "acesso auditável, nunca venda. Ocorrências:\n  " + "\n  ".join(ofensas)
    )


def test_guardrail_realmente_escaneia_algo():
    """Sanidade: o scan não está vazio (senão a tripwire seria falso-verde)."""
    arquivos = _arquivos_para_escanear()
    assert len(arquivos) > 10, (
        f"Esperava escanear o código de app/ + frontend; achei só {len(arquivos)} "
        "arquivos — caminho de scan provavelmente quebrou."
    )

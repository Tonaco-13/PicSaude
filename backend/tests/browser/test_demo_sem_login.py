"""
tests/browser/test_demo_sem_login.py — KIMI3-002 §1 (handoff §11: "demo sem login").

O QUE PROVA
-----------
Decisão ratificada do dono (2026-08-02): "sem login" = SEM DIGITAR SENHA, não
sem escolha. Dois comportamentos andam juntos:

1. Acesso DIRETO por URL a `prescritor.html` / `cidadao.html` autentica sozinho
   (_autoLoginDemo, mesmo padrão do dispensador) — o usuário não trava numa
   tela de senha/OTP. Antes deste item, só o dispensador tinha esse caminho.
2. O portal (`entrar.html` desde o flip da abertura, 30/08 — era
   `index.html`) MANTÉM o seletor de personas de 1 clique.

FRONTEIRA (handoff §11 — não regredir)
--------------------------------------
RBAC/auth não é tocado: o JWT vem de POST /demo/login (JWT real, mesmo
JWT_SECRET) e o require_role não sabe que é demo. Bypass de require_role em
DEMO_MODE é PROIBIDO (classe core). Este teste não usa sessão plantada —
propositalmente: o sessionStorage vazio é o cenário do acesso direto.
"""
from __future__ import annotations

from playwright.sync_api import expect

_TIMEOUT_MS = 15_000

# Personas canônicas do seed de demo (demo.py::_PERSONAS / seed_demo.py).
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_NOME_PACIENTE = "João Demo da Silva"


def _sem_erros(erros: list[str], tela: str) -> None:
    assert not erros, f"Erros de console/JS em {tela}:\n" + "\n".join(f"  - {e}" for e in erros)


def test_prescritor_direto_auto_login(page, app_demo, erros_de_console):
    """URL direta do prescritor, SEM sessão plantada → dashboard, sem tela de senha."""
    page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")

    # 🎯 Entra no dashboard autenticado como a persona demo do prescritor…
    expect(page.locator("#tela-dashboard")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#prof-nome")).to_contain_text(_NOME_PRESCRITOR)
    # 🎯 …e a tela de acesso (CNS + senha) NÃO fica no caminho.
    expect(page.locator("#tela-acesso")).to_be_hidden()
    _sem_erros(erros_de_console, "prescritor.html (auto-login demo)")


def test_cidadao_direto_auto_login(page, app_demo, erros_de_console):
    """URL direta do cidadão, SEM sessão plantada → carteira, sem CPF/OTP."""
    page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")

    # 🎯 Abre a carteira autenticado como a persona demo do paciente…
    expect(page.locator("#tela-carteira")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#tela-carteira")).to_contain_text(_NOME_PACIENTE)
    # 🎯 …e as telas de CPF e de validação (OTP) NÃO ficam no caminho.
    expect(page.locator("#tela-acesso")).to_be_hidden()
    expect(page.locator("#tela-validacao")).to_be_hidden()
    _sem_erros(erros_de_console, "cidadao.html (auto-login demo)")


def test_portal_mantem_seletor_de_personas(page, app_demo, erros_de_console):
    """Decisão do dono: o portal NÃO perde o seletor — 'sem login' é 1 clique."""
    page.goto(f"{app_demo}/entrar.html", wait_until="networkidle")

    # 🎯 Os 3 cards de persona continuam no portal (seletor de 1 clique).
    expect(page.locator('a.card[href="prescritor.html"]')).to_be_visible()
    expect(page.locator('a.card[href="dispensador.html"]')).to_be_visible()
    expect(page.locator('a.card[href="cidadao.html"]')).to_be_visible()
    _sem_erros(erros_de_console, "entrar.html (seletor de personas)")

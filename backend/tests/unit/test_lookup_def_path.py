"""Unit — resolução do caminho da base DEF (medicamentos) em empacotamento.

Regressão do bug de produção: a CSV `data/def_medicamentos.csv` não ia na imagem
Docker, então a base DEF carregava vazia (o DEF "não carregava" na vitrine). O fix
introduz o override `PICSAUDE_DEF_CSV` para apontar a CSV num caminho estável.
"""
from __future__ import annotations

import os

from app.ai import lookup_def


def test_override_por_env_tem_prioridade(monkeypatch):
    monkeypatch.setenv("PICSAUDE_DEF_CSV", "/caminho/empacotado/def.csv")
    assert lookup_def._resolver_base_csv() == "/caminho/empacotado/def.csv"


def test_fallback_layout_dev_sem_env(monkeypatch):
    monkeypatch.delenv("PICSAUDE_DEF_CSV", raising=False)
    caminho = lookup_def._resolver_base_csv()
    assert caminho.endswith(os.path.join("data", "def_medicamentos.csv"))


def test_base_carrega_no_layout_dev():
    """No repo (dev), a CSV existe e a base não fica vazia — espelha o que a imagem
    precisa entregar (na imagem, via PICSAUDE_DEF_CSV)."""
    assert lookup_def.tamanho_base() > 0

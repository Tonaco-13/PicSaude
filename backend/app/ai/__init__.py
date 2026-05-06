"""
app/ai
======
Módulo de IA farmacêutica do PicSaúde — v1 (lookup + regras, stateless).

PRINCÍPIOS
----------
  Não generativa   — nada de texto inventado; apenas lookup e regras explícitas.
  Determinística   — mesmo input → mesmo output, sempre.
  Explicável       — todo resultado traz match_tipo, score, fonte, versao_base.
  Não bloqueante   — sugere e alerta; nunca impede o fluxo clínico.
  Stateless        — sem estado interno persistente; sem escrita em DB.

MÓDULOS
-------
  normalizacao_medicamento  ← normalização textual (lowercase, acentos, abreviações…)
  lookup_def                ← busca na base local def_medicamentos.csv
  regras_farmaceuticas      ← regras determinísticas (forma→unidade, incoerências)
  ia_farmaceutica           ← função principal sugerir_medicamento()

ROTAS (ver routers/ia.py)
-------------------------
  POST /ia/medicamentos/sugerir   ← endpoint consultivo (sem gravação em DB)
"""

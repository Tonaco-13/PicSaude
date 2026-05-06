"""
ai_documental — IA Documental v1 (Ticket 35)
============================================
Módulo de validação estrutural de documentos clínicos.

Princípio central:
  A IA não escreve o documento — ela garante que o documento esteja correto.

Componentes:
  templates_atestado.py  — template CFM-aligned + renderização
  regras_atestado.py     — validação, alertas de texto vago, sugestões de redação,
                           coerência CID ↔ texto clínico
  ia_documental.py       — função principal validar_atestado()

Escopo atual: atestado médico.
Preparado para: declaração, relatório, laudo (não implementados neste ticket).
"""
from app.ai_documental.ia_documental import validar_atestado

__all__ = ["validar_atestado"]

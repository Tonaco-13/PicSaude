"""
texto_atestado.py
=================
Corpo do atestado — FONTE ÚNICA do texto (TICKET-ATESTADO-RASCUNHO-ESPELHO).

O PROBLEMA QUE ESTE MÓDULO FECHA
--------------------------------
Existiam DOIS construtores do texto do atestado, e eles divergiam:

  - `ai_documental/templates_atestado.py` montava o RASCUNHO ("para fins X…
    necessita de afastamento", data ISO, sem município, registro nu, ignorando
    o conselho emissor);
  - `domain/pdf_atestado.py` montava o DOCUMENTO OFICIAL ("para os devidos fins
    de X… esteve sob cuidados médicos", data BR, "Recife, 19/07/2026",
    "CRM-PE 12345").

O profissional conferia um texto na tela e assinava outro no PDF. O rascunho não
era um documento falso — era um **falso espelho**, que é a forma sutil do mesmo
defeito. Um espelho que mostra outra pessoa é pior que nenhum espelho: o
profissional confia nele.

A partir daqui há UM construtor. O PDF e o rascunho consomem esta função e
diferem apenas em **como renderizam a ênfase** — negrito `<b>` no ReportLab,
`<strong>` no HTML —, nunca em como montam a frase.

POR QUE TRECHOS, E NÃO STRING COM MARKUP
----------------------------------------
`<b>` é markup do ReportLab, não do domínio. Se esta função devolvesse a frase
já com `<b>`, o rascunho teria de desmontá-la com regex para remontar em
`<strong>` — e "remontar a frase" é exatamente o que reabre a divergência. Por
isso o retorno é estrutural: parágrafos de trechos, cada trecho sabendo se é
enfático. Quem renderiza escolhe o markup; ninguém reescreve o texto.

REDAÇÃO
-------
Ao unificar, adotou-se **"para fins {finalidade}"** — a redação que estava no
rascunho. A do documento oficial ("para os devidos fins de trabalhistas") é
agramatical: a finalidade já entra flexionada como adjetivo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Estrutura do texto — conteúdo e ênfase, sem markup
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Trecho:
    """Pedaço contíguo do texto, com ou sem ênfase.

    `enfase=True` é o que o PDF imprime em negrito e o rascunho envolve em
    `<strong>`. O domínio diz "isto é enfático"; não diz com que tag.
    """

    texto: str
    enfase: bool = False


@dataclass(frozen=True)
class Paragrafo:
    """Parágrafo do corpo do atestado, como sequência de trechos."""

    trechos: tuple[Trecho, ...]

    def texto_puro(self) -> str:
        """Conteúdo sem nenhuma marcação — é ESTE valor que o espelho compara."""
        return "".join(t.texto for t in self.trechos)

    def para_reportlab(self) -> str:
        """Renderização para `reportlab.platypus.Paragraph` (ênfase = `<b>`)."""
        return "".join(
            f"<b>{_escapar(t.texto)}</b>" if t.enfase else _escapar(t.texto)
            for t in self.trechos
        )

    def para_html(self) -> str:
        """Renderização para a tela do rascunho (ênfase = `<strong>`).

        O escape acontece AQUI, no domínio, porque é aqui que se sabe o que é
        markup e o que é conteúdo digitado pelo profissional. A tela recebe HTML
        já seguro e o insere direto — não pode escapar de novo, ou as tags
        apareceriam literais.
        """
        return "".join(
            f"<strong>{_escapar(t.texto)}</strong>" if t.enfase else _escapar(t.texto)
            for t in self.trechos
        )


def _escapar(texto: str) -> str:
    """Escapa os três caracteres que quebram tanto o mini-XML do ReportLab
    quanto o HTML da tela. A ordem importa: `&` primeiro."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def texto_puro(paragrafos: tuple[Paragrafo, ...]) -> str:
    """Corpo inteiro sem marcação, parágrafos separados por linha em branco."""
    return "\n\n".join(p.texto_puro() for p in paragrafos)


# ---------------------------------------------------------------------------
# Formatadores compartilhados
# ---------------------------------------------------------------------------

def formatar_data_br(iso: Optional[str]) -> str:
    """Data ISO → dd/mm/aaaa. Entrada inválida volta como veio (nunca levanta:
    um atestado não deve falhar de renderizar por causa de um campo de data)."""
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(iso)


def periodo_horario(hora_inicio: Optional[str], hora_fim: Optional[str]) -> str:
    """Trecho do horário de comparecimento — vazio quando nada foi declarado.

    As duas horas são independentes e sempre opcionais: um atendimento pode ter
    hora de chegada sem alta prevista. Cada combinação tem sua redação; nenhuma
    inventa a hora que falta.
    """
    ini = (hora_inicio or "").strip()
    fim = (hora_fim or "").strip()
    if ini and fim:
        return f", no período das {ini} às {fim}"
    if ini:
        return f", a partir das {ini}"
    if fim:
        return f", até as {fim}"
    return ""


def clausula_clinica(indicacao: Optional[str], cid: Optional[str]) -> str:
    """Trecho clínico OPCIONAL — só aparece quando declarado (privacidade).

    O CFM admite atestado sem CID: o diagnóstico só é registrado com anuência do
    paciente. Os quatro casos (texto+CID, só texto, só CID, nada) existem para
    que a pontuação feche em todos eles.
    """
    ind = (indicacao or "").strip()
    codigo = (cid or "").strip()
    if ind and codigo:
        return f", em razão de quadro clínico compatível com {ind} (CID {codigo})"
    if ind:
        return f", em razão de quadro clínico compatível com {ind}"
    if codigo:
        return f" (CID {codigo})"
    return ""


# ---------------------------------------------------------------------------
# Corpo do atestado — a fonte única
# ---------------------------------------------------------------------------

def corpo_atestado(
    *,
    nome_paciente: str,
    finalidade: str,
    dias_afastamento: Optional[int],
    data_documento: str,
    indicacao_clinica: Optional[str] = None,
    codigo_cid: Optional[str] = None,
    adjetivo_cuidados: str = "médicos",
    adjetivo_atendimento: str = "médico",
    hora_inicio: Optional[str] = None,
    hora_fim: Optional[str] = None,
    observacao_complementar: Optional[str] = None,
) -> tuple[Paragrafo, ...]:
    """Corpo do atestado: frase principal + observação complementar (se houver).

    Dois ramos de frase, escolhidos por `dias_afastamento`:
      - com dias  → AFASTAMENTO ("esteve sob cuidados … devendo permanecer
        afastado(a) …");
      - sem dias  → COMPARECIMENTO ("compareceu a atendimento …"). Nem todo
        atestado afasta.

    `adjetivo_cuidados` / `adjetivo_atendimento` vêm do conselho emissor
    (`domain/conselho_profissional.py`): um atestado do CFO fala em cuidados
    **odontológicos**. O horário entra nos DOIS ramos — declarado e não impresso
    seria perda silenciosa de um dado que o profissional digitou.

    A OBSERVAÇÃO COMPLEMENTAR é parágrafo próprio, depois do corpo, e nunca o
    substitui: os campos estruturados continuam sendo a autoridade sobre dias,
    datas e finalidade. É por isso que ela é um ACRÉSCIMO e não um corpo
    editável — texto livre no lugar do corpo permitiria escrever "5 dias" com
    `dias_afastamento=3` no banco, e aí documento e carteira do cidadão
    divergiriam.
    """
    clausula = clausula_clinica(indicacao_clinica, codigo_cid)
    data_fmt = formatar_data_br(data_documento)
    periodo = periodo_horario(hora_inicio, hora_fim)

    if dias_afastamento and dias_afastamento > 0:
        frase = (
            Trecho("Atesto, para fins "),
            Trecho(finalidade, enfase=True),
            Trecho(", que "),
            Trecho(nome_paciente, enfase=True),
            Trecho(
                f" esteve sob cuidados {adjetivo_cuidados} na data de "
                f"{data_fmt}{periodo}{clausula}, devendo permanecer afastado(a) "
                f"de suas atividades habituais por "
            ),
            Trecho(f"{dias_afastamento} dia(s)", enfase=True),
            Trecho(" a partir desta data."),
        )
    else:
        frase = (
            Trecho("Atesto, para fins "),
            Trecho(finalidade, enfase=True),
            Trecho(", que "),
            Trecho(nome_paciente, enfase=True),
            Trecho(
                f" compareceu a atendimento {adjetivo_atendimento} na data de "
                f"{data_fmt}{periodo}{clausula}."
            ),
        )

    paragrafos = [Paragrafo(frase)]

    observacao = (observacao_complementar or "").strip()
    if observacao:
        paragrafos.append(Paragrafo((Trecho(observacao),)))

    return tuple(paragrafos)

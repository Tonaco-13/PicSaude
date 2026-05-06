# TICKET 17 — PDF RECEITUÁRIOS ANVISA VERSÃO 2 (PICSAÚDE)

## Prompt para Claude Code

> Cole o texto abaixo no seu Claude Code.

---

```
=== TICKET 17 — PDF RECEITUÁRIOS ANVISA VERSÃO 2 ===

CONTEXTO

O PicSaúde já possui:
- Motor regulatório (Ticket 15) que classifica itens por grupo
  e gera receituários na tabela `receituarios`
- Adapter SNCR com stub (Ticket 16A) que numera receituários
  (status: "numerado_stub" ou "nao_requer_sncr")
- PDF de prescrição genérica (app/domain/pdf_prescricao.py)
  usando ReportLab + Platypus, formato A4, paleta PicSaúde
- Infraestrutura de assinatura ICP-Brasil e gov.br

O que FALTA é a geração do PDF regulatório — o documento
que o paciente leva à farmácia, compatível em estrutura e
campos obrigatórios com os modelos Anvisa Versão 2
(publicada em 16/03/2026, obrigatória a partir de
18/05/2026). NÃO afirmamos reprodução visual pixel-perfect
dos modelos oficiais — apenas compatibilidade estrutural
e de campos obrigatórios.

DIFERENÇA FUNDAMENTAL:
- pdf_prescricao.py gera o PDF da PRESCRIÇÃO (ato clínico,
  todos os itens, documento interno/operacional)
- pdf_receituario.py gera o PDF do RECEITUÁRIO (documento
  regulatório, por grupo, segue modelo Anvisa, apresentado
  na farmácia)

Este ticket NÃO altera o PDF de prescrição existente.

O diretório do projeto é:
/Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

Instruções de reconexão do PostgreSQL:
PGBIN=~/Library/Python/3.9/lib/python/site-packages/pgserver/pginstall/bin
$PGBIN/pg_ctl -D /tmp/picsaude-pgdata -l /tmp/picsaude-pgdata/pg.log start
export DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_dev

--------------------------------------------------
OBJETIVO
--------------------------------------------------

Criar gerador de PDF para cada tipo de receituário,
compatível em campos e estrutura com os modelos Anvisa
Versão 2 (sem afirmar reprodução visual oficial), com:

1. Layout distinto por tipo (cor, título, campos)
2. Todos os campos obrigatórios da RDC 1.000/2025
3. QR Code de autenticação
4. Campo de numeração SNCR (quando aplicável)
5. Identificação visual clara do tipo de receituário
6. Endpoint para download do PDF
7. Transição de status para "emitido"
8. Testes de integração

--------------------------------------------------
ESCOPO
--------------------------------------------------

ENTRA:
- Módulo pdf_receituario.py (gerador de PDF)
- Mapeamento de cores/layout por tipo_receituario
- QR Code com dados de verificação
- Endpoint GET /receituarios/{receituario_id}/pdf
- Transição de status "numerado_stub" → "emitido"
  e "nao_requer_sncr" → "emitido"
- Registro de evento "receituario_emitido" no ledger
- Testes de integração

NÃO ENTRA:
- Integração real com SNCR (Ticket 16B)
- Assinatura digital PAdES/LTV embutida no PDF (escopo futuro)
- Grupo Retenção/antimicrobianos (Ticket 18)
- Alteração no PDF de prescrição existente
- Alteração no motor regulatório
- Alteração no adapter SNCR

--------------------------------------------------
PASSO 1 — INVESTIGAÇÃO PRÉVIA (OBRIGATÓRIO)
--------------------------------------------------

ANTES de escrever código, ler e entender:

1. app/domain/pdf_prescricao.py
   - Padrão de geração (ReportLab + Platypus)
   - Helpers: _fmt_cpf, _fmt_data, _truncar_hash
   - Estilo de código e paleta de cores
   - Estrutura: _build_styles() → blocos → doc.build(story)
   - SEGUIR EXATAMENTE o mesmo padrão

2. app/models/receituario.py
   - Campos disponíveis para o PDF
   - Relacionamentos (prescricao, itens)
   - Campo numeracao_sncr (pode ser NULL ou "STUB-...")
   - Campo status (valores possíveis)

3. app/domain/motor_regulatorio.py
   - GRUPOS_REGULATORIOS — tipos de receituário
   - Mapeamento tipo → cor → nome

4. app/routers/receituarios.py
   - Endpoints existentes (gerar, numerar)
   - Padrão de autenticação e autorização
   - Helpers de serialização

5. app/models/prescricao.py, prescricao_item.py
   - Dados do prescritor e paciente
   - Campos de assinatura

6. app/models/prescritor.py, paciente.py
   - Campos disponíveis para identificação

Reportar o que encontrou antes de prosseguir.

--------------------------------------------------
PASSO 2 — MAPEAMENTO DE CORES E LAYOUT POR TIPO
--------------------------------------------------

Definir em app/domain/pdf_receituario.py:

CORES_RECEITUARIO = {
    "notificacao_receita_a": {
        "cor_primaria": "#F9A825",       # Amarelo Anvisa
        "cor_fundo_cabecalho": "#FFF8E1", # Amarelo claro
        "cor_borda": "#F57F17",          # Amarelo forte
        "titulo": "NOTIFICAÇÃO DE RECEITA A",
        "subtitulo": "Listas A1 / A2 / A3 — Portaria SVS/MS nº 344/1998",
        "cor_papel": "AMARELA",
    },
    "notificacao_receita_b": {
        "cor_primaria": "#1565C0",       # Azul Anvisa
        "cor_fundo_cabecalho": "#E3F2FD", # Azul claro
        "cor_borda": "#0D47A1",          # Azul forte
        "titulo": "NOTIFICAÇÃO DE RECEITA B",
        "subtitulo": "Listas B1 / B2 — Portaria SVS/MS nº 344/1998",
        "cor_papel": "AZUL",
    },
    "receita_controle_especial": {
        "cor_primaria": "#37474F",       # Cinza-escuro
        "cor_fundo_cabecalho": "#ECEFF1", # Cinza claro
        "cor_borda": "#263238",          # Quase preto
        "titulo": "RECEITA DE CONTROLE ESPECIAL",
        "subtitulo": "Lista C — 2 vias — Portaria SVS/MS nº 344/1998",
        "cor_papel": "BRANCA",
    },
    "notificacao_receita_especial": {
        "cor_primaria": "#6A1B9A",       # Roxo
        "cor_fundo_cabecalho": "#F3E5F5", # Roxo claro
        "cor_borda": "#4A148C",          # Roxo forte
        "titulo": "NOTIFICAÇÃO DE RECEITA ESPECIAL",
        "subtitulo": "Retinoides / Talidomida — Listas D1 / D2",
        "cor_papel": "BRANCA",
    },
    "receita_simples": {
        "cor_primaria": "#2E7D32",       # Verde PicSaúde
        "cor_fundo_cabecalho": "#E8F5E9", # Verde claro
        "cor_borda": "#1B5E20",          # Verde forte
        "titulo": "RECEITA SIMPLES",
        "subtitulo": "Sem controle regulatório especial",
        "cor_papel": "BRANCA",
    },
}

NOTAS IMPORTANTES:
- As cores são APROXIMAÇÕES dos modelos oficiais
  (os PDFs reais da Anvisa usam cores específicas
  que não estão documentadas em hexadecimal)
- O amarelo e azul são os mais regulatoricamente
  relevantes — devem ser CLARAMENTE identificáveis
- Se encontrar referências mais precisas nos modelos
  oficiais, ajustar

--------------------------------------------------
PASSO 3 — CAMPOS OBRIGATÓRIOS POR MODELO ANVISA V2
--------------------------------------------------

Todos os receituários V2 DEVEM conter:

CAMPOS COMUNS (todos os tipos):
1. Cabeçalho regulatório
   - Tipo do receituário (ex: "NOTIFICAÇÃO DE RECEITA A")
   - Cor identificadora (amarela, azul, etc.)
   - Logo/marca "SNCR — Sistema Nacional de Controle
     de Receituários" (texto, não imagem)

2. Numeração SNCR
   - numeracao_sncr do receituário
   - Se stub: exibir com indicação "[DESENVOLVIMENTO]"
   - Se NULL (receita simples): campo não aparece

3. Identificação do prescritor
   - Nome completo
   - CNS (Cartão Nacional de Saúde)
   - Modo de assinatura declarado

4. Identificação do paciente (MUDANÇA V2)
   - Nome completo
   - CPF (OBRIGATÓRIO em V2 — substituiu endereço)
   - CPF mascarado: 123.***.***-01

5. Medicamentos
   - Nome do medicamento
   - Concentração
   - Forma farmacêutica
   - Quantidade (numeral + unidade)
   - Posologia completa

6. Informações regulatórias
   - Número de vias (1, 2 ou 3)
   - Indicação de retenção pela farmácia
   - Classe de controle do item (A1, B1, etc.)

7. Dados de rastreabilidade
   - Protocolo da prescrição
   - Data de emissão
   - Hash SHA-256 do documento
   - Identificação do adapter (stub/real)

8. QR Code de rastreabilidade interna PicSaúde
   - IMPORTANTE: enquanto o SNCR real não estiver integrado,
     este QR é rastreabilidade INTERNA do PicSaúde, NÃO
     validação oficial SNCR. Não chamar de "verificação
     oficial" no PDF.
   - Contém: protocolo + numeracao_sncr + hash (primeiros 16 chars)
   - Posição: canto inferior direito
   - Tamanho: 25mm × 25mm
   - Label no PDF: "QR — Rastreabilidade PicSaúde"
     (NÃO "Verificação SNCR")

9. Área de assinatura
   - Para assinatura digital: indicação do certificado
   - Linha de assinatura do prescritor

10. Rodapé
    - "Documento gerado por PicSaúde — SNCR"
    - Data/hora de geração
    - Indicação de versão do modelo: "Modelo Anvisa Versão 2"

CAMPOS ESPECÍFICOS POR TIPO:

Notificação A (Amarela):
- Fundo amarelo no cabeçalho
- "ATENÇÃO: Substância sujeita a controle especial"
- "3 VIAS — 1ª via Anvisa / 2ª via farmácia / 3ª via paciente"

Notificação B (Azul):
- Fundo azul no cabeçalho
- "2 VIAS — 1ª via farmácia / 2ª via paciente"

Receita Controle Especial (Branca):
- Cabeçalho neutro com borda
- "2 VIAS — 1ª via retida pela farmácia"

Notificação Especial (Retinoides/Talidomida):
- Alerta: "ATENÇÃO: Medicamento com risco teratogênico"
- "2 VIAS — 1ª via farmácia / 2ª via paciente"

Receita Simples:
- Layout limpo sem alertas especiais
- Sem campo SNCR
- "1 VIA"

--------------------------------------------------
PASSO 4 — GERADOR DE PDF (IMPLEMENTAÇÃO)
--------------------------------------------------

Criar: app/domain/pdf_receituario.py

Estrutura da função principal:

def gerar_pdf_receituario(
    *,
    # receituário
    tipo_receituario: str,
    grupo_nome: str,
    numeracao_sncr: str | None,
    status: str,
    vias: int,
    retencao_farmacia: bool,
    adapter_usado: str | None,
    # prescrição
    protocolo: str,
    assinatura_hash: str | None,
    assinatura_modo: str | None,
    data_emissao: str,
    data_validade: str | None,
    indicacao_clinica: str | None,
    # prescritor
    nome_prescritor: str,
    cns_prescritor: str,
    # paciente
    nome_paciente: str,
    cpf_paciente: str,
    # itens do receituário
    itens: list[dict],
    # meta
    classe_controle_itens: list[str] | None = None,
) -> bytes:
    """
    Gera PDF do receituário conforme modelo Anvisa Versão 2.

    Retorna bytes do PDF pronto para StreamingResponse.
    """

ESTRUTURA DO PDF (blocos, de cima para baixo):

1. CABEÇALHO REGULATÓRIO (fundo colorido por tipo)
   ┌──────────────────────────────────────────────┐
   │  NOTIFICAÇÃO DE RECEITA A                    │
   │  Listas A1/A2/A3 — Portaria SVS/MS 344/1998 │
   │  SNCR — Sistema Nacional de Controle de      │
   │         Receituários                         │
   │                                [COR: AMARELA]│
   └──────────────────────────────────────────────┘

2. FAIXA DE NUMERAÇÃO SNCR
   ┌──────────────────────────────────────────────┐
   │  Nº SNCR: STUB-2026-NRA-000000001           │
   │  [DESENVOLVIMENTO — numeração não regulatória]│
   └──────────────────────────────────────────────┘
   (Se receita simples: bloco omitido)

3. SEÇÃO PRESCRITOR
   Nome: Dr. Fulano de Tal
   CNS: 987654321098765
   Assinatura: ICP-Brasil — Certificado A3

4. SEÇÃO PACIENTE
   Nome: João da Silva
   CPF: 123.***.***-01

5. SEÇÃO MEDICAMENTOS (tabela)
   | # | Medicamento        | Concentração | Qtd  | Posologia     |
   |---|--------------------| -------------|------|---------------|
   | 1 | DIAZEPAM           | 10mg         | 30cp | 1cp 8/8h...   |

   Com classe_controle exibida: [B1] ao lado do nome

6. SEÇÃO INFORMAÇÕES REGULATÓRIAS
   Nº de vias: 2
   Retenção farmácia: Sim — 1ª via retida
   Indicação clínica: [se informada]

7. SEÇÃO RASTREABILIDADE
   Protocolo: abc-1234-...
   Data emissão: 25/04/2026 às 14:30
   Validade: 30 dias (receituário controlado)
   Hash SHA-256: a1b2c3d4e5f6...

8. QR CODE + ASSINATURA (lado a lado)
   ┌─────────────────────────────┬──────────┐
   │  ________________________   │  [QR]    │
   │  Dr. Fulano de Tal          │  [CODE]  │
   │  CNS 987654321098765        │  25×25mm │
   └─────────────────────────────┴──────────┘

9. RODAPÉ
   "Documento gerado por PicSaúde — SNCR"
   "Modelo Anvisa Versão 2 — Vigente a partir de 18/05/2026"

GERAÇÃO DO QR CODE:

Usar a biblioteca `qrcode` (pip install qrcode[pil]):

import qrcode
from io import BytesIO

def _gerar_qr_code(dados: str) -> bytes:
    """Gera QR code como PNG em memória."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(dados)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()

Dados do QR Code (string codificada):
  protocolo={protocolo}
  sncr={numeracao_sncr or "N/A"}
  hash={assinatura_hash[:16] if assinatura_hash else "N/A"}
  tipo={tipo_receituario}
  emitido={data_emissao}

Para inserir no PDF com ReportLab:
  from reportlab.platypus import Image as RLImage
  from io import BytesIO

  qr_bytes = _gerar_qr_code(qr_data_string)
  qr_image = RLImage(BytesIO(qr_bytes), width=25*mm, height=25*mm)

PADRÕES OBRIGATÓRIOS (seguir pdf_prescricao.py):
- Mesmo formato de margens (20mm)
- Mesma tipografia (Helvetica, Helvetica-Bold)
- Mesmos helpers (_fmt_cpf, _fmt_data, _truncar_hash)
  → IMPORTAR de pdf_prescricao.py, NÃO duplicar
- ReportLab Platypus (SimpleDocTemplate, Table, Paragraph)
- Retornar bytes via BytesIO

DIFERENÇAS em relação a pdf_prescricao.py:
- Cabeçalho COLORIDO por tipo (não navy fixo)
- QR Code (prescrição não tem)
- Campos regulatórios (vias, retenção, classe controle)
- Numeração SNCR
- Alerta de substância controlada (A, D)
- Título é o tipo do receituário (não "RECEITA MÉDICA")

--------------------------------------------------
PASSO 5 — ENDPOINT DE DOWNLOAD DO PDF
--------------------------------------------------

Adicionar ao router de receituários (app/routers/receituarios.py):

GET /prescricoes/{protocolo}/receituarios/{receituario_id}/pdf

Fluxo:
1. Autenticar prescritor (role="prescritor")
2. Buscar prescrição por protocolo
3. Verificar posse (CNS do token = prescritor da prescrição)
4. Buscar receituário por ID
5. Verificar que receituário pertence à prescrição
6. Verificar que receituário está em status numerável:
   - "numerado_stub" → OK, gera PDF
   - "nao_requer_sncr" → OK, gera PDF
   - "numerado" → OK, gera PDF (futuro, SNCR real)
   - "emitido" → OK, retorna PDF (reemissão, idempotente)
   - "gerado" → 422: "Receituário não numerado.
     Chame POST /numerar primeiro."
   - "cancelado" → 422: "Receituário cancelado."
7. Carregar itens do receituário (receituario_itens →
   prescricao_itens)
8. Carregar prescritor e paciente
9. Chamar gerar_pdf_receituario(...)
10. Se status era "numerado_stub" ou "nao_requer_sncr"
    ou "numerado":
    → Atualizar status para "emitido"
    → Atualizar emitido_em = datetime.utcnow()
    → Registrar evento "receituario_emitido" no ledger:
      payload: {
        "receituario_id": ...,
        "tipo_receituario": "...",
        "numeracao_sncr": "...",
        "adapter_usado": "...",
        "ticket_referencia": "TICKET-17"
      }
11. Se status já era "emitido" (acesso ao PDF já emitido):
    → NÃO registrar novo evento "receituario_emitido"
    → Registrar evento "receituario_pdf_acessado" (leve,
      para trilha de acesso, não duplicar semântica de
      emissão)
    → Justificativa: "reemitido" sugere novo documento;
      aqui é apenas download repetido do mesmo PDF.
      Usar "pdf_acessado" evita spam no ledger se
      alguém abrir o PDF muitas vezes.
12. Retornar StreamingResponse com:
    - media_type: "application/pdf"
    - headers: {
        "Content-Disposition":
          f'inline; filename="receituario-{tipo_abrev}-{receituario_id}.pdf"'
      }
    - Usar tipo_abrev (NRA, NRB, RCE, NRE, RSI) no nome do arquivo

AUTENTICAÇÃO:
- Requer role "prescritor"
- Verificar posse da prescrição

IDEMPOTÊNCIA:
- Se já emitido → retorna PDF sem reemitir evento principal
- NÃO alterar numeração ou dados existentes

--------------------------------------------------
PASSO 6 — INDICAÇÃO DE STUB NO PDF
--------------------------------------------------

IMPORTANTE: Quando adapter_usado="stub", o PDF DEVE
indicar CLARAMENTE que é um documento de desenvolvimento:

1. Faixa de numeração deve conter:
   "[DESENVOLVIMENTO — numeração não regulatória]"
   em texto vermelho (#D32F2F)

2. Marca d'água diagonal NO PDF INTEIRO:
   "DOCUMENTO SEM VALIDADE REGULATÓRIA"
   - Cor: cinza claro com transparência (#BDBDBD, alpha=0.15)
   - Rotação: 45 graus
   - Fonte: Helvetica-Bold, 40pt
   - Posição: centro da página

   Implementação da marca d'água com ReportLab:
   Usar onFirstPage/onLaterPages callback do
   SimpleDocTemplate:

   def _watermark_stub(canvas, doc):
       if is_stub:
           canvas.saveState()
           canvas.setFont("Helvetica-Bold", 40)
           canvas.setFillColor(colors.HexColor("#BDBDBD"),
                               alpha=0.15)
           canvas.translate(A4[0]/2, A4[1]/2)
           canvas.rotate(45)
           canvas.drawCentredString(
               0, 0,
               "DOCUMENTO SEM VALIDADE REGULATÓRIA"
           )
           canvas.restoreState()

3. Rodapé deve indicar:
   "⚠ Numeração STUB — apenas para desenvolvimento e testes"

Quando adapter_usado="real" (futuro):
- Nenhuma marca d'água
- Nenhum indicativo de desenvolvimento
- Faixa de numeração normal

Quando receita simples (nao_requer_sncr):
- Sem marca d'água (não é stub)
- Sem faixa SNCR (não passa pelo SNCR)
- Layout limpo

--------------------------------------------------
PASSO 7 — TESTES DE INTEGRAÇÃO
--------------------------------------------------

Criar: tests/integration/test_pdf_receituario.py

1. test_gerar_pdf_notificacao_a_amarela
   - Criar prescrição com item A1 → gerar → numerar → PDF
   - Verificar: retorna bytes de PDF válido
   - Verificar: content-type = application/pdf
   - Verificar: status do receituário = "emitido"
   - Verificar: emitido_em não é NULL

2. test_gerar_pdf_notificacao_b_azul
   - Criar prescrição com item B1 → gerar → numerar → PDF
   - Verificar: retorna PDF válido
   - Verificar: status = "emitido"

3. test_gerar_pdf_receita_controle_especial
   - Criar prescrição com item C5 → gerar → numerar → PDF
   - Verificar: retorna PDF válido

4. test_gerar_pdf_receita_simples
   - Criar prescrição com item sem classe → gerar → numerar → PDF
   - Verificar: retorna PDF válido
   - Verificar: status transicionou de "nao_requer_sncr" → "emitido"

5. test_pdf_bloqueia_receituario_nao_numerado
   - Criar prescrição → gerar (sem numerar) → tentar PDF
   - Deve retornar 422: "Receituário não numerado"

6. test_pdf_acesso_repetido_idempotente
   - Gerar PDF uma vez (status → "emitido")
   - Acessar PDF novamente (mesmo receituário)
   - Deve retornar PDF sem erro
   - Deve registrar evento "receituario_pdf_acessado" (leve)
   - NÃO deve registrar evento "receituario_emitido" duplicado

7. test_pdf_registra_evento_ledger
   - Após gerar PDF, verificar evento "receituario_emitido"
     no ledger
   - Payload deve conter tipo_receituario, numeracao_sncr,
     adapter_usado

8. test_pdf_stub_tem_marca_dagua
   - Gerar PDF com adapter_usado="stub"
   - Parsear PDF (com PyPDF2/pdfplumber se disponível)
   - OU: verificar que bytes do PDF contêm a string
     "DOCUMENTO SEM VALIDADE" (busca simples em bytes)

9. test_pdf_contém_qr_code
   - Gerar PDF de receituário controlado
   - Verificar que bytes do PDF contêm dados de imagem
     (presença de stream de imagem PNG)
   - OU: verificar tamanho do PDF > tamanho mínimo esperado

10. test_pdf_receita_simples_sem_campo_sncr
    - Gerar PDF de receita simples
    - Verificar que string "SNCR" NÃO aparece no PDF
      (ou aparece apenas no rodapé genérico)

11. test_fluxo_completo_gerar_numerar_pdf
    - Prescrição com 3 itens: A1 + B1 + sem classe
    - Gerar receituários (3 receituários)
    - Numerar (2 numerados + 1 nao_requer_sncr)
    - Gerar PDF de cada um
    - Verificar 3 PDFs válidos
    - Verificar todos com status "emitido"
    - Verificar 3 eventos "receituario_emitido" no ledger

12. test_pdf_exige_autenticacao
    - Tentar GET /pdf sem token → 401 ou 403
    - Tentar com token de outro prescritor → 403

Executar:
export DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_test
cd /Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend
pytest tests/integration/test_pdf_receituario.py -v

Também rodar todos os testes existentes para não-regressão:
pytest tests/integration/ -v

--------------------------------------------------
PASSO 8 — DEPENDÊNCIAS
--------------------------------------------------

Instalar biblioteca de QR Code:
pip install qrcode[pil]

Verificar que Pillow está disponível (necessário para
qrcode[pil]):
pip install Pillow

Se preferir NÃO adicionar dependência de qrcode,
alternativa com ReportLab puro:
  from reportlab.graphics.barcode.qr import QrCodeWidget
  from reportlab.graphics.shapes import Drawing
  from reportlab.graphics import renderPDF

  qr = QrCodeWidget(data_string)
  qr.barWidth = 25 * mm
  qr.barHeight = 25 * mm
  d = Drawing(25 * mm, 25 * mm)
  d.add(qr)

PREFERIR a solução com ReportLab puro (QrCodeWidget)
para não adicionar dependência externa desnecessária.

--------------------------------------------------
PASSO 9 — DOCUMENTAÇÃO
--------------------------------------------------

Atualizar: docs/adapter_sncr.md

Adicionar seção:
"## Geração de PDF (Ticket 17)"
- Tipos de receituário e cores associadas
- Campos obrigatórios por modelo
- QR Code: conteúdo e posição
- Marca d'água em modo stub
- Transição de status: numerado* → emitido
- Endpoint GET /receituarios/{id}/pdf

Também criar: docs/pdf_receituarios.md
- Referência completa do módulo pdf_receituario.py
- Mapeamento de cores por tipo
- Exemplo visual (descrição textual do layout)
- Diferenças entre pdf_prescricao e pdf_receituario
- Modelo Anvisa Versão 2: campos obrigatórios
- Mudança V1→V2: CPF substituiu endereço do paciente

--------------------------------------------------
SALVAGUARDAS
--------------------------------------------------

1. NÃO alterar pdf_prescricao.py (é outro documento)
2. NÃO alterar motor_regulatorio.py
3. NÃO alterar sncr_interface.py, sncr_stub.py, sncr_factory.py
4. NÃO alterar o endpoint /gerar existente
5. NÃO alterar o endpoint /numerar existente
6. NÃO inventar campos Anvisa — usar apenas os confirmados
   pela pesquisa normativa (ver seção PASSO 3)
7. IMPORTAR helpers de pdf_prescricao.py (não duplicar)
8. Marca d'água OBRIGATÓRIA quando adapter_usado="stub"
9. QR Code OBRIGATÓRIO em todos os receituários
   (rastreabilidade interna PicSaúde, NÃO validação SNCR)
10. Rollback explícito em caso de falha (usar get_tx)
11. Se algum teste existente quebrar, parar e reportar
12. CPF do paciente no PDF:
    - Em modo stub (adapter_usado="stub"): MASCARAR CPF
      (123.***.***-01)
    - Em modo real (adapter_usado="real", futuro): seguir
      EXATAMENTE o modelo oficial Anvisa vigente
    - Registrar TODO_REGULATORIO no ledger para confirmar
      se o documento final regulatório deve exibir CPF
      completo ou mascarado. Até validação jurídica,
      o mascaramento é a escolha conservadora.
13. PREFERIR QrCodeWidget do ReportLab (sem dependência extra)

--------------------------------------------------
DEFINIÇÃO DE PRONTO
--------------------------------------------------

Responder com:

1. Módulo criado: app/domain/pdf_receituario.py
   - Tipos suportados (quantos?)
   - Cores mapeadas
   - QR Code implementado (com qual biblioteca?)
   - Marca d'água stub funcionando

2. Endpoint criado: GET /prescricoes/{protocolo}/receituarios/{receituario_id}/pdf
   - Status codes retornados (200, 401, 403, 404, 422)
   - Content-Type do response
   - Nome do arquivo no Content-Disposition

3. Transição de status funcionando:
   - numerado_stub → emitido ✓
   - nao_requer_sncr → emitido ✓
   - emitido → emitido (reemissão idempotente) ✓

4. Eventos no ledger:
   - receituario_emitido registrado (1ª emissão) ✓
   - receituario_pdf_acessado registrado (acesso repetido) ✓
   - todo_regulatorio para CPF (confirmar se completo ou
     mascarado no modo real) ✓

5. Nº de testes criados e resultado do pytest -v
6. Testes existentes continuam passando (total geral)
7. Documentação atualizada/criada
8. Exemplo de execução:
   - Gerar receituários → numerar → download PDF
   - Mostrar tamanho do PDF gerado
   - Confirmar presença de QR Code
9. Confirmação de que PDF stub tem marca d'água
10. Confirmação de que nenhum módulo existente foi alterado

Frase final obrigatória:

"PDF RECEITUÁRIOS ANVISA V2 ATIVO"
```

---

## Notas para o time de revisão

### Por que PDF separado da prescrição?

| Documento | Finalidade | Audiência | Regulação |
|-----------|-----------|-----------|-----------|
| PDF Prescrição | Ato clínico completo | Prescritor, prontuário | CFM 2.299/2021 |
| PDF Receituário | Documento regulatório | Farmácia, paciente, Anvisa | RDC 1.000/2025 |

São documentos DISTINTOS com propósitos diferentes.
Uma prescrição com 3 itens (A1 + B1 + simples) gera
1 PDF de prescrição e 3 PDFs de receituário.

### Modelo Anvisa Versão 2 — Mudanças confirmadas

| Aspecto | V1 (13/02/2026) | V2 (16/03/2026) |
|---------|-----------------|-----------------|
| ID paciente | Endereço | CPF/Passaporte |
| Obrigatoriedade | Transitório | Mandatório (18/05/2026) |
| Campo endereço | Presente | REMOVIDO |

### Fluxo completo após Ticket 17

```
Prescrição criada
  → POST /gerar (Ticket 15) — motor regulatório
    → 3 receituários (A, B, simples)
  → POST /numerar (Ticket 16A) — adapter SNCR
    → 2 numerados (STUB-...) + 1 nao_requer_sncr
  → GET /pdf (Ticket 17) — gera PDF por receituário
    → 3 PDFs distintos, cada um com layout Anvisa
    → Status: "emitido"
```

### Dependências resolvidas

| Dependência | Status |
|-------------|--------|
| ReportLab | ✅ Já instalado e em uso |
| QR Code | ✅ ReportLab QrCodeWidget (sem dep. extra) |
| Motor regulatório | ✅ Ticket 15 pronto |
| SNCR numeração | ✅ Ticket 16A pronto |
| Modelo de dados | ✅ Tabelas existentes |

### Sequência pós-Ticket 17

- **Ticket 18**: Grupo Retenção (antimicrobianos/GLP-1)
- **Ticket 16B**: Integração real SNCR (quando API disponível)
- **Futuro**: Assinatura PAdES/LTV embutida no PDF

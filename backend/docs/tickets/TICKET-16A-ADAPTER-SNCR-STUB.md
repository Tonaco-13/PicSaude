# TICKET 16A — ADAPTER SNCR COM STUB (PICSAÚDE)

## Prompt para Claude Code

> Cole o texto abaixo no seu Claude Code.

---

```
=== TICKET 16A — ADAPTER SNCR COM STUB ===

CONTEXTO

O PicSaúde possui motor regulatório local (Ticket 15) que:
- Classifica itens por grupo regulatório (A, B, C, D, Simples)
- Agrupa itens por tipo de receituário
- Gera receituários na tabela receituarios
- Valida nível de assinatura por grupo
- Campo numeracao_sncr existe mas está NULL

A RDC 1.000/2025 exige que receituários eletrônicos sejam
emitidos EXCLUSIVAMENTE por sistemas integrados ao SNCR via
API, com numeração individualizada previamente concedida.

PROBLEMA: A especificação técnica da API do SNCR não está
publicamente disponível (abril/2026). Plataformas como Memed
já integraram, mas a documentação pode estar restrita a
parceiros credenciados.

SOLUÇÃO: Criar a camada de integração com interface definida
(contrato) e implementação stub que simula o SNCR. Quando a
documentação real chegar, troca-se o adapter — o resto do
sistema não muda.

Este é um ticket de ARQUITETURA + PREPARAÇÃO.
NÃO é integração real com a Anvisa.

O diretório do projeto é:
/Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

Instruções de reconexão do PostgreSQL:
PGBIN=~/Library/Python/3.9/lib/python/site-packages/pgserver/pginstall/bin
$PGBIN/pg_ctl -D /tmp/picsaude-pgdata -l /tmp/picsaude-pgdata/pg.log start
export DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_dev

--------------------------------------------------
OBJETIVO
--------------------------------------------------

Criar adapter SNCR com:

1. Interface (contrato/protocolo) que define as operações SNCR
2. Implementação stub que simula respostas do SNCR
3. Fluxo completo: requisitar numeração → vincular ao receituário
   → atualizar status → registrar no ledger
4. Configuração por variável de ambiente para alternar entre
   stub e implementação real (futura)
5. Testes de integração do fluxo completo

--------------------------------------------------
ESCOPO
--------------------------------------------------

ENTRA:
- Interface do adapter SNCR (ABC ou Protocol)
- Implementação stub (mock local)
- Endpoint para numerar receituários via SNCR
- Estados de sincronização do receituário
- Migration Alembic (se necessário para novos campos)
- Testes de integração
- Documentação

NÃO ENTRA:
- Integração real com API da Anvisa (Ticket 16B futuro)
- Credenciamento da plataforma na Anvisa
- Geração de PDF (Ticket 17)
- Grupo 5 retenção (Ticket 18)
- Alteração no motor regulatório (Ticket 15)

--------------------------------------------------
PASSO 1 — INVESTIGAÇÃO PRÉVIA (OBRIGATÓRIO)
--------------------------------------------------

ANTES de escrever código, ler e entender:

1. app/domain/motor_regulatorio.py
   - GrupoRegulatorio (dataclass)
   - GRUPOS_REGULATORIOS
   - agrupar_por_receituario()
   - validar_assinatura_para_receituario()

2. app/models/receituario.py
   - Tabela receituarios (campos existentes)
   - Tabela receituario_itens
   - Campo numeracao_sncr (nullable String(50))
   - Campo status (valores atuais)
   - Campo substituido_em

3. app/routers/receituarios.py
   - Endpoint POST /prescricoes/{protocolo}/receituarios/gerar
   - Como receituários são criados
   - Como eventos são registrados no ledger

4. app/domain/assinatura.py
   - MODOS_DIGITAIS_VALIDOS
   - TIPOS_CERTIFICADO_VALIDOS

5. app/models/prescricao_assinatura.py
   - tipo_certificado (A1, A3, gov_br_nuvem)
   - status_validacao

Reportar o que encontrou antes de prosseguir.

--------------------------------------------------
PASSO 2 — INTERFACE DO ADAPTER (CONTRATO)
--------------------------------------------------

Criar: app/adapters/sncr_interface.py

Definir a interface usando ABC (Abstract Base Class) ou
Protocol do Python:

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class NumeracaoSNCR:
    """Resultado de uma requisição de numeração ao SNCR."""
    numero: str                   # ex: "SNCR-2026-NRA-000001234"
    tipo_receituario: str         # ex: "notificacao_receita_a"
    prescritor_cpf: str           # CPF vinculado
    concedida_em: datetime        # timestamp da concessão
    valida_ate: datetime | None   # prazo de validade (se houver)
    lote_id: str | None           # ID do lote de numeração

@dataclass(frozen=True)
class RegistroUtilizacao:
    """Resultado do registro de utilização (dispensação)."""
    numero_sncr: str
    registrado_em: datetime
    dispensador_cnes: str | None
    status: str                   # "utilizado" | "cancelado"

@dataclass(frozen=True)
class ResultadoSNCR:
    """Wrapper de resultado para operações SNCR."""
    sucesso: bool
    dados: NumeracaoSNCR | RegistroUtilizacao | None
    erro: str | None
    codigo_erro: str | None       # ex: "SNCR_TIMEOUT", "SNCR_INVALIDO"
    tentativa: int                # número da tentativa (para retry)

class SNCRAdapter(ABC):
    """
    Contrato para integração com o SNCR da Anvisa.

    Implementações:
    - SNCRStub: mock local para desenvolvimento/teste
    - SNCRReal: integração real (Ticket 16B, quando API disponível)
    """

    @abstractmethod
    def requisitar_numeracao(
        self,
        tipo_receituario: str,
        prescritor_cpf: str,
        quantidade: int = 1,
    ) -> list[ResultadoSNCR]:
        """
        Requisita numeração ao SNCR para receituários.

        Args:
            tipo_receituario: tipo do receituário (ex: "notificacao_receita_a")
            prescritor_cpf: CPF do prescritor (vinculação obrigatória)
            quantidade: número de numerações solicitadas

        Returns:
            Lista de ResultadoSNCR, um por numeração solicitada.

        A implementação real usará assinatura qualificada ICP-Brasil
        para autenticar a requisição.
        """
        ...

    @abstractmethod
    def verificar_numeracao(
        self,
        numero_sncr: str,
    ) -> ResultadoSNCR:
        """
        Verifica validade de uma numeração SNCR.

        Usado pela farmácia na dispensação (escopo futuro),
        mas definido na interface para completude.
        """
        ...

    @abstractmethod
    def registrar_utilizacao(
        self,
        numero_sncr: str,
        dispensador_cnes: str,
        data_dispensacao: datetime,
    ) -> ResultadoSNCR:
        """
        Registra utilização (dispensação) de um receituário.

        Escopo da farmácia, não do prescritor.
        Definido na interface para completude do contrato.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Verifica se o SNCR está acessível."""
        ...

IMPORTANTE:
- A interface deve ser ESTÁVEL — não vai mudar quando a
  implementação real chegar
- Os campos do NumeracaoSNCR são inferidos dos requisitos
  normativos (podem mudar com a especificação real)
- Documentar quais campos são confirmados vs inferidos

--------------------------------------------------
PASSO 3 — IMPLEMENTAÇÃO STUB
--------------------------------------------------

Criar: app/adapters/sncr_stub.py

O stub simula o comportamento esperado do SNCR:

class SNCRStub(SNCRAdapter):
    """
    Implementação stub do SNCR para desenvolvimento e testes.

    Gera numerações locais no formato:
    STUB-{ANO}-{TIPO_ABREV}-{SEQUENCIAL:09d}

    NÃO tem validade regulatória.
    Receituários numerados pelo stub são marcados como
    "numerado_stub" (não "numerado").
    """

Comportamento do stub:

1. requisitar_numeracao():
   - Gerar número sequencial local:
     STUB-2026-NRA-000000001 (para Notificação A)
     STUB-2026-NRB-000000001 (para Notificação B)
     STUB-2026-RCE-000000001 (para Receita Controle Especial)
     etc.
   - Usar contador atômico (thread-safe) para sequencial
   - Retornar ResultadoSNCR com sucesso=True
   - Incluir prescritor_cpf na vinculação

2. verificar_numeracao():
   - Se número começa com "STUB-": retornar válido
   - Se não: retornar erro "Numeração não reconhecida pelo stub"

3. registrar_utilizacao():
   - Retornar sucesso (mock)
   - Registrar em log

4. health_check():
   - Retornar True (sempre disponível)

GUARDRAILS DO STUB:
- Toda numeração gerada pelo stub DEVE ter prefixo "STUB-"
  para ser distinguível de numeração real
- O status do receituário com numeração stub deve ser
  "numerado_stub", NÃO "numerado"
- Logs devem indicar claramente "[SNCR-STUB]" em cada operação
- Em produção futura, o stub deve ser substituído — nunca usado

--------------------------------------------------
PASSO 4 — FACTORY E CONFIGURAÇÃO
--------------------------------------------------

Criar: app/adapters/sncr_factory.py

A factory decide qual implementação usar baseada em
variável de ambiente:

import os

def get_sncr_adapter() -> SNCRAdapter:
    """
    Retorna o adapter SNCR configurado.

    Variável de ambiente: SNCR_ADAPTER
    - "stub" (default): usa SNCRStub (dev/teste)
    - "real": usa SNCRReal (Ticket 16B, não implementado ainda)

    Se SNCR_ADAPTER="real" e SNCRReal não estiver disponível,
    levantar erro explícito — NÃO fazer fallback silencioso.
    """
    adapter_type = os.environ.get("SNCR_ADAPTER", "stub")

    if adapter_type == "stub":
        from app.adapters.sncr_stub import SNCRStub
        return SNCRStub()
    elif adapter_type == "real":
        raise NotImplementedError(
            "SNCRReal não implementado. "
            "Aguardando especificação técnica da API da Anvisa. "
            "Use SNCR_ADAPTER=stub para desenvolvimento."
        )
    else:
        raise ValueError(f"SNCR_ADAPTER inválido: {adapter_type}")

IMPORTANTE:
- NÃO fazer fallback silencioso de "real" para "stub"
- Se alguém configurar "real" em produção antes de ter a
  implementação, o sistema deve FALHAR EXPLICITAMENTE
- Mesmo padrão do guardrail SQLite em produção (main.py)

--------------------------------------------------
PASSO 5 — ESTADOS DO RECEITUÁRIO (MIGRATION)
--------------------------------------------------

O campo status da tabela receituarios precisa suportar
novos estados. Verificar os valores atuais e, se necessário,
criar migration.

Estados do ciclo de vida completo:

1. "gerado" — receituário criado pelo motor regulatório
2. "nao_requer_sncr" — receita simples/comum, não passa pelo SNCR
3. "numerado_stub" — numeração obtida via stub (dev/teste)
4. "numerado" — numeração real obtida do SNCR
5. "emitido" — assinado e disponibilizado ao paciente
6. "dispensado" — registro de utilização feito pela farmácia
7. "expirado" — prazo ultrapassado sem dispensação
8. "cancelado" — cancelado por correção/erro
9. "todo_regulatorio" — numerado mas com pendência regulatória registrada

Verificar se o campo status atual (String(20)) comporta
esses valores. Se necessário, aumentar para String(30).

Se necessário, criar migration:
alembic revision -m "expand_receituario_status_field"

Também adicionar campo (se não existir):

| Coluna | Tipo | Nullable | Nota |
|--------|------|----------|------|
| numerado_em | DateTime | Y | timestamp da numeração |
| emitido_em | DateTime | Y | timestamp da emissão |
| adapter_usado | String(20) | Y | "stub" ou "real" — rastreabilidade |

--------------------------------------------------
PASSO 6 — ENDPOINT DE NUMERAÇÃO
--------------------------------------------------

Adicionar endpoint no router de receituários:

POST /prescricoes/{protocolo}/receituarios/numerar

Fluxo:
1. Buscar prescrição por protocolo
2. Carregar receituários ativos (status="gerado")
3. Se não houver receituários gerados → 404 ou instrução
   para chamar /gerar primeiro
4. Derivar requer_sncr EXPLICITAMENTE para cada receituário:
   requer_sncr = tipo_receituario != "receita_simples"
   (ou equivalente: tipo_receituario not in ["receita_simples", "receita_comum"])
   NÃO inferir de outro campo — derivar do tipo_receituario diretamente.

   Para cada receituário que requer SNCR (requer_sncr=True):
   a. Obter adapter via get_sncr_adapter()
   b. Chamar adapter.requisitar_numeracao()
   c. Atualizar receituario:
      - numeracao_sncr = número obtido
      - status = "numerado_stub" ou "numerado"
      - numerado_em = timestamp
      - adapter_usado = "stub" ou "real"
5. Para receituários que NÃO requerem SNCR (receita simples/comum):
   - status = "nao_requer_sncr" (AJUSTE: NÃO usar "numerado")
   - numeracao_sncr = NULL
   - Justificativa: "numerado" implica que passou pelo SNCR.
     Receita simples nunca passa pelo SNCR, então o status
     deve refletir isso semanticamente
6. Registrar evento no ledger:
   tipo_evento: "receituarios_numerados"
   payload: {
     "adapter": "stub",
     "receituarios_numerados": N,
     "numeracoes": [...],
     "ticket_referencia": "TICKET-16A"
   }
7. Retornar receituários com numeração

Resposta:
{
  "prescricao_protocolo": "...",
  "adapter": "stub",
  "receituarios": [
    {
      "id": 1,
      "tipo": "notificacao_receita_a",
      "numeracao_sncr": "STUB-2026-NRA-000000001",
      "status": "numerado_stub",
      "numerado_em": "2026-04-24T...",
      "requer_sncr": true
    },
    {
      "id": 2,
      "tipo": "receita_simples",
      "numeracao_sncr": null,
      "status": "nao_requer_sncr",
      "requer_sncr": false
    }
  ],
  "total_numerados": 2
}

AUTENTICAÇÃO:
- Requer role "prescritor"
- Verificar posse da prescrição

IDEMPOTÊNCIA:
- Se receituário já está numerado → retornar existente
- NÃO renumerar receituário já numerado

VALIDAÇÃO DE ASSINATURA (AJUSTE OBRIGATÓRIO):
- Este ticket NÃO valida criptograficamente a assinatura
- Apenas CONSULTA o nível declarado na tabela prescricao_assinatura
  (tipo_certificado: A1, A3, gov_br_nuvem)
- Compara o nível declarado com o nível exigido pelo grupo
  regulatório do receituário (via motor_regulatorio)
- Se nível declarado é insuficiente:
  → NÃO bloqueia com 422
  → Numera normalmente mas registra TODO_REGULATORIO no ledger:
    tipo_evento: "todo_regulatorio"
    payload: {
      "receituario_id": ...,
      "motivo": "nivel_assinatura_insuficiente",
      "nivel_declarado": "gov_br_nuvem",
      "nivel_exigido": "icp_brasil",
      "acao_necessaria": "validar_assinatura_antes_emissao"
    }
- A validação criptográfica real é responsabilidade de outro
  momento do fluxo (emissão/Ticket 17), NÃO da numeração
- Justificativa: numeração é reserva de número, não emissão.
  Bloquear aqui criaria acoplamento desnecessário

--------------------------------------------------
PASSO 7 — TESTES DE INTEGRAÇÃO
--------------------------------------------------

Adicionar em tests/integration/test_sncr_adapter.py:

1. test_stub_gera_numeracao_com_prefixo_stub
   - Chamar requisitar_numeracao() no stub
   - Numeração deve começar com "STUB-"
   - Resultado deve ter sucesso=True

2. test_stub_numeracao_sequencial
   - Requisitar 3 numerações seguidas
   - Números devem ser sequenciais

3. test_stub_vincula_cpf_prescritor
   - Numeração deve estar vinculada ao CPF informado

4. test_stub_health_check
   - health_check() retorna True

5. test_factory_retorna_stub_por_default
   - Sem SNCR_ADAPTER definido → retorna SNCRStub

6. test_factory_real_levanta_erro
   - SNCR_ADAPTER=real → NotImplementedError

7. test_endpoint_numerar_receituario_controlado
   - Criar prescrição → gerar receituários → numerar
   - Receituário controlado deve ter numeracao_sncr com prefixo STUB-
   - Status deve ser "numerado_stub"

8. test_endpoint_numerar_receita_simples
   - Receita simples → numeracao_sncr=NULL, status="nao_requer_sncr"

9. test_endpoint_nao_renumera_existente
   - Chamar /numerar duas vezes → idempotente

10. test_endpoint_registra_todo_regulatorio_assinatura_insuficiente
    - Receituário controlado com gov.br (quando exige ICP-Brasil)
    - Deve numerar normalmente (NÃO bloquear com 422)
    - Deve registrar evento "todo_regulatorio" no ledger
    - Payload deve indicar nivel_declarado e nivel_exigido

11. test_endpoint_registra_evento_ledger
    - Após numerar, evento "receituarios_numerados" no ledger
    - Payload deve indicar adapter="stub"

12. test_stub_distinguivel_de_real
    - Verificar que numeração stub é claramente identificável
    - Status "numerado_stub" ≠ "numerado"

Executar:
export DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_test
cd /Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend
pytest tests/integration/test_sncr_adapter.py -v

Também rodar todos os testes existentes para não-regressão:
pytest tests/integration/ -v

--------------------------------------------------
PASSO 8 — DOCUMENTAÇÃO
--------------------------------------------------

Criar: docs/adapter_sncr.md

Conteúdo:
1. Objetivo do adapter pattern
2. Interface SNCRAdapter (contrato)
3. Implementação stub (comportamento, formato de numeração)
4. Factory e configuração (SNCR_ADAPTER)
5. Estados do receituário (diagrama textual do ciclo de vida)
6. Fluxo de numeração (endpoint → adapter → banco → ledger)
7. Guardrails (prefixo STUB-, status "numerado_stub", sem fallback)
8. Como substituir o stub pela implementação real (Ticket 16B):
   - Criar app/adapters/sncr_real.py implementando SNCRAdapter
   - Atualizar factory para instanciar SNCRReal
   - Configurar SNCR_ADAPTER=real
   - Status passa a ser "numerado" (sem "_stub")
   - Numeração sem prefixo "STUB-"
9. Pendências:
   - Especificação técnica da API SNCR (Anvisa)
   - Credenciamento da plataforma
   - Ambiente de homologação

--------------------------------------------------
SALVAGUARDAS
--------------------------------------------------

1. NÃO alterar models existentes (prescricoes, prescricao_itens,
   prescricao_eventos, prescricao_assinatura)
2. NÃO alterar motor_regulatorio.py
3. NÃO alterar o endpoint /gerar existente
4. NÃO fazer fallback silencioso de "real" para "stub"
5. NÃO usar numeração stub como se fosse real
6. NÃO remover o prefixo "STUB-" da numeração mock
7. NÃO alterar a lógica de assinatura existente
8. Rollback explícito em caso de falha (usar get_tx)
9. Se algum teste existente quebrar, parar e reportar
10. Toda numeração stub deve ser distinguível por prefixo
    E por status ("numerado_stub")

--------------------------------------------------
DEFINIÇÃO DE PRONTO
--------------------------------------------------

Responder com:

1. Interface criada: app/adapters/sncr_interface.py
   - Operações definidas (requisitar, verificar, registrar, health)
2. Stub criado: app/adapters/sncr_stub.py
   - Formato de numeração
   - Comportamento do contador
3. Factory criada: app/adapters/sncr_factory.py
   - Configuração por variável de ambiente
4. Migration (se necessária): campos adicionados
5. Endpoint POST /prescricoes/{protocolo}/receituarios/numerar
   funcionando
6. Nº de testes criados e resultado do pytest -v
7. Testes existentes continuam passando (total de testes)
8. Documentação criada: docs/adapter_sncr.md
9. Exemplo de execução: gerar → numerar → verificar status
10. Confirmação de que numeração stub é claramente
    distinguível (prefixo + status)
11. Confirmação de que nenhum model/router existente foi alterado

Frase final obrigatória:

"ADAPTER SNCR ATIVO (STUB)"
```

---

## Notas para o time de revisão

### Por que adapter pattern?

| Alternativa | Problema |
|-------------|----------|
| Implementar SNCR real direto | API não documentada — impossível |
| Esperar documentação para começar | Prazo de junho se aproxima — perda de tempo |
| Mockar nos testes e pronto | Não testa o fluxo real (endpoint → adapter → banco → ledger) |
| Adapter com stub | ✅ Fluxo completo testável, substituição limpa quando API chegar |

### Decisões de segurança

| Decisão | Justificativa |
|---------|---------------|
| Prefixo "STUB-" obrigatório | Impede que numeração mock seja confundida com real |
| Status "numerado_stub" ≠ "numerado" | Impede que receituário stub passe por real no sistema |
| Sem fallback silencioso | Se alguém configura "real" sem ter a implementação, o sistema falha — não finge que funciona |
| Consulta nível declarado (não valida cripto) | Numera sempre, mas registra TODO_REGULATORIO se nível insuficiente |
| Status "nao_requer_sncr" para receita simples | Semântica correta: receita simples nunca passa pelo SNCR |
| requer_sncr derivado de tipo_receituario | Regra explícita: != receita_simples/comum, sem ambiguidade |

### Sequência pós-Ticket 16A

- **Ticket 16B**: Implementação real do SNCRAdapter (quando API disponível)
- **Ticket 17**: Geração de PDF dos receituários (modelos Versão 2 Anvisa)
- **Ticket 18**: Grupo Retenção (antimicrobianos/GLP-1)

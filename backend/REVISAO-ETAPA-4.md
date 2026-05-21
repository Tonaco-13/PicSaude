# Relatório de Revisão Estática: Etapa 4 (Instance ID)

**Objetivo:** Avaliar a implementação da Etapa 4 do PicSaúde sob a ótica de simplicidade, legibilidade, pragmatismo e onboarding, focando em complexidade, fragilidades e propagação do `instance_id`.

## P1 (Bloqueador)

**1. Overhead de Banco de Dados (Query extra por transação)**
- **Arquivo/Linha:** `app/instance.py:382` (em `get_instance_id_conn`, no bloco de `SELECT primeiro`).
- **O que está errado/melhorável:** A função `get_instance_id_conn(conn)` executa um `SELECT` na tabela `meta_instalacao` a cada invocação. Como os routers a chamam em cada transação clínica (para propagar para o ledger e outbox), há a introdução de uma query extra para absolutamente *todas* as transações do sistema. Sendo o `instance_id` uma marca d'água imutável da instalação (UUID v4), isso configura um overhead de I/O massivo e injustificado.
- **Sugestão concreta:** Implementar um simples cache em memória no nível do módulo (ex: variável `_CACHED_INSTANCE_ID = None` que é preenchida na primeira leitura ou usando `@functools.lru_cache`). A leitura ao banco de dados deve ocorrer apenas uma vez por worker da aplicação.

## P2 (Relevante mas não bloqueador)

**2. Propagação Manual nos Routers (Boilerplate excessivo e Fragilidade)**
- **Arquivo/Linha:** `app/domain/ledger.py:143` (assinatura de `registrar_evento_ledger`) e vários em `app/routers/*.py` (ex: `app/routers/pedidos_exame.py:299`).
- **O que está errado/melhorável:** A decisão arquitetural forçou os routers a buscarem o `instance_id` (via `get_instance_id_conn(conn)`) e passá-lo manualmente em cada chamada para o ledger e outbox. Isso polui a camada de roteamento com preocupações puramente de auditoria de infraestrutura e aumenta a fragilidade: um desenvolvedor novo criando um endpoint inevitavelmente se esquecerá de passá-lo ou achará confuso. Apesar do tipo `keyword-only` levantar erro cedo, o padrão é frágil pela repetição mecânica.
- **Sugestão concreta:** Como o `instance_id` é imutável para a instância inteira, os helpers `registrar_evento_ledger` e `registrar_outbox` deveriam ler a variável/cache global em memória diretamente, dispensando a injeção via argumento vinda do router. O router não deve saber o que é `instance_id`.

**3. Lógica complexa de First-Boot acoplada a fluxos transacionais**
- **Arquivo/Linha:** `app/instance.py:393` (lógica de INSERT e tratamento de UUID v4 no bloco "2. First boot").
- **O que está errado/melhorável:** Injetar a responsabilidade de "inicialização do banco no first-boot" (incluindo concorrência e tratamento de Dialeto de Banco com RETURNING vs INSERT OR IGNORE) dentro de uma função `_conn` feita para rodar em transações clínicas é um risco. Se essa rota for chamada em paralelo nos primeiros instantes, a transação clínica estaria mesclada à lógica de setup global.
- **Sugestão concreta:** O ciclo de vida da aplicação (startup/lifespan) deve ser o *único* responsável por garantir o first-boot via `get_instance_id(session)`. Em runtime (nos routers), devemos apenas ler a constante da memória.

## P3 (Lapidação textual / Sugestão)

**4. Onboarding: Risco de confusão semântica nos helpers**
- **Arquivo/Linha:** `app/domain/ledger.py` (docstring inicial) e `app/instance.py`.
- **O que está errado/melhorável:** Um desenvolvedor novo gastando 5 minutos no onboarding verá `instance_id` sendo passado junto de variáveis muito dinâmicas de transação dentro de `conn`. A intuição inicial de 9 em 10 devs será achar que `instance_id` diz respeito a um "ID de Request" ou "ID de Transação". A explicação conceitual se perde no meio do overhead mecânico.
- **Sugestão concreta:** Remover a passagem de `instance_id` em tempo de request mitigaria a ilusão completamente. Como ajuste puramente textual por enquanto, adicionar na docstring da API pública dos helpers um lembrete (em caixa alta) de que o valor representa o Servidor/Instalação física e nunca muda durante a vida do banco de dados.

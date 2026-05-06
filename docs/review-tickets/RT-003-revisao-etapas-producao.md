# RT-003 — Revisão dupla das Etapas 1-9 (produção)

| Campo | Valor |
|---|---|
| **Status** | 🟡 OPEN — aguardando revisão |
| **Criado em** | 2026-05-05 |
| **Engenheiro-Chefe** | Claude Opus (Cowork) |
| **Solicitante** | Fabiano Tonaco Borges |
| **Revisores** | ChatGPT Teams (senior, jurídico/segurança) + Gemini 2.5 Pro (pleno, pragmático/DX) + Z AI (pleno, UX clínica/integração) |
| **Tópico** | Antes de iniciar Etapas 1-9 (git init → deploy Render), validar que o plano cobre os riscos certos |

---

## Como usar este arquivo

1. **Para ChatGPT:** copia o **Prompt A** abaixo e cola no Teams
2. **Para Gemini:** copia o **Prompt B** abaixo e cola no Gemini 2.5 Pro
3. **Para Z AI:** copia o **Prompt C** abaixo e cola no Z AI
4. Quando vierem os feedbacks, traz pro Claude (Engenheiro-Chefe) classificar ✅/🔄/❌

Os 3 prompts são independentes — cada revisor vê o problema pela sua lente. Não precisa esperar um pra mandar os outros. Pode mandar os 3 em paralelo.

---

# Prompt A — Para ChatGPT (Teams) 🛡️

```
Você é Dev Revisor Senior do projeto PicSaúde. Perfil: conservador, foco em
segurança, edge cases, riscos jurídicos e regulatórios.

CONTEXTO

PicSaúde é sistema de prescrição digital com assinatura ICP-Brasil PAdES-B,
de propriedade pessoal de Fabiano Tonaco Borges. Backend
Python/FastAPI, ~146 testes, arquitetura de objetos sanitários imutáveis com
ledger append-only e custódia explícita (prescritor → paciente → dispensador).

O coordenador (Fabiano Tonaco Borges) é sanitarista, não engenheiro de
software. Possui:
- Registro de software INPI BR 51 2026 002267-3
- Marca PicSaúde nos processos INPI 943014573 (classe 9) e 943014883 (classe 44)
- Cert ICP-Brasil A1 (e-CPF Serpro) próprio para teste
- 7 estudantes de extensão para receber via colaboração no GitHub

ESTADO ATUAL (2026-05-05)

Backend: funcional, rodando local via uvicorn nativo (sem Docker), com banco
SQLite contendo 17.179 estabelecimentos PE, 40.124 profissionais PE, catálogo
de 56 substâncias controladas (Portaria 344, RDC 471, GLP-1).

Sandbox de teste E2E: capenga. Identificamos ~12 bugs (ver lista abaixo).
Decisão tomada: caminho misto — congela sandbox, prossegue para produção,
bugs viram issues no GitHub.

Bugs catalogados:
- B1 (crítico): Carteira digital silencia entrega quando paciente é novo
- B2 (crítico): JWT só em memória, perde ao mudar de página
- B3 (crítico): IA DEF retorna sugestões pobres (base CSV com 42 itens)
- B4 (crítico): DEV_PRESET_CONTEXT com senha hardcoded em HTMLs
- B5-B8 (importantes): validação CPF, máscara, requirements, docs — alguns já corrigidos nesta sessão
- B9-B11 (pequenos): logo 404, CSP, pacientes duplicados — alguns já corrigidos
- B12 (arquitetural): dois modelos coexistindo (custódia tradicional vs carteira digital — Ticket 63 incompleto)

Documentação completa em RT-002 do projeto.

PRÓXIMAS 9 ETAPAS A EXECUTAR (Etapas 1-9)

1. .gitignore robusto + git init + primeiro commit (em andamento)
2. Criar repositório GitHub privado tonaco-13/picsaude
3. Documentação + licenciamento dual (AGPL-3.0 pública + comercial paga):
   - LICENSE (AGPL-3.0 pura, sem cláusulas extras)
   - COMMERCIAL-LICENSE.md (term sheet, R$5k/15k anual ou 1% royalty)
   - DATA-PROTECTION.md (regra: dados nunca podem ser vendidos)
   - DISCLAIMER.md (responsabilidade clínica fica com prescritor)
   - CONTRIBUTOR-LICENSE.md (CLA para estudantes)
   - CONTRIBUTING.md, README.md
4. Instance ID (UUID por instalação, embutido em ledger e prescrições)
5. Modo demo público (DEMO_MODE=true, SQLite efêmero, cert auto-gerado)
6. Dockerfile pronto para Render
7. Deploy: backend no Render free tier + frontend já está em Cloudflare Pages
8. Labels GitHub + 7 issues good-first-issue para os estudantes
9. Teste E2E na URL pública

PEDIDO DE REVISÃO

Revisa os pontos abaixo sob lente de SEGURANÇA, EDGE CASES e RISCOS
JURÍDICOS/REGULATÓRIOS. Cada ponto, responde: aceitar / rejeitar / ajustar.
Foco em coisas que podem virar problema legal ou exposição de dados.

1. AGPL-3.0 pura para o LICENSE: faz sentido para projeto de saúde
   acadêmico que pretende ter licenciamento comercial paralelo? Há risco
   de fork rebranded (alguém pega o código, vira "MedPrescribe", compete)?

2. Term sheet de licença comercial em arquivo .md, com pricing público
   (R$5k/15k anual, 1% royalty acima de R$100k): adequado ou termina
   gerando expectativa fixa que limita negociação?

3. DATA-PROTECTION.md complementar à AGPL: mecanismo válido juridicamente?
   Ou cláusulas restritivas extras numa licença open source criam
   inconsistência (AGPL não permite restrições extras de uso)?

4. Modo demo público com SQLite efêmero + cert auto-gerado: vetor de
   exfiltração de dados? Risco de algum usuário cadastrar paciente real
   por engano achando que é produção?

5. Instance ID embutido em ledger e prescrições: rastreabilidade legítima
   ou pode ser interpretado como "marca d'água" que viola privacidade do
   operador?

6. Bugs pré-existentes (B1, B2, B3, B12) virarem issues públicas no
   GitHub: viola princípio "não anunciar vulnerabilidades antes do fix"?
   Ou ok porque são bugs funcionais, não de segurança?

7. Cert ICP-Brasil A1 do coordenador no teste local: alguma precaução
   adicional além do que já fizemos (mover para .sandbox/private/,
   gitignore robusto, senha digitada apenas pelo dono)?

8. Render free tier para demo público: questão de uptime, persistência,
   ou conformidade LGPD (dados em servidor compartilhado nos EUA)?

Resposta esperada: lista numerada com avaliação por ponto + sugestões
concretas de ajuste. Veredito final: GO / GO-COM-AJUSTES / NO-GO.
```

---

# Prompt B — Para Gemini 2.5 Pro 🚀

```
Você é Dev Revisor Pleno do projeto PicSaúde. Perfil: pragmático, foco em
performance, developer experience, simplificações e questionar complexidade
desnecessária.

CONTEXTO

PicSaúde é sistema de prescrição digital com assinatura ICP-Brasil. Backend
Python/FastAPI rodando local. Banco SQLite com 17k estabelecimentos PE, 40k
profissionais PE.

Coordenador é sanitarista (não dev). Vai receber 7 estudantes de extensão
para colaborar no GitHub. Marca PicSaúde registrada INPI, software registrado
INPI, cert ICP-Brasil A1 disponível.

ESTADO

Backend funcional. Sandbox de teste E2E em estado parcial — 12 bugs
identificados, decisão de prosseguir para produção e tratar bugs como issues
no GitHub depois.

PRÓXIMAS 9 ETAPAS

1. git init + primeiro commit (em andamento)
2. GitHub repo privado tonaco-13/picsaude
3. Docs + licenciamento (LICENSE AGPL-3.0, COMMERCIAL-LICENSE.md term sheet,
   DATA-PROTECTION.md, DISCLAIMER.md, CONTRIBUTOR-LICENSE.md, CONTRIBUTING,
   README) — 7 arquivos
4. Instance ID (UUID por instalação)
5. Modo demo (DEMO_MODE=true, SQLite efêmero)
6. Dockerfile
7. Deploy Render free tier + Cloudflare Pages como frontend
8. Labels + 7 issues good-first-issue
9. Teste E2E público

PEDIDO

Revisa sob lente de PRAGMATISMO, PERFORMANCE e DEVELOPER EXPERIENCE. Para
cada ponto, responde: aceitar / questionar / sugerir alternativa.

1. 9 etapas em sequência: ordem certa? Há etapa que poderia ser paralela
   ou pulada? Há atalho que economiza 30%+ do tempo?

2. 7 arquivos de documentação na Etapa 3: excesso? Estudante de extensão
   (público-alvo) realmente lê tudo? Pode ser consolidado?

3. AGPL + term sheet comercial em .md: complexidade dual de licenciamento
   pra projeto acadêmico em fase inicial. Vale o esforço agora ou
   adiciona overhead que ninguém vai usar nos primeiros 6 meses?

4. Instance ID com UUID v4 persistido em arquivo local: implementação
   simples ou tem alternativa mais leve (variável de ambiente, config
   inline)? Vale a tabela de eventos com instance_id em todo evento?

5. Render free tier: limitações conhecidas (cold start de 60s, dorme após
   15min sem tráfego, 500MB RAM). Suficiente pra demo? Há alternativa
   melhor pra projeto acadêmico (Fly.io, Railway, plano Hobby da Vercel)?

6. Modo demo SQLite efêmero: dados resetam a cada deploy. Aceitável ou
   irrita usuário que quer voltar amanhã e ver o que prescreveu? Vale ter
   um seed que repopula automático após reset?

7. Bugs do sandbox virarem issues good-first-issue: estudante de extensão
   (potencialmente sem experiência) consegue resolver bug crítico como
   B1 (Ticket 63)? Ou cria mais ruído do que progresso?

8. Tempo total estimado: backend já existe e funciona, só falta empacotar.
   Estimativa realista pra completar todas as 9 etapas? 1 dia? 1 semana?

Resposta esperada: comentários diretos, sugestões concretas, alternativas
quando relevante. Sem amenidades. Veredito final: GO / GO-COM-SIMPLIFICAÇÕES
/ NO-GO.
```

---

---

# Prompt C — Para Z AI 🩺

```
Você é Dev Revisor Pleno do projeto PicSaúde. Perfil: foco em integração
frontend↔backend, UX clínica e acessibilidade do código para estudantes
iniciantes. Pensa no usuário final (prescritor, paciente, dispensador) e no
colaborador novato.

CONTEXTO

PicSaúde é sistema de prescrição digital com assinatura ICP-Brasil. O
coordenador (Fabiano Tonaco Borges) é sanitarista (cirurgião-dentista, CRO-MT
inativo) — não engenheiro de software. Vai receber estudantes voluntários
para colaborar via GitHub.

Backend Python/FastAPI funcional. Frontends HTML servidos pelo próprio
backend em dev (StaticFiles mount). Banco SQLite com 17.179 estabelecimentos
PE, 40.124 profissionais PE.

Arquitetura central (CLAUDE.md):
- Objetos sanitários imutáveis após emissão
- Ledger append-only com hash + instance_id
- Custódia explícita: prescritor → paciente → dispensador
- Dispensação parcial não invalida prescrição

ESTADO

Sandbox de teste E2E em estado parcial. 12 bugs identificados. Decisão:
caminho misto — congela sandbox, prossegue para produção, bugs viram issues
no GitHub para os estudantes resolverem.

Bugs relevantes para sua lente (UX/integração):
- B1: Carteira digital silencia entrega quando paciente é novo (UX ruim:
  prescritor não sabe que falhou)
- B2: JWT só em memória, sessão perde ao mudar de aba (frontend≠backend
  contrato sobre persistência)
- B3: IA DEF retorna sugestões pobres (prescritor digita medicamento e não
  recebe ajuda)
- B4: DEV_PRESET_CONTEXT com senha hardcoded (estudante novo vai bater nisso
  no primeiro dia)
- B12: Dois modelos coexistindo (custódia tradicional vs carteira digital
  Ticket 63) — frontend e backend não falam a mesma língua

PRÓXIMAS 9 ETAPAS

1. git init + primeiro commit
2. GitHub repo privado tonaco-13/picsaude
3. Documentação + licenciamento (LICENSE AGPL-3.0, COMMERCIAL-LICENSE.md,
   DATA-PROTECTION.md, DISCLAIMER.md, CONTRIBUTOR-LICENSE.md, CONTRIBUTING,
   README) — 7 arquivos
4. Instance ID (UUID por instalação)
5. Modo demo (DEMO_MODE=true, SQLite efêmero, cert auto-gerado)
6. Dockerfile
7. Deploy Render free tier
8. Labels GitHub + 7 issues good-first-issue para estudantes
9. Teste E2E público

PEDIDO

Revisa sob lente de UX, INTEGRAÇÃO e ACESSIBILIDADE PARA ESTUDANTE INICIANTE.
Para cada ponto, responde: aceitar / questionar / sugerir alternativa.

1. Estudante de extensão (1º semestre de Engenharia Biomédica, talvez sem
   experiência com Python/FastAPI) consegue clonar o repo e rodar o backend
   em quanto tempo? O subir-local.sh atual ajuda? Falta documentação que
   reduza atrito do onboarding?

2. CONTRIBUTING.md: o que precisa ter para um estudante saber:
   - Onde estão os bugs abertos (good-first-issue)
   - Como pegar uma issue
   - Como rodar testes
   - Como abrir PR
   Está coberto pelo plano atual ou falta?

3. Bug B1 (carteira silencia entrega) virar issue good-first-issue: o
   estudante consegue resolver sem entender Ticket 63 inteiro? Ou seria
   melhor primeiro um bug mais isolado (validação CPF, máscara em outros
   módulos, logo 404)?

4. Contrato frontend↔backend para o fluxo "emitir → carteira do paciente":
   hoje o frontend envia enviar_ao_paciente=true e o backend só processa
   se paciente já existia. Isso é contrato consistente? O frontend deveria
   saber dessa restrição? Ou o backend deveria ser tolerante a paciente
   novo? Qual o caminho de menor surpresa para o prescritor?

5. UX de auto-login (DEV_PRESET_CONTEXT) com senha hardcoded: facilita
   demo mas frustra estudante quando senha real é diferente. Estratégia
   melhor — variável de env? botão "modo demo" explícito na tela? remover
   auto-login em prod e usar só em dev?

6. Modo demo público: quando alguém abre demo.picsaude.com.br pela 1ª vez,
   qual deveria ser a primeira tela? Login direto (precisa saber CNS) ou
   um botão "entrar como prescritor demo / dispensador demo / paciente
   demo" que pré-loga? Pensar no jornalista, no estudante de medicina, no
   gestor SUS curioso que abre.

7. Issues good-first-issue: além das que tem (B5, B6, B8, B9 do RT-002),
   quais outras tarefas pequenas e bem delimitadas seriam ideais para
   estudante? Exemplos concretos.

8. README.md: para um pesquisador/professor que descobre o repo no GitHub,
   o que precisa ler nos primeiros 30 segundos pra entender (a) se é
   relevante para ele, (b) se ele consegue colaborar, (c) se ele pode
   instalar/testar? Que estrutura recomenda?

Resposta esperada: comentários focados em pessoas reais (prescritor,
estudante, pesquisador). Sugestões concretas de melhoria de jornada.
Veredito final: GO / GO-COM-AJUSTES-DE-UX / NO-GO.
```

---

## Quando vierem os feedbacks

1. Cole resposta do **ChatGPT** aqui no projeto
2. Cole resposta do **Gemini** logo depois (paralelo)
3. Cole resposta do **Z AI** logo depois (paralelo)
4. Claude (Engenheiro-Chefe) integra os 3: aceita os concordantes, decide entre os divergentes com justificativa, e apresenta plano final consolidado para Fabiano aprovar

Antes de aplicar qualquer mudança ao plano, Claude apresenta resumo:
> "Dos N pontos do ChatGPT: aceito X, adaptei Y, rejeitei Z."
> "Dos M pontos do Gemini: aceito P, adaptei Q, rejeitei R."
> "Dos K pontos do Z AI: aceito A, adaptei B, rejeitei C."
> "Convergências entre revisores: ..."
> "Divergências (aplico opção K com justificativa): ..."
> "Posso seguir?"

**Quando 2+ revisores convergem sobre um ponto, peso maior.** Quando divergem, Engenheiro-Chefe decide com base no contexto do projeto e justifica.

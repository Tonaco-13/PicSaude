# Prompt para o Arquiteto — análise estática do conceito de abertura

> Data: 2026-08-29 · Autor da exploração: Fabiano + Kimi (conversa de design)
> Natureza: **exploração conceitual fora do código de produção.**
> Nada aqui é pedido de implementação. É pedido de **opinião fundamentada**.

---

## 1. O que você deve analisar

| Artefato | Caminho |
|---|---|
| Conceito de landing (HTML puro, autocontido) | `/Volumes/fabianotonaco/Developer/PicSaude_Dev/conceitos-landing/index.html` |
| PDF renderizado da página (8 páginas) | `/Volumes/fabianotonaco/Developer/PicSaude_Dev/conceitos-landing/picsaude-conceito-abertura.pdf` |
| Fachada atual em produção (para comparar) | `/Volumes/fabianotonaco/Developer/PicSaude_Dev/index.html` |
| Contratos do domínio | `AGENTS.md` (raiz do projeto) e `backend/app/domain/states.py` |

**Modo de trabalho pedido:** análise estática e somente leitura. Não altere nenhum
arquivo. Não execute o backend. O engenheiro está trabalhando no código neste
momento. Se quiser ver a página no ar, `npm run dev` dentro de `conceitos-landing/`
sobe um preview estático (vite), mas isso é opcional — o PDF basta para a leitura.

---

## 2. O que o conceito tenta fazer

A página de abertura atual (`index.html` da raiz) é uma porta de serviço: seletor
de estações, lente de auditoria, estado da instância. O conceito propõe uma página
pública de verdade, com três apostas:

1. **O objeto em movimento como hero.** Um cartão-objeto viaja por um trilho de
   quatro estações. Trilho fixo e harmonizado: cada estação exibe o objeto cuja
   história culmina nela — Consultório: **Pedido de Exame** · Carteira Cidadã:
   **Encaminhamento** · Farmácia: **Receita** · Cuidado Entregue: **Laudo**.
   A troca acontece na chegada à estação, no mesmo relógio dos sinais verdes
   (16s por viagem). A nota diz: *"O objeto muda. O trilho, não."*
2. **Trilho harmonizado com o vocabulário da casa.** Cada parada é
   **estação + estado real da máquina de estados**:
   Consultório/`pendente` → Carteira Cidadã/`transferida_paciente` →
   Farmácia/`em_custodia` → Cuidado entregue/`dispensada`.
   Os pontos verdejam quando o objeto alcança a estação.
3. **A Lente de Auditoria como protagonista pública** (um campo central,
   visão neutra: existência e estado, nunca dados clínicos). As estações de
   acesso subiram para o header como pílulas discretas — Consultório, Farmácia,
   Carteira Cidadã, Clínica / Laboratório — ao lado do Entrar, com os nomes
   oficiais da fachada (decisão FACHADA de 25/08: estações, não atores).
   Não há mais seção de cards de módulos na página.
4. **Reveals estilo Apple.** Da seção "A jornada do objeto" em diante, os blocos
   emergem ao entrar na tela. Implementado como camada extra: sem JS ou com
   `prefers-reduced-motion`, todo o conteúdo nasce visível.

Assinatura do rodapé: **"PicSaúde. Feito para o SUS."**
Regras de copy assumidas: frases curtas, zero travessões, números sempre marcados
como ilustrativos, aviso explícito de protótipo conceitual.

---

## 3. O que pedimos da sua análise

### 3.1 Fidelidade ao domínio (a pergunta mais importante)
- Os quatro estados exibidos no trilho estão corretos e na ordem correta segundo
  `states.py` e o Contrato de Estados (AGENTS.md §5b)?
- A frase *"O objeto muda. O trilho, não."* é verdadeira para o NUCLEO_SANITARIO?
  Ou seja: a metáfora de trilho fixo com objeto variável representa fielmente o
  núcleo genérico (ledger + custódia + estados), ou esconde diferenças reais entre
  os objetos (ex.: laudo tem ciência por abertura, encaminhamento tem
  contrarreferência, agendamento não tem custódia)?
- A jornada em 4 gestos (emitir → cidadão → balcão → dispensada) é fiel ao fluxo
  digital da prescrição? Há algum gesto obrigatório omitido que torne a narrativa
  enganosa (ex.: token de apresentação)?

### 3.2 Honestidade das promessas
A página afirma, entre outras coisas: "nenhum papel obrigatório", "a soma do
entregue jamais passa do prescrito", "toda correção é um novo objeto derivado",
"a lente nunca expõe dados clínicos". Verifique uma a uma contra o sistema real:
cada promessa é cumprida hoje pelo backend? Alguma é aspiracional e deveria ser
sinalizada como tal?

### 3.3 Os números da faixa "1 · 7 · 0"
- **1** ledger imutável — correto, ou já são vários ledgers por objeto
  (`prescricao_eventos`, `encaminhamento_eventos`, etc.) e a frase precisa mudar?
- **7** tipos de objeto em circulação — a lente pública lista: receita, atestado,
  pedido de exame, laudo, encaminhamento, contrarreferência, circulação
  diagnóstica. Confere?
- **0** papel obrigatório — o fluxo exclusivamente físico (AGENTS.md §6) torna
  essa frase falsa ou apenas incompleta?

### 3.4 Risco arquitetural
Se esta página um dia virar a abertura real do picsaude.com.br: há algo no
conceito que criaria acoplamento indevido, vazamento de informação, ou expectativa
pública que a arquitetura atual não sustenta (ex.: a consulta da lente por CPF)?

### 3.5 O que você mudaria
Opinião livre do arquiteto: o que está errado, o que está fraco, o que está
ausente. Incluindo se a decisão de tirar as estações do corpo da página e
elevá-las a pílulas no header é defensável do ponto de vista operacional
(quem trabalha na plataforma chega direto ao trabalho?).

---

## 4. Formato da resposta pedida

Relatório curto, em português, com um veredito por seção (3.1 a 3.5):
**CONFERE / CONFERE COM RESSALVA / NÃO CONFERE**, seguido de justificativa com
referência ao arquivo e à seção do AGENTS.md ou do código que embasa. Fechar com
um parecer de uma frase: *"este conceito honra / não honra a arquitetura da casa."*

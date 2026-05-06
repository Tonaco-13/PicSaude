# Adicionar máscara de CPF (XXX.XXX.XXX-XX) com tratamento do sentinela de não-identificação

**Labels sugeridas:** `good first issue`, `frontend`, `regulatorio`
**Classe (CLAUDE.md §10):** `local-extension` (UI puro, sem alteração de contrato público)
**Estimativa:** 4–8h para estudante de extensão (DOM puro, sem backend)

---

## Contexto

O PicSaúde captura CPF do paciente em vários formulários: emissão de prescrição (`prescritor.html`), dispensação no balcão (`dispensador.html`), e cadastros futuros. Hoje o campo aceita qualquer formato — usuário pode digitar `123.456.789-09`, `12345678909`, ou variações com espaços. Isso causa três problemas:

1. **Erros de digitação invisíveis.** Sem formato visível, o prescritor não percebe que digitou 10 dígitos em vez de 11.
2. **Inconsistência entre formulários.** O backend normaliza (`utils/helpers.py:normalize_cpf`), mas o usuário não sabe que a normalização existe — pode ficar inseguro.
3. **Confusão com o CPF sentinela.** O sistema tem um caso especial regulatório: o CPF `00000000000` representa "prescrição física sem identificação do paciente" (CLAUDE.md §6a). Hoje, o usuário pode digitar 11 zeros acidentalmente e gerar prescrição com sentinela sem perceber.

**Por que isso importa regulatoriamente:** sob a RDC 1.000/2025, a identificação do paciente é parte da rastreabilidade da prescrição. Erro silencioso de digitação em campo crítico tem peso em auditoria.

---

## O que fazer

### Parte 1 — Máscara automática conforme digita

- Em todos os campos de CPF (input com classe ou atributo identificável), aplicar máscara `XXX.XXX.XXX-XX` em tempo real
- Usuário digita só dígitos, frontend injeta os pontos e o traço automaticamente
- Aceitar paste com ou sem formatação:
  - Colar `12345678909` → vira `123.456.789-09`
  - Colar `123.456.789-09` → mantém formatação
  - Colar texto com espaços/caracteres extras → ignora não-dígitos
- No mobile, `inputmode="numeric"` para abrir teclado numérico

### Parte 2 — Validação dos dígitos verificadores

- Validar quando o campo está completo (11 dígitos), **não** a cada caractere
- Algoritmo padrão dos dígitos verificadores do CPF (referência: [Receita Federal](https://www.receita.fazenda.gov.br))
- Se inválido, exibir mensagem em PT-BR: **"CPF inválido — verifique os dígitos"**
- Se válido, marcar campo como aceito (borda verde, ou indicador discreto)

### Parte 3 — Tratamento do CPF sentinela (CLAUDE.md §6a)

Este é o detalhe específico do PicSaúde. **Por favor leia esta parte com atenção.**

O sistema tem um valor reservado: CPF `00000000000` significa "prescrição física sem identificação digital do paciente". É matematicamente inválido (não passa no algoritmo dos dígitos verificadores), e isso é proposital — garante que nenhum CPF real coincida com o sentinela.

**Como integrar:**

- Adicionar checkbox próximo ao campo CPF: **"Paciente sem identificação (prescrição física)"**
- Quando marcado:
  - Campo CPF é desabilitado e exibe `000.000.000-00` em cinza
  - Sistema envia `00000000000` ao backend
  - Validação de dígitos é bypassada (não exibir mensagem de erro)
- Quando desmarcado:
  - Campo CPF normal, com máscara e validação ativas
  - Se usuário tentou digitar 11 zeros manualmente, validação rejeita normalmente (sentinela só vem do checkbox)

**Por que dois caminhos:** o sentinela é caso especial conhecido pelo sistema, não digitação acidental. A separação visual deixa claro para o prescritor que ele está fazendo uma prescrição sem paciente identificado — decisão consciente, não erro.

---

## Onde fazer

Arquivos afetados:

```
prescritor.html       ← campo CPF do paciente
dispensador.html      ← campo CPF do paciente no balcão
(qualquer formulário futuro com campo CPF)
```

Sugestão de implementação: criar função utilitária `mascaraCPF(inputElement)` em arquivo JS separado (ex: `static/js/mascara-cpf.js`) e importar nos dois HTMLs. Evita duplicação de código.

---

## Como testar

### Manualmente

1. Abrir `prescritor.html`, preencher campo CPF:
   - Digitar `12345678909` → deve aparecer `123.456.789-09`
   - Apagar e digitar `12345678900` (CPF inválido) → após 11 dígitos, exibir "CPF inválido"
   - Marcar checkbox "Paciente sem identificação" → campo desabilita, mostra `000.000.000-00`
   - Submeter → backend recebe `00000000000`
2. Abrir `dispensador.html`, repetir os passos
3. Testar em mobile (ou DevTools modo responsivo): teclado numérico aparece

### Testes automatizados

Adicionar testes em `tests/test_mascara_cpf.py` ou equivalente no frontend:

- [ ] Input `12345678909` → output formatado `123.456.789-09`
- [ ] Input com paste `123.456.789-09` → mantém formato
- [ ] Input com paste `abc 123.456.789-09 def` → vira `123.456.789-09`
- [ ] CPF válido (ex: `11144477735`) → não exibe erro
- [ ] CPF inválido (ex: `12345678900`) → exibe erro após 11 dígitos
- [ ] CPF com 10 dígitos digitados → não exibe erro ainda
- [ ] Checkbox marcado → envia `00000000000`, sem erro de validação
- [ ] Checkbox desmarcado + 11 zeros digitados → exibe erro de validação

---

## Critérios de aceitação

- [ ] Máscara `XXX.XXX.XXX-XX` aplicada em todos os campos CPF dos formulários existentes
- [ ] Paste com ou sem formatação funciona corretamente
- [ ] Mobile abre teclado numérico (`inputmode="numeric"`)
- [ ] Validação dos dígitos verificadores acontece após 11 dígitos digitados
- [ ] Mensagem de erro em PT-BR clara
- [ ] Checkbox "Paciente sem identificação" implementado conforme especificação
- [ ] Backend recebe sempre 11 dígitos (com ou sem sentinela)
- [ ] Função `mascaraCPF` em arquivo JS separado, reutilizável
- [ ] Testes automatizados cobrindo os 8 cenários da seção "Como testar"
- [ ] Nenhuma regressão nos testes existentes (146 testes devem continuar passando)

---

## Definition of Done

- Código revisado e merged via PR
- Testado manualmente no Chrome/Firefox + mobile (real ou DevTools)
- CPF do prescritor e do paciente cobertos (se houver mais de um campo CPF na tela)
- PR descreve o que foi feito e referencia esta issue

---

## Referências

- **CLAUDE.md §6a** — Convenção do CPF sentinela `00000000000`
- **`backend/app/utils/helpers.py:normalize_cpf`** — função que normaliza CPF no backend (não modificar, só usar)
- **RDC 1.000/2025** — exigência de identificação do paciente na prescrição
- Algoritmo dos dígitos verificadores do CPF: referência clássica disponível em qualquer documentação técnica brasileira

---

## Dúvidas?

Esta issue é didática por design — se algo não estiver claro, pergunte! Pode comentar aqui ou abrir uma discussion no GitHub. Não tem pergunta boba.

Antes de começar, confirme com o coordenador:

1. Que você leu CLAUDE.md (pelo menos a seção §6a)
2. Que assinou o CONTRIBUTOR-LICENSE.md
3. Que rodou `pytest` localmente e os 146 testes passam (assim você sabe que o setup está OK)

Bom trabalho! 💊

# Demonstração da assinatura A1 (ICP-Brasil) — roteiro local

> Guia para mostrar a assinatura digital **com o seu certificado real**, rodando
> tudo **localmente** no Mac. A chave privada nunca sai da máquina e nunca entra
> no repositório.

---

## Antes de começar (uma vez)

1. **Suba o PicSaúde local** (sem Docker), em modo dev:
   ```bash
   ./subir-local.sh
   ```
   Isso sobe o backend em `http://localhost:8000` com SQLite local. Em dev:
   - o **cofre** de certificados fica liberado (na vitrine pública ele é bloqueado);
   - a validação de cadeia ICP é tolerante (não precisa do truststore para a demo).

2. **(Higiene, recomendado)** defina uma chave de cifragem do cofre antes de subir,
   para o seu `.pfx` não ser guardado com a chave-sentinela de dev:
   ```bash
   export PFX_ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
   ./subir-local.sh
   ```
   Guarde esse valor se quiser reabrir o mesmo banco depois (sem ele, o `.pfx`
   cifrado não é mais legível). Para uma demo descartável, pode omitir.

3. **Confirme que NÃO está em modo demo:** `PICSAUDE_DEMO_MODE` deve estar
   desligado (é o default). Em modo demo a assinatura com chave real é bloqueada
   de propósito.

---

## O roteiro da demo (na frente da médica)

1. **Abra o `prescritor.html`** (duplo-clique abre via `file://`, que já aponta
   para `http://127.0.0.1:8000`). Faça login como prescritor.

2. **Envie seu certificado** — no bloco verde "Emissão Digital — Assinatura
   ICP-Brasil", clique em **“🪪 Meu certificado ICP-Brasil”**:
   - selecione seu arquivo `.pfx`/`.p12`;
   - digite a senha do certificado;
   - **Enviar certificado** → aparece "✓ Certificado válido: SEU NOME (CPF …)".

   *Por baixo:* o backend abre o `.pfx`, extrai sua identidade (CPF/nome do
   certificado), valida a estrutura e guarda o arquivo **cifrado (AES-256-GCM)**.
   A senha **não** é armazenada.

3. **Preencha uma prescrição** (paciente + um medicamento) e clique em
   **“🔐 Assinar e Emitir com Certificado Local (A1/A3 — ICP-Brasil)”**.
   A prescrição é emitida com força legal (modo `icp_brasil_local`).

4. **Na tela de sucesso**, aparece o bloco **“🔏 Assinatura ICP-Brasil (PAdES)”**.
   Clique em **“📄 Assinar com ICP-Brasil e baixar PDF”**:
   - digite a senha do seu certificado (usada uma vez, não fica guardada);
   - o PDF assinado é **baixado automaticamente**.

5. **Mostre a prova** — abra o PDF no **Adobe Reader** ou em
   **https://validar.iti.gov.br**: o documento aparece com a assinatura digital
   **válida**, vinculada ao seu nome e CPF, na cadeia ICP-Brasil. Não é simulação —
   é um documento juridicamente assinado.

---

## Como funciona por baixo (para explicar, se quiser)

- A assinatura é **PAdES-B** (padrão ICP-Brasil para PDF), feita pelo `pyHanko`.
- O fluxo é **server-side, mas tudo na sua máquina**: o PDF é gerado, o `.pfx` é
  decifrado **só na memória**, assinado, e a chave é descartada em seguida.
- Cada assinatura registra um evento `pdf_assinado_pades` no **ledger imutável**
  (hash do PDF + serial do certificado) — auditoria, como todo o resto do PicSaúde.
- A credibilidade vem do **próprio PDF**: ele carrega o certificado e a cadeia, e
  valida em qualquer ferramenta oficial — independente do nosso backend.

---

## Segurança (o que garante que sua chave está protegida)

| Garantia | Como |
|---|---|
| O `.pfx` real nunca vai ao repositório | `.gitignore` cobre `*.pfx`, `*.p12`, `*.pem`, `*.db` |
| A senha não é guardada | Fornecida a cada assinatura, usada e descartada |
| A chave fica cifrada em repouso | AES-256-GCM com `PFX_ENCRYPTION_KEY` |
| Tudo é local | Backend em `localhost`; nada trafega para fora |
| Vitrine pública não assina com chave real | Bloqueio por `PICSAUDE_DEMO_MODE` |

---

## Se algo der errado na hora

| Sintoma | Causa provável | Ação |
|---|---|---|
| "Nenhum certificado ativo" ao assinar | `.pfx` não foi enviado | Use "🪪 Meu certificado ICP-Brasil" primeiro |
| "Senha do certificado inválida" | senha do `.pfx` errada | Redigite a senha |
| "Assinatura desabilitada (modo demonstração)" | `PICSAUDE_DEMO_MODE=true` | Suba sem o modo demo (default dev) |
| Botão de assinar não aparece | emitiu em outro modo | Emita pelo botão "Certificado Local (A1/A3)" |

> Implementação: endpoint `POST /prescricoes/{protocolo}/pdf-assinado`
> (`backend/app/routers/prescricoes.py`), motor `assinar_pdf_icp`
> (`backend/app/domain/pdf_assinatura.py`), cofre `cofre_pfx.py`.
> Testes: `backend/tests/test_assinatura_a1_prescricao.py`.

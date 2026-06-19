# TICKET — Auditoria de segurança (SOMENTE LEITURA): assinatura ICP-Brasil A1 + cofre de certificado

> **Para:** Jules (revisor independente)
> **De:** Engenheiro-Chefe (PicSaúde)
> **Tipo:** Auditoria de segurança pré-exposição — **read-only**

---

## ⛔ REGRA INVIOLÁVEL — NÃO MODIFICAR NADA

Esta é uma auditoria **exclusivamente de leitura**. Você está proibido de:

- editar, criar, mover ou apagar qualquer arquivo;
- fazer commit, abrir PR, ou propor patch aplicável;
- refatorar, "consertar de passagem" ou rodar formatadores;
- alterar dependências, configs ou migrations.

**A sua entrega é um RELATÓRIO de achados, em texto.** Nenhuma mudança de código.
Se vir algo a corrigir, descreva e recomende — não implemente. Quem implementa
é o Engenheiro-Chefe, depois de discutir os achados com o coordenador.

---

## Contexto (por que esta auditoria, agora)

O PicSaúde é uma plataforma de prescrição digital com assinatura ICP-Brasil
(PAdES). O **backend de assinatura já existe e está commitado** (Tickets 21/68):
cadastro de certificado A1 (.pfx) cifrado em cofre, assinatura PAdES do PDF e
verificação criptográfica.

Estamos prestes a **ligar essa cadeia à interface do prescritor** — ou seja, a
expor o fluxo para prescritores reais subindo certificados A1 reais. Antes de
expor, queremos um pente-fino independente na superfície mais sensível: **chave
privada, cifra em repouso, senha, authz e validação da cadeia ICP-Brasil.**

Um erro aqui é grave (vazamento de chave, assinatura forjável, IDOR). Por isso a
auditoria vem **antes** da fiação na UI.

---

## Escopo — APENAS estes alvos

Auditar somente os arquivos abaixo (e o que eles chamam diretamente). **Não**
auditar UI, módulos clínicos não relacionados, nem o resto do repositório.

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/domain/cofre_pfx.py` | cifra/decifra do `.pfx` em repouso |
| `backend/app/routers/prescritor.py` (`upload_certificado`) | cadastro do certificado A1 |
| `backend/app/routers/receituarios.py` (`baixar_pdf_assinado`, `_carregar_certificado_ativo`, `_certificado_para_nivel`, `_nivel_atende_minimo`) | assinatura PAdES + nível regulatório |
| `backend/app/domain/pdf_assinatura.py` | geração/assinatura do PDF (pyHanko) |
| `backend/app/domain/assinatura_icp.py` | verificação criptográfica ICP-Brasil (Ticket 68) |
| tabela `prescritor_certificados` (schema + uso) | armazenamento do material de chave |

---

## O que verificar — checklist de invariantes

### A. Material de chave (.pfx) e cofre
- [ ] O `.pfx` e a senha **nunca** aparecem em log, mensagem de erro ou resposta HTTP.
- [ ] Cifra em repouso é autenticada (AES-GCM ou equivalente): **IV único por registro**, tag verificada na decifra. Sem ECB, sem IV reutilizado/fixo.
- [ ] A chave de cifra vem de `PFX_ENCRYPTION_KEY` (env). **Garantir que a chave-sentinela hardcoded (para testes) NUNCA seja alcançável em produção** — se a env faltar em prod, deve **falhar fechado**, não cair na sentinela.
- [ ] A senha do `.pfx` (`senha_pfx`) trafega só por TLS, não é persistida, não é cacheada, e sai da memória assim que possível.

### B. Cadastro do certificado (`upload_certificado`)
- [ ] Valida o `.pfx` com segurança (parse robusto, limite de tamanho, rejeita malformado).
- [ ] **Authz:** o prescritor autenticado só cadastra o **próprio** certificado (sem IDOR via id no path/body).
- [ ] Vincula o certificado ao prescritor de forma verificável (ex.: CPF no certificado == CPF do prescritor). Há essa amarra?

### C. Assinatura (`baixar_pdf_assinado`)
- [ ] **Authz:** só o dono assina; não dá para assinar com o certificado de outro prescritor nem assinar a prescrição de outro (IDOR).
- [ ] O hash assinado corresponde ao **documento canônico** correto (sem TOCTOU entre o que foi validado e o que foi assinado).
- [ ] Nível PAdES adequado (B-LT/B-LTA?) e **carimbo de tempo (TSA)** confiável embutido.
- [ ] O evento `pdf_assinado_pades` é append-only, registra o hash do PDF assinado, e não é forjável/replayável.

### D. Verificação ICP-Brasil (`assinatura_icp.py`)
- [ ] A verificação valida a **cadeia completa até a AC-Raiz ICP-Brasil** (e revogação CRL/OCSP) — **não apenas validade temporal**. Se hoje só checa validade no tempo, isso é um achado.
- [ ] Resistente a certificado autoassinado / cadeia não-confiável se passando por válido.

### E. Separação demo × produção
- [ ] Em modo demo/vitrine pública, o cadastro de certificado **real** e a assinatura com chave real estão bloqueados ou neutralizados (não deve haver upload de `.pfx` real num ambiente público).

---

## Formato da entrega (relatório, sem código)

Para cada achado:

```
[SEVERIDADE: crítico | alto | médio | baixo]
Arquivo:linha
Descrição do problema
Evidência (trecho/observação)
Recomendação (textual — NÃO um patch)
```

E, ao final, um veredicto único:

> **Go / No-Go** para expor a cadeia de assinatura A1 na UI do prescritor — com a
> lista de itens que precisam ser corrigidos antes de qualquer exposição.

Obrigado. Lembrando: **somente leitura — não modificar nada.**

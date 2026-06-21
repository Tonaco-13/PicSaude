# TICKET F2 — Validação da cadeia ICP-Brasil + revogação na verificação de assinatura

> Origem: achado **F2** da auditoria de segurança (Jules, 2026-06-19).
> Classe: **`core`** (assinatura/verificação) — exige revisão central.
> Bloqueia: NO-GO para expor a assinatura A1 na UI (junto com F3).

---

## Problema

`backend/app/domain/assinatura_icp.py: verificar_assinatura_icp` hoje valida
apenas:

1. assinatura matemática (`public_key.verify`, Passo 4);
2. validade temporal do certificado (`verificar_validade_temporal`, Passo 5).

**Não valida a cadeia de confiança até a AC-Raiz ICP-Brasil, nem a revogação.**
Consequência: um certificado **autoassinado** (ou emitido por uma CA arbitrária)
com datas válidas e assinatura matematicamente correta passa como `valida=True`.
Em um sistema de prescrição regulado, isso permite assinatura forjável.

## Objetivo (invariante)

> Uma assinatura só é `valida=True` se o certificado **encadeia até uma AC-Raiz
> ICP-Brasil confiável** e **não está revogado**.

## Abordagem — faseada

### Fase A — cadeia de confiança (mínimo para abrir o portão)
- Empacotar no repositório o **trust store ICP-Brasil**: AC-Raiz (todas as
  versões vigentes, v1…vN) + ACs intermediárias relevantes, em PEM. São
  certificados **públicos**, publicados pelo ITI.
- Validar o *path* do certificado do prescritor até uma raiz confiável; rejeitar
  autoassinado / cadeia não-ancorada.
- Biblioteca: **`pyhanko_certvalidator`** (já vem com pyHanko, que já é
  dependência) faz construção de cadeia + validação. Evita dependência nova.

### Fase B — revogação (depois de A)
- Checagem de revogação **OCSP** (preferencial) com *fallback* **CRL**.
- Definir política explícita: revogado → **hard-fail**; responder
  indisponível → política de *soft-fail* com log auditável (decisão a registrar
  no ticket de implementação).
- Cache de respostas OCSP/CRL para não pesar a cada verificação.
- (Opcional) checar OIDs de política ICP-Brasil (A1/A3).

## Escopo

**Inclui:** `assinatura_icp.py` (caminho de verificação), bundle do trust store,
testes com cadeia de teste (CA própria de teste) + caso autoassinado rejeitado.
**Não inclui:** o caminho de **assinatura** PAdES (pyHanko já assina); fluxo A3.

## Critérios de aceite
- [ ] Certificado autoassinado → `valida=False` (cadeia não-confiável).
- [ ] Certificado encadeando a CA fora do ICP-Brasil → rejeitado.
- [ ] Certificado encadeando a AC-Raiz ICP-Brasil de teste → aceito.
- [ ] (Fase B) certificado revogado → rejeitado.
- [ ] Testes cobrindo cada caso; sem regressão nos testes atuais de `assinatura_icp`.

## Esforço / riscos
- Fase A: **médio** (trust store + path validation + testes).
- Fase B: **médio-alto** (infra OCSP/CRL + política soft/hard-fail).
- Risco de manutenção: o ITI publica novas AC-Raiz periodicamente — o trust
  store precisa de um caminho de atualização documentado.

## Relação com F3
F2 torna a **identidade do certificado confiável** (encadeia ao ICP-Brasil).
F3 **amarra essa identidade ao prescritor certo** (CPF). Juntos = identidade
confiável vinculada à conta correta. Um sem o outro não fecha o portão.

# Manifesto — fontes oficiais ANVISA (staging, NÃO commitado)

Baixado pelo arquiteto (Z) em 28/08/2026 da página oficial:
https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista-substancias
Estes são os PDFs do HISTÓRICO DE EMENDAS ao Anexo I da Portaria 344/98 — não a lista consolidada.
A lista consolidada requer exportação interativa do Anvisa Legis (ver DESENHO-TALAO-DIGITAL-SNCR.md §1.1).
[Adendo 13/09/2026: a consolidada foi depositada nesta pasta — ver última entrada. Exportação via browser (Chromium/Playwright), courier Kimi.]

## PORTARIA-344-1998-CONSOLIDADA-anvisalegis-2026-09-13.pdf  —  sha256:58e88fd05cee24ac…
- Fonte (URL): https://anvisalegis.datalegis.net/action/ActionDatalegis.php?acao=abrirTextoAto&tipo=POR&numeroAto=00000344&seqAto=000&valorAno=1998&orgao=SVS/MS&codTipo=&desItem=&desItemFim=&cod_menu=1696&cod_modulo=134&pesquisa=true
- Nota de edição: TEXTO CONSOLIDADO Anvisa Legis — "VIGENTE COM ALTERAÇÕES", atualizado até a Atualização nº 101 (RDC nº 1.036, de 09/07/2026). 57 páginas A4, 4,8 MB. Capturado via Chromium headless (print-to-PDF da visualização completa) porque a rota de impressão devolve vazio para curl (§1.1 do desenho). Sem login.
- Probes de verificação: TALIDOMIDA (Lista A1) ✓ · LISTA DAS SUBSTÂNCIAS PSICOTRÓPICAS (B1) ✓ · todas as listas A1→F ✓ · ANEXOS I–IV ✓ · encerra com "Este texto não substitui a Publicação Oficial" ✓
- **Errata da transcrição (13/09, engenheiro):** a probe "TALIDOMIDA (Lista A1)" está incorreta — nas listas de substância, talidomida aparece **uma única vez, na Lista C3**, como `1.Ftalimidoglutarimida (talidomida)` (p. 31). As ocorrências das p. 47–49 estão nos ANEXOS do Termo de Esclarecimento, que não são lista de substância. A probe de captura continua válida como prova de que o PDF baixou inteiro; o que não vale é a atribuição de lista. Conferido linha a linha no PDF. Ver `docs/tickets/RECONCILIACAO-ANEXO-I-2026-09-13.md`.
- **Também da transcrição:** o consolidado traz o CÓDIGO da lista (`LISTA - B1`) além do título formal, e o código é indispensável — A3 e B1 compartilham o título "LISTA DAS SUBSTÂNCIAS PSICOTRÓPICAS", então mapear por título colapsaria as duas.
- 1ª página: MINISTÉRIO DA SAÚDE • SECRETARIA DE VIGILÂNCIA SANITÁRIA • PORTARIA Nº 344, DE 12 DE MAIO DE 1998 • Aprova o Regulamento Técnico sobre substâncias e medicamentos sujeitos a controle especial.
- Data: 13/09/2026

## f1.bin  —  sha256:f6f72a3bbc06ee4e…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6527json-file-1/@@display-file/file
- Âncora na página: republicada em 01/09/2020
- 1ª página: REPÚBLICA FEDERATIVA DO BRASIL • IMPRENSA NACIONAL Ano CLVIII Nº 168-B Brasília - DF, terça-feira, 1

## f2.bin  —  sha256:1f3a42eb9ad5b814…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6529json-file-1/@@display-file/file
- Âncora na página: RDC nº 405, de 22/07/2020
- 1ª página: 23/07/2020 RESOLUÇÃO DE DIRETORIA COLEGIADA - RDC Nº 405, DE 22 DE JULHO DE 2020 - RESOLUÇÃO DE DIRE

## f3.bin  —  sha256:10d9905dec5f5e10…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6537json-file-1/@@display-file/file
- Âncora na página: Orientações
- 1ª página: Orientação sobre a classificação genérica de substâncias proscritas CLASSE ESTRUTURAL DAS FENILETILA

## f4.bin  —  sha256:23ac10a45677c38a…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6543json-file-1/@@display-file/file
- Âncora na página: RDC n° 246, de 21/08/2018
- 1ª página: Nº 162, quarta-feira, 22 de agosto de 2018 55ISSN 1677-70421 Documento assinado digitalmente conform

## f5.bin  —  sha256:c4dc86ce27742acf…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6544json-file-1/@@display-file/file
- Âncora na página: RDC n° 227, de 17/05/2018
- 1ª página: 76 ISSN 1677-7042 Nº 97, terça-feira, 22 de maio de 2018 Documento assinado digitalmente conforme MP

## f6.bin  —  sha256:7adf6f6a091ef3ae…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6545json-file-1/@@display-file/file
- Âncora na página: RDC n° 192, de 11/12/2017
- 1ª página: Nº 237, terça-feira, 12 de dezembro de 2017 59ISSN 1677-70421 Este documento pode ser verificado no 

## f7.bin  —  sha256:e5635b5ffa561be4…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6546json-file-1/@@display-file/file
- Âncora na página: RDC n° 188, de 13/11/2017
- 1ª página: 92 ISSN 1677-7042 1 Nº 219, quinta-feira, 16 de novembro de 2017 Este documento pode ser verificado 

## f8.bin  —  sha256:5e32fb8bcb84f2a4…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6547json-file-1/@@display-file/file
- Âncora na página: RDC nº 186, de 25/10/2017
- 1ª página: Nº 205, quarta-feira, 25 de outubro de 2017 47ISSN 1677-70421 Este documento pode ser verificado no 

## f9.bin  —  sha256:abf5283eba13096c…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6548json-file-1/@@display-file/file
- Âncora na página: RDC nº 175, de 19/09/2017
- 1ª página: Nº 180, terça-feira, 19 de setembro de 2017 33ISSN 1677-7042 Este documento pode ser verificado no e

## f10.bin  —  sha256:d058c6052493dc2d…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6549json-file-1/@@display-file/file
- Âncora na página: Orientações
- 1ª página: Página 1 de 33 ORIENTAÇÕES SOBRE A CLASSIFICAÇÃO DE SUBSTÂNCIAS PROSCRITAS POR CLASSES ESTRUTURAIS D

## f11.bin  —  sha256:f3114fa1659ef15d…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6550json-file-1/@@display-file/file
- Âncora na página: RDC n° 169, de 15/08/2017
- 1ª página: Nº 158, quinta-feira, 17 de agosto de 2017166 ISSN 1677-7042 Este documento pode ser verificado no e

## f12.bin  —  sha256:e593301d2a2426fd…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6551json-file-1/@@display-file/file
- Âncora na página: RDC nº 159, de 02/06/2017
- 1ª página: Nº 106, segunda-feira, 5 de junho de 2017 103ISSN 1677-7042 Este documento pode ser verificado no en

## f13.bin  —  sha256:3fa1187ff37b3c81…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6552json-file-1/@@display-file/file
- Âncora na página: RDC nº 143, de 17/03/2017
- 1ª página: Nº 54, segunda-feira, 20 de março de 2017 55ISSN 1677-7042 Este documento pode ser verificado no end

## f14.bin  —  sha256:a273d12670209b84…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6553json-file-1/@@display-file/file
- Âncora na página: RDC nº 117, de 19/10/2016
- 1ª página: Nº 202, quinta-feira, 20 de outubro de 201632 ISSN 1677-7042 Este documento pode ser verificado no e

## f15.bin  —  sha256:696adfe045422558…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6554json-file-1/@@display-file/file
- Âncora na página: RDC nº 103, de 31/08/2016
- 1ª página: Nº 169, quinta-feira, 1 de setembro de 2016 39ISSN 1677-7042 Este documento pode ser verificado no e

## f16.bin  —  sha256:c3b29f8e20abd869…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6555json-file-1/@@display-file/file
- Âncora na página: RDC nº 87, de 28/06/2016
- 1ª página: Nº 123, quarta-feira, 29 de junho de 2016 41ISSN 1677-7042 Este documento pode ser verificado no end

## f17.bin  —  sha256:368c8ef5bd055153…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6556json-file-1/@@display-file/file
- Âncora na página: RDC nº 79, de 23/05/2016
- 1ª página: Nº 98, terça-feira, 24 de maio de 201636 ISSN 1677-7042 Este documento pode ser verificado no endere

## f18.bin  —  sha256:db3ff7eec4fc101a…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6557json-file-1/@@display-file/file
- Âncora na página: Orientações
- 1ª página: ORIENTAÇÃO SOBRE A NOVA FORMA DE CLASSIFICAÇÃO DE SUBS- TÂNCIAS PROSCRITAS POR CLASSES ESTRUTURAIS D

## f19.bin  —  sha256:42e628307e6865b6…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6558json-file-1/@@display-file/file
- Âncora na página: RDC nº 66, de 18/03/2016
- 1ª página: Nº 54, segunda-feira, 21 de março de 201628 ISSN 1677-7042 Este documento pode ser verificado no end

## f20.bin  —  sha256:dea9f035c7533059…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6559json-file-1/@@display-file/file
- Âncora na página: RDC nº 65, de 02/03/2016
- 1ª página: RESOLUÇÃO DA DIRETORIA COLEGIADA - RDC N° 65, DE 2 DE MARÇO DE 2016. Dispõe sobre a atualização do A

## f21.bin  —  sha256:cf79acbe7fc92cb5…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6560json-file-1/@@display-file/file
- Âncora na página: RDC nº 49, de 11/11/2015
- 1ª página: Página 6 de 60 EXTRATO DIÁRIO Diário Oficial da União nº 216 Brasília-DF, quinta-feira, 12 de novemb

## f22.bin  —  sha256:3459903e68158436…
- URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/lista/arquivos-controlados/6561json-file-1/@@display-file/file
- Âncora na página: RDC nº 147, de 28/05/1999
- 1ª página: Publicação - Diário Oficial Seção 1 N.º 102 Segunda -Feira, 31 Mai 1999 AGÊNCIA NACIONAL DE VIGILÂNC

/* ==========================================================================
 * catalogos-encaminhamento.js — ENG-016 §5
 *
 * Catálogos LOCAIS e VERSIONADOS do formulário de encaminhamento.
 *
 * POR QUE LOCAL, E POR QUE ARQUIVO
 * --------------------------------
 * §5 do DESENHO-ENCAMINHAMENTO-UX: "lista local versionada", "mini-catálogo
 * local (snapshot versionado)". O que a regra proíbe é a chamada externa ao
 * vivo no caminho clínico — é o R4 (§2a) aplicado à referência: identificador
 * externo entra por importação periódica e é congelado, nunca consultado ao
 * vivo enquanto o médico digita.
 *
 * Ficam em ARQUIVO (e não em tabela + endpoint) porque são dado de REFERÊNCIA
 * puro: não têm dono, não têm ciclo de vida, ninguém os edita em produção. Uma
 * tabela pediria migração, endpoint, cache e um guard de escopo para devolver
 * exatamente a mesma lista que um `<script>` entrega — complexidade sem
 * pergunta que a justifique. Versionado é o arquivo estar no git: mudou a
 * lista, aparece no diff.
 *
 * ⚠️ O MINI-CID É PARCIAL, E ISSO ESTÁ DITO
 * -----------------------------------------
 * O §5 fala em "~300 APS frequentes". Esta lista é MENOR e contém só códigos
 * verificáveis. Encher a lista até um número alvo com códigos plausíveis seria
 * pior que a lista curta: CID errado ENTRA NO HASH e viaja como declaração
 * clínica de quem emitiu. O escape "não listado" existe justamente para isso —
 * digitar o código correto é melhor que escolher um parecido.
 *
 * Completar a lista é importação de catálogo (classe `adapter`, §10): entra por
 * snapshot versionado, nunca por consulta ao vivo.
 * ========================================================================== */

window.CATALOGOS_ENCAMINHAMENTO = {
  versao: "2026-08-23.1",

  /* Especialidades — o §5 pede 10–15 na demo. A ordem é alfabética de
     propósito: ordenar por "mais usada" seria capturar demanda pela porta dos
     fundos, exatamente o que a sugestão de destino declara e mitiga. */
  especialidades: [
    "CARDIOLOGIA",
    "CIRURGIA GERAL",
    "DERMATOLOGIA",
    "ENDOCRINOLOGIA",
    "GASTROENTEROLOGIA",
    "GINECOLOGIA",
    "NEUROLOGIA",
    "OFTALMOLOGIA",
    "ORTOPEDIA",
    "OTORRINOLARINGOLOGIA",
    "PEDIATRIA",
    "PNEUMOLOGIA",
    "PSIQUIATRIA",
    "REUMATOLOGIA",
    "UROLOGIA",
  ],

  /* Finalidade estruturada (§5). Os códigos são os do backend
     (`FINALIDADES_ENCAMINHAMENTO`); o rótulo é o que o médico lê. */
  finalidades: [
    { codigo: "avaliacao",          rotulo: "Avaliação especializada" },
    { codigo: "conduta",            rotulo: "Definição de conduta" },
    { codigo: "exame_complementar", rotulo: "Exame complementar" },
    { codigo: "segunda_opiniao",    rotulo: "Segunda opinião" },
    { codigo: "seguimento",         rotulo: "Seguimento compartilhado" },
    { codigo: "outra",              rotulo: "Outra (especificar)" },
  ],

  /* Mini-CID — snapshot parcial de condições frequentes na APS.
     Ver o aviso no topo: parcial de propósito, com escape validado. */
  cid: [
    { codigo: "E11",   descricao: "Diabetes mellitus tipo 2" },
    { codigo: "E10",   descricao: "Diabetes mellitus tipo 1" },
    { codigo: "E78",   descricao: "Distúrbios do metabolismo de lipoproteínas" },
    { codigo: "E66",   descricao: "Obesidade" },
    { codigo: "E03",   descricao: "Hipotireoidismo" },
    { codigo: "E05",   descricao: "Tireotoxicose (hipertireoidismo)" },
    { codigo: "I10",   descricao: "Hipertensão essencial (primária)" },
    { codigo: "I20",   descricao: "Angina pectoris" },
    { codigo: "I25",   descricao: "Doença isquêmica crônica do coração" },
    { codigo: "I48",   descricao: "Fibrilação e flutter atrial" },
    { codigo: "I50",   descricao: "Insuficiência cardíaca" },
    { codigo: "I64",   descricao: "Acidente vascular cerebral não especificado" },
    { codigo: "I83",   descricao: "Varizes dos membros inferiores" },
    { codigo: "J45",   descricao: "Asma" },
    { codigo: "J44",   descricao: "Doença pulmonar obstrutiva crônica" },
    { codigo: "J30",   descricao: "Rinite alérgica" },
    { codigo: "J01",   descricao: "Sinusite aguda" },
    { codigo: "K21",   descricao: "Doença de refluxo gastroesofágico" },
    { codigo: "K29",   descricao: "Gastrite e duodenite" },
    { codigo: "K80",   descricao: "Colelitíase" },
    { codigo: "K40",   descricao: "Hérnia inguinal" },
    { codigo: "K59",   descricao: "Outros transtornos funcionais do intestino" },
    { codigo: "M54",   descricao: "Dorsalgia" },
    { codigo: "M17",   descricao: "Gonartrose (artrose do joelho)" },
    { codigo: "M16",   descricao: "Coxartrose (artrose do quadril)" },
    { codigo: "M79",   descricao: "Outros transtornos dos tecidos moles" },
    { codigo: "M81",   descricao: "Osteoporose sem fratura patológica" },
    { codigo: "M06",   descricao: "Outras artrites reumatoides" },
    { codigo: "M10",   descricao: "Gota" },
    { codigo: "N18",   descricao: "Doença renal crônica" },
    { codigo: "N20",   descricao: "Calculose do rim e do ureter" },
    { codigo: "N39",   descricao: "Outros transtornos do trato urinário" },
    { codigo: "N40",   descricao: "Hiperplasia da próstata" },
    { codigo: "N92",   descricao: "Menstruação excessiva, frequente e irregular" },
    { codigo: "F32",   descricao: "Episódios depressivos" },
    { codigo: "F41",   descricao: "Outros transtornos ansiosos" },
    { codigo: "F17",   descricao: "Transtornos por uso de tabaco" },
    { codigo: "F10",   descricao: "Transtornos por uso de álcool" },
    { codigo: "G43",   descricao: "Enxaqueca" },
    { codigo: "G40",   descricao: "Epilepsia" },
    { codigo: "G47",   descricao: "Distúrbios do sono" },
    { codigo: "H25",   descricao: "Catarata senil" },
    { codigo: "H40",   descricao: "Glaucoma" },
    { codigo: "H52",   descricao: "Transtornos da acomodação e da refração" },
    { codigo: "H66",   descricao: "Otite média supurativa" },
    { codigo: "H90",   descricao: "Perda de audição por transtorno condutivo/neurossensorial" },
    { codigo: "L20",   descricao: "Dermatite atópica" },
    { codigo: "L40",   descricao: "Psoríase" },
    { codigo: "L70",   descricao: "Acne" },
    { codigo: "D50",   descricao: "Anemia por deficiência de ferro" },
    { codigo: "R07",   descricao: "Dor de garganta e no peito" },
    { codigo: "R10",   descricao: "Dor abdominal e pélvica" },
    { codigo: "R51",   descricao: "Cefaleia" },
    { codigo: "R42",   descricao: "Tontura e instabilidade" },
    { codigo: "Z00",   descricao: "Exame geral e investigação de pessoas sem queixa" },
  ],
};

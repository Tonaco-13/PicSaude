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

  // CBO:GERADO-INICIO — NÃO EDITAR À MÃO. Bloco regenerado por
  // backend/scripts/importar_snapshot_cbo_encaminhamento.py (DESENHO-
  // TYPEAHEAD-ENCAMINHAMENTO-CBO.md §3, PR `adapter`). Mudar a base é
  // editar a FONTE VERIFICADA no script e rodá-lo de novo — nunca editar
  // o array abaixo diretamente (drift entre script e arquivo é exatamente
  // o defeito que "importação versionada" existe para evitar).
  especialidades: [
    { titulo: "CARDIOLOGIA",          codigo: "2251-20", familia: "2251" },
    { titulo: "CIRURGIA GERAL",       codigo: "2252-25", familia: "2252" },
    { titulo: "DERMATOLOGIA",         codigo: "2251-35", familia: "2251" },
    { titulo: "ENDOCRINOLOGIA",       codigo: "2251-55", familia: "2251" },
    { titulo: "ENFERMAGEM",           codigo: "2235-05", familia: "2235" },
    { titulo: "FISIOTERAPIA",         codigo: "2236-05", familia: "2236" },
    { titulo: "FONOAUDIOLOGIA",       codigo: "2238-10", familia: "2238" },
    { titulo: "GASTROENTEROLOGIA",    codigo: "2251-65", familia: "2251" },
    { titulo: "GINECOLOGIA",          codigo: "2252-50", familia: "2252" },
    { titulo: "NEUROLOGIA",           codigo: "2251-12", familia: "2251" },
    { titulo: "NUTRIÇÃO",             codigo: "2237-10", familia: "2237" },
    { titulo: "ODONTOLOGIA",          codigo: "2232-08", familia: "2232" },
    { titulo: "OFTALMOLOGIA",         codigo: "2252-65", familia: "2252" },
    { titulo: "ORTOPEDIA",            codigo: "2252-70", familia: "2252" },
    { titulo: "OTORRINOLARINGOLOGIA", codigo: "2252-75", familia: "2252" },
    { titulo: "PEDIATRIA",            codigo: "2251-24", familia: "2251" },
    { titulo: "PNEUMOLOGIA",          codigo: "2251-27", familia: "2251" },
    { titulo: "PSICOLOGIA",           codigo: "2515-10", familia: "2515" },
    { titulo: "PSIQUIATRIA",          codigo: "2251-33", familia: "2251" },
    { titulo: "REUMATOLOGIA",         codigo: "2251-36", familia: "2251" },
    { titulo: "UROLOGIA",             codigo: "2252-85", familia: "2252" },
  ],

  especialidadesFonte: {
    fonte: "CBO/MTE — Portaria 397/2002",
    versao: "CBO 2002",
    unidade: "entradas",
    data_snapshot: "2026-08-28",
    familias_incluidas: {
      "2251": "Médicos clínicos",
      "2252": "Médicos em especialidades cirúrgicas",
      "2232": "Cirurgiões-dentistas",
      "2235": "Enfermeiros e afins",
      "2236": "Fisioterapeutas",
      "2237": "Nutricionistas",
      "2238": "Fonoaudiólogos",
      "2515": "Psicólogos e psicanalistas",
    },
  },
  // CBO:GERADO-FIM

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

  /* Provenância do mini-CID — mesma disciplina da especialidade acima:
     `total` sempre de `cid.length`, nunca duplicado aqui. Sem `versao`
     de propósito — o mini-CID não é um snapshot datado, é uma lista
     parcial e permanentemente incompleta (ver aviso no topo do arquivo). */
  cidFonte: {
    fonte: "parcial",
    unidade: "códigos verificáveis",
  },

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

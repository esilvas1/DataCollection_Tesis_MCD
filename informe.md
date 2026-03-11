---
title: "Recopilación de Información del Proyecto"
lang: es
header-includes: |
  <style>
    html { background-color: #1e1e1e; color: #c5c8c6; }
    body {
      margin: 0 auto;
      max-width: 52em;
      padding: 50px;
      background-color: #252526;
      color: #c5c8c6;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      hyphens: auto;
      overflow-wrap: break-word;
      text-rendering: optimizeLegibility;
      font-kerning: normal;
      border-radius: 6px;
      box-shadow: 0 2px 16px rgba(0,0,0,0.6);
      line-height: 1.7;
    }
    @media (max-width: 600px) {
      body { font-size: 0.9em; padding: 12px; }
      h1 { font-size: 1.8em; }
    }
    @media print {
      html { background-color: white; }
      body { background-color: transparent; color: black; font-size: 12pt; }
      p, h2, h3 { orphans: 3; widows: 3; }
      h2, h3, h4 { page-break-after: avoid; }
    }
    p { margin: 1em 0; color: #c5c8c6; }
    a { color: #7ec0ed; }
    a:visited { color: #9872a2; }
    img { max-width: 100%; }
    svg { height: auto; max-width: 100%; }
    h1 { color: #7ec0ed; border-bottom: 3px solid #7ec0ed; padding-bottom: 8px; margin-top: 1.4em; }
    h2 { color: #9872a2; margin-top: 1.4em; }
    h3 { color: #7ec48c; margin-top: 1.4em; }
    h4, h5, h6 { color: #c5c8c6; margin-top: 1.4em; }
    h5, h6 { font-size: 1em; font-style: italic; }
    h6 { font-weight: normal; }
    strong { color: #7ec48c; }
    em { color: #b5cea8; }
    ol, ul { padding-left: 1.7em; margin-top: 1em; }
    li > ol, li > ul { margin-top: 0; }
    li { color: #c5c8c6; margin: 4px 0; }
    blockquote {
      margin: 1em 0 1em 1.7em;
      padding-left: 1em;
      border-left: 3px solid #9872a2;
      color: #808080;
    }
    code {
      font-family: Menlo, Monaco, Consolas, 'Lucida Console', monospace;
      font-size: 85%;
      background-color: #1e1e1e;
      color: #7ec48c;
      padding: 1px 4px;
      border-radius: 3px;
      hyphens: manual;
      white-space: pre-wrap;
    }
    pre {
      margin: 1em 0;
      overflow: auto;
      background-color: #1e1e1e;
      padding: 16px;
      border-radius: 5px;
      border-left: 4px solid #7ec0ed;
    }
    pre code { padding: 0; overflow: visible; overflow-wrap: normal; background-color: transparent; color: #c5c8c6; }
    hr { border: none; border-top: 2px solid #3e3e42; margin: 1.5em 0; }
    table { margin: 1em 0; border-collapse: collapse; width: 100%; overflow-x: auto; display: block; font-variant-numeric: lining-nums tabular-nums; }
    table caption { margin-bottom: 0.75em; color: #808080; }
    tbody { margin-top: 0.5em; border-top: 1px solid #3e3e42; border-bottom: 1px solid #3e3e42; }
    th { border-top: 1px solid #3e3e42; padding: 0.25em 0.5em; background-color: #2d2d2d; color: #7ec0ed; }
    td { padding: 0.125em 0.5em 0.25em 0.5em; color: #c5c8c6; border-bottom: 1px solid #3e3e42; }
    header { margin-bottom: 4em; text-align: center; }
    #TOC li { list-style: none; }
    #TOC ul { padding-left: 1.3em; }
    #TOC > ul { padding-left: 0; }
    #TOC a:not(:hover) { text-decoration: none; }
    span.smallcaps { font-variant: small-caps; }
    div.columns { display: flex; gap: min(4vw, 1.5em); }
    div.column { flex: auto; overflow-x: auto; }
    div.hanging-indent { margin-left: 1.5em; text-indent: -1.5em; }
    ul.task-list[class] { list-style: none; }
    ul.task-list li input[type="checkbox"] { font-size: inherit; width: 0.8em; margin: 0 0.8em 0.2em -1.6em; vertical-align: middle; }
    .display.math { display: block; text-align: center; margin: 0.5rem auto; }
    /* Override pandoc syntax highlighting for dark theme (Monokai Dimmed) */
    div.sourceCode { background-color: #1e1e1e; border-radius: 5px; border-left: 4px solid #7ec0ed; padding: 4px 0; margin: 1em 0; }
    pre.sourceCode { background-color: transparent; padding: 12px 16px; margin: 0; }
    code.sourceCode { background-color: transparent; color: #c5c8c6; }
    code span.kw { color: #9872a2; font-weight: bold; }  /* Keyword */
    code span.cf { color: #9872a2; font-weight: bold; }  /* ControlFlow */
    code span.ot { color: #9872a2; }                     /* Other */
    code span.fu { color: #7ec0ed; }                     /* Function */
    code span.dt { color: #7ec0ed; }                     /* DataType */
    code span.st { color: #7ec48c; }                     /* String */
    code span.ch { color: #7ec48c; }                     /* Char */
    code span.ss { color: #7ec48c; }                     /* SpecialString */
    code span.vs { color: #7ec48c; }                     /* VerbatimString */
    code span.im { color: #7ec48c; font-weight: normal; } /* Import */
    code span.dv { color: #b5cea8; }                     /* DecVal */
    code span.bn { color: #b5cea8; }                     /* BaseN */
    code span.fl { color: #b5cea8; }                     /* Float */
    code span.pp { color: #b5cea8; }                     /* Preprocessor */
    code span.co { color: #6a9955; font-style: italic; } /* Comment */
    code span.in { color: #6a9955; font-style: italic; } /* Information */
    code span.an { color: #6a9955; font-style: italic; } /* Annotation */
    code span.wa { color: #dcdcaa; font-style: italic; } /* Warning */
    code span.op { color: #c5c8c6; }                     /* Operator */
    code span.va { color: #9cdcfe; }                     /* Variable */
    code span.at { color: #9cdcfe; }                     /* Attribute */
    code span.sc { color: #7ec48c; }                     /* SpecialChar */
    code span.er { color: #f44747; font-weight: bold; }  /* Error */
    code span.al { color: #f44747; font-weight: bold; }  /* Alert */
    code span.ex { color: #c5c8c6; }                     /* Extension */
  </style>
---

## PROYECTO:

Desarrollo de Metodología Basada en Métodos de Ciencia de Datos para Predecir Indicadores de Calidad del Servicio (SAIDI y SAIFI)

## Objetivo del Proyecto


Desarrollar una metodología predictiva basada en ciencia de datos para anticipar los indicadores de calidad del servicio eléctrico SAIDI (System Average Interruption Duration Index) y SAIFI (System Average Interruption Frequency Index) en redes de distribución eléctrica de una empresa de energía en el Norte de Santander.

# Fuentes de información:


- Base regultoria de Activos - (BRAE)
- Sistema de Gestion de Interrupciones - Outage Management System  (OMS)
- Sistema de información Geografica - Geographic Information System (GIS)
- Sistema de Administración Comercial - (SAC)
- Sistema de Administración de Activos - Enterprise Asset Management(EAM) 
- Fuentes externas climatologicas (Ideam, DHIME)

## Nota sobre el sistema OMS

A partir del año 2023, la Electrificadora de Norte de Santander realizó una migración de su sistema de gestión de interrupciones. Como resultado, la recopilación de información de interrupciones eléctricas se realizó a partir de **dos bases de datos provenientes de sistemas distintos**:

- **OMS Energy** — sistema utilizado hasta antes de la migración, del cual se extrae la información histórica de interrupciones previas a 2023.
- **OMS SP7 de Siemens** — nuevo sistema implementado desde 2023, del cual se obtiene la información de interrupciones a partir de dicha fecha.

Esta dualidad de fuentes implica diferencias estructurales en los esquemas de datos (nombres de campos, codificaciones, granularidad) que fueron consideradas durante el proceso de integración y homologación de la información.

## Ejemplo de consulta_1 SQL — Extracción de eventos de interrupción

A continuación se muestra un ejemplo representativo de la consulta utilizada para extraer los eventos de interrupción del sistema OMS Energy:

```sql
SELECT FDD_CODIGOEVENTO AS ID_EVENTO
	  ,FDD_FINICIAL AS FECHA_INICIO
	  ,FDD_FFINAL AS FECHA_FIN
	  ,'' AS ELEMENTO_FALLADO
	  ,FDD_CODIGOELEMENTO AS ELEMENTO_AFECTADO
FROM BRAE.QA_TFDDREGISTRO
WHERE TO_CHAR(FDD_FINICIAL,'YYYY') IN ('2021', '2022', '2023', '2024', '2025')  
AND FDD_EXCLUSION = 'NO EXCLUIDA'
AND FDD_CAUSA_SSPD NOT IN (1)
AND FDD_FFINAL IS NOT NULL;

```

**Muestra de resultados (5 registros):**

| ID_EVENTO | FECHA_INICIO | FECHA_FIN | ELEMENTO_FALLADO | ELEMENTO_AFECTADO |
|-----------|-------------|-----------|------------------|-------------------|
| 801851 | 14/03/21 06:59:00 | 14/03/21 09:30:00 |  | 2T00469 |
| 801851 | 14/03/21 06:59:00 | 14/03/21 09:30:00 |  | 2T00641 |
| 801851 | 14/03/21 06:59:00 | 14/03/21 09:30:00 |  | 2T00471 |
| 787355 | 02/01/21 06:41:14 | 02/01/21 15:00:00 |  | 1T04758 |
| 787355 | 02/01/21 06:41:14 | 02/01/21 15:00:00 |  | 1T07090 |



```sql
SELECT DISTINCT MINICIAL as CODIGO_MANIOBRA, BREAKER AS ELEMENTO_FALLADO
FROM OMS.INTERUPC
LEFT JOIN OMS.MANIOBRAS ON INTERUPC.MINICIAL = MANIOBRAS.CODE
WHERE TO_NUMBER(TO_CHAR(INTERUPC.FINICIAL, 'YYYY')) >= 2019
AND TIPO != 'PRUEBA'
AND CAUSA != 'PRUEBA'
AND INTERUPC.TYPEEQUIP != 'Transformer';

```

**Muestra de resultados (5 registros):**

| CODIGO_MANIOBRA | ELEMENTO_FALLADO |
|-----------------|------------------|
| MAN-00412 | CB_NORTE_01 |
| MAN-00587 | CB_CENTRO_03 |
| MAN-00731 | CB_SUR_02 |
| MAN-00865 | CB_ORIENTE_05 |
| MAN-01024 | CB_NORTE_04 |

> *Nota: Los valores mostrados son ilustrativos. Los datos reales provienen de la tabla `OMS.INTERUPC` del sistema OMS Energy.*


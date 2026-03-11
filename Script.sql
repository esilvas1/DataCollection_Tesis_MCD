select * from qa_tfddregistro;

create table brae.qa_telemento_fallado (
    codigo_manobra varchar2(100),
    elemento_fallado varchar2(100)
);



SELECT DISTINCT FDD_PERIODO_TC1 
FROM QA_TFDDREGISTRO
WHERE FDD_ELEMENTOFALLA IS NULL
ORDER BY 1;




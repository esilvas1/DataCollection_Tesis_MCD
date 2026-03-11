LOAD DATA
CHARACTERSET AL32UTF8
SKIP 1
INFILE 'D:\OneDrive - Grupo EPM\8. UNIVERSIDAD JAVERIANA\Applied Project I\Project\Data Collection\DATA\ID_Elementos_Causantes.csv'
INTO TABLE brae.qa_telemento_fallado
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
TRAILING NULLCOLS
(
  codigo_manobra,
  elemento_fallado
)

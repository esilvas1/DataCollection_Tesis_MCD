import re
from datetime import datetime

def extract_cells_from_sqlnb(sqlnb_file):
    """Extrae las celdas del archivo .sqlnb (formato YAML)"""
    try:
        with open(sqlnb_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        cells = []
        
        # Dividir por celdas usando el patrón "- kind:"
        cell_blocks = re.split(r'- kind:', content)[1:]  # Ignorar el primer split vacío
        
        for block in cell_blocks:
            # Extraer el tipo de celda (1=markdown, 2=code)
            kind_match = re.search(r'^\s*(\d+)', block)
            if not kind_match:
                continue
            
            kind = kind_match.group(1)
            language = 'markdown' if kind == '1' else 'oracle-sql'
            
            # Extraer el contenido entre comillas
            value_match = re.search(r'value:\s*["\'](.+?)["\'](?:\s|$)', block, re.DOTALL)
            if not value_match:
                # Intentar con multilinea
                value_match = re.search(r'value:\s*"(.*?)"', block, re.DOTALL)
            
            if value_match:
                cell_content = value_match.group(1)
                # Limpiar escape characters
                cell_content = cell_content.replace('\\r\\n', '\n').replace('\\n', '\n')
                cell_content = cell_content.replace('\\"', '"')
                
                cells.append({
                    'language': language,
                    'content': cell_content.strip()
                })
        
        return cells
    except Exception as e:
        print(f"Error al leer el archivo .sqlnb: {e}")
        import traceback
        traceback.print_exc()
        return []

def highlight_sql(sql_code):
    """Aplica resaltado de sintaxis SQL"""
    # Keywords SQL
    keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'AS', 'JOIN', 
                'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'LIKE', 'IS', 'NULL']
    
    # Functions
    functions = ['TO_CHAR', 'TO_DATE', 'ROUND', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN']
    
    result = sql_code
    
    # Resaltar funciones
    for func in functions:
        result = re.sub(f'\\b{func}\\b', f'<span class="function">{func}</span>', result, flags=re.IGNORECASE)
    
    # Resaltar keywords
    for keyword in keywords:
        result = re.sub(f'\\b{keyword}\\b', f'<span class="keyword">{keyword}</span>', result, flags=re.IGNORECASE)
    
    # Resaltar strings
    result = re.sub(r"'([^']*)'", r"<span class='string'>'\1'</span>", result)
    
    # Resaltar números
    result = re.sub(r'\b(\d+)\b', r'<span class="number">\1</span>', result)
    
    return result

def generate_html(cells, output_file):
    """Genera el archivo HTML a partir de las celdas extraídas"""
    
    html_header = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Recopilación de Información - Proyecto SAIDI/SAIFI</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
            line-height: 1.6;
        }
        .container {
            background-color: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 { 
            color: #2c3e50; 
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 { 
            color: #34495e; 
            margin-top: 30px;
        }
        h3 { 
            color: #7f8c8d; 
            margin-top: 25px;
        }
        .sql-code {
            background-color: #282c34;
            color: #abb2bf;
            padding: 20px;
            border-radius: 5px;
            overflow-x: auto;
            font-family: 'Courier New', Consolas, monospace;
            font-size: 14px;
            margin: 15px 0;
            border-left: 4px solid #61dafb;
            white-space: pre;
        }
        .keyword { color: #c678dd; font-weight: bold; }
        .string { color: #98c379; }
        .function { color: #61dafb; }
        .number { color: #d19a66; }
        .markdown-content {
            margin: 20px 0;
        }
        .info-box {
            background-color: #e8f4f8;
            padding: 20px;
            border-left: 4px solid #3498db;
            margin: 20px 0;
            border-radius: 4px;
        }
        hr {
            border: none;
            border-top: 2px solid #ecf0f1;
            margin: 30px 0;
        }
        strong {
            color: #2c3e50;
        }
        .section-title {
            background-color: #34495e;
            color: white;
            padding: 10px 15px;
            border-radius: 4px;
            margin-top: 30px;
        }
        ul, ol {
            margin: 10px 0;
            padding-left: 30px;
        }
        li {
            margin: 5px 0;
        }
    </style>
</head>
<body>
    <div class="container">
"""
    
    html_footer = """
        <hr>
        <footer style="text-align: center; color: #7f8c8d; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ecf0f1;">
            <p><strong>Pontificia Universidad Javeriana</strong></p>
            <p>Applied Project I - Grupo EPM</p>
            <p>Norte de Santander, Colombia</p>
            <p style="font-size: 0.9em; margin-top: 10px;">Generado el {date}</p>
        </footer>
    </div>
</body>
</html>
"""
    
    html_content = html_header
    sql_counter = 1
    
    for i, cell in enumerate(cells):
        if cell['language'] == 'markdown':
            # Convertir markdown básico a HTML
            content = cell['content']
            
            # Convertir headers
            content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
            content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
            content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
            
            # Convertir bold
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            
            # Convertir líneas separadoras
            content = content.replace('---', '<hr>')
            
            # Convertir párrafos
            paragraphs = content.split('\n\n')
            formatted_paragraphs = []
            for p in paragraphs:
                p = p.strip()
                if p and not p.startswith('<'):
                    formatted_paragraphs.append(f'<p>{p}</p>')
                else:
                    formatted_paragraphs.append(p)
            
            content = '\n'.join(formatted_paragraphs)
            
            html_content += f'<div class="markdown-content">\n{content}\n</div>\n'
            
        elif cell['language'] == 'oracle-sql':
            sql_code = cell['content'].strip()
            if sql_code:
                highlighted_sql = highlight_sql(sql_code)
                
                # Agregar título de sección para cada consulta
                if sql_counter > 1:
                    html_content += f'''
        <div class="section-title">
            <h3 style="margin: 0;">📝 Consulta {sql_counter}</h3>
        </div>
'''
                
                html_content += f'''
        <div class="sql-code">{highlighted_sql}</div>
'''
                sql_counter += 1
    
    # Agregar footer con fecha actual
    html_content += html_footer.format(date=datetime.now().strftime('%d de %B de %Y'))
    
    # Guardar archivo HTML
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ HTML generado exitosamente: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Error al guardar el archivo HTML: {e}")
        return False

def main():
    """Función principal"""
    sqlnb_file = 'Collection_Script.sqlnb'
    html_file = 'Collection_Script.html'
    
    print("🔄 Actualizando HTML desde archivo .sqlnb...")
    print(f"📂 Leyendo: {sqlnb_file}")
    
    # Extraer celdas
    cells = extract_cells_from_sqlnb(sqlnb_file)
    
    if not cells:
        print("❌ No se pudieron extraer las celdas del archivo .sqlnb")
        return
    
    print(f"✅ {len(cells)} celdas extraídas")
    
    # Generar HTML
    print(f"📝 Generando HTML: {html_file}")
    success = generate_html(cells, html_file)
    
    if success:
        print("\n🎉 ¡Proceso completado exitosamente!")
        print(f"📄 Archivo HTML actualizado: {html_file}")
    else:
        print("\n❌ Hubo un error al generar el HTML")

if __name__ == "__main__":
    main()

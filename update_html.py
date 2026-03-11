import json
import os
import re
from collections import Counter
from datetime import datetime
from html import escape

def extract_cells_from_sqlnb(sqlnb_file):
    """Extrae las celdas del archivo .sqlnb (JSON tipo notebook o YAML ligero)"""
    try:
        with open(sqlnb_file, 'r', encoding='utf-8-sig') as f:
            raw = f.read()

        cells = []
        stripped = raw.lstrip()

        if stripped.startswith('{') or stripped.startswith('['):
            data = json.loads(raw)
            for cell in data.get('cells', []):
                cell_type = cell.get('cell_type', '').lower()
                language = 'markdown' if cell_type == 'markdown' else cell.get('metadata', {}).get('language', 'oracle-sql')

                source = cell.get('source', [])
                if isinstance(source, list):
                    cell_content = '\n'.join(source)
                else:
                    cell_content = str(source)

                cell_content = cell_content.replace('\r\n', '\n').replace('\r', '\n')

                cells.append({
                    'language': language,
                    'content': cell_content.strip()
                })
        else:
            current = None
            buffer = []
            in_value = False

            def finalize_cell():
                nonlocal current, buffer
                if current is not None:
                    cell_content = '\n'.join(buffer)
                    cell_content = cell_content.replace('\\r\\n', '\n').replace('\\n', '\n')
                    cell_content = cell_content.replace('\\t', '\t')
                    cell_content = cell_content.replace('\\"', '"')
                    cell_content = cell_content.replace('\\r', '')
                    cell_content = cell_content.replace('\r', '')
                    current['content'] = cell_content.strip()
                    cells.append(current)
                current = None
                buffer = []

            for line in raw.splitlines():
                kind_match = re.match(r'^\s*-\s*kind:\s*(\d+)\s*$', line)
                if kind_match and not in_value:
                    finalize_cell()
                    kind = kind_match.group(1)
                    current = {'language': 'markdown' if kind == '1' else 'oracle-sql'}
                    continue

                if current is None:
                    continue

                if in_value:
                    if line.rstrip().endswith('"'):
                        buffer.append(line.rstrip()[:-1])
                        in_value = False
                    else:
                        buffer.append(line)
                    continue

                value_match = re.match(r'^\s*value:\s*(.*)$', line)
                if value_match:
                    value_part = value_match.group(1)
                    if value_part.startswith('"'):
                        value_part = value_part[1:]
                        if value_part.rstrip().endswith('"'):
                            buffer.append(value_part.rstrip()[:-1])
                        else:
                            buffer.append(value_part)
                            in_value = True
                    else:
                        buffer.append(value_part)
                    continue

                lang_match = re.match(r'^\s*languageId:\s*(.+)$', line)
                if lang_match:
                    lang = lang_match.group(1).strip().lower()
                    current['language'] = 'markdown' if lang == 'markdown' else lang
                    continue

            finalize_cell()

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

def _scan_csv_inventory(data_dir):
    inventory = []
    if not os.path.isdir(data_dir):
        return inventory

    for file_name in sorted(os.listdir(data_dir)):
        if not file_name.lower().endswith('.csv'):
            continue
        file_path = os.path.join(data_dir, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = iter(f)
                header_line = next(reader, '')
                header = [h.strip().strip('"') for h in header_line.split(',')] if header_line else []
                row_count = 0
                for _ in reader:
                    row_count += 1

            inventory.append({
                'file': file_name,
                'rows': row_count,
                'columns': len(header),
                'sample_columns': header[:6]
            })
        except Exception:
            inventory.append({
                'file': file_name,
                'rows': 0,
                'columns': 0,
                'sample_columns': ['Error al leer']
            })

    return inventory


def _analyze_event_files(data_dir):
    result = {
        'total_events': 0,
        'avg_duration_min': None,
        'by_period': Counter(),
        'by_cause': Counter(),
        'by_file': Counter()
    }
    duration_sum = 0.0
    duration_count = 0

    if not os.path.isdir(data_dir):
        return result

    event_files = [
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.lower().startswith('eventos_brae_part') and f.lower().endswith('.csv')
    ]

    for file_path in sorted(event_files):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.read().splitlines()
            if not lines:
                continue
            header = [h.strip().strip('"') for h in lines[0].split(',')]
            index = {name: idx for idx, name in enumerate(header)}
            for row in lines[1:]:
                if not row.strip():
                    continue
                parts = row.split(',')
                result['total_events'] += 1
                result['by_file'][os.path.basename(file_path)] += 1

                if 'MES_PERIODO' in index and index['MES_PERIODO'] < len(parts):
                    value = parts[index['MES_PERIODO']].strip().strip('"')
                    if value:
                        result['by_period'][value] += 1

                if 'ID_CAUSA_SSPD' in index and index['ID_CAUSA_SSPD'] < len(parts):
                    value = parts[index['ID_CAUSA_SSPD']].strip().strip('"')
                    if value:
                        result['by_cause'][value] += 1

                if 'DURACION_EVENTO_MIN' in index and index['DURACION_EVENTO_MIN'] < len(parts):
                    value = parts[index['DURACION_EVENTO_MIN']].strip().strip('"')
                    try:
                        duration_sum += float(value)
                        duration_count += 1
                    except ValueError:
                        pass
        except Exception:
            continue

    if duration_count:
        result['avg_duration_min'] = round(duration_sum / duration_count, 2)

    return result


def _analyze_elemento_fallado(data_dir):
    result = Counter()
    file_path = os.path.join(data_dir, 'Elemento_Fallado_OMS.csv')
    if not os.path.isfile(file_path):
        return result
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
        if not lines:
            return result
        header = [h.strip().strip('"') for h in lines[0].split(',')]
        index = {name: idx for idx, name in enumerate(header)}
        element_idx = index.get('ELEMENTO_FALLADO')
        if element_idx is None:
            return result
        for row in lines[1:]:
            parts = row.split(',')
            if element_idx < len(parts):
                value = parts[element_idx].strip().strip('"')
                if value:
                    result[value] += 1
    except Exception:
        return result
    return result


def _render_bar_chart_html(title, items, unit='registros'):
    if not items:
        return f"<p><em>No hay datos para {escape(title)}.</em></p>"
    max_value = max(value for _, value in items) or 1
    rows = []
    for label, value in items:
        width = (value / max_value) * 100
        rows.append(
            f"<div class='bar-row'>"
            f"<div class='bar-label'>{escape(label)}</div>"
            f"<div class='bar' style='width:{width:.1f}%;'></div>"
            f"<div class='bar-value'>{value} {escape(unit)}</div>"
            f"</div>"
        )
    return (
        f"<div class='bar-chart'>"
        f"<h3 class='section-title-text'>{escape(title)}</h3>"
        f"{''.join(rows)}"
        f"</div>"
    )


def _render_inventory_html(inventory, event_summary, elemento_top):
    if not inventory:
        return '<p><em>No se encontraron archivos CSV para inventariar.</em></p>'

    rows = []
    for item in inventory:
        columns = ', '.join(item['sample_columns']) if item['sample_columns'] else '—'
        rows.append(
            "<tr>"
            f"<td>{escape(item['file'])}</td>"
            f"<td>{item['rows']}</td>"
            f"<td>{item['columns']}</td>"
            f"<td>{escape(columns)}</td>"
            "</tr>"
        )

    avg_duration = event_summary.get('avg_duration_min')
    avg_duration_text = f"{avg_duration} min" if avg_duration is not None else 'No disponible'

    elemento_rows = ''
    for label, value in elemento_top:
        elemento_rows += f"<li>{escape(label)}: {value}</li>"

    return (
        "<div class='info-box'>"
        "<h3>Inventario de registros</h3>"
        "<div class='table-wrapper'>"
        "<table>"
        "<thead><tr><th>Archivo</th><th>Registros</th><th>Columnas</th><th>Columnas clave</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
        "<h3>Análisis interno de eventos (desconexiones)</h3>"
        f"<p><strong>Total de eventos:</strong> {event_summary.get('total_events', 0)}</p>"
        f"<p><strong>Duración promedio:</strong> {avg_duration_text}</p>"
        "<h3>Elementos fallados más frecuentes</h3>"
        f"<ul>{elemento_rows or '<li>No disponible</li>'}</ul>"
        "</div>"
    )


def generate_html(cells, output_file, data_dir='DATA'):
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
            background-color: #1e1e1e;
            color: #c5c8c6;
            line-height: 1.6;
        }
        .container {
            background-color: #252526;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 16px rgba(0,0,0,0.6);
        }
        h1 { 
            color: #7ec0ed; 
            border-bottom: 3px solid #7ec0ed;
            padding-bottom: 10px;
        }
        h2 { 
            color: #9872a2; 
            margin-top: 30px;
        }
        h3 { 
            color: #7ec48c; 
            margin-top: 25px;
        }
        p {
            color: #c5c8c6;
        }
        .sql-code {
            background-color: #1e1e1e;
            color: #c5c8c6;
            padding: 20px;
            border-radius: 5px;
            overflow-x: auto;
            font-family: 'Courier New', Consolas, monospace;
            font-size: 14px;
            margin: 15px 0;
            border-left: 4px solid #7ec0ed;
            white-space: pre;
        }
        .keyword { color: #9872a2; font-weight: bold; }
        .string { color: #7ec48c; }
        .function { color: #7ec0ed; }
        .number { color: #b5cea8; }
        .markdown-content {
            margin: 20px 0;
        }
        .info-box {
            background-color: #2d2d2d;
            padding: 20px;
            border-left: 4px solid #7ec0ed;
            margin: 20px 0;
            border-radius: 4px;
            color: #c5c8c6;
        }
        hr {
            border: none;
            border-top: 2px solid #3e3e42;
            margin: 30px 0;
        }
        strong {
            color: #7ec48c;
        }
        .section-title {
            background-color: #2d2d2d;
            color: #c5c8c6;
            padding: 10px 15px;
            border-radius: 4px;
            margin-top: 30px;
            border-left: 3px solid #9872a2;
        }
        .section-title-text {
            margin: 0 0 10px 0;
            color: #7ec48c;
            font-size: 1.05rem;
        }
        .table-wrapper {
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0 20px 0;
            font-size: 14px;
        }
        th, td {
            text-align: left;
            padding: 8px 10px;
            border-bottom: 1px solid #3e3e42;
            color: #c5c8c6;
        }
        th {
            background-color: #2d2d2d;
            color: #7ec0ed;
        }
        .bar-chart {
            margin: 15px 0 25px 0;
        }
        .bar-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 6px 0;
        }
        .bar-label {
            width: 280px;
            font-size: 13px;
            color: #c5c8c6;
        }
        .bar {
            height: 14px;
            background: #7ec0ed;
            border-radius: 4px;
            flex: 1;
        }
        .bar-value {
            min-width: 70px;
            font-size: 12px;
            color: #808080;
        }
        ul, ol {
            margin: 10px 0;
            padding-left: 30px;
        }
        li {
            margin: 5px 0;
            color: #c5c8c6;
        }
    </style>
</head>
<body>
    <div class="container">
"""
    
    html_footer = """
        <hr>
        <footer style="text-align: center; color: #808080; margin-top: 40px; padding-top: 20px; border-top: 1px solid #3e3e42;">
            <p><strong style="color: #7ec48c;">Pontificia Universidad Javeriana</strong></p>
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
    
    def convert_markdown_to_html(content):
        content = content.replace('\r', '')
        content = re.sub(r'\n[ \t]{6,}', ' ', content)
        lines = content.split('\n')

        blocks = []
        current_paragraph = []

        def flush_paragraph():
            nonlocal current_paragraph
            if current_paragraph:
                paragraph = ' '.join(line.strip() for line in current_paragraph if line.strip())
                if paragraph:
                    paragraph = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', paragraph)
                    blocks.append(f'<p>{paragraph}</p>')
                current_paragraph = []

        for line in lines:
            stripped = line.strip()

            if not stripped:
                flush_paragraph()
                continue

            if stripped == '---':
                flush_paragraph()
                blocks.append('<hr>')
                continue

            header_match = re.match(r'^(#{1,3})\s+(.+)$', stripped)
            if header_match:
                flush_paragraph()
                level = len(header_match.group(1))
                text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', header_match.group(2))
                blocks.append(f'<h{level}>{text}</h{level}>')
                continue

            current_paragraph.append(stripped)

        flush_paragraph()
        return '\n'.join(blocks)

    for i, cell in enumerate(cells):
        if cell['language'] == 'markdown':
            # Convertir markdown básico a HTML
            content = convert_markdown_to_html(cell['content'])
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

    # Inventario y análisis de eventos
    inventory = _scan_csv_inventory(data_dir)
    event_summary = _analyze_event_files(data_dir)
    elemento_fallado = _analyze_elemento_fallado(data_dir)

    html_content += "\n<div class=\"section-title\"><h3 style=\"margin: 0;\">📦 Inventario y análisis de eventos</h3></div>\n"
    html_content += _render_inventory_html(
        inventory,
        event_summary,
        elemento_fallado.most_common(10)
    )

    # Gráficos
    inventory_items = [(item['file'], item['rows']) for item in inventory]
    html_content += _render_bar_chart_html(
        'Cantidad de registros por lote de información',
        inventory_items,
        unit='registros'
    )

    if event_summary['by_period']:
        period_items = sorted(event_summary['by_period'].items())
        html_content += _render_bar_chart_html(
            'Eventos (desconexiones) por mes/periodo',
            period_items,
            unit='eventos'
        )

    if event_summary['by_cause']:
        cause_items = event_summary['by_cause'].most_common(10)
        html_content += _render_bar_chart_html(
            'Top 10 causas (ID_CAUSA_SSPD)',
            cause_items,
            unit='eventos'
        )
    
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
    success = generate_html(cells, html_file, data_dir='DATA')
    
    if success:
        print("\n🎉 ¡Proceso completado exitosamente!")
        print(f"📄 Archivo HTML actualizado: {html_file}")
    else:
        print("\n❌ Hubo un error al generar el HTML")

if __name__ == "__main__":
    main()

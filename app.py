# ==============================================================
# GENERACIÓN DE PDF REFACTORIZADA (con multi_cell nativo)
# ==============================================================

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.set_margins(left=15, top=15, right=15)
pdf.add_page()

# Constantes de diseño (ajustables)
MARGIN_LEFT = 15
PAGE_WIDTH = 210 - 30
FONT_SIZE_LEVEL1 = 9
FONT_SIZE_LEVEL2 = 8
FONT_SIZE_LEVEL3 = 7
FONT_SIZE_TITLE = 20
FONT_SIZE_TOTAL = 14
COLOR_LEVEL1 = (0, 0, 0)
COLOR_LEVEL2 = (68, 68, 68)
COLOR_LEVEL3 = (136, 136, 136)
DARK_GRAY = (40, 40, 40)
SEPARATOR_COLOR = (230, 230, 230)
PADDING_BETWEEN_PRODUCTS = 3

# Anchos de columna (ajustados para números largos)
W = {
    'codigo': 14,
    'marca': 14,
    'modelo': 36,
    'cant': 9,
    'p_unit': 18,
    'iva': 11,
    'subtotal': 20,
    'desc': 14,
    'neto': 20,
    'iva_monto': 16,
}
W_EINHELL = [W['codigo'], W['marca'], W['modelo'], W['cant'], W['p_unit'], W['iva'], W['subtotal'], W['desc'], W['neto'], W['iva_monto']]
W_OTRAS = W_EINHELL  # Mismos anchos para todas las marcas (las columnas de embalaje se dibujan en la descripción)

# Funciones auxiliares de dibujo (reutilizables)
def draw_title():
    pdf.set_x(MARGIN_LEFT + PAGE_WIDTH - 80)
    pdf.set_font("Arial", 'B', FONT_SIZE_TITLE)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(80, 12, clean_text("PROFORMA DE PEDIDO"), ln=True, align='R')
    pdf.ln(2)

def draw_separator_line():
    pdf.set_draw_color(*SEPARATOR_COLOR)
    pdf.line(MARGIN_LEFT, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
    pdf.ln(4)

def draw_client_block():
    pdf.set_font("Arial", 'B', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 6, clean_text("Cliente:"), ln=True)
    pdf.set_font("Arial", '', 10)
    codigo_cliente = cli_info.get('CODIGO') or cli_info.get('Código') or cli_info.get('Codigo')
    if codigo_cliente and pd.notna(codigo_cliente):
        pdf.cell(0, 6, clean_text(f"{cliente_seleccionado} (Código: {codigo_cliente})"), ln=True)
    else:
        pdf.cell(0, 6, clean_text(cliente_seleccionado), ln=True)
    pdf.cell(0, 6, clean_text(f"CUIT: {cli_info.get('C.U.I.T.', '-')}"), ln=True)
    direccion_cliente = cli_info.get('Dirección') or cli_info.get('DOMICILIO') or cli_info.get('Domicilio')
    if direccion_cliente and pd.notna(direccion_cliente):
        pdf.cell(0, 6, clean_text(direccion_cliente), ln=True)
    pdf.cell(0, 6, clean_text(f"Condición: {cli_info.get('FORMA DE PAGO', '-')}"), ln=True)
    pdf.cell(0, 6, clean_text(f"Vendedor: {cli_info.get('NOMB.VENDEDOR', '-')}"), ln=True)
    if retira_local:
        pdf.cell(0, 6, clean_text("Entrega: El cliente retira en el local"), ln=True)
    elif direccion_entrega:
        pdf.cell(0, 6, clean_text(f"Entrega: {direccion_entrega}"), ln=True)
    else:
        pdf.cell(0, 6, clean_text("Entrega: En dirección del cliente (sin especificar)"), ln=True)
    pdf.cell(0, 6, clean_text(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), ln=True)
    pdf.ln(8)

def draw_brand_header(marca, count):
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, clean_text(f"{marca} ({count} productos)"), ln=True)
    pdf.ln(2)

def draw_table_header(es_einhell):
    pdf.set_font("Arial", 'B', FONT_SIZE_LEVEL1)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_text_color(0, 0, 0)
    pdf.set_x(MARGIN_LEFT)

    if es_einhell:
        headers = ["Código", "Marca", "Herramienta", "Cant", "P.Unit", "IVA%", "Subtotal", "Desc.", "Neto", "IVA"]
        widths = W_EINHELL
    else:
        headers = ["Código", "Marca", "Modelo", "Cant", "P.Unit", "IVA%", "Subtotal", "Desc.", "Neto", "IVA"]
        widths = W_OTRAS

    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, clean_text(h), border=0, align='C', fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(255, 255, 255)

# -------------------------------------------------------------------
# NUEVA FUNCIÓN draw_product_row (refactorizada, sin truncamiento manual)
# -------------------------------------------------------------------
def draw_product_row(row, es_einhell):
    # --- Preparación de datos (todos pasan por clean_text) ---
    codigo = clean_text(str(row['Codigo']))[:12]
    marca_text = clean_text(str(row['Marca']))[:12]
    cant = str(int(row['Cantidad'])) if row['Cantidad'].is_integer() else f"{row['Cantidad']:.1f}"
    p_unit = fmt_currency(row['Precio_Unitario'])
    iva_text = format_iva(row['IVA'], row['Es_Oferta'])
    subtotal = fmt_currency(row['Subtotal_Bruto'])
    descuento = fmt_currency(row['Monto_Descuento'])
    neto = fmt_currency(row['Neto_Calculado'])
    iva_monto = fmt_currency(row['Monto_IVA'])

    # Nombre del producto (Herramienta para Einhell, Modelo para otras)
    if es_einhell:
        producto_nombre = clean_text(str(row.get('Herramienta', '')))[:40]
    else:
        producto_nombre = clean_text(str(row.get('Modelo', '')))[:38]

    # Descripción (se usará con multi_cell)
    desc_text = clean_text(str(row.get('Descripcion', '')))
    if row['Es_Oferta']:
        desc_text = "OFERTA " + desc_text
    if es_einhell:
        alimentacion = clean_text(str(row.get('Tipo_Alimentacion', '')))
        if alimentacion:
            desc_text += f" ({alimentacion})"
    else:
        # Agregar datos de embalaje para Fijaciones, KWB, Penosil
        emb = clean_text(str(row.get('Embalaje', '')))
        caja = clean_text(str(row.get('CantidadPorCaja', '')))
        unidad = clean_text(str(row.get('UnidadPrecio', '')))
        if emb or caja or unidad:
            desc_text += f" | Emb: {emb} Caja: {caja} Unidad: {unidad}"

    widths = W_EINHELL if es_einhell else W_OTRAS

    # --- Verificar espacio en página ---
    if pdf.get_y() > 250:
        pdf.add_page()
        draw_table_header(es_einhell)

    # --- Dibujar Nivel 1 (Código, Marca, Producto, Cantidad) ---
    y_inicial = pdf.get_y()
    pdf.set_x(MARGIN_LEFT)
    pdf.set_font("Arial", 'B', FONT_SIZE_LEVEL1)
    pdf.set_text_color(COLOR_LEVEL1[0], COLOR_LEVEL1[1], COLOR_LEVEL1[2])

    pdf.cell(widths[0], 6, codigo, border=0, align='L')
    pdf.cell(widths[1], 6, marca_text, border=0, align='L')
    pdf.cell(widths[2], 6, producto_nombre, border=0, align='L')
    pdf.cell(widths[3], 6, cant, border=0, align='C')
    # Rellenar el resto de columnas vacías (nivel 1)
    for i in range(4, len(widths)):
        pdf.cell(widths[i], 6, "", border=0, align='R' if i in (4,6,7,8,9) else 'C')
    pdf.ln()

    # --- Dibujar Nivel 2 (Precios) ---
    pdf.set_x(MARGIN_LEFT)
    pdf.set_font("Arial", '', FONT_SIZE_LEVEL2)
    pdf.set_text_color(COLOR_LEVEL2[0], COLOR_LEVEL2[1], COLOR_LEVEL2[2])

    # Celdas vacías para las primeras 4 columnas (nivel 1)
    pdf.cell(widths[0], 5.5, "", border=0, align='L')
    pdf.cell(widths[1], 5.5, "", border=0, align='L')
    pdf.cell(widths[2], 5.5, "", border=0, align='L')
    pdf.cell(widths[3], 5.5, "", border=0, align='C')
    # Precios alineados a la derecha
    pdf.cell(widths[4], 5.5, p_unit, border=0, align='R')
    pdf.cell(widths[5], 5.5, iva_text, border=0, align='C')
    pdf.cell(widths[6], 5.5, subtotal, border=0, align='R')
    pdf.cell(widths[7], 5.5, descuento, border=0, align='R')
    pdf.cell(widths[8], 5.5, neto, border=0, align='R')
    pdf.cell(widths[9], 5.5, iva_monto, border=0, align='R')
    pdf.ln()

    # --- Dibujar Nivel 3 (Descripción) con multi_cell nativo ---
    if desc_text.strip():
        pdf.set_x(MARGIN_LEFT + 2)  # pequeña sangría
        pdf.set_font("Arial", 'I', FONT_SIZE_LEVEL3)
        pdf.set_text_color(COLOR_LEVEL3[0], COLOR_LEVEL3[1], COLOR_LEVEL3[2])
        # multi_cell se encarga del salto de línea automático
        pdf.multi_cell(PAGE_WIDTH - 4, 4.5, desc_text, border=0, align='L')
        # multi_cell ya actualizó el Y, pero puede que haya dejado espacio extra
        # Forzamos a que el Y se sitúe justo después de la última línea de descripción
        # y añadimos un pequeño padding antes de la línea separadora.
    else:
        # Si no hay descripción, solo movemos el cursor ligeramente
        pdf.ln(2)

    # --- Restaurar estilo y dibujar línea separadora ---
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', FONT_SIZE_LEVEL2)

    # Aseguramos que el Y esté al menos 2 mm por debajo de la última línea
    # (multi_cell ya posicionó el Y, pero agregamos un margen)
    pdf.set_y(pdf.get_y() + PADDING_BETWEEN_PRODUCTS)

    # Línea separadora (sutil)
    pdf.set_draw_color(*SEPARATOR_COLOR)
    pdf.line(MARGIN_LEFT, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
    pdf.ln(2)  # Pequeño espacio después de la línea

# -------------------------------------------------------------------
# BLOQUE PRINCIPAL DE GENERACIÓN (recorre marcas y productos)
# -------------------------------------------------------------------

draw_title()
draw_separator_line()
draw_client_block()

marcas_en_pedido = sorted(df_carrito['Marca'].unique())

for idx_marca, marca in enumerate(marcas_en_pedido):
    subset = df_carrito[df_carrito['Marca'] == marca]
    es_einhell = (marca == "Einhell")

    # Verificar espacio antes de la marca
    if pdf.get_y() > 200 and idx_marca > 0:
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

    draw_brand_header(marca, len(subset))
    draw_table_header(es_einhell)

    for _, row in subset.iterrows():
        draw_product_row(row, es_einhell)

    # Subtotal de la marca
    bruto_marca = subset['Subtotal_Bruto'].sum()
    neto_marca = subset['Neto_Calculado'].sum()
    iva_marca = subset['Monto_IVA'].sum()
    desc_marca = bruto_marca - neto_marca
    total_marca = neto_marca + iva_marca

    if pdf.get_y() > 220:
        pdf.add_page()
    pdf.set_draw_color(*SEPARATOR_COLOR)
    pdf.line(MARGIN_LEFT, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 9)
    pdf.set_text_color(0, 0, 0)
    pdf.set_x(MARGIN_LEFT)
    pdf.cell(0, 6, clean_text(f"Subtotal {marca}"), ln=True)
    pdf.set_font("Arial", '', 8)
    pdf.set_x(MARGIN_LEFT)
    labels = ["Bruto", "Descuento", "Neto", "IVA", "TOTAL"]
    values = [bruto_marca, desc_marca, neto_marca, iva_marca, total_marca]
    for lbl, val in zip(labels, values):
        pdf.cell(36, 5, clean_text(f"{lbl}: {fmt_currency(val)}"), border=0, align='L')
    pdf.ln()
    pdf.ln(4)  # espacio entre marcas

# Bloque de totales finales (similar al original, pero con control de página)
if pdf.get_y() > 200:
    pdf.add_page()

pdf.ln(6)
pdf.set_font("Arial", 'B', 10)
pdf.set_text_color(0, 0, 0)
pdf.cell(0, 7, clean_text(f"Descuentos aplicados: {texto_descuentos}"), ln=True)
pdf.ln(4)

block_width = 80
x_start = MARGIN_LEFT + PAGE_WIDTH - block_width
pdf.set_x(x_start)

pdf.set_font("Arial", 'B', 9)
pdf.cell(block_width, 6, clean_text("Subtotal Bruto:"), border=0, align='L')
pdf.set_x(x_start + 40)
pdf.set_font("Arial", '', 9)
pdf.cell(block_width - 40, 6, fmt_currency(total_bruto), border=0, align='R')
pdf.ln()

pdf.set_x(x_start)
pdf.set_font("Arial", 'B', 9)
pdf.cell(block_width, 6, clean_text("Descuentos:"), border=0, align='L')
pdf.set_x(x_start + 40)
pdf.set_font("Arial", '', 9)
pdf.cell(block_width - 40, 6, fmt_currency(total_descuento), border=0, align='R')
pdf.ln()

pdf.set_x(x_start)
pdf.set_font("Arial", 'B', 9)
pdf.cell(block_width, 6, clean_text("Neto:"), border=0, align='L')
pdf.set_x(x_start + 40)
pdf.set_font("Arial", '', 9)
pdf.cell(block_width - 40, 6, fmt_currency(total_neto), border=0, align='R')
pdf.ln()

pdf.set_x(x_start)
pdf.set_font("Arial", 'B', 9)
pdf.cell(block_width, 6, clean_text("IVA Total:"), border=0, align='L')
pdf.set_x(x_start + 40)
pdf.set_font("Arial", '', 9)
pdf.cell(block_width - 40, 6, fmt_currency(total_iva), border=0, align='R')
pdf.ln()

pdf.ln(4)
pdf.set_draw_color(200, 200, 200)
pdf.line(x_start, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
pdf.ln(3)

# TOTAL FINAL
pdf.set_x(x_start)
pdf.set_fill_color(DARK_GRAY[0], DARK_GRAY[1], DARK_GRAY[2])
pdf.rect(x_start, pdf.get_y(), block_width, 10, 'F')
pdf.set_y(pdf.get_y() + 2)
pdf.set_x(x_start + 2)
pdf.set_font("Arial", 'B', FONT_SIZE_TOTAL)
pdf.set_text_color(255, 255, 255)
pdf.cell(block_width - 4, 8, clean_text("TOTAL FINAL"), border=0, align='L')
pdf.set_x(x_start + 40)
pdf.cell(block_width - 40, 8, fmt_currency(total_final), border=0, align='R')
pdf.set_text_color(0, 0, 0)
pdf.ln(12)

# Notas y leyenda
if pdf.get_y() > 250:
    pdf.add_page()
pdf.set_font("Arial", 'I', 8)
pdf.set_text_color(80, 80, 80)
pdf.cell(0, 5, clean_text("(*) Los articulos marcados como OFERTA o de la hoja 'BATERIAS Y CARGADORES' no reciben descuentos adicionales."), ln=True)
pdf.ln(3)
pdf.set_font("Arial", 'B', 8)
pdf.set_text_color(0, 0, 0)
pdf.cell(0, 5, clean_text("Leyenda de colores por marca (solo en pantalla):"), ln=True)
pdf.set_font("Arial", '', 8)
for marca, hex_color in MARCAS_COLORS_HEX.items():
    pdf.set_text_color(0, 0, 0)
    pdf.cell(20, 5, clean_text(f"{marca}:"), border=0)
    pdf.set_text_color(int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16))
    pdf.cell(20, 5, clean_text("-"), border=0)
    pdf.ln(4)
pdf.set_text_color(0, 0, 0)

# Guardar PDF
fd, path = tempfile.mkstemp(suffix=".pdf")
try:
    pdf.output(path)
    with open(path, "rb") as f:
        pdf_bytes = f.read()
    st.download_button(
        label="⬇️ Descargar PDF",
        data=pdf_bytes,
        file_name=f"Pedido_{clean_text(cliente_seleccionado[:20])}_{datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf"
    )
    st.success("✅ PDF generado exitosamente.")
finally:
    os.close(fd)

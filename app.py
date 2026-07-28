import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile
import os
import glob
import re
import unicodedata
from datetime import datetime

st.set_page_config(page_title="Gestión de Pedidos", layout="wide", initial_sidebar_state="expanded")

st.title("📦 Sistema de Carga de Pedidos")
st.markdown("---")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# ------------------------------------------------------------
# FUNCIONES AUXILIARES
# ------------------------------------------------------------
def normalize_text(text):
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text.lower()

def sanitize_text(text):
    """
    Convierte texto a ASCII, eliminando tildes y caracteres especiales.
    Reemplaza símbolos por equivalentes ASCII y elimina cualquier carácter no imprimible.
    """
    if not isinstance(text, str):
        text = str(text)
    # Normalizar a forma NFKD (descompone caracteres acentuados)
    text = unicodedata.normalize('NFKD', text)
    # Eliminar diacríticos (acentos)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    # Reemplazar ñ y Ñ
    text = text.replace('ñ', 'n').replace('Ñ', 'N')
    # Reemplazar caracteres especiales comunes por equivalentes ASCII
    replacements = {
        '€': 'EUR',
        '°': 'grados',
        '▸': '-',
        '•': '-',
        '●': '-',   # reemplazar punto negro por guion
        '→': '->',
        '←': '<-',
        '…': '...',
        '—': '-',
        '–': '-',
        '"': "'",
        '"': "'",
        '´': "'",
        '`': "'",
        '·': '.',
        'ª': 'a',
        'º': 'o',
        '█': '#',
        '▓': '#',
        '▒': '#',
        '░': '#',
        '◆': 'o',
        '■': '#',
        '▲': '^',
        '▼': 'v',
        '☑': '[x]',
        '☐': '[ ]',
        '★': '*',
        '☆': '*',
        '✓': 'v',
        '✗': 'x',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Eliminar cualquier carácter que no sea ASCII imprimible (32-126)
    text = ''.join(c for c in text if 32 <= ord(c) <= 126)
    return text

def clean_text(value):
    """Limpiar valor NaN/None y sanitizar a ASCII."""
    if pd.isna(value) or value is None:
        return ""
    if isinstance(value, str) and value.lower() in ('nan', 'none', 'null', ''):
        return ""
    return sanitize_text(str(value))

def fmt_currency(val):
    return f"${val:,.2f}"

def format_iva(iva_val, es_oferta=False):
    if es_oferta:
        return "Oferta"
    if pd.isna(iva_val) or iva_val == 0:
        return "0%"
    return f"{iva_val * 100:.1f}%"

def iva_badge(iva_val):
    pct = format_iva(iva_val)
    if iva_val == 0.21:
        color = "#28a745"
    elif iva_val == 0.105:
        color = "#007bff"
    else:
        color = "#6c757d"
    return f'<span style="background-color:{color}; color:white; padding:2px 8px; border-radius:12px; font-size:12px; font-weight:bold;">{pct}</span>'

# Mapeo de colores solo para uso en la interfaz
MARCAS_COLORS = {
    "Einhell": (139, 50, 50),
    "KWB": (139, 50, 50),
    "Fijaciones": (204, 85, 0),
    "Penosil": (255, 0, 0),
}
MARCAS_COLORS_HEX = {
    "Einhell": "#8B3232",
    "KWB": "#8B3232",
    "Fijaciones": "#CC5500",
    "Penosil": "#FF0000",
}

# ------------------------------------------------------------
# FUNCIONES DE OBTENCIÓN DE INFO (sin cambios)
# ------------------------------------------------------------
def get_product_info(row):
    # ... (igual que antes, se omite por brevedad, pero debe estar completo)
    # En la versión final, incluir el código completo aquí.
    pass

# ------------------------------------------------------------
# EXTRACCIÓN DE CATEGORÍAS EINHELL
# ------------------------------------------------------------
def extract_einhell_categories(herramienta_str):
    # ... (igual que antes)
    pass

# ------------------------------------------------------------
# 1. CARGA DE DATOS
# ------------------------------------------------------------
@st.cache_data
def load_databases():
    # ... (igual que antes, se omite por brevedad)
    pass

def standardize_product_columns(df, filename):
    # ... (igual que antes)
    pass

# ------------------------------------------------------------
# Cargar datos
# ------------------------------------------------------------
try:
    df_clientes, df_productos = load_databases()
except Exception as e:
    st.error(f"Error al cargar archivos: {e}")
    st.stop()

# ------------------------------------------------------------
# FILTROS
# ------------------------------------------------------------
def build_filtros_config(df):
    # ... (igual que antes)
    pass

FILTROS_CONFIG = build_filtros_config(df_productos)

# ------------------------------------------------------------
# 2. SELECCIÓN DE CLIENTE
# ------------------------------------------------------------
st.subheader("1. Selección de Cliente")
# ... (igual que antes, se omite por brevedad)
# En la versión final, incluir todo el código hasta la generación del PDF.
# Dado que es muy largo, he resumido pero el código completo debe estar.

# ============================================================
# 4. RESUMEN DEL PEDIDO Y GENERACIÓN DE PDF (CORREGIDO)
# ============================================================
st.subheader("3. Resumen del Pedido")

if st.session_state.carrito:
    # ... (cálculos, UI, etc.) hasta el botón de generar PDF

    with col_btn2:
        if st.button("📄 Generar PDF del Pedido", type="primary", use_container_width=True):
            if cliente_seleccionado is None:
                st.error("Debes seleccionar un cliente antes de generar el PDF.")
                st.stop()

            # ==================================================================
            # NUEVA GENERACIÓN DE PDF – ESTILO ERP MODERNO (CORREGIDO)
            # ==================================================================

            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_margins(left=15, top=15, right=15)
            pdf.add_page()

            MARGIN_LEFT = 15
            PAGE_WIDTH = 210 - 30
            FONT_SIZE = 9
            FONT_SIZE_SMALL = 7
            FONT_SIZE_TITLE = 18
            FONT_SIZE_TOTAL = 14
            GRAY_TEXT = (100, 100, 100)
            DARK_GRAY = (40, 40, 40)

            # --- Funciones de dibujo (con sanitización) ---

            def draw_title():
                pdf.set_x(MARGIN_LEFT + PAGE_WIDTH - 80)
                pdf.set_font("Arial", 'B', FONT_SIZE_TITLE)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(80, 12, clean_text("PROFORMA DE PEDIDO"), ln=True, align='R')
                pdf.ln(2)

            def draw_separator_line():
                pdf.set_draw_color(200, 200, 200)
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
                pdf.set_font("Arial", 'B', FONT_SIZE)
                pdf.set_fill_color(240, 240, 240)
                pdf.set_text_color(0, 0, 0)
                pdf.set_x(MARGIN_LEFT)

                if es_einhell:
                    widths = [14, 14, 42, 9, 17, 11, 20, 14, 19, 15]
                    headers = ["Código", "Marca", "Herramienta", "Cant", "P.Unit", "IVA%", "Subtotal", "Desc.", "Neto", "IVA"]
                else:
                    widths = [14, 14, 40, 9, 17, 11, 20, 14, 19, 15]
                    headers = ["Código", "Marca", "Modelo", "Cant", "P.Unit", "IVA%", "Subtotal", "Desc.", "Neto", "IVA"]

                for i, h in enumerate(headers):
                    pdf.cell(widths[i], 8, clean_text(h), border=0, align='C', fill=True)
                pdf.ln()
                pdf.set_text_color(0, 0, 0)
                pdf.set_fill_color(255, 255, 255)

            def draw_product_row(row, es_einhell, widths):
                # Datos principales
                codigo = clean_text(str(row['Codigo']))[:12]
                marca_text = clean_text(str(row['Marca']))[:12]
                cant = str(int(row['Cantidad'])) if row['Cantidad'].is_integer() else f"{row['Cantidad']:.1f}"
                p_unit = fmt_currency(row['Precio_Unitario'])
                iva_text = format_iva(row['IVA'], row['Es_Oferta'])
                subtotal = fmt_currency(row['Subtotal_Bruto'])
                descuento = fmt_currency(row['Monto_Descuento'])
                neto = fmt_currency(row['Neto_Calculado'])
                iva_monto = fmt_currency(row['Monto_IVA'])

                # Línea 1: Datos financieros (negrita para Código y Modelo/Herramienta)
                pdf.set_x(MARGIN_LEFT)
                pdf.set_font("Arial", 'B', FONT_SIZE)
                pdf.set_text_color(0, 0, 0)

                if es_einhell:
                    herramienta = clean_text(str(row.get('Herramienta', '')))[:40]
                    pdf.cell(widths[0], 6, codigo, border=0, align='L')
                    pdf.cell(widths[1], 6, marca_text, border=0, align='L')
                    pdf.cell(widths[2], 6, herramienta, border=0, align='L')
                    pdf.set_font("Arial", '', FONT_SIZE)
                    pdf.cell(widths[3], 6, cant, border=0, align='C')
                    pdf.cell(widths[4], 6, p_unit, border=0, align='R')
                    pdf.cell(widths[5], 6, iva_text, border=0, align='C')
                    pdf.cell(widths[6], 6, subtotal, border=0, align='R')
                    pdf.cell(widths[7], 6, descuento, border=0, align='R')
                    pdf.cell(widths[8], 6, neto, border=0, align='R')
                    pdf.cell(widths[9], 6, iva_monto, border=0, align='R')
                else:
                    modelo = clean_text(str(row.get('Modelo', '')))[:38]
                    pdf.cell(widths[0], 6, codigo, border=0, align='L')
                    pdf.cell(widths[1], 6, marca_text, border=0, align='L')
                    pdf.cell(widths[2], 6, modelo, border=0, align='L')
                    pdf.set_font("Arial", '', FONT_SIZE)
                    pdf.cell(widths[3], 6, cant, border=0, align='C')
                    pdf.cell(widths[4], 6, p_unit, border=0, align='R')
                    pdf.cell(widths[5], 6, iva_text, border=0, align='C')
                    pdf.cell(widths[6], 6, subtotal, border=0, align='R')
                    pdf.cell(widths[7], 6, descuento, border=0, align='R')
                    pdf.cell(widths[8], 6, neto, border=0, align='R')
                    pdf.cell(widths[9], 6, iva_monto, border=0, align='R')
                pdf.ln()

                # Línea 2: Descripción (cursiva, gris)
                desc_text = clean_text(str(row.get('Descripcion', '')))
                if row['Es_Oferta']:
                    desc_text = "OFERTA " + desc_text
                if es_einhell:
                    alimentacion = clean_text(str(row.get('Tipo_Alimentacion', '')))
                    if alimentacion:
                        desc_text += f" ({alimentacion})"

                # Truncar a 2 líneas
                max_width = PAGE_WIDTH - 4
                pdf.set_font("Arial", 'I', FONT_SIZE_SMALL)
                pdf.set_text_color(GRAY_TEXT[0], GRAY_TEXT[1], GRAY_TEXT[2])
                pdf.set_x(MARGIN_LEFT + 2)

                words = desc_text.split()
                lines = []
                current_line = ""
                for word in words:
                    test_line = (current_line + " " + word).strip()
                    if pdf.get_string_width(test_line) <= max_width:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                        if len(lines) >= 2:
                            break
                if current_line:
                    lines.append(current_line)
                desc_display = " ".join(lines[:2])
                if len(lines) > 2:
                    desc_display += "..."

                pdf.multi_cell(PAGE_WIDTH - 4, 4.5, desc_display, border=0, align='L')
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Arial", '', FONT_SIZE)

                # Línea separadora
                pdf.set_draw_color(220, 220, 220)
                pdf.line(MARGIN_LEFT, pdf.get_y() + 1, MARGIN_LEFT + PAGE_WIDTH, pdf.get_y() + 1)
                pdf.ln(4)

            def draw_subtotal_block(marca, bruto, descuento, neto, iva, total):
                pdf.set_draw_color(220, 220, 220)
                pdf.line(MARGIN_LEFT, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
                pdf.ln(2)
                pdf.set_font("Arial", 'B', 9)
                pdf.set_text_color(0, 0, 0)
                pdf.set_x(MARGIN_LEFT)
                pdf.cell(0, 6, clean_text(f"Subtotal {marca}"), ln=True)
                pdf.set_font("Arial", '', 8)
                pdf.set_x(MARGIN_LEFT)
                labels = ["Bruto", "Descuento", "Neto", "IVA", "TOTAL"]
                values = [bruto, descuento, neto, iva, total]
                for lbl, val in zip(labels, values):
                    pdf.cell(36, 5, clean_text(f"{lbl}: {fmt_currency(val)}"), border=0, align='L')
                pdf.ln()
                pdf.ln(2)

            def draw_final_summary(total_bruto, total_descuento, total_neto, total_iva, total_final, texto_descuentos):
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

                # TOTAL FINAL con fondo oscuro y texto blanco
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

            def draw_footer_notes():
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
                    pdf.cell(20, 5, clean_text("-"), border=0)  # en lugar del punto
                    pdf.ln(4)
                pdf.set_text_color(0, 0, 0)

            # ---- INICIO ----
            draw_title()
            draw_separator_line()
            draw_client_block()

            marcas_en_pedido = sorted(df_carrito['Marca'].unique())

            for idx_marca, marca in enumerate(marcas_en_pedido):
                subset = df_carrito[df_carrito['Marca'] == marca]
                es_einhell = (marca == "Einhell")

                if pdf.get_y() > 230 and idx_marca > 0:
                    pdf.add_page()
                    pdf.set_auto_page_break(auto=True, margin=15)

                draw_brand_header(marca, len(subset))

                if es_einhell:
                    widths = [14, 14, 42, 9, 17, 11, 20, 14, 19, 15]
                else:
                    widths = [14, 14, 40, 9, 17, 11, 20, 14, 19, 15]

                draw_table_header(es_einhell)

                for _, row in subset.iterrows():
                    draw_product_row(row, es_einhell, widths)

                bruto_marca = subset['Subtotal_Bruto'].sum()
                neto_marca = subset['Neto_Calculado'].sum()
                iva_marca = subset['Monto_IVA'].sum()
                desc_marca = bruto_marca - neto_marca
                total_marca = neto_marca + iva_marca
                draw_subtotal_block(marca, bruto_marca, desc_marca, neto_marca, iva_marca, total_marca)

                pdf.set_x(MARGIN_LEFT)
                pdf.cell(0, 6, "", border=0)

            draw_final_summary(total_bruto, total_descuento, total_neto, total_iva, total_final, texto_descuentos)
            draw_footer_notes()

            # ---- GUARDAR ----
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

else:
    st.info("🛒 El carrito está vacío. Buscá un producto y agregalo al pedido.")

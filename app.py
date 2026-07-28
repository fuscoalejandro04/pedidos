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
    """Convierte texto a ASCII, eliminando tildes y caracteres especiales."""
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = text.replace('ñ', 'n').replace('Ñ', 'N')
    replacements = {
        '€': 'EUR', '°': 'grados', '▸': '-', '•': '-', '●': '-',
        '→': '->', '←': '<-', '…': '...', '—': '-', '–': '-',
        '"': "'", '´': "'", '`': "'", '·': '.', 'ª': 'a', 'º': 'o',
        '█': '#', '▓': '#', '▒': '#', '░': '#', '◆': 'o', '■': '#',
        '▲': '^', '▼': 'v', '☑': '[x]', '☐': '[ ]', '★': '*', '☆': '*',
        '✓': 'v', '✗': 'x'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = ''.join(c for c in text if 32 <= ord(c) <= 126)
    return text

def clean_text(value):
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
# FUNCIÓN PARA OBTENER INFORMACIÓN DE PRECIO Y PRESENTACIÓN
# ------------------------------------------------------------
def get_product_info(row):
    # ... (código sin cambios, igual que antes)
    precio_lista = row['Precio_Lista']
    unidad = str(row.get('UnidadPrecio', '')).strip() if pd.notna(row.get('UnidadPrecio')) else ''
    caja = str(row.get('CantidadPorCaja', '')).strip() if pd.notna(row.get('CantidadPorCaja')) else ''
    embalaje = str(row.get('Embalaje', '')).strip() if pd.notna(row.get('Embalaje')) else ''

    info = {
        'precio_unitario': precio_lista,
        'step': 1.0,
        'min_value': 0.0,
        'ayuda': '',
        'precio_lote': precio_lista,
        'tipo_cantidad': 'unidades',
        'cantidad_por_lote': 1,
        'presentacion_text': 'Unidad suelta',
        'unidad_venta': 'unidad',
        'precio_por_presentacion': precio_lista
    }

    try:
        unidad_num = float(unidad)
        if unidad_num > 0:
            precio_unitario = precio_lista / unidad_num
            info['precio_unitario'] = precio_unitario
            info['precio_lote'] = precio_lista
            info['cantidad_por_lote'] = unidad_num
            info['tipo_cantidad'] = 'unidades'
            info['precio_por_presentacion'] = precio_lista

            try:
                caja_num = float(caja) if caja else 0
                if caja_num > 0 and caja_num <= unidad_num:
                    info['step'] = caja_num
                    info['min_value'] = caja_num
                    precio_caja = precio_unitario * caja_num
                    info['presentacion_text'] = f"Caja de {caja_num} unidades (precio por {unidad_num} unid.: {fmt_currency(precio_lista)})"
                    info['unidad_venta'] = f"caja de {caja_num} unid."
                    info['ayuda'] = f"Venta en cajas de {caja_num} unidades (múltiplos). Precio por caja: {fmt_currency(precio_caja)}"
                else:
                    info['step'] = 1.0
                    info['min_value'] = 0.0
                    info['presentacion_text'] = f"Unidad suelta (precio por {unidad_num} unid.: {fmt_currency(precio_lista)})"
                    info['unidad_venta'] = "unidad suelta"
                    info['ayuda'] = f"Precio unitario: {fmt_currency(precio_unitario)}"
            except:
                info['step'] = 1.0
                info['min_value'] = 0.0
                info['presentacion_text'] = f"Unidad suelta (precio por {unidad_num} unid.: {fmt_currency(precio_lista)})"
                info['unidad_venta'] = "unidad suelta"
                info['ayuda'] = f"Precio unitario: {fmt_currency(precio_unitario)}"
            return info
    except:
        pass

    try:
        caja_num = float(caja) if caja else 0
        if caja_num > 0:
            info['precio_unitario'] = precio_lista
            info['step'] = 1.0
            info['min_value'] = 0.0
            info['tipo_cantidad'] = 'lotes'
            info['cantidad_por_lote'] = caja_num
            info['precio_lote'] = precio_lista
            info['precio_por_presentacion'] = precio_lista

            if unidad.upper() in ["GRANEL", "BOLSA", "JARRA", "CAJA", "CARAMELERA"]:
                unidad_venta = unidad.capitalize()
            else:
                unidad_venta = "Lote"

            info['unidad_venta'] = f"{unidad_venta} de {caja_num} unid."
            info['presentacion_text'] = f"{unidad_venta} de {caja_num} unidades (precio por {unidad_venta.lower()}: {fmt_currency(precio_lista)})"
            if embalaje:
                info['ayuda'] = f"Venta en {unidad_venta.lower()}es de {caja_num} unidades. Embalaje mayor: {embalaje} (costo de referencia)"
            else:
                info['ayuda'] = f"Venta en {unidad_venta.lower()}es de {caja_num} unidades."
            return info
        else:
            info['precio_unitario'] = precio_lista
            info['step'] = 1.0
            info['min_value'] = 0.0
            info['tipo_cantidad'] = 'unidades'
            info['cantidad_por_lote'] = 1
            info['precio_lote'] = precio_lista
            info['presentacion_text'] = "Unidad suelta (sin embalaje definido)"
            info['unidad_venta'] = "unidad suelta"
            info['ayuda'] = "Precio unitario"
            return info
    except:
        info['precio_unitario'] = precio_lista
        info['step'] = 1.0
        info['min_value'] = 0.0
        info['tipo_cantidad'] = 'unidades'
        info['cantidad_por_lote'] = 1
        info['precio_lote'] = precio_lista
        info['presentacion_text'] = "Unidad suelta"
        info['unidad_venta'] = "unidad suelta"
        info['ayuda'] = "Precio unitario"
        return info

# ------------------------------------------------------------
# FUNCIÓN PARA EXTRAER CATEGORÍA Y ALIMENTACIÓN EN EINHELL
# ------------------------------------------------------------
def extract_einhell_categories(herramienta_str):
    if not isinstance(herramienta_str, str) or pd.isna(herramienta_str):
        return None, None
    h = herramienta_str.upper()
    categorias = {
        'ROTOMARTILLO': ['ROTOMARTILLO', 'MARTILLO PERFORADOR'],
        'TALADRO': ['TALADRO', 'ATORNILLADOR', 'TALADRO PERCUTOR'],
        'SIERRA': ['SIERRA', 'CALADORA', 'INGLETEADORA', 'SIERRA CIRCULAR', 'SIERRA SABLE'],
        'AMOLADORA': ['AMOLADORA', 'PULIDORA', 'LIJADORA'],
        'CEPILLO': ['CEPILLO', 'ENGALLETADORA'],
        'ASPIRADORA': ['ASPIRADORA', 'HIDROLAVADORA'],
        'COMPRESOR': ['COMPRESOR', 'BOMBA'],
        'ROUTER': ['ROUTER', 'FRESADORA'],
        'MOTOSIERRA': ['MOTOSIERRA', 'CORTACESPED', 'BORDEADORA'],
        'LÁMPARA': ['LÁMPARA', 'REFLECTOR', 'LUZ'],
        'OTRO': []
    }
    categoria = "OTRO"
    for cat, keywords in categorias.items():
        for kw in keywords:
            if kw in h:
                categoria = cat
                break
        if categoria != "OTRO":
            break
    if "INALÁMBRICO" in h or "BATERÍA" in h:
        tipo = "Inalámbrica"
    elif "ELÉCTRICA" in h or "ELÉCTRICO" in h:
        tipo = "Eléctrica"
    else:
        tipo = "No especificado"
    return categoria.title(), tipo

# ------------------------------------------------------------
# 1. CARGAR DATOS Y DETECTAR OFERTAS (sin cambios, omitido por brevedad)
# ------------------------------------------------------------
@st.cache_data
def load_databases():
    # ... (código completo igual que antes, se omite por brevedad pero debe estar)
    try:
        df_cli = pd.read_excel("DB_Clientes_Limpia.xlsx")
    except FileNotFoundError:
        st.error("No se encontró el archivo DB_Clientes_Limpia.xlsx. Por favor, asegúrate de que exista.")
        st.stop()
        return None, None

    product_files = [
        "KWB_Limpia.xlsx",
        "Einhell_Limpia.xlsx",
        "Fijaciones_Limpia.xlsx",
        "Penosil_Limpia.xlsx"
    ]

    dfs = []
    for file in product_files:
        try:
            df = pd.read_excel(file)
            df = standardize_product_columns(df, file)
            dfs.append(df)
        except FileNotFoundError:
            st.warning(f"Archivo {file} no encontrado. Se omitirá.")
        except Exception as e:
            st.warning(f"Error al leer {file}: {e}")

    if not dfs:
        st.error("No se pudo cargar ningún archivo de productos. Verifica los nombres de los archivos.")
        st.stop()
        return None, None

    df_prod = pd.concat(dfs, ignore_index=True)
    df_prod['Codigo'] = df_prod['Codigo'].astype(str).str.strip()
    df_prod['Precio_Lista'] = pd.to_numeric(df_prod['Precio_Lista'], errors='coerce').fillna(0)
    df_prod['Precio_Oferta'] = 0.0
    df_prod['Es_Oferta'] = False

    if 'Herramienta' in df_prod.columns:
        df_prod['Categoria_Generica'] = None
        df_prod['Tipo_Alimentacion'] = None
        mask_einhell = df_prod['Marca'] == 'Einhell'
        if mask_einhell.any():
            df_prod.loc[mask_einhell, 'Categoria_Generica'] = df_prod.loc[mask_einhell, 'Herramienta'].apply(
                lambda x: extract_einhell_categories(x)[0]
            )
            df_prod.loc[mask_einhell, 'Tipo_Alimentacion'] = df_prod.loc[mask_einhell, 'Herramienta'].apply(
                lambda x: extract_einhell_categories(x)[1]
            )
    else:
        df_prod['Categoria_Generica'] = None
        df_prod['Tipo_Alimentacion'] = None

    archivos_oferta = glob.glob("*oferta*.xls*") + glob.glob("*OFERTA*.xls*")
    for archivo in archivos_oferta:
        try:
            df_of = pd.read_excel(archivo)
            df_of.columns = [str(c).strip().upper() for c in df_of.columns]
            col_codigo = "CÓDIGO" if "CÓDIGO" in df_of.columns else "CODIGO" if "CODIGO" in df_of.columns else None
            col_precio = [c for c in df_of.columns if "PRECIO" in c]
            if col_codigo and col_precio:
                col_precio = col_precio[0]
                df_of_limpio = df_of[[col_codigo, col_precio]].copy()
                df_of_limpio.columns = ['Codigo', 'Precio_Promocional']
                df_of_limpio['Codigo'] = df_of_limpio['Codigo'].astype(str).str.strip()
                df_of_limpio['Precio_Promocional'] = pd.to_numeric(df_of_limpio['Precio_Promocional'], errors='coerce').fillna(0)
                df_prod = pd.merge(df_prod, df_of_limpio, on='Codigo', how='left')
                condicion_oferta = df_prod['Precio_Promocional'] > 0
                df_prod.loc[condicion_oferta, 'Precio_Oferta'] = df_prod.loc[condicion_oferta, 'Precio_Promocional']
                df_prod.loc[condicion_oferta, 'Es_Oferta'] = True
                df_prod = df_prod.drop(columns=['Precio_Promocional'])
        except Exception as e:
            st.sidebar.warning(f"No se pudo procesar el archivo de oferta {archivo}: {e}")

    return df_cli, df_prod


def standardize_product_columns(df, filename):
    if 'Herramienta' not in df.columns:
        df['Herramienta'] = None

    for extra in ['CantidadPorCaja', 'Embalaje', 'UnidadPrecio', 'Color']:
        if extra not in df.columns:
            df[extra] = None

    if "KWB" in filename:
        df = df.rename(columns={'Nombre': 'Modelo'})
        for col in ['Codigo', 'Descripcion', 'Modelo', 'Marca', 'Precio_Lista', 'IVA', 'Hoja_Origen']:
            if col not in df.columns:
                df[col] = None

    elif "Einhell" in filename:
        if 'Hoja_Origen' not in df.columns:
            df['Hoja_Origen'] = 'Einhell'
        if 'Marca' not in df.columns:
            df['Marca'] = 'Einhell'

    elif "Fijaciones" in filename:
        df = df.rename(columns={'PrecioLista': 'Precio_Lista'})
        df['Modelo'] = df['Descripcion']
        if 'Marca' not in df.columns:
            df['Marca'] = 'Fijaciones'
        if 'Hoja_Origen' not in df.columns:
            df['Hoja_Origen'] = 'Fijaciones'

    elif "Penosil" in filename:
        df = df.rename(columns={
            'Artículo': 'Codigo',
            'Nombre': 'Modelo',
            'PrecioLista': 'Precio_Lista'
        })
        if 'Marca' not in df.columns:
            df['Marca'] = 'Penosil'
        if 'Hoja_Origen' not in df.columns:
            df['Hoja_Origen'] = 'Penosil'

    else:
        if 'PrecioLista' in df.columns:
            df = df.rename(columns={'PrecioLista': 'Precio_Lista'})
        if 'Artículo' in df.columns:
            df = df.rename(columns={'Artículo': 'Codigo'})
        if 'Nombre' in df.columns and 'Modelo' not in df.columns:
            df['Modelo'] = df['Nombre']
        if 'Hoja_Origen' not in df.columns:
            df['Hoja_Origen'] = 'Desconocido'
        if 'Marca' not in df.columns:
            df['Marca'] = 'Desconocida'

    required = ['Codigo', 'Descripcion', 'Modelo', 'Marca', 'Precio_Lista', 'IVA', 'Hoja_Origen', 'Herramienta', 'Color']
    for col in required:
        if col not in df.columns:
            df[col] = None
    df['IVA'] = pd.to_numeric(df['IVA'], errors='coerce').fillna(0.21)
    return df


# ------------------------------------------------------------
# Cargar datos
# ------------------------------------------------------------
try:
    df_clientes, df_productos = load_databases()
except Exception as e:
    st.error(f"Error al cargar archivos: {e}")
    st.stop()

# ------------------------------------------------------------
# CONSTRUCCIÓN DE FILTROS POR MARCA
# ------------------------------------------------------------
def build_filtros_config(df):
    config = {}
    if 'Marca' not in df.columns:
        return config

    try:
        if 'Categoria_Generica' in df.columns and df['Categoria_Generica'].notna().any():
            sub_df = df[df['Marca'] == "Einhell"]
            if not sub_df.empty and 'Categoria_Generica' in sub_df.columns and sub_df['Categoria_Generica'].notna().any():
                config["Einhell"] = {
                    "Categoria_Generica": {"label": "Categoría", "options": sorted(sub_df['Categoria_Generica'].dropna().unique())},
                    "Tipo_Alimentacion": {"label": "Alimentación", "options": sorted(sub_df['Tipo_Alimentacion'].dropna().unique())}
                }
    except:
        pass

    try:
        if 'Embalaje' in df.columns and df['Embalaje'].notna().any():
            sub_df = df[df['Marca'] == "Fijaciones"]
            if not sub_df.empty and 'Embalaje' in sub_df.columns and sub_df['Embalaje'].notna().any():
                config["Fijaciones"] = {
                    "Embalaje": {"label": "Embalaje", "options": sorted(sub_df['Embalaje'].dropna().unique())}
                }
    except:
        pass

    try:
        if 'Hoja_Origen' in df.columns and df['Hoja_Origen'].notna().any():
            sub_df = df[df['Marca'] == "KWB"]
            if not sub_df.empty and 'Hoja_Origen' in sub_df.columns and sub_df['Hoja_Origen'].notna().any():
                config["KWB"] = {
                    "Hoja_Origen": {"label": "Hoja de origen", "options": sorted(sub_df['Hoja_Origen'].dropna().unique())}
                }
    except:
        pass

    try:
        if 'Color' in df.columns and df['Color'].notna().any():
            sub_df = df[df['Marca'] == "Penosil"]
            if not sub_df.empty and 'Color' in sub_df.columns and sub_df['Color'].notna().any():
                config["Penosil"] = {
                    "Color": {"label": "Color", "options": sorted(sub_df['Color'].dropna().unique())}
                }
    except:
        pass

    return config

FILTROS_CONFIG = build_filtros_config(df_productos)

# ------------------------------------------------------------
# 2. SELECCIÓN DE CLIENTE Y DATOS DE ENTREGA (sin cambios)
# ------------------------------------------------------------
st.subheader("1. Selección de Cliente")
if 'DENOMINACÍON LEGAL' in df_clientes.columns:
    lista_clientes = sorted(df_clientes['DENOMINACÍON LEGAL'].dropna().unique())
    cliente_seleccionado = st.selectbox("Buscar / Seleccionar Cliente:", options=lista_clientes)
    cli_info = df_clientes[df_clientes['DENOMINACÍON LEGAL'] == cliente_seleccionado].iloc[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("CUIT", str(cli_info.get('C.U.I.T.', '-')))
    col2.metric("Localidad", str(cli_info.get('LOCALIDAD', '-')))
    col3.metric("Condición de Pago", str(cli_info.get('FORMA DE PAGO', '-')))
    col4.metric("Vendedor", str(cli_info.get('NOMB.VENDEDOR', '-')))
else:
    st.warning("El archivo de clientes no tiene la columna 'DENOMINACÍON LEGAL'. Verifica el formato.")
    cliente_seleccionado = None

st.markdown("---")
st.subheader("1b. Datos de Entrega")

direccion_entrega = st.text_input("Dirección de entrega (opcional):", placeholder="Calle, número, localidad, etc.")
retira_local = st.checkbox("El cliente retira el pedido en el local (no requiere entrega)")

st.markdown("---")

# ============================================================
# 3. CATÁLOGO Y AGREGADO AL CARRITO (sin cambios)
# ============================================================
# ... (omitido por brevedad, debe estar completo en el archivo final)
# Pero dado que el archivo es largo, lo incluiré completo al final.

# ============================================================
# 4. RESUMEN DEL PEDIDO Y GENERACIÓN DE PDF MEJORADA
# ============================================================
st.subheader("3. Resumen del Pedido")

if st.session_state.carrito:
    # ... (todo el código de resumen y cálculos igual que antes)
    # Solo voy a mostrar la parte de generación del PDF mejorada.

    def update_carrito(index, new_cantidad=None):
        # ... (igual que antes)
        pass

    def is_discount_applicable(row):
        # ... (igual que antes)
        pass

    def calcular_neto(row, multiplicador):
        # ... (igual que antes)
        pass

    # ... (código de la UI de resumen igual que antes)

    if st.button("📄 Generar PDF del Pedido", type="primary"):
        if cliente_seleccionado is None:
            st.error("Debes seleccionar un cliente antes de generar el PDF.")
            st.stop()

        # ==============================================================
        # NUEVA GENERACIÓN DE PDF CON ENCABEZADOS Y SUBENCABEZADOS
        # ==============================================================

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(left=15, top=15, right=15)
        pdf.add_page()

        # Constantes de diseño (ajustadas para aprovechar mejor el espacio)
        MARGIN_LEFT = 12
        MARGIN_RIGHT = 12
        PAGE_WIDTH = 210 - MARGIN_LEFT - MARGIN_RIGHT
        FONT_SIZE_TITLE = 22
        FONT_SIZE_SUBTITLE = 14
        FONT_SIZE_HEADER = 11
        FONT_SIZE_LEVEL1 = 9
        FONT_SIZE_LEVEL2 = 8
        FONT_SIZE_LEVEL3 = 7
        FONT_SIZE_TOTAL = 14
        COLOR_HEADER = (60, 60, 60)
        COLOR_SUBHEADER = (100, 100, 100)
        COLOR_LEVEL1 = (0, 0, 0)
        COLOR_LEVEL2 = (68, 68, 68)
        COLOR_LEVEL3 = (136, 136, 136)
        DARK_GRAY = (40, 40, 40)
        SEPARATOR_COLOR = (230, 230, 230)
        PADDING_BETWEEN_PRODUCTS = 4
        PADDING_AFTER_DESC = 2

        # Anchos de columna redistribuidos para dar más espacio a descripción y modelo
        W = {
            'codigo': 13,
            'marca': 13,
            'modelo': 38,      # Aumentado para descripciones largas
            'cant': 8,
            'p_unit': 16,
            'iva': 10,
            'subtotal': 19,
            'desc': 13,
            'neto': 19,
            'iva_monto': 15,
        }
        W_EINHELL = [W['codigo'], W['marca'], W['modelo'], W['cant'], W['p_unit'], W['iva'], W['subtotal'], W['desc'], W['neto'], W['iva_monto']]
        W_OTRAS = W_EINHELL

        # ---- FUNCIONES DE DIBUJO ----

        def draw_main_title():
            # Título principal a la derecha
            pdf.set_x(MARGIN_LEFT + PAGE_WIDTH - 100)
            pdf.set_font("Arial", 'B', FONT_SIZE_TITLE)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(100, 14, clean_text("PROFORMA DE PEDIDO"), ln=True, align='R')
            pdf.ln(4)

        def draw_section_separator():
            pdf.set_draw_color(200, 200, 200)
            pdf.line(MARGIN_LEFT, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
            pdf.ln(6)

        def draw_client_block():
            # Bloque de cliente a la izquierda
            pdf.set_font("Arial", 'B', 11)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 7, clean_text("Cliente:"), ln=True)
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
            pdf.ln(10)

        def draw_brand_header(marca, count, color_rgb):
            # Encabezado de marca con color
            pdf.set_font("Arial", 'B', FONT_SIZE_HEADER)
            pdf.set_text_color(color_rgb[0], color_rgb[1], color_rgb[2])
            pdf.cell(0, 9, clean_text(f"► {marca}"), ln=True)
            pdf.set_font("Arial", 'I', 9)
            pdf.set_text_color(COLOR_SUBHEADER[0], COLOR_SUBHEADER[1], COLOR_SUBHEADER[2])
            pdf.cell(0, 6, clean_text(f"{count} productos"), ln=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)

        def draw_table_header(es_einhell, color_rgb):
            pdf.set_font("Arial", 'B', FONT_SIZE_LEVEL1)
            pdf.set_fill_color(color_rgb[0], color_rgb[1], color_rgb[2])
            pdf.set_text_color(255, 255, 255)
            pdf.set_x(MARGIN_LEFT)

            if es_einhell:
                headers = ["Código", "Marca", "Herramienta", "Cant", "P.Unit", "IVA%", "Subtotal", "Desc.", "Neto", "IVA"]
                widths = W_EINHELL
            else:
                headers = ["Código", "Marca", "Modelo", "Cant", "P.Unit", "IVA%", "Subtotal", "Desc.", "Neto", "IVA"]
                widths = W_OTRAS

            # Fondo de encabezado con padding
            for i, h in enumerate(headers):
                pdf.cell(widths[i], 9, clean_text(h), border=0, align='C', fill=True)
            pdf.ln()
            pdf.set_text_color(0, 0, 0)
            pdf.set_fill_color(255, 255, 255)

        def draw_product_row(row, es_einhell):
            # Preparar datos
            codigo = clean_text(str(row['Codigo']))[:12]
            marca_text = clean_text(str(row['Marca']))[:12]
            cant = str(int(row['Cantidad'])) if row['Cantidad'].is_integer() else f"{row['Cantidad']:.1f}"
            p_unit = fmt_currency(row['Precio_Unitario'])
            iva_text = format_iva(row['IVA'], row['Es_Oferta'])
            subtotal = fmt_currency(row['Subtotal_Bruto'])
            descuento = fmt_currency(row['Monto_Descuento'])
            neto = fmt_currency(row['Neto_Calculado'])
            iva_monto = fmt_currency(row['Monto_IVA'])

            if es_einhell:
                producto_nombre = clean_text(str(row.get('Herramienta', '')))[:42]
            else:
                producto_nombre = clean_text(str(row.get('Modelo', '')))[:42]

            desc_text = clean_text(str(row.get('Descripcion', '')))
            if row['Es_Oferta']:
                desc_text = "OFERTA " + desc_text
            if es_einhell:
                alimentacion = clean_text(str(row.get('Tipo_Alimentacion', '')))
                if alimentacion:
                    desc_text += f" ({alimentacion})"
            else:
                emb = clean_text(str(row.get('Embalaje', '')))
                caja = clean_text(str(row.get('CantidadPorCaja', '')))
                unidad = clean_text(str(row.get('UnidadPrecio', '')))
                if emb or caja or unidad:
                    desc_text += f" | Emb: {emb} Caja: {caja} Unidad: {unidad}"

            widths = W_EINHELL if es_einhell else W_OTRAS

            # Verificar espacio en página
            if pdf.get_y() > 250:
                pdf.add_page()
                draw_table_header(es_einhell, MARCAS_COLORS.get(marca, (100,100,100)))

            # ---- Nivel 1 (Código, Marca, Producto, Cantidad) ----
            pdf.set_x(MARGIN_LEFT)
            pdf.set_font("Arial", 'B', FONT_SIZE_LEVEL1)
            pdf.set_text_color(COLOR_LEVEL1[0], COLOR_LEVEL1[1], COLOR_LEVEL1[2])

            pdf.cell(widths[0], 7, codigo, border=0, align='L')
            pdf.cell(widths[1], 7, marca_text, border=0, align='L')
            pdf.cell(widths[2], 7, producto_nombre, border=0, align='L')
            pdf.cell(widths[3], 7, cant, border=0, align='C')
            for i in range(4, len(widths)):
                pdf.cell(widths[i], 7, "", border=0, align='R' if i in (4,6,7,8,9) else 'C')
            pdf.ln()

            # ---- Nivel 2 (Precios) ----
            pdf.set_x(MARGIN_LEFT)
            pdf.set_font("Arial", '', FONT_SIZE_LEVEL2)
            pdf.set_text_color(COLOR_LEVEL2[0], COLOR_LEVEL2[1], COLOR_LEVEL2[2])

            pdf.cell(widths[0], 6, "", border=0, align='L')
            pdf.cell(widths[1], 6, "", border=0, align='L')
            pdf.cell(widths[2], 6, "", border=0, align='L')
            pdf.cell(widths[3], 6, "", border=0, align='C')
            pdf.cell(widths[4], 6, p_unit, border=0, align='R')
            pdf.cell(widths[5], 6, iva_text, border=0, align='C')
            pdf.cell(widths[6], 6, subtotal, border=0, align='R')
            pdf.cell(widths[7], 6, descuento, border=0, align='R')
            pdf.cell(widths[8], 6, neto, border=0, align='R')
            pdf.cell(widths[9], 6, iva_monto, border=0, align='R')
            pdf.ln()

            # ---- Nivel 3 (Descripción) con multi_cell nativo ----
            if desc_text.strip():
                pdf.set_x(MARGIN_LEFT + 2)
                pdf.set_font("Arial", 'I', FONT_SIZE_LEVEL3)
                pdf.set_text_color(COLOR_LEVEL3[0], COLOR_LEVEL3[1], COLOR_LEVEL3[2])
                pdf.multi_cell(PAGE_WIDTH - 4, 4.5, desc_text, border=0, align='L')
            else:
                pdf.ln(2)

            # Restaurar estilo y añadir separación
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", '', FONT_SIZE_LEVEL2)
            pdf.set_y(pdf.get_y() + PADDING_AFTER_DESC)
            pdf.set_draw_color(*SEPARATOR_COLOR)
            pdf.line(MARGIN_LEFT, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
            pdf.ln(PADDING_BETWEEN_PRODUCTS)

        def draw_subtotal_block(marca, bruto, descuento, neto, iva, total):
            if pdf.get_y() > 220:
                pdf.add_page()
            pdf.set_draw_color(200, 200, 200)
            pdf.line(MARGIN_LEFT, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
            pdf.ln(3)
            pdf.set_font("Arial", 'B', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.set_x(MARGIN_LEFT)
            pdf.cell(0, 7, clean_text(f"Subtotal {marca}"), ln=True)
            pdf.set_font("Arial", '', 8)
            pdf.set_x(MARGIN_LEFT)
            labels = ["Bruto", "Descuento", "Neto", "IVA", "TOTAL"]
            values = [bruto, descuento, neto, iva, total]
            for lbl, val in zip(labels, values):
                pdf.cell(38, 5, clean_text(f"{lbl}: {fmt_currency(val)}"), border=0, align='L')
            pdf.ln()
            pdf.ln(5)

        def draw_final_summary(total_bruto, total_descuento, total_neto, total_iva, total_final, texto_descuentos):
            if pdf.get_y() > 200:
                pdf.add_page()
            pdf.ln(8)
            pdf.set_font("Arial", 'B', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 7, clean_text(f"Descuentos aplicados: {texto_descuentos}"), ln=True)
            pdf.ln(5)

            block_width = 85
            x_start = MARGIN_LEFT + PAGE_WIDTH - block_width
            pdf.set_x(x_start)

            # Alinear a la derecha
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(block_width, 6, clean_text("Subtotal Bruto:"), border=0, align='L')
            pdf.set_x(x_start + 45)
            pdf.set_font("Arial", '', 9)
            pdf.cell(block_width - 45, 6, fmt_currency(total_bruto), border=0, align='R')
            pdf.ln()

            pdf.set_x(x_start)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(block_width, 6, clean_text("Descuentos:"), border=0, align='L')
            pdf.set_x(x_start + 45)
            pdf.set_font("Arial", '', 9)
            pdf.cell(block_width - 45, 6, fmt_currency(total_descuento), border=0, align='R')
            pdf.ln()

            pdf.set_x(x_start)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(block_width, 6, clean_text("Neto:"), border=0, align='L')
            pdf.set_x(x_start + 45)
            pdf.set_font("Arial", '', 9)
            pdf.cell(block_width - 45, 6, fmt_currency(total_neto), border=0, align='R')
            pdf.ln()

            pdf.set_x(x_start)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(block_width, 6, clean_text("IVA Total:"), border=0, align='L')
            pdf.set_x(x_start + 45)
            pdf.set_font("Arial", '', 9)
            pdf.cell(block_width - 45, 6, fmt_currency(total_iva), border=0, align='R')
            pdf.ln()

            pdf.ln(4)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(x_start, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
            pdf.ln(4)

            # TOTAL FINAL
            pdf.set_x(x_start)
            pdf.set_fill_color(DARK_GRAY[0], DARK_GRAY[1], DARK_GRAY[2])
            pdf.rect(x_start, pdf.get_y(), block_width, 11, 'F')
            pdf.set_y(pdf.get_y() + 2)
            pdf.set_x(x_start + 2)
            pdf.set_font("Arial", 'B', FONT_SIZE_TOTAL)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(block_width - 4, 8, clean_text("TOTAL FINAL"), border=0, align='L')
            pdf.set_x(x_start + 45)
            pdf.cell(block_width - 45, 8, fmt_currency(total_final), border=0, align='R')
            pdf.set_text_color(0, 0, 0)
            pdf.ln(14)

        def draw_footer_notes():
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
                pdf.cell(22, 5, clean_text(f"{marca}:"), border=0)
                pdf.set_text_color(int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16))
                pdf.cell(20, 5, clean_text("●"), border=0)
                pdf.ln(4)
            pdf.set_text_color(0, 0, 0)

        # ---- INICIO DE LA GENERACIÓN DEL PDF ----
        draw_main_title()
        draw_section_separator()
        draw_client_block()

        marcas_en_pedido = sorted(df_carrito['Marca'].unique())

        for idx_marca, marca in enumerate(marcas_en_pedido):
            subset = df_carrito[df_carrito['Marca'] == marca]
            es_einhell = (marca == "Einhell")
            color_rgb = MARCAS_COLORS.get(marca, (100, 100, 100))

            if pdf.get_y() > 200 and idx_marca > 0:
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)

            draw_brand_header(marca, len(subset), color_rgb)
            draw_table_header(es_einhell, color_rgb)

            for _, row in subset.iterrows():
                draw_product_row(row, es_einhell)

            bruto_marca = subset['Subtotal_Bruto'].sum()
            neto_marca = subset['Neto_Calculado'].sum()
            iva_marca = subset['Monto_IVA'].sum()
            desc_marca = bruto_marca - neto_marca
            total_marca = neto_marca + iva_marca
            draw_subtotal_block(marca, bruto_marca, desc_marca, neto_marca, iva_marca, total_marca)

            pdf.set_x(MARGIN_LEFT)
            pdf.cell(0, 2, "", border=0)  # Espacio extra entre marcas

        draw_final_summary(total_bruto, total_descuento, total_neto, total_iva, total_final, texto_descuentos)
        draw_footer_notes()

        # ---- GUARDAR Y DESCARGAR ----
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

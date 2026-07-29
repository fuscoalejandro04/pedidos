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
# FUNCIONES AUXILIARES (limpieza de texto, moneda, IVA)
# ------------------------------------------------------------
def normalize_text(text):
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text.lower()

def sanitize_text(text):
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
# 1. CARGAR DATOS Y DETECTAR OFERTAS
# ------------------------------------------------------------
@st.cache_data
def load_databases():
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
# 2. SELECCIÓN DE CLIENTE Y DATOS DE ENTREGA
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
# 3. CATÁLOGO Y AGREGADO AL CARRITO
# ============================================================
st.subheader("2. Catálogo de Productos")

marcas_disponibles = sorted(df_productos['Marca'].dropna().unique())
marca_filtro = st.selectbox("Filtrar por Línea / Marca:", options=["Todas"] + marcas_disponibles)

if marca_filtro == "Todas":
    filtros_adicionales = {}
else:
    filtros_adicionales = FILTROS_CONFIG.get(marca_filtro, {})

num_extra = len(filtros_adicionales)
if num_extra > 0:
    cols = st.columns([1] * num_extra + [2])
else:
    cols = st.columns([1])

filtro_valores = {}
col_idx = 0
for campo, config in filtros_adicionales.items():
    opciones = config["options"]
    if opciones:
        valor = cols[col_idx].selectbox(config["label"], options=["Todas"] + opciones)
        filtro_valores[campo] = valor
        col_idx += 1

busqueda = cols[-1].text_input("🔍 Buscar por Código, Modelo, Descripción, Marca o Herramienta:")

df_filtrado = df_productos.copy()

if marca_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Marca'] == marca_filtro]

for campo, valor in filtro_valores.items():
    if valor != "Todas":
        df_filtrado = df_filtrado[df_filtrado[campo] == valor]

if busqueda:
    palabras = [normalize_text(p) for p in busqueda.split()]
    df_filtrado['Codigo_norm'] = df_filtrado['Codigo'].astype(str).apply(normalize_text)
    df_filtrado['Modelo_norm'] = df_filtrado['Modelo'].astype(str).apply(normalize_text)
    df_filtrado['Descripcion_norm'] = df_filtrado['Descripcion'].astype(str).apply(normalize_text)
    df_filtrado['Marca_norm'] = df_filtrado['Marca'].astype(str).apply(normalize_text)
    if 'Herramienta' in df_filtrado.columns:
        df_filtrado['Herramienta_norm'] = df_filtrado['Herramienta'].astype(str).apply(normalize_text)

    def matches_all(row):
        text = f"{row['Codigo_norm']} {row['Modelo_norm']} {row['Descripcion_norm']} {row['Marca_norm']}"
        if 'Herramienta_norm' in row:
            text += f" {row['Herramienta_norm']}"
        return all(p in text for p in palabras)

    mask = df_filtrado.apply(matches_all, axis=1)
    df_filtrado = df_filtrado.loc[mask].copy()

    if not df_filtrado.empty:
        def relevance_score(row):
            score = 0
            cod = row['Codigo_norm']
            mod = row['Modelo_norm']
            desc = row['Descripcion_norm']
            for p in palabras:
                if p in cod:
                    score += 10
                if p in mod:
                    score += 5
                if p in desc:
                    score += 1
                if 'Herramienta_norm' in row and p in row['Herramienta_norm']:
                    score += 3
            return score

        df_filtrado['Relevance'] = df_filtrado.apply(relevance_score, axis=1)
        df_filtrado = df_filtrado.sort_values('Relevance', ascending=False)
        cols_aux = ['Codigo_norm', 'Modelo_norm', 'Descripcion_norm', 'Marca_norm']
        if 'Herramienta_norm' in df_filtrado.columns:
            cols_aux.append('Herramienta_norm')
        df_filtrado = df_filtrado.drop(columns=cols_aux + ['Relevance'])
    else:
        cols_aux = ['Codigo_norm', 'Modelo_norm', 'Descripcion_norm', 'Marca_norm']
        if 'Herramienta_norm' in df_filtrado.columns:
            cols_aux.append('Herramienta_norm')
        df_filtrado = df_filtrado.drop(columns=cols_aux)

st.markdown("##### Agregar al Pedido")

if not df_filtrado.empty:
    def format_display(row):
        precio = row['Precio_Oferta'] if row['Es_Oferta'] else row['Precio_Lista']
        etiqueta = "🔥 OFERTA " if row['Es_Oferta'] else ""
        herramienta = str(row.get('Herramienta', ''))[:20] if pd.notna(row.get('Herramienta')) else ''
        iva_str = format_iva(row['IVA'], row['Es_Oferta'])
        iva_icon = "🔵" if row['IVA'] == 0.105 else "🟢" if row['IVA'] == 0.21 else "⚪"
        desc = str(row['Descripcion'])[:25]
        parts = [f"{row['Codigo']}", f"{row['Marca']}"]
        if herramienta:
            parts.append(f"[{herramienta}]")
        parts.append(f"{desc}")
        parts.append(f"{fmt_currency(precio)}")
        parts.append(f"{iva_icon} {iva_str}")
        return f"{etiqueta} | ".join(parts)

    df_filtrado['Display'] = df_filtrado.apply(format_display, axis=1)

    df_filtrado['Codigo_Base'] = df_filtrado['Codigo'].astype(str).apply(lambda x: re.sub(r'[^0-9]', '', x))
    df_filtrado['Clave_Producto'] = df_filtrado['Codigo_Base'] + '_' + df_filtrado['Marca']

    productos_unicos = df_filtrado.drop_duplicates(subset=['Clave_Producto']).copy()
    productos_unicos['Descripcion'] = productos_unicos['Descripcion'].fillna('').astype(str)
    productos_unicos['Display'] = productos_unicos.apply(format_display, axis=1)
    display_options = productos_unicos['Display'].tolist()

    col_sel, col_qty, col_btn = st.columns([3, 1, 1])
    prod_seleccionado_display = col_sel.selectbox("Seleccione el producto:", options=display_options)

    if prod_seleccionado_display:
        prod_row = productos_unicos[productos_unicos['Display'] == prod_seleccionado_display].iloc[0]
        clave_seleccionada = prod_row['Clave_Producto']

        presentaciones = df_filtrado[df_filtrado['Clave_Producto'] == clave_seleccionada].copy()
        presentaciones = presentaciones.sort_values(['CantidadPorCaja', 'Embalaje'], ascending=[True, True])

        if len(presentaciones) > 1:
            def format_presentacion(row):
                info = get_product_info(row)
                return info['presentacion_text']

            presentaciones['Presentacion_Label'] = presentaciones.apply(format_presentacion, axis=1)
            presentacion_opciones = presentaciones['Presentacion_Label'].tolist()
            presentacion_seleccionada = st.selectbox("Elegir presentación:", options=presentacion_opciones)
            prod_data = presentaciones[presentaciones['Presentacion_Label'] == presentacion_seleccionada].iloc[0]
        else:
            prod_data = presentaciones.iloc[0]

        info = get_product_info(prod_data)

        with st.expander("📋 Detalles del producto seleccionado", expanded=True):
            col_det1, col_det2 = st.columns(2)
            col_det1.markdown(f"**Código:** `{prod_data['Codigo']}`")
            col_det1.markdown(f"**Marca:** {prod_data['Marca']}")
            col_det1.markdown(f"**Modelo:** {prod_data['Modelo']}")
            if pd.notna(prod_data.get('Herramienta')):
                col_det1.markdown(f"**Herramienta:** {prod_data['Herramienta']}")
            if pd.notna(prod_data.get('Categoria_Generica')):
                col_det1.markdown(f"**Categoría:** {prod_data['Categoria_Generica']}")
            if pd.notna(prod_data.get('Tipo_Alimentacion')):
                col_det1.markdown(f"**Alimentación:** {prod_data['Tipo_Alimentacion']}")
            col_det2.markdown(f"**Descripción:** {prod_data['Descripcion']}")
            col_det2.markdown(f"**IVA:** {iva_badge(prod_data['IVA'])}", unsafe_allow_html=True)

            extra_info = []
            if pd.notna(prod_data.get('Embalaje')):
                extra_info.append(f"**Embalaje mayor:** {prod_data['Embalaje']}")
            if pd.notna(prod_data.get('CantidadPorCaja')):
                extra_info.append(f"**Cant. por unidad de venta:** {prod_data['CantidadPorCaja']}")
            if pd.notna(prod_data.get('UnidadPrecio')):
                extra_info.append(f"**Unidad de precio:** {prod_data['UnidadPrecio']}")
            if extra_info:
                st.markdown("**Datos de empaque:** " + " | ".join(extra_info))

            st.markdown("---")
            st.markdown(f"**Unidad de venta:** {info['unidad_venta']}")
            if info['tipo_cantidad'] == 'lotes':
                st.markdown(f"**Precio por {info['unidad_venta']}:** {fmt_currency(info['precio_lote'])}")
                st.markdown(f"**Cada {info['unidad_venta']} contiene:** {info['cantidad_por_lote']} unidades")
                st.markdown(f"**Precio unitario (referencia):** {fmt_currency(info['precio_lote'] / info['cantidad_por_lote'])}")
            else:
                st.markdown(f"**Precio unitario:** {fmt_currency(info['precio_unitario'])}")
                st.markdown(f"**Presentación de:** {info['cantidad_por_lote']} unidades ({fmt_currency(info['precio_lote'])})")
                if info['step'] > 1:
                    st.info(f"📦 Venta en cajas de {info['step']} unidades. La cantidad debe ser múltiplo de {info['step']}.")

            precio_oferta = prod_data['Precio_Oferta'] if prod_data['Es_Oferta'] else None
            if prod_data['Es_Oferta']:
                st.markdown(f"**Precio de oferta:** {fmt_currency(precio_oferta)} por unidad")
            if prod_data.get('Hoja_Origen') and "BATERÍAS Y CARGADORES" in str(prod_data['Hoja_Origen']).upper():
                st.info("🔋 Este producto es de la hoja BATERÍAS Y CARGADORES y no recibe descuentos adicionales.")

        if prod_data['Es_Oferta']:
            precio_unitario_a_usar = prod_data['Precio_Oferta']
        else:
            precio_unitario_a_usar = info['precio_unitario']

        step = info['step']
        min_val = info['min_value']
        valor_inicial = step if step > 1 else 1.0

        if info['tipo_cantidad'] == 'lotes':
            label_cantidad = f"Cantidad ({info['unidad_venta']})"
            ayuda_extra = f" (1 {info['unidad_venta']} = {info['cantidad_por_lote']} unidades)"
        else:
            if step > 1:
                label_cantidad = f"Cantidad (múltiplos de {step})"
                ayuda_extra = f" (caja de {step} unidades)"
            else:
                label_cantidad = "Cantidad (unidades sueltas)"
                ayuda_extra = ""

        cantidad = col_qty.number_input(
            label_cantidad,
            min_value=min_val,
            value=valor_inicial,
            step=step,
            format="%g"
        )

        if info['ayuda']:
            st.caption(info['ayuda'] + (ayuda_extra if ayuda_extra else ""))

        if col_btn.button("➕ Agregar al Carrito", use_container_width=True):
            if cantidad <= 0:
                st.error("La cantidad debe ser mayor a 0.")
            else:
                if step > 1 and min_val > 0:
                    if cantidad % step != 0:
                        st.error(f"La cantidad debe ser múltiplo de {step} (cajas completas).")
                        st.stop()

                clave_presentacion = f"{prod_data['Codigo']}_{prod_data.get('Embalaje', '')}_{prod_data.get('CantidadPorCaja', '')}_{prod_data.get('UnidadPrecio', '')}"

                item_existente = None
                for idx, item in enumerate(st.session_state.carrito):
                    if item.get('Clave_Presentacion') == clave_presentacion:
                        item_existente = idx
                        break

                if item_existente is not None:
                    st.session_state.carrito[item_existente]['Cantidad'] += cantidad
                    st.session_state.carrito[item_existente]['Subtotal_Bruto'] = st.session_state.carrito[item_existente]['Precio_Unitario'] * st.session_state.carrito[item_existente]['Cantidad']
                    st.success(f"¡Cantidad actualizada! +{cantidad} unidades (total: {st.session_state.carrito[item_existente]['Cantidad']})")
                else:
                    st.session_state.carrito.append({
                        "Codigo": str(prod_data['Codigo']),
                        "Descripcion": str(prod_data['Descripcion']),
                        "Modelo": str(prod_data['Modelo']),
                        "Marca": str(prod_data['Marca']),
                        "Hoja_Origen": str(prod_data['Hoja_Origen']),
                        "Herramienta": str(prod_data.get('Herramienta', '')) if pd.notna(prod_data.get('Herramienta')) else '',
                        "Categoria_Generica": str(prod_data.get('Categoria_Generica', '')) if pd.notna(prod_data.get('Categoria_Generica')) else '',
                        "Tipo_Alimentacion": str(prod_data.get('Tipo_Alimentacion', '')) if pd.notna(prod_data.get('Tipo_Alimentacion')) else '',
                        "Cantidad": cantidad,
                        "Precio_Unitario": precio_unitario_a_usar,
                        "Es_Oferta": prod_data['Es_Oferta'],
                        "IVA": prod_data['IVA'],
                        "Subtotal_Bruto": precio_unitario_a_usar * cantidad,
                        "Embalaje": str(prod_data.get('Embalaje', '')) if pd.notna(prod_data.get('Embalaje')) else '',
                        "CantidadPorCaja": str(prod_data.get('CantidadPorCaja', '')) if pd.notna(prod_data.get('CantidadPorCaja')) else '',
                        "UnidadPrecio": str(prod_data.get('UnidadPrecio', '')) if pd.notna(prod_data.get('UnidadPrecio')) else '',
                        "Precio_Presentacion": info['precio_lote'],
                        "Tipo_Cantidad": info['tipo_cantidad'],
                        "Cantidad_Por_Lote": info['cantidad_por_lote'],
                        "Step": info['step'],
                        "Min_Value": info['min_value'],
                        "Clave_Presentacion": clave_presentacion,
                        "Presentacion_Text": info['presentacion_text'],
                        "Unidad_Venta": info['unidad_venta']
                    })
                    st.success(f"¡Agregado: {cantidad}x {prod_data['Codigo']}!")
else:
    st.info("No se encontraron productos con esa búsqueda.")

st.markdown("---")

# ============================================================
# 4. RESUMEN DEL PEDIDO Y GENERACIÓN DE PDF
# ============================================================
st.subheader("3. Resumen del Pedido")

if st.session_state.carrito:
    def update_carrito(index, new_cantidad=None):
        if new_cantidad is not None:
            if new_cantidad <= 0:
                st.session_state.carrito.pop(index)
                st.rerun()
                return
            step = st.session_state.carrito[index].get('Step', 1)
            min_val = st.session_state.carrito[index].get('Min_Value', 0)
            if step > 1 and min_val > 0:
                if new_cantidad % step != 0:
                    new_cantidad = ((new_cantidad + step - 1) // step) * step
                    st.warning(f"La cantidad se ajustó a {new_cantidad} (múltiplo de {step})")
            st.session_state.carrito[index]['Cantidad'] = new_cantidad
            st.session_state.carrito[index]['Subtotal_Bruto'] = st.session_state.carrito[index]['Precio_Unitario'] * new_cantidad
        else:
            st.session_state.carrito.pop(index)
        st.rerun()

    def is_discount_applicable(row):
        if row['Es_Oferta']:
            return False
        if row.get('Hoja_Origen') and "BATERÍAS Y CARGADORES" in str(row['Hoja_Origen']).upper():
            return False
        return True

    def calcular_neto(row, multiplicador):
        if is_discount_applicable(row):
            return row['Subtotal_Bruto'] * multiplicador
        return row['Subtotal_Bruto']

    st.markdown("#### Bonificaciones y Cierre")
    col_desc1, col_desc2, col_desc3, _ = st.columns([1, 1, 1, 2])

    desc_gen = col_desc1.number_input("Desc. General (%)", min_value=0.0, max_value=100.0, value=30.0, step=1.0)
    desc_ad1 = col_desc2.number_input("Desc. Adicional 1 (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
    desc_ad2 = col_desc3.number_input("Desc. Adicional 2 (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)

    multiplicador_desc = (1 - (desc_gen / 100)) * (1 - (desc_ad1 / 100)) * (1 - (desc_ad2 / 100))
    descuentos_usados = [f"-{d}%" for d in [desc_gen, desc_ad1, desc_ad2] if d > 0]
    texto_descuentos = " ".join(descuentos_usados) if descuentos_usados else "Sin bonificación"

    df_carrito = pd.DataFrame(st.session_state.carrito)

    df_carrito['Neto_Calculado'] = df_carrito.apply(lambda row: calcular_neto(row, multiplicador_desc), axis=1)
    df_carrito['Monto_Descuento'] = df_carrito['Subtotal_Bruto'] - df_carrito['Neto_Calculado']
    df_carrito['Monto_IVA'] = df_carrito['Neto_Calculado'] * df_carrito['IVA']

    total_bruto = df_carrito['Subtotal_Bruto'].sum()
    total_neto = df_carrito['Neto_Calculado'].sum()
    total_iva = df_carrito['Monto_IVA'].sum()
    total_final = total_neto + total_iva
    total_descuento = total_bruto - total_neto

    st.markdown("#### 📊 Resumen General")
    col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
    col_kpi1.metric("Subtotal Bruto", fmt_currency(total_bruto))
    col_kpi2.metric(f"Descuentos ({texto_descuentos})", fmt_currency(total_descuento))
    col_kpi3.metric("Neto", fmt_currency(total_neto))
    col_kpi4.metric("IVA Total", fmt_currency(total_iva))
    col_kpi5.metric("Total Final", fmt_currency(total_final), delta=None)

    st.markdown("---")

    st.markdown("#### 📋 Detalle de Productos")
    base_cols = ['Codigo', 'Marca', 'Modelo', 'Descripcion', 'Cantidad', 'Precio_Unitario', 'IVA', 'Subtotal_Bruto', 'Monto_Descuento', 'Neto_Calculado', 'Monto_IVA', 'Es_Oferta']
    extra_cols = []
    if 'Embalaje' in df_carrito.columns and df_carrito['Embalaje'].notna().any():
        extra_cols.extend(['Embalaje', 'CantidadPorCaja', 'UnidadPrecio'])
    if extra_cols:
        idx = base_cols.index('Descripcion') + 1
        cols_mostrar = base_cols[:idx] + extra_cols + base_cols[idx:]
    else:
        cols_mostrar = base_cols
    cols_mostrar = [col for col in cols_mostrar if col in df_carrito.columns]

    df_mostrar = df_carrito[cols_mostrar].copy()
    numeric_cols = ['Precio_Unitario', 'Subtotal_Bruto', 'Monto_Descuento', 'Neto_Calculado', 'Monto_IVA']
    for col in numeric_cols:
        if col in df_mostrar.columns:
            df_mostrar[col] = df_mostrar[col].apply(fmt_currency)
    if 'IVA' in df_mostrar.columns:
        df_mostrar['IVA'] = df_mostrar.apply(lambda row: format_iva(row['IVA'], row['Es_Oferta']), axis=1)
    if 'Es_Oferta' in df_mostrar.columns:
        df_mostrar['Es_Oferta'] = df_mostrar['Es_Oferta'].apply(lambda x: "🔥 Oferta" if x else "")

    st.dataframe(df_mostrar, use_container_width=True)

    st.markdown("---")

    st.markdown("#### 📦 Resumen por Marca")
    marcas_unicas = sorted(df_carrito['Marca'].unique())
    marca_data = []
    for marca in marcas_unicas:
        mask = df_carrito['Marca'] == marca
        subset = df_carrito[mask]
        bruto = subset['Subtotal_Bruto'].sum()
        neto = subset['Neto_Calculado'].sum()
        iva = subset['Monto_IVA'].sum()
        desc = bruto - neto
        final = neto + iva
        items = len(subset)
        ofertas = subset[subset['Es_Oferta'] == True]['Codigo'].tolist()
        marca_data.append({
            'Marca': marca,
            'Items': items,
            'Bruto': bruto,
            'Descuento': desc,
            'Neto': neto,
            'IVA': iva,
            'Total': final,
            'Ofertas': ", ".join(ofertas) if ofertas else "Ninguna"
        })

    df_marca = pd.DataFrame(marca_data)
    for col in ['Bruto', 'Descuento', 'Neto', 'IVA', 'Total']:
        df_marca[col] = df_marca[col].apply(fmt_currency)
    st.dataframe(df_marca, use_container_width=True)

    st.markdown("---")

    col_tot1, col_tot2, col_tot3, col_tot4, col_tot5 = st.columns(5)
    col_tot1.metric("Subtotal Bruto", fmt_currency(total_bruto))
    col_tot2.metric(f"Descuentos ({texto_descuentos})", fmt_currency(total_descuento))
    col_tot3.metric("Neto", fmt_currency(total_neto))
    col_tot4.metric("IVA Total", fmt_currency(total_iva))
    col_tot5.metric("TOTAL FINAL", fmt_currency(total_final), delta=None, delta_color="inverse")

    st.markdown("---")

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("🗑️ Vaciar Carrito", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

    with col_btn2:
        if st.button("📄 Generar PDF del Pedido", type="primary", use_container_width=True):
            if cliente_seleccionado is None:
                st.error("Debes seleccionar un cliente antes de generar el PDF.")
                st.stop()

            # ==============================================================
            # NUEVO MOTOR PDF - JERARQUÍA CENTRADA EN VENDEDOR
            # ==============================================================

            # ---------- CONSTANTES DE DISEÑO ----------
            MARGIN_LEFT = 12
            MARGIN_RIGHT = 12
            MARGIN_TOP = 12
            PAGE_WIDTH = 210 - MARGIN_LEFT - MARGIN_RIGHT
            MARGIN_BOTTOM = 18

            # Tamaños de fuente (jerarquía clara)
            FS_TITLE = 16
            FS_CLIENT = 8.5
            FS_BRAND = 10
            FS_PROD_NAME = 9.5       # Nombre del producto
            FS_QTY = 14              # Cantidad (MUY DESTACADA)
            FS_DETAILS = 7.5         # Detalles/descripción
            FS_SECONDARY = 7.5       # PU, IVA, descuento, neto
            FS_TOTAL_LINE = 10       # Total de línea (destacado)
            FS_SUBTOTAL = 9
            FS_FINAL = 12

            # Colores
            COLOR_SEPARATOR = (190, 190, 190)
            COLOR_DISCOUNT = (180, 0, 0)
            COLOR_SECONDARY = (90, 90, 90)

            # Alturas y espaciados (compactos)
            LINE_HEIGHT = 4.5
            PADDING_AFTER_PRODUCT = 2

            # ---------- FUNCIONES DE DIBUJO ----------

            def draw_title(pdf):
                pdf.set_x(MARGIN_LEFT + PAGE_WIDTH - 80)
                pdf.set_font("Arial", "B", FS_TITLE)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(80, 11, "PROFORMA DE PEDIDO", ln=True, align="R")
                pdf.ln(3)

            def draw_client_block(pdf, cli_info, cliente_seleccionado, direccion_entrega, retira_local):
                """Encabezado del cliente en 2 columnas (muy compacto)"""
                # Datos
                codigo_cliente = cli_info.get('CODIGO') or cli_info.get('Código') or cli_info.get('Codigo')
                cuit = cli_info.get('C.U.I.T.', '-')
                direccion_cliente = cli_info.get('Dirección') or cli_info.get('DOMICILIO') or cli_info.get('Domicilio')
                condicion = cli_info.get('FORMA DE PAGO', '-')
                vendedor = cli_info.get('NOMB.VENDEDOR', '-')
                fecha = datetime.now().strftime('%d/%m/%Y %H:%M')

                pdf.set_font("Arial", "", FS_CLIENT)
                pdf.set_text_color(0, 0, 0)

                # Fila 1: Cliente (con código)  |  Fecha
                pdf.set_x(MARGIN_LEFT)
                if codigo_cliente and pd.notna(codigo_cliente):
                    pdf.cell(PAGE_WIDTH * 0.55, 5, f"Cliente: {clean_text(cliente_seleccionado)} (Cód: {codigo_cliente})", border=0)
                else:
                    pdf.cell(PAGE_WIDTH * 0.55, 5, f"Cliente: {clean_text(cliente_seleccionado)}", border=0)
                pdf.cell(PAGE_WIDTH * 0.45, 5, f"Fecha: {fecha}", border=0, align="R")
                pdf.ln(5)

                # Fila 2: CUIT  |  Vendedor
                pdf.set_x(MARGIN_LEFT)
                pdf.cell(PAGE_WIDTH * 0.55, 5, f"CUIT: {cuit}", border=0)
                pdf.cell(PAGE_WIDTH * 0.45, 5, f"Vendedor: {vendedor}", border=0, align="R")
                pdf.ln(5)

                # Fila 3: Dirección del cliente  |  Condición de pago
                pdf.set_x(MARGIN_LEFT)
                if direccion_cliente and pd.notna(direccion_cliente):
                    pdf.cell(PAGE_WIDTH * 0.55, 5, clean_text(direccion_cliente), border=0)
                else:
                    pdf.cell(PAGE_WIDTH * 0.55, 5, "", border=0)
                pdf.cell(PAGE_WIDTH * 0.45, 5, f"Condición: {condicion}", border=0, align="R")
                pdf.ln(5)

                # Fila 4: Entrega  |  (vacío o información adicional)
                pdf.set_x(MARGIN_LEFT)
                if retira_local:
                    pdf.cell(PAGE_WIDTH * 0.55, 5, "Entrega: El cliente retira en el local", border=0)
                elif direccion_entrega:
                    pdf.cell(PAGE_WIDTH * 0.55, 5, f"Entrega: {clean_text(direccion_entrega)}", border=0)
                else:
                    pdf.cell(PAGE_WIDTH * 0.55, 5, "Entrega: Sin especificar", border=0)
                pdf.cell(PAGE_WIDTH * 0.45, 5, "", border=0, align="R")
                pdf.ln(5)

                pdf.ln(4)

            def draw_brand_header(pdf, marca, count):
                color_map = {
                    "Einhell": (139, 50, 50),
                    "KWB": (139, 50, 50),
                    "Fijaciones": (204, 85, 0),
                    "Penosil": (255, 0, 0),
                }
                color = color_map.get(marca, (80, 80, 80))
                pdf.set_font("Arial", "B", FS_BRAND)
                pdf.set_text_color(color[0], color[1], color[2])
                pdf.set_x(MARGIN_LEFT)
                pdf.cell(PAGE_WIDTH, 6, f"► {marca} ({count} productos)", ln=True)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(1)

            def draw_separator(pdf, y=None):
                if y is None:
                    y = pdf.get_y()
                pdf.set_draw_color(*COLOR_SEPARATOR)
                pdf.line(MARGIN_LEFT, y, MARGIN_LEFT + PAGE_WIDTH, y)

            def estimate_product_height(pdf, row, es_einhell):
                """Calcula la altura exacta que ocupará un bloque de producto."""
                # Preparar textos
                if es_einhell:
                    nombre = clean_text(str(row.get('Herramienta', row['Modelo'])))
                else:
                    nombre = clean_text(str(row.get('Modelo', '')))

                # Construir detalles
                detalles = []
                if pd.notna(row.get('Color')) and row['Color']:
                    detalles.append(f"Color: {clean_text(row['Color'])}")
                if pd.notna(row.get('Embalaje')) and row['Embalaje']:
                    detalles.append(f"Emb: {clean_text(row['Embalaje'])}")
                if pd.notna(row.get('CantidadPorCaja')) and row['CantidadPorCaja']:
                    detalles.append(f"Caja: {clean_text(row['CantidadPorCaja'])}")
                if pd.notna(row.get('UnidadPrecio')) and row['UnidadPrecio']:
                    detalles.append(f"Unidad: {clean_text(row['UnidadPrecio'])}")
                if not es_einhell and not detalles:
                    detalles.append(clean_text(str(row.get('Descripcion', ''))))
                texto_detalles = " | ".join(detalles) if detalles else ""

                # Calcular líneas del nombre (ocupa el ancho total menos 40 mm para la cantidad)
                name_width = PAGE_WIDTH - 42
                pdf.set_font("Arial", "B", FS_PROD_NAME)
                avg_char_width = pdf.get_string_width("M") * 0.6
                chars_per_line = int(name_width / avg_char_width) if avg_char_width > 0 else 40
                lines_nombre = max(1, (len(nombre) + chars_per_line - 1) // chars_per_line)

                # Calcular líneas de detalles (MultiCell a todo lo ancho)
                lines_detalles = 0
                if texto_detalles:
                    pdf.set_font("Arial", "I", FS_DETAILS)
                    avg_char_width = pdf.get_string_width("M") * 0.6
                    chars_per_line = int((PAGE_WIDTH - 4) / avg_char_width) if avg_char_width > 0 else 40
                    lines_detalles = max(1, (len(texto_detalles) + chars_per_line - 1) // chars_per_line)

                # Altura total:
                # Línea 1: nombre + cantidad (altura variable según líneas de nombre)
                # Línea 2: detalles (altura variable)
                # Línea 3: precios secundarios + total (altura fija)
                # Separador + padding
                height = 0
                height += lines_nombre * LINE_HEIGHT
                if lines_detalles > 0:
                    height += lines_detalles * LINE_HEIGHT + 1
                height += 5.5  # línea de precios
                height += PADDING_AFTER_PRODUCT
                return height

            def draw_product_block(pdf, row, es_einhell):
                """
                Dibuja un producto con jerarquía:
                - Línea 1: [Código - Nombre] (negrita)  y  [CANTIDAD] (grande, negrita, derecha)
                - Línea 2: detalles (cursiva, pequeño) si existen
                - Línea 3: PU: $xxx  IVA: xx%  Descuento: -$xxx  (pequeño, gris)  → TOTAL: $xxx (negrita)
                """
                # Preparar datos
                codigo = clean_text(str(row['Codigo']))[:12]
                if es_einhell:
                    nombre = clean_text(str(row.get('Herramienta', row['Modelo'])))
                else:
                    nombre = clean_text(str(row.get('Modelo', '')))

                cant = int(row['Cantidad']) if row['Cantidad'].is_integer() else row['Cantidad']
                p_unit = row['Precio_Unitario']
                subtotal = row['Subtotal_Bruto']
                descuento = row['Monto_Descuento']
                neto = row['Neto_Calculado']
                iva_monto = row['Monto_IVA']
                iva_tasa = row['IVA']
                es_oferta = row['Es_Oferta']
                total_linea = neto + iva_monto

                # Construir detalles
                detalles = []
                if pd.notna(row.get('Color')) and row['Color']:
                    detalles.append(f"Color: {clean_text(row['Color'])}")
                if pd.notna(row.get('Embalaje')) and row['Embalaje']:
                    detalles.append(f"Emb: {clean_text(row['Embalaje'])}")
                if pd.notna(row.get('CantidadPorCaja')) and row['CantidadPorCaja']:
                    detalles.append(f"Caja: {clean_text(row['CantidadPorCaja'])}")
                if pd.notna(row.get('UnidadPrecio')) and row['UnidadPrecio']:
                    detalles.append(f"Unidad: {clean_text(row['UnidadPrecio'])}")
                if not es_einhell and not detalles:
                    detalles.append(clean_text(str(row.get('Descripcion', ''))))
                texto_detalles = " | ".join(detalles) if detalles else ""

                # ----- Línea 1: Nombre (izquierda)  |  Cantidad (derecha, enorme) -----
                name_width = PAGE_WIDTH - 42
                pdf.set_x(MARGIN_LEFT)
                pdf.set_font("Arial", "B", FS_PROD_NAME)
                pdf.set_text_color(0, 0, 0)

                # Nombre con código
                name_text = f"{codigo} - {nombre}"
                # Si el nombre es muy largo, usar MultiCell para que no se corte
                if pdf.get_string_width(name_text) > name_width:
                    # Usamos MultiCell para el nombre, pero la cantidad va aparte
                    pdf.set_x(MARGIN_LEFT)
                    pdf.multi_cell(name_width, LINE_HEIGHT, name_text, border=0, align="L")
                    # Guardar la posición Y después del nombre
                    y_after_name = pdf.get_y()
                    # Ahora dibujamos la cantidad en la posición correcta (a la derecha, alineada a la parte superior del bloque)
                    # Para simplificar, usamos un enfoque: primero dibujamos la cantidad, luego el nombre.
                    # Mejor: dibujamos cantidad en la primera línea usando cell normal.
                    # Volvemos atrás y lo hacemos de forma más controlada
                    pdf.set_y(pdf.get_y() - LINE_HEIGHT * 1.5)  # retrocedemos un poco
                    # Re-dibujamos con enfoque de dos columnas
                    pdf.set_x(MARGIN_LEFT)
                    pdf.set_font("Arial", "B", FS_PROD_NAME)
                    # Usamos cell para el nombre, truncando si es necesario
                    pdf.cell(name_width, LINE_HEIGHT, name_text[:60], border=0, align="L")
                    # Cantidad a la derecha
                    pdf.set_x(MARGIN_LEFT + name_width)
                    pdf.set_font("Arial", "B", FS_QTY)
                    pdf.set_text_color(0, 0, 0)
                    pdf.cell(42, LINE_HEIGHT, f"{cant}", border=0, align="R")
                    pdf.ln(LINE_HEIGHT)
                else:
                    # Nombre cabe en una línea
                    pdf.set_x(MARGIN_LEFT)
                    pdf.cell(name_width, LINE_HEIGHT, name_text, border=0, align="L")
                    pdf.set_x(MARGIN_LEFT + name_width)
                    pdf.set_font("Arial", "B", FS_QTY)
                    pdf.set_text_color(0, 0, 0)
                    pdf.cell(42, LINE_HEIGHT, f"{cant}", border=0, align="R")
                    pdf.ln(LINE_HEIGHT)

                # ----- Línea 2: Detalles (MultiCell, cursiva, pequeño) -----
                if texto_detalles:
                    pdf.set_x(MARGIN_LEFT + 2)
                    pdf.set_font("Arial", "I", FS_DETAILS)
                    pdf.set_text_color(COLOR_SECONDARY[0], COLOR_SECONDARY[1], COLOR_SECONDARY[2])
                    pdf.multi_cell(PAGE_WIDTH - 4, LINE_HEIGHT, texto_detalles, border=0, align="L")
                    pdf.set_y(pdf.get_y() + 1)  # pequeño padding

                # ----- Línea 3: Precios secundarios (izquierda) y Total (derecha) -----
                pdf.set_x(MARGIN_LEFT)
                pdf.set_font("Arial", "", FS_SECONDARY)
                pdf.set_text_color(COLOR_SECONDARY[0], COLOR_SECONDARY[1], COLOR_SECONDARY[2])

                # Precio Unitario
                pu_text = f"PU: {fmt_currency(p_unit)}"
                pdf.cell(50, 5, pu_text, border=0, align="L")

                # IVA
                iva_text = f"IVA: {format_iva(iva_tasa, es_oferta)}"
                pdf.cell(35, 5, iva_text, border=0, align="L")

                # Descuento (si aplica)
                if descuento > 0:
                    pdf.set_text_color(*COLOR_DISCOUNT)
                    pdf.cell(45, 5, f"Desc: -{fmt_currency(descuento)}", border=0, align="L")
                    pdf.set_text_color(COLOR_SECONDARY[0], COLOR_SECONDARY[1], COLOR_SECONDARY[2])
                else:
                    pdf.cell(45, 5, "", border=0, align="L")

                # Total de línea (destacado, a la derecha)
                pdf.set_x(MARGIN_LEFT + PAGE_WIDTH - 70)
                pdf.set_font("Arial", "B", FS_TOTAL_LINE)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(70, 5, f"→ TOTAL: {fmt_currency(total_linea)}", border=0, align="R")
                pdf.ln(5.5)

                # Separador
                draw_separator(pdf, pdf.get_y())
                pdf.ln(PADDING_AFTER_PRODUCT)

            def draw_subtotal_block(pdf, marca, bruto, descuento, neto, iva, total):
                if pdf.get_y() > 200:
                    pdf.add_page()
                pdf.set_draw_color(*COLOR_SEPARATOR)
                pdf.line(MARGIN_LEFT, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
                pdf.ln(2)
                pdf.set_font("Arial", "B", FS_SUBTOTAL)
                pdf.set_text_color(0, 0, 0)
                pdf.set_x(MARGIN_LEFT)
                pdf.cell(0, 5.5, f"Subtotal {marca}", ln=True)
                pdf.set_font("Arial", "", FS_SUBTOTAL - 1)
                pdf.set_x(MARGIN_LEFT)
                items = [
                    f"Bruto: {fmt_currency(bruto)}",
                    f"Descuento: {fmt_currency(descuento)}",
                    f"Neto: {fmt_currency(neto)}",
                    f"IVA: {fmt_currency(iva)}",
                    f"TOTAL: {fmt_currency(total)}"
                ]
                for item in items:
                    pdf.cell(36, 4.5, item, border=0, align="L")
                pdf.ln()
                pdf.ln(3)

            def draw_final_summary(pdf, total_bruto, total_descuento, total_neto, total_iva, total_final, texto_descuentos):
                if pdf.get_y() > 180:
                    pdf.add_page()
                pdf.ln(5)
                pdf.set_font("Arial", "B", FS_SUBTOTAL)
                pdf.set_text_color(0, 0, 0)
                pdf.set_x(MARGIN_LEFT)
                pdf.cell(0, 6, f"Descuentos aplicados: {texto_descuentos}", ln=True)
                pdf.ln(3)

                block_width = 80
                x_start = MARGIN_LEFT + PAGE_WIDTH - block_width

                pdf.set_font("Arial", "B", FS_SUBTOTAL - 1)
                pdf.set_x(x_start)
                pdf.cell(block_width, 4.5, f"Subtotal Bruto: {fmt_currency(total_bruto)}", border=0, align="L")
                pdf.ln(4.5)

                pdf.set_x(x_start)
                pdf.cell(block_width, 4.5, f"Descuentos: {fmt_currency(total_descuento)}", border=0, align="L")
                pdf.ln(4.5)

                pdf.set_x(x_start)
                pdf.cell(block_width, 4.5, f"Neto: {fmt_currency(total_neto)}", border=0, align="L")
                pdf.ln(4.5)

                pdf.set_x(x_start)
                pdf.cell(block_width, 4.5, f"IVA Total: {fmt_currency(total_iva)}", border=0, align="L")
                pdf.ln(5)

                pdf.set_draw_color(*COLOR_SEPARATOR)
                pdf.line(x_start, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
                pdf.ln(3)

                pdf.set_x(x_start)
                pdf.set_fill_color(40, 40, 40)
                pdf.rect(x_start, pdf.get_y(), block_width, 10, "F")
                pdf.set_y(pdf.get_y() + 2)
                pdf.set_x(x_start + 4)
                pdf.set_font("Arial", "B", FS_FINAL)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(block_width - 8, 6.5, f"TOTAL FINAL: {fmt_currency(total_final)}", border=0, align="R")
                pdf.set_text_color(0, 0, 0)
                pdf.ln(12)

            def draw_footer_notes(pdf):
                if pdf.get_y() > 250:
                    pdf.add_page()
                pdf.set_font("Arial", "I", 6.5)
                pdf.set_text_color(80, 80, 80)
                pdf.set_x(MARGIN_LEFT)
                pdf.cell(0, 4, "(*) Los artículos marcados como OFERTA o de la hoja 'BATERIAS Y CARGADORES' no reciben descuentos adicionales.", ln=True)
                pdf.ln(1.5)
                pdf.set_font("Arial", "B", 6.5)
                pdf.set_text_color(0, 0, 0)
                pdf.set_x(MARGIN_LEFT)
                pdf.cell(0, 4, "Leyenda de colores por marca (solo en pantalla):", ln=True)
                pdf.set_font("Arial", "", 6.5)
                for marca, hex_color in MARCAS_COLORS_HEX.items():
                    pdf.set_x(MARGIN_LEFT)
                    pdf.set_text_color(0, 0, 0)
                    pdf.cell(20, 3.5, f"{marca}:", border=0)
                    r = int(hex_color[1:3], 16)
                    g = int(hex_color[3:5], 16)
                    b = int(hex_color[5:7], 16)
                    pdf.set_text_color(r, g, b)
                    pdf.cell(12, 3.5, "●", border=0)
                    pdf.ln(3)
                pdf.set_text_color(0, 0, 0)

            # ---------- CONSTRUCCIÓN DEL PDF ----------
            pdf = FPDF()
            pdf.set_auto_page_break(auto=False)
            pdf.set_margins(left=MARGIN_LEFT, top=MARGIN_TOP, right=MARGIN_RIGHT)
            pdf.add_page()

            # 1. Título
            draw_title(pdf)

            # 2. Datos del cliente (2 columnas)
            draw_client_block(pdf, cli_info, cliente_seleccionado, direccion_entrega, retira_local)

            # 3. Procesar cada marca
            marcas_en_pedido = sorted(df_carrito['Marca'].unique())

            for idx_marca, marca in enumerate(marcas_en_pedido):
                subset = df_carrito[df_carrito['Marca'] == marca]
                es_einhell = (marca == "Einhell")

                draw_brand_header(pdf, marca, len(subset))

                for _, row in subset.iterrows():
                    height_needed = estimate_product_height(pdf, row, es_einhell)
                    # Si no cabe en el espacio restante, salto de página
                    if pdf.get_y() + height_needed > 297 - MARGIN_BOTTOM:
                        pdf.add_page()
                        # Volver a dibujar el encabezado de la marca en la nueva página
                        draw_brand_header(pdf, marca, len(subset))

                    draw_product_block(pdf, row, es_einhell)

                # Subtotal de la marca
                bruto_marca = subset['Subtotal_Bruto'].sum()
                neto_marca = subset['Neto_Calculado'].sum()
                iva_marca = subset['Monto_IVA'].sum()
                desc_marca = bruto_marca - neto_marca
                total_marca = neto_marca + iva_marca
                draw_subtotal_block(pdf, marca, bruto_marca, desc_marca, neto_marca, iva_marca, total_marca)

            # 4. Resumen final
            draw_final_summary(
                pdf,
                total_bruto,
                total_descuento,
                total_neto,
                total_iva,
                total_final,
                texto_descuentos
            )

            # 5. Notas al pie
            draw_footer_notes(pdf)

            # ---------- GUARDAR Y DESCARGAR ----------
            fd, path = tempfile.mkstemp(suffix=".pdf")
            try:
                pdf.output(path)
                with open(path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=f"Pedido_{clean_text(cliente_seleccionado[:20])}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    key="pdf_download_btn"
                )
                st.success("✅ PDF generado exitosamente.")
            finally:
                os.close(fd)
                if os.path.exists(path):
                    os.remove(path)

else:
    st.info("🛒 El carrito está vacío. Buscá un producto y agregalo al pedido.")

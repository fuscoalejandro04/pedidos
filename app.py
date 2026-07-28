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
    Convierte texto a ASCII eliminando tildes, eñes y caracteres especiales.
    Reemplaza símbolos comunes por equivalentes.
    """
    if not isinstance(text, str):
        text = str(text)
    # Normalizar a forma NFKD (descompone caracteres acentuados)
    text = unicodedata.normalize('NFKD', text)
    # Eliminar diacríticos (acentos)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    # Reemplazar ñ y Ñ
    text = text.replace('ñ', 'n').replace('Ñ', 'N')
    # Reemplazar caracteres especiales comunes
    replacements = {
        '€': 'EUR',
        '$': 'USD',
        '°': 'grados',
        '▸': '-',
        '•': '*',
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
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Eliminar cualquier carácter que no sea ASCII imprimible (32-126)
    text = ''.join(c for c in text if 32 <= ord(c) <= 126)
    return text

def fmt_currency(val):
    return f"${val:,.2f}"

def format_iva(iva_val):
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

# Mapeo de colores por marca (para PDF)
MARCAS_COLORS = {
    "Einhell": (139, 0, 0),    # Rojo oscuro
    "KWB": (139, 0, 0),        # Rojo oscuro
    "Fijaciones": (204, 85, 0), # Naranja oscuro
    "Penosil": (178, 34, 34),   # Rojo
}
MARCAS_COLORS_HEX = {
    "Einhell": "#8B0000",
    "KWB": "#8B0000",
    "Fijaciones": "#CC5500",
    "Penosil": "#B22222",
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
# CONSTRUCCIÓN DE FILTROS POR MARCA (con verificaciones robustas)
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
# 2. SELECCIÓN DE CLIENTE
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

# ============================================================
# 3. CATÁLOGO Y AGREGADO AL CARRITO
# ============================================================
st.subheader("2. Catálogo de Productos")

# --- Filtro principal: Marca ---
marcas_disponibles = sorted(df_productos['Marca'].dropna().unique())
marca_filtro = st.selectbox("Filtrar por Línea / Marca:", options=["Todas"] + marcas_disponibles)

if marca_filtro == "Todas":
    filtros_adicionales = {}
else:
    filtros_adicionales = FILTROS_CONFIG.get(marca_filtro, {})

# --- Mostrar filtros adicionales en columnas dinámicas ---
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

# --- Aplicar filtros ---
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
        iva_str = format_iva(row['IVA'])
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
# 4. RESUMEN DEL PEDIDO (CON AGRUPACIÓN POR MARCA)
# ============================================================
st.subheader("3. Resumen del Pedido")

if st.session_state.carrito:
    # --- Funciones de ayuda para el resumen ---
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

    # --- Obtener descuentos ---
    st.markdown("#### Bonificaciones y Cierre")
    col_desc1, col_desc2, col_desc3, _ = st.columns([1, 1, 1, 2])

    desc_gen = col_desc1.number_input("Desc. General (%)", min_value=0.0, max_value=100.0, value=30.0, step=1.0)
    desc_ad1 = col_desc2.number_input("Desc. Adicional 1 (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
    desc_ad2 = col_desc3.number_input("Desc. Adicional 2 (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)

    multiplicador_desc = (1 - (desc_gen / 100)) * (1 - (desc_ad1 / 100)) * (1 - (desc_ad2 / 100))
    descuentos_usados = [f"-{d}%" for d in [desc_gen, desc_ad1, desc_ad2] if d > 0]
    texto_descuentos = " ".join(descuentos_usados) if descuentos_usados else "Sin bonificación"

    # --- Crear DataFrame del carrito ---
    df_carrito = pd.DataFrame(st.session_state.carrito)

    # Calcular neto y descuento por producto
    df_carrito['Neto_Calculado'] = df_carrito.apply(lambda row: calcular_neto(row, multiplicador_desc), axis=1)
    df_carrito['Monto_Descuento'] = df_carrito['Subtotal_Bruto'] - df_carrito['Neto_Calculado']
    df_carrito['Monto_IVA'] = df_carrito['Neto_Calculado'] * df_carrito['IVA']

    # --- Calcular totales generales ---
    total_bruto = df_carrito['Subtotal_Bruto'].sum()
    total_neto = df_carrito['Neto_Calculado'].sum()
    total_iva = df_carrito['Monto_IVA'].sum()
    total_final = total_neto + total_iva
    total_descuento = total_bruto - total_neto

    # --- Resumen General (KPI Cards) ---
    st.markdown("#### 📊 Resumen General")
    col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
    col_kpi1.metric("Subtotal Bruto", fmt_currency(total_bruto))
    col_kpi2.metric(f"Descuentos ({texto_descuentos})", fmt_currency(total_descuento))
    col_kpi3.metric("Neto", fmt_currency(total_neto))
    col_kpi4.metric("IVA Total", fmt_currency(total_iva))
    col_kpi5.metric("Total Final", fmt_currency(total_final), delta=None)

    st.markdown("---")

    # --- Tabla completa de productos ---
    st.markdown("#### 📋 Detalle de Productos")

    # Definir columnas base
    base_cols = ['Codigo', 'Marca', 'Modelo', 'Descripcion', 'Cantidad', 'Precio_Unitario', 'IVA', 'Subtotal_Bruto', 'Monto_Descuento', 'Neto_Calculado', 'Monto_IVA', 'Es_Oferta']

    # Verificar si existen columnas de embalaje en df_carrito
    extra_cols = []
    if 'Embalaje' in df_carrito.columns and df_carrito['Embalaje'].notna().any():
        extra_cols.extend(['Embalaje', 'CantidadPorCaja', 'UnidadPrecio'])

    # Construir lista final sin duplicados
    if extra_cols:
        idx = base_cols.index('Descripcion') + 1
        cols_mostrar = base_cols[:idx] + extra_cols + base_cols[idx:]
    else:
        cols_mostrar = base_cols

    # Filtrar solo las columnas que existen en df_carrito
    cols_mostrar = [col for col in cols_mostrar if col in df_carrito.columns]

    # Crear DataFrame de visualización
    df_mostrar = df_carrito[cols_mostrar].copy()

    # Formatear columnas numéricas
    numeric_cols = ['Precio_Unitario', 'Subtotal_Bruto', 'Monto_Descuento', 'Neto_Calculado', 'Monto_IVA']
    for col in numeric_cols:
        if col in df_mostrar.columns:
            df_mostrar[col] = df_mostrar[col].apply(fmt_currency)
    if 'IVA' in df_mostrar.columns:
        df_mostrar['IVA'] = df_mostrar['IVA'].apply(format_iva)
    if 'Es_Oferta' in df_mostrar.columns:
        df_mostrar['Es_Oferta'] = df_mostrar['Es_Oferta'].apply(lambda x: "🔥 Oferta" if x else "")

    st.dataframe(df_mostrar, use_container_width=True)

    st.markdown("---")

    # --- AGRUPACIÓN POR MARCA (Subtotales) ---
    st.markdown("#### 📦 Resumen por Marca")

    # Calcular subtotales por marca
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
        # Productos en oferta
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

    # Mostrar como tabla con formato
    df_marca = pd.DataFrame(marca_data)
    for col in ['Bruto', 'Descuento', 'Neto', 'IVA', 'Total']:
        df_marca[col] = df_marca[col].apply(fmt_currency)
    st.dataframe(df_marca, use_container_width=True)

    st.markdown("---")

    # --- Totales finales consolidados ---
    col_tot1, col_tot2, col_tot3, col_tot4, col_tot5 = st.columns(5)
    col_tot1.metric("Subtotal Bruto", fmt_currency(total_bruto))
    col_tot2.metric(f"Descuentos ({texto_descuentos})", fmt_currency(total_descuento))
    col_tot3.metric("Neto", fmt_currency(total_neto))
    col_tot4.metric("IVA Total", fmt_currency(total_iva))
    col_tot5.metric("TOTAL FINAL", fmt_currency(total_final), delta=None, delta_color="inverse")

    st.markdown("---")

    # --- Botones de acción ---
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

            # --- INICIO DE GENERACIÓN DE PDF MEJORADO ---
            pdf = FPDF()
            pdf.add_page()

            # ---- ENCABEZADO ----
            pdf.set_font("Arial", 'B', 18)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 12, sanitize_text("PROFORMA DE PEDIDO"), ln=True, align='C')
            pdf.ln(4)

            pdf.set_draw_color(100, 100, 100)
            pdf.line(10, 28, 200, 28)
            pdf.ln(6)

            pdf.set_font("Arial", 'B', 11)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 7, sanitize_text(f"Cliente: {cliente_seleccionado}"), ln=True)
            pdf.set_font("Arial", '', 10)
            pdf.cell(0, 6, sanitize_text(f"CUIT: {cli_info.get('C.U.I.T.', '-')} | Condicion: {cli_info.get('FORMA DE PAGO', '-')}"), ln=True)
            pdf.cell(0, 6, sanitize_text(f"Vendedor: {cli_info.get('NOMB.VENDEDOR', '-')}"), ln=True)
            pdf.cell(0, 6, sanitize_text(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), ln=True)
            pdf.ln(6)

            # ---- TABLA DE PRODUCTOS (AGRUPA POR MARCA) ----
            marcas_en_pedido = sorted(df_carrito['Marca'].unique())

            col_anchos = {
                'Codigo': 14,
                'Marca': 14,
                'Modelo': 18,
                'Descripcion': 28,
                'Emb': 10,
                'Caja': 9,
                'Unidad': 9,
                'Cant': 9,
                'P.Unit': 14,
                'IVA%': 9,
                'Subtotal': 16,
                'Desc.': 12,
                'Neto': 16,
                'IVA': 12,
            }

            def draw_table_header(pdf, extra_cols):
                pdf.set_font("Arial", 'B', 7)
                pdf.set_fill_color(60, 60, 60)
                pdf.set_text_color(255, 255, 255)
                pdf.set_x(10)

                headers = ["Codigo", "Marca", "Modelo", "Descripcion"]
                if extra_cols:
                    headers += ["Emb.", "Caja", "Unidad"]
                headers += ["Cant", "P.Unit", "IVA%", "Subtotal", "Desc.", "Neto", "IVA"]

                widths = [col_anchos['Codigo'], col_anchos['Marca'], col_anchos['Modelo'], col_anchos['Descripcion']]
                if extra_cols:
                    widths += [col_anchos['Emb'], col_anchos['Caja'], col_anchos['Unidad']]
                widths += [col_anchos['Cant'], col_anchos['P.Unit'], col_anchos['IVA%'], col_anchos['Subtotal'], col_anchos['Desc.'], col_anchos['Neto'], col_anchos['IVA']]

                for i, h in enumerate(headers):
                    pdf.cell(widths[i], 8, sanitize_text(h), border=1, align='C', fill=True)
                pdf.ln()
                pdf.set_text_color(0, 0, 0)
                pdf.set_fill_color(255, 255, 255)

            def draw_product_row(pdf, row, extra_cols, color_marca):
                pdf.set_font("Arial", '', 6)
                pdf.set_fill_color(color_marca[0], color_marca[1], color_marca[2])
                pdf.set_text_color(255, 255, 255)

                row_height = 5.5
                pdf.set_x(10)
                if pdf.get_y() > 260:
                    pdf.add_page()
                    draw_table_header(pdf, extra_cols)

                codigo = sanitize_text(str(row['Codigo'])[:8])
                marca = sanitize_text(str(row['Marca'])[:10])
                modelo = sanitize_text(str(row['Modelo'])[:12])
                desc_text = sanitize_text(str(row['Descripcion'])[:22])
                if row['Es_Oferta']:
                    desc_text = "OFERTA " + desc_text

                widths = [col_anchos['Codigo'], col_anchos['Marca'], col_anchos['Modelo'], col_anchos['Descripcion']]
                if extra_cols:
                    widths += [col_anchos['Emb'], col_anchos['Caja'], col_anchos['Unidad']]
                widths += [col_anchos['Cant'], col_anchos['P.Unit'], col_anchos['IVA%'], col_anchos['Subtotal'], col_anchos['Desc.'], col_anchos['Neto'], col_anchos['IVA']]

                # Construir datos
                data = [codigo, marca, modelo, desc_text]
                if extra_cols:
                    data += [
                        sanitize_text(str(row.get('Embalaje', ''))[:5]),
                        sanitize_text(str(row.get('CantidadPorCaja', ''))[:5]),
                        sanitize_text(str(row.get('UnidadPrecio', ''))[:5])
                    ]
                data += [
                    str(int(row['Cantidad'])) if row['Cantidad'].is_integer() else f"{row['Cantidad']:.1f}",
                    fmt_currency(row['Precio_Unitario']),
                    format_iva(row['IVA']),
                    fmt_currency(row['Subtotal_Bruto']),
                    fmt_currency(row['Monto_Descuento']),
                    fmt_currency(row['Neto_Calculado']),
                    fmt_currency(row['Monto_IVA'])
                ]

                for i, d in enumerate(data):
                    align = 'R' if i >= len(data) - 4 else ('C' if i >= 8 else 'L')
                    pdf.cell(widths[i], row_height, d, border=1, align=align, fill=True)

                pdf.ln()
                pdf.set_text_color(0, 0, 0)
                pdf.set_fill_color(255, 255, 255)

            has_extra = 'Embalaje' in df_carrito.columns and df_carrito['Embalaje'].notna().any()

            for marca in marcas_en_pedido:
                subset = df_carrito[df_carrito['Marca'] == marca]
                color_marca = MARCAS_COLORS.get(marca, (100, 100, 100))

                pdf.set_font("Arial", 'B', 10)
                pdf.set_text_color(color_marca[0], color_marca[1], color_marca[2])
                pdf.cell(0, 8, sanitize_text(f"- {marca} ({len(subset)} productos)"), ln=True)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(2)

                draw_table_header(pdf, has_extra)

                for _, row in subset.iterrows():
                    draw_product_row(pdf, row, has_extra, color_marca)

                bruto_marca = subset['Subtotal_Bruto'].sum()
                neto_marca = subset['Neto_Calculado'].sum()
                iva_marca = subset['Monto_IVA'].sum()
                desc_marca = bruto_marca - neto_marca
                total_marca = neto_marca + iva_marca

                pdf.set_font("Arial", 'B', 8)
                pdf.set_text_color(50, 50, 50)
                pdf.set_draw_color(200, 200, 200)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(1)
                pdf.set_x(10)
                subtotal_text = sanitize_text(f"Subtotal {marca}: Bruto {fmt_currency(bruto_marca)} | Desc. {fmt_currency(desc_marca)} | Neto {fmt_currency(neto_marca)} | IVA {fmt_currency(iva_marca)} | Total {fmt_currency(total_marca)}")
                pdf.cell(0, 6, subtotal_text, ln=True)
                pdf.ln(4)
                pdf.set_text_color(0, 0, 0)

            # ---- RESÚMENES FINALES ----
            pdf.ln(4)
            pdf.set_font("Arial", 'B', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 7, sanitize_text(f"Descuentos aplicados: {texto_descuentos}"), ln=True)
            pdf.ln(2)

            pdf.set_font("Arial", 'B', 10)
            pdf.set_fill_color(240, 240, 240)
            pdf.set_x(10)

            pdf.cell(100, 8, "Subtotal Bruto (Sin Descuentos):", border=0, align='R')
            pdf.cell(80, 8, fmt_currency(total_bruto), border=0, align='R')
            pdf.ln()

            pdf.cell(100, 8, sanitize_text(f"Descuentos ({texto_descuentos}):"), border=0, align='R')
            pdf.cell(80, 8, fmt_currency(total_descuento), border=0, align='R')
            pdf.ln()

            pdf.set_font("Arial", 'B', 10)
            pdf.cell(100, 8, "Neto:", border=0, align='R')
            pdf.cell(80, 8, fmt_currency(total_neto), border=0, align='R')
            pdf.ln()

            pdf.set_font("Arial", '', 10)
            pdf.cell(100, 8, "IVA Total:", border=0, align='R')
            pdf.cell(80, 8, fmt_currency(total_iva), border=0, align='R')
            pdf.ln()

            pdf.set_draw_color(100, 100, 100)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)

            pdf.set_font("Arial", 'B', 14)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(100, 10, "TOTAL FINAL:", border=0, align='R')
            pdf.cell(80, 10, fmt_currency(total_final), border=0, align='R')
            pdf.ln(8)

            # ---- NOTAS Y LEYENDA ----
            pdf.set_font("Arial", 'I', 8)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 5, sanitize_text("(*) Los articulos marcados como OFERTA o de la hoja 'BATERÍAS Y CARGADORES' no reciben descuentos adicionales."), ln=True)

            pdf.ln(2)
            pdf.set_font("Arial", 'B', 8)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, "Leyenda de colores por marca:", ln=True)
            pdf.set_font("Arial", '', 8)
            for marca, hex_color in MARCAS_COLORS_HEX.items():
                pdf.set_text_color(0, 0, 0)
                pdf.cell(20, 5, sanitize_text(f"{marca}:"), border=0)
                pdf.set_text_color(int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16))
                pdf.cell(20, 5, "██████", border=0)
                pdf.ln(4)
            pdf.set_text_color(0, 0, 0)

            # ---- GUARDAR Y DESCARGAR ----
            fd, path = tempfile.mkstemp(suffix=".pdf")
            try:
                pdf.output(path)
                with open(path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=f"Pedido_{sanitize_text(cliente_seleccionado[:20])}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )
                st.success("✅ PDF generado exitosamente.")
            finally:
                os.close(fd)

else:
    st.info("🛒 El carrito está vacío. Buscá un producto y agregalo al pedido.")

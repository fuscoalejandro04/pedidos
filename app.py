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
        '€': 'EUR', '°': 'grados', '▸': '-', '•': '*', '→': '->', '←': '<-',
        '…': '...', '—': '-', '–': '-', '"': "'", '´': "'", '`': "'", '·': '.',
        'ª': 'a', 'º': 'o', '█': '#', '▓': '#', '▒': '#', '░': '#'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = ''.join(c for c in text if 32 <= ord(c) <= 126)
    return text

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

# Paleta de colores
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
                extra_info.append(f)

import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile
import os
import glob
import re
import unicodedata
from datetime import datetime
import math

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

def clean_nan(val):
    """Limpia valores nulos de pandas para que no se impriman como 'nan' en el PDF."""
    if pd.isna(val) or str(val).strip().lower() in ['nan', 'none', 'null', '']:
        return ""
    return str(val).strip()

def sanitize_text(text):
    """Convierte texto a ASCII, eliminando tildes y caracteres especiales."""
    text = clean_nan(text)
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

# Paleta de colores Ajustada (Solo Encabezados)
MARCAS_COLORS = {
    "Einhell": (200, 65, 65),    # Rojo oscuro/pastel suave
    "KWB": (200, 65, 65),        # Rojo oscuro/pastel suave
    "Fijaciones": (204, 85, 0),  # Naranja
    "Penosil": (255, 0, 0),      # Rojo puro
}
MARCAS_COLORS_HEX = {
    "Einhell": "#C84141",
    "KWB": "#C84141",
    "Fijaciones": "#CC5500",
    "Penosil": "#FF0000",
}

# ------------------------------------------------------------
# FUNCIÓN PARA OBTENER INFORMACIÓN DE PRECIO Y PRESENTACIÓN
# ------------------------------------------------------------
def get_product_info(row):
    precio_lista = row['Precio_Lista']
    unidad = clean_nan(row.get('UnidadPrecio', ''))
    caja = clean_nan(row.get('CantidadPorCaja', ''))
    embalaje = clean_nan(row.get('Embalaje', ''))

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
        if unidad:
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
            return info
    except:
        return info


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

def standardize_product_columns(df, filename):
    # 1. PRIMERO hacemos los renombramientos según el archivo
    if "KWB" in filename:
        if 'Nombre' in df.columns: 
            df = df.rename(columns={'Nombre': 'Modelo'})
        df['Marca'] = 'KWB'
        
    elif "Einhell" in filename:
        df['Hoja_Origen'] = 'Einhell'
        df['Marca'] = 'Einhell'
        
    elif "Fijaciones" in filename:
        if 'PrecioLista' in df.columns: 
            df = df.rename(columns={'PrecioLista': 'Precio_Lista'})
        if 'Descripcion' in df.columns: 
            df['Modelo'] = df['Descripcion']
        df['Marca'] = 'Fijaciones'
        df['Hoja_Origen'] = 'Fijaciones'
        
    elif "Penosil" in filename:
        df = df.rename(columns={'Artículo': 'Codigo', 'Nombre': 'Modelo', 'PrecioLista': 'Precio_Lista'})
        df['Marca'] = 'Penosil'
        df['Hoja_Origen'] = 'Penosil'
        
    else:
        if 'PrecioLista' in df.columns: 
            df = df.rename(columns={'PrecioLista': 'Precio_Lista'})
        if 'Artículo' in df.columns: 
            df = df.rename(columns={'Artículo': 'Codigo'})
        if 'Nombre' in df.columns and 'Modelo' not in df.columns: 
            df['Modelo'] = df['Nombre']

    # 2. DESPUÉS verificamos y agregamos las columnas faltantes (evita duplicados)
    required = ['Codigo', 'Descripcion', 'Modelo', 'Marca', 'Precio_Lista', 'IVA', 
                'Hoja_Origen', 'Herramienta', 'Color', 'CantidadPorCaja', 'Embalaje', 'UnidadPrecio']
    
    for col in required:
        if col not in df.columns:
            df[col] = None

    df['IVA'] = pd.to_numeric(df.get('IVA', 0.21), errors='coerce').fillna(0.21)
    
    return df

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

    product_files = ["KWB_Limpia.xlsx", "Einhell_Limpia.xlsx", "Fijaciones_Limpia.xlsx", "Penosil_Limpia.xlsx"]
    dfs = []
    
    for file in product_files:
        try:
            df = pd.read_excel(file)
            df = standardize_product_columns(df, file)
            dfs.append(df)
        except FileNotFoundError:
            pass
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

    df_prod['Categoria_Generica'] = None
    df_prod['Tipo_Alimentacion'] = None
    mask_einhell = df_prod['Marca'] == 'Einhell'
    if mask_einhell.any() and 'Herramienta' in df_prod.columns:
        df_prod.loc[mask_einhell, 'Categoria_Generica'] = df_prod.loc[mask_einhell, 'Herramienta'].apply(lambda x: extract_einhell_categories(x)[0])
        df_prod.loc[mask_einhell, 'Tipo_Alimentacion'] = df_prod.loc[mask_einhell, 'Herramienta'].apply(lambda x: extract_einhell_categories(x)[1])

    archivos_oferta = glob.glob("*oferta*.xls*") + glob.glob("*OFERTA*.xls*")
    for archivo in archivos_oferta:
        try:
            df_of = pd.read_excel(archivo)
            df_of.columns = [str(c).strip().upper() for c in df_of.columns]
            col_codigo = "CÓDIGO" if "CÓDIGO" in df_of.columns else "CODIGO" if "CODIGO" in df_of.columns else None
            col_precio = [c for c in df_of.columns if "PRECIO" in c]
            if col_codigo and col_precio:
                df_of_limpio = df_of[[col_codigo, col_precio[0]]].copy()
                df_of_limpio.columns = ['Codigo', 'Precio_Promocional']
                df_of_limpio['Codigo'] = df_of_limpio['Codigo'].astype(str).str.strip()
                df_of_limpio['Precio_Promocional'] = pd.to_numeric(df_of_limpio['Precio_Promocional'], errors='coerce').fillna(0)
                df_prod = pd.merge(df_prod, df_of_limpio, on='Codigo', how='left')
                condicion_oferta = df_prod['Precio_Promocional'] > 0
                df_prod.loc[condicion_oferta, 'Precio_Oferta'] = df_prod.loc[condicion_oferta, 'Precio_Promocional']
                df_prod.loc[condicion_oferta, 'Es_Oferta'] = True
                df_prod = df_prod.drop(columns=['Precio_Promocional'])
        except Exception:
            pass

    return df_cli, df_prod

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
    if 'Marca' not in df.columns: return config
    
    if 'Categoria_Generica' in df.columns:
        sub_einhell = df[df['Marca'] == "Einhell"]
        if not sub_einhell.empty:
            config["Einhell"] = {
                "Categoria_Generica": {"label": "Categoría", "options": sorted(sub_einhell['Categoria_Generica'].dropna().unique())},
                "Tipo_Alimentacion": {"label": "Alimentación", "options": sorted(sub_einhell['Tipo_Alimentacion'].dropna().unique())}
            }
    if 'Embalaje' in df.columns:
        sub_fija = df[df['Marca'] == "Fijaciones"]
        if not sub_fija.empty:
            config["Fijaciones"] = {"Embalaje": {"label": "Embalaje", "options": sorted(sub_fija['Embalaje'].dropna().unique())}}
    if 'Hoja_Origen' in df.columns:
        sub_kwb = df[df['Marca'] == "KWB"]
        if not sub_kwb.empty:
            config["KWB"] = {"Hoja_Origen": {"label": "Hoja de origen", "options": sorted(sub_kwb['Hoja_Origen'].dropna().unique())}}
    if 'Color' in df.columns:
        sub_penosil = df[df['Marca'] == "Penosil"]
        if not sub_penosil.empty:
            config["Penosil"] = {"Color": {"label": "Color", "options": sorted(sub_penosil['Color'].dropna().unique())}}
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
col_ent1, col_ent2 = st.columns([3, 1])
direccion_entrega = col_ent1.text_input("📍 Dirección de entrega alternativa (opcional):", placeholder="Calle, número, localidad, etc. (Dejar vacío si es la principal)")
retira_local = col_ent2.checkbox("🏠 El cliente retira el pedido")

st.markdown("---")

# ============================================================
# 3. CATÁLOGO Y AGREGADO AL CARRITO
# ============================================================
st.subheader("2. Catálogo de Productos")

marcas_disponibles = sorted(df_productos['Marca'].dropna().unique())
marca_filtro = st.selectbox("Filtrar por Línea / Marca:", options=["Todas"] + marcas_disponibles)

filtros_adicionales = FILTROS_CONFIG.get(marca_filtro, {}) if marca_filtro != "Todas" else {}

num_extra = len(filtros_adicionales)
cols = st.columns([1] * num_extra + [2]) if num_extra > 0 else st.columns([1])

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

if marca_filtro != "Todas": df_filtrado = df_filtrado[df_filtrado['Marca'] == marca_filtro]
for campo, valor in filtro_valores.items():
    if valor != "Todas": df_filtrado = df_filtrado[df_filtrado[campo] == valor]

if busqueda:
    palabras = [normalize_text(p) for p in busqueda.split()]
    for col in ['Codigo', 'Modelo', 'Descripcion', 'Marca', 'Herramienta']:
        if col in df_filtrado.columns:
            df_filtrado[col+'_norm'] = df_filtrado[col].astype(str).apply(normalize_text)

    def matches_all(row):
        text = f"{row['Codigo_norm']} {row['Modelo_norm']} {row['Descripcion_norm']} {row['Marca_norm']}"
        if 'Herramienta_norm' in row: text += f" {row['Herramienta_norm']}"
        return all(p in text for p in palabras)

    df_filtrado = df_filtrado.loc[df_filtrado.apply(matches_all, axis=1)].copy()

st.markdown("##### Agregar al Pedido")

if not df_filtrado.empty:
    def format_display(row):
        precio = row['Precio_Oferta'] if row['Es_Oferta'] else row['Precio_Lista']
        etiqueta = "🔥 OFERTA " if row['Es_Oferta'] else ""
        herr = clean_nan(row.get('Herramienta', ''))[:20]
        iva_str = format_iva(row['IVA'], row['Es_Oferta'])
        desc = clean_nan(row['Descripcion'])[:25]
        parts = [f"{row['Codigo']}", f"{row['Marca']}"]
        if herr: parts.append(f"[{herr}]")
        parts.extend([desc, fmt_currency(precio), iva_str])
        return f"{etiqueta} | ".join(parts)

    df_filtrado['Display'] = df_filtrado.apply(format_display, axis=1)
    df_filtrado['Codigo_Base'] = df_filtrado['Codigo'].astype(str).apply(lambda x: re.sub(r'[^0-9]', '', x))
    df_filtrado['Clave_Producto'] = df_filtrado['Codigo_Base'] + '_' + df_filtrado['Marca']

    productos_unicos = df_filtrado.drop_duplicates(subset=['Clave_Producto']).copy()
    display_options = productos_unicos['Display'].tolist()

    col_sel, col_qty, col_btn = st.columns([3, 1, 1])
    prod_seleccionado_display = col_sel.selectbox("Seleccione el producto:", options=display_options)

    if prod_seleccionado_display:
        prod_row = productos_unicos[productos_unicos['Display'] == prod_seleccionado_display].iloc[0]
        presentaciones = df_filtrado[df_filtrado['Clave_Producto'] == prod_row['Clave_Producto']].copy()
        
        if len(presentaciones) > 1:
            presentaciones['Presentacion_Label'] = presentaciones.apply(lambda r: get_product_info(r)['presentacion_text'], axis=1)
            presentacion_sel = st.selectbox("Elegir presentación:", options=presentaciones['Presentacion_Label'].tolist())
            prod_data = presentaciones[presentaciones['Presentacion_Label'] == presentacion_sel].iloc[0]
        else:
            prod_data = presentaciones.iloc[0]

        info = get_product_info(prod_data)

        with st.expander("📋 Detalles del producto", expanded=True):
            st.markdown(f"**Código:** `{prod_data['Codigo']}` | **Marca:** {prod_data['Marca']} | **Descripción:** {prod_data['Descripcion']}")
            if prod_data['Es_Oferta']: st.markdown(f"**🔥 OFERTA:** {fmt_currency(prod_data['Precio_Oferta'])}")

        step = info['step']
        cantidad = col_qty.number_input("Cantidad", min_value=info['min_value'], value=step if step>0 else 1.0, step=step)

        if col_btn.button("➕ Agregar al Carrito", use_container_width=True):
            if cantidad > 0 and (step <= 1 or cantidad % step == 0):
                precio_usar = prod_data['Precio_Oferta'] if prod_data['Es_Oferta'] else info['precio_unitario']
                clave_present = f"{prod_data['Codigo']}_{prod_data.get('Embalaje','')}"
                
                item_existente = next((i for i, item in enumerate(st.session_state.carrito) if item['Clave_Presentacion'] == clave_present), None)
                if item_existente is not None:
                    st.session_state.carrito[item_existente]['Cantidad'] += cantidad
                    st.session_state.carrito[item_existente]['Subtotal_Bruto'] = st.session_state.carrito[item_existente]['Precio_Unitario'] * st.session_state.carrito[item_existente]['Cantidad']
                    st.success("¡Cantidad actualizada!")
                else:
                    st.session_state.carrito.append({
                        "Codigo": str(prod_data['Codigo']),
                        "Descripcion": clean_nan(prod_data.get('Descripcion')),
                        "Modelo": clean_nan(prod_data.get('Modelo')),
                        "Marca": str(prod_data['Marca']),
                        "Hoja_Origen": clean_nan(prod_data.get('Hoja_Origen')),
                        "Herramienta": clean_nan(prod_data.get('Herramienta')),
                        "Categoria_Generica": clean_nan(prod_data.get('Categoria_Generica')),
                        "Tipo_Alimentacion": clean_nan(prod_data.get('Tipo_Alimentacion')),
                        "Cantidad": cantidad,
                        "Precio_Unitario": precio_usar,
                        "Es_Oferta": prod_data['Es_Oferta'],
                        "IVA": prod_data['IVA'],
                        "Subtotal_Bruto": precio_usar * cantidad,
                        "Embalaje": clean_nan(prod_data.get('Embalaje')),
                        "CantidadPorCaja": clean_nan(prod_data.get('CantidadPorCaja')),
                        "UnidadPrecio": clean_nan(prod_data.get('UnidadPrecio')),
                        "Clave_Presentacion": clave_present
                    })
                    st.success("¡Producto agregado!")
            else:
                st.error("Revisar múltiplos de cantidad.")
else:
    st.info("No se encontraron productos.")

st.markdown("---")

# ============================================================
# 4. RESUMEN DEL PEDIDO & GENERACIÓN PDF (Estilo ERP)
# ============================================================
st.subheader("3. Resumen del Pedido")

if st.session_state.carrito:
    col_desc1, col_desc2, col_desc3, _ = st.columns([1, 1, 1, 2])
    desc_gen = col_desc1.number_input("Desc. General (%)", min_value=0.0, max_value=100.0, value=30.0, step=1.0)
    desc_ad1 = col_desc2.number_input("Desc. Adicional 1 (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
    desc_ad2 = col_desc3.number_input("Desc. Adicional 2 (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)

    multiplicador_desc = (1 - (desc_gen / 100)) * (1 - (desc_ad1 / 100)) * (1 - (desc_ad2 / 100))
    descuentos_usados = [f"-{d}%" for d in [desc_gen, desc_ad1, desc_ad2] if d > 0]
    texto_descuentos = " ".join(descuentos_usados) if descuentos_usados else "Sin bonificación"

    df_carrito = pd.DataFrame(st.session_state.carrito)
    
    def calcular_neto(row, mult):
        # Ofertas o Baterías no llevan descuento
        if row['Es_Oferta'] or ("BATERÍAS Y CARGADORES" in str(row['Hoja_Origen']).upper()):
            return row['Subtotal_Bruto']
        return row['Subtotal_Bruto'] * mult

    df_carrito['Neto_Calculado'] = df_carrito.apply(lambda row: calcular_neto(row, multiplicador_desc), axis=1)
    df_carrito['Monto_Descuento'] = df_carrito['Subtotal_Bruto'] - df_carrito['Neto_Calculado']
    df_carrito['Monto_IVA'] = df_carrito['Neto_Calculado'] * df_carrito['IVA']

    total_bruto = df_carrito['Subtotal_Bruto'].sum()
    total_neto = df_carrito['Neto_Calculado'].sum()
    total_iva = df_carrito['Monto_IVA'].sum()
    total_final = total_neto + total_iva
    total_descuento = total_bruto - total_neto

    # Resumen UI
    col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
    col_kpi1.metric("Subtotal Bruto", fmt_currency(total_bruto))
    col_kpi2.metric("Descuentos", fmt_currency(total_descuento))
    col_kpi3.metric("Neto", fmt_currency(total_neto))
    col_kpi4.metric("IVA Total", fmt_currency(total_iva))
    col_kpi5.metric("Total Final", fmt_currency(total_final))

    st.markdown("---")
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("🗑️ Vaciar Carrito", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

    with col_btn2:
        if st.button("📄 Generar PDF del Pedido (Formato ERP)", type="primary", use_container_width=True):
            if cliente_seleccionado is None:
                st.error("Debes seleccionar un cliente.")
                st.stop()

            # ----------------------------------------------------------------------
            # GENERADOR DE PDF PROFESIONAL (Minimalista / Estilo Stripe/Odoo/SAP)
            # ----------------------------------------------------------------------
            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            # Constantes de diseño
            MARGIN_LEFT = 12
            PAGE_WIDTH = 186
            FONT_SIZE_DATA = 8
            FONT_SIZE_DESC = 7
            
            # Función local de truncado seguro
            def truncate_description(texto, max_width=PAGE_WIDTH - 10):
                if not texto: return ""
                palabras = texto.split()
                linea_actual = ""
                for palabra in palabras:
                    if pdf.get_string_width(linea_actual + " " + palabra) <= max_width:
                        linea_actual += " " + palabra if linea_actual else palabra
                    else:
                        return linea_actual + "..."
                return linea_actual

            # ---- HEADER DEL DOCUMENTO (Estilo Factura) ----
            pdf.set_font("Arial", 'B', 18)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(100, 8, sanitize_text("PROFORMA DE PEDIDO"), ln=0, align='L')
            
            pdf.set_font("Arial", '', 10)
            pdf.cell(86, 8, sanitize_text(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), ln=1, align='R')
            
            pdf.set_draw_color(200, 200, 200)
            pdf.line(MARGIN_LEFT, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
            pdf.ln(5)

            # Datos Cliente (Bill To / Ship To)
            pdf.set_font("Arial", 'B', 11)
            cod_cli = clean_nan(cli_info.get('CODIGO', cli_info.get('Código', cli_info.get('Codigo', ''))))
            cli_title = f"Cliente: {cliente_seleccionado}" + (f" (Cod: {cod_cli})" if cod_cli else "")
            pdf.cell(0, 6, sanitize_text(cli_title), ln=True)

            pdf.set_font("Arial", '', 9)
            pdf.cell(0, 5, sanitize_text(f"CUIT: {cli_info.get('C.U.I.T.', '-')} | Condicion: {cli_info.get('FORMA DE PAGO', '-')}"), ln=True)
            
            dir_cli = clean_nan(cli_info.get('Dirección', cli_info.get('DOMICILIO', '')))
            if dir_cli: pdf.cell(0, 5, sanitize_text(f"Direccion Fra.: {dir_cli}"), ln=True)
            
            pdf.cell(0, 5, sanitize_text(f"Vendedor: {cli_info.get('NOMB.VENDEDOR', '-')}"), ln=True)
            pdf.ln(2)
            
            # Info de entrega destacada
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(0, 5, "Informacion de Logistica / Entrega:", ln=True)
            pdf.set_font("Arial", '', 9)
            if retira_local:
                pdf.cell(0, 5, sanitize_text("-> EL CLIENTE RETIRA EN EL LOCAL"), ln=True)
            elif direccion_entrega:
                pdf.cell(0, 5, sanitize_text(f"-> ENTREGAR EN: {direccion_entrega}"), ln=True)
            else:
                pdf.cell(0, 5, sanitize_text("-> Entrega en domicilio de facturacion registrado."), ln=True)
            
            pdf.ln(8)

            # ---- RECORRER MARCAS Y GENERAR TABLA ----
            marcas_en_pedido = sorted(df_carrito['Marca'].unique())

            for idx_marca, marca in enumerate(marcas_en_pedido):
                subset = df_carrito[df_carrito['Marca'] == marca]
                color_rgb = MARCAS_COLORS.get(marca, (100, 100, 100))

                if pdf.get_y() > 230 and idx_marca > 0:
                    pdf.add_page()
                    
                # Nombre de la marca (Header Color)
                pdf.set_font("Arial", 'B', 10)
                pdf.set_fill_color(color_rgb[0], color_rgb[1], color_rgb[2])
                pdf.set_text_color(255, 255, 255)
                pdf.cell(PAGE_WIDTH, 7, sanitize_text(f"   {marca} ({len(subset)} productos)"), ln=True, fill=True)
                
                # Encabezados de Columnas
                pdf.set_font("Arial", 'B', FONT_SIZE_DATA)
                pdf.set_text_color(0, 0, 0)
                pdf.set_fill_color(245, 245, 245)
                
                # Anchos exactos (Suma = 186)
                w = [16, 14, 38, 10, 18, 11, 20, 18, 19, 22]
                headers = ["Codigo", "Marca", "Modelo/Herr.", "Cant", "P.Unit", "IVA%", "Subtotal", "Desc.", "Neto", "IVA Mto"]
                
                for i, h in enumerate(headers):
                    align = 'L' if i < 3 else ('C' if i in [3,5] else 'R')
                    pdf.cell(w[i], 6, sanitize_text(h), border=0, align=align, fill=True)
                pdf.ln()

                # Filas de Productos
                for _, row in subset.iterrows():
                    codigo = sanitize_text(str(row['Codigo']))[:12]
                    marca_txt = sanitize_text(str(row['Marca']))[:10]
                    cant = str(int(row['Cantidad'])) if row['Cantidad'].is_integer() else f"{row['Cantidad']:.1f}"
                    p_unit = fmt_currency(row['Precio_Unitario'])
                    iva_txt = format_iva(row['IVA'], row['Es_Oferta'])
                    subt = fmt_currency(row['Subtotal_Bruto'])
                    desc_val = fmt_currency(row['Monto_Descuento'])
                    neto = fmt_currency(row['Neto_Calculado'])
                    iva_val = fmt_currency(row['Monto_IVA'])
                    
                    is_oferta = row['Es_Oferta']

                    # --- LÍNEA 1: Datos Financieros ---
                    rh = 6 # Row height
                    pdf.set_font("Arial", 'B', FONT_SIZE_DATA)
                    pdf.cell(w[0], rh, codigo, align='L')
                    
                    pdf.set_font("Arial", '', FONT_SIZE_DATA)
                    pdf.cell(w[1], rh, marca_txt, align='L')
                    
                    pdf.set_font("Arial", 'B', FONT_SIZE_DATA)
                    modelo_herramienta = clean_nan(row.get('Herramienta') if marca == 'Einhell' else row.get('Modelo'))
                    pdf.cell(w[2], rh, sanitize_text(modelo_herramienta)[:25], align='L')
                    
                    pdf.set_font("Arial", '', FONT_SIZE_DATA)
                    pdf.cell(w[3], rh, cant, align='C')
                    pdf.cell(w[4], rh, p_unit, align='R')
                    pdf.cell(w[5], rh, iva_txt, align='C')
                    pdf.cell(w[6], rh, subt, align='R')
                    
                    if is_oferta:
                        pdf.set_font("Arial", 'B', FONT_SIZE_DATA)
                        pdf.set_text_color(200, 50, 50)
                        pdf.cell(w[7], rh, "OFERTA", align='R')
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_font("Arial", '', FONT_SIZE_DATA)
                    else:
                        pdf.cell(w[7], rh, desc_val, align='R')
                        
                    pdf.cell(w[8], rh, neto, align='R')
                    pdf.cell(w[9], rh, iva_val, align='R')
                    pdf.ln()

                    # --- LÍNEA 2: Descripción limpia (Cursiva Gris) ---
                    desc_text = clean_nan(row.get('Descripcion'))
                    if is_oferta: desc_text = "OFERTA - " + desc_text
                    
                    # Agregar detalles según marca pero sin las columnas duras en Einhell
                    if marca == "Einhell":
                        alim = clean_nan(row.get('Tipo_Alimentacion'))
                        if alim and alim != "No especificado": desc_text += f" ({alim})"
                    else:
                        extra_info = filter(None, [clean_nan(row.get('Embalaje')), clean_nan(row.get('CantidadPorCaja')), clean_nan(row.get('UnidadPrecio'))])
                        extra_str = " ".join(extra_info)
                        if extra_str: desc_text += f" | Empaque: {extra_str}"

                    desc_text = truncate_description(desc_text)
                    
                    if desc_text:
                        pdf.set_x(MARGIN_LEFT + w[0] + w[1]) # Indentado bajo el modelo
                        pdf.set_font("Arial", 'I', FONT_SIZE_DESC)
                        pdf.set_text_color(100, 100, 100) # Gris ERP
                        pdf.cell(PAGE_WIDTH - w[0] - w[1], 4, sanitize_text(desc_text), align='L')
                        pdf.set_text_color(0, 0, 0)
                        pdf.ln()

                    # Separador sutil
                    pdf.set_y(pdf.get_y() + 1)
                    pdf.set_draw_color(230, 230, 230)
                    pdf.line(MARGIN_LEFT, pdf.get_y(), MARGIN_LEFT + PAGE_WIDTH, pdf.get_y())
                    pdf.set_y(pdf.get_y() + 1)

                pdf.ln(6)

            # ---- BLOQUE DE TOTALES ALINEADO A LA DERECHA ----
            # Estilo Factura Odoo/Stripe
            pdf.ln(4)
            block_width = 85
            start_x = MARGIN_LEFT + PAGE_WIDTH - block_width
            
            pdf.set_font("Arial", '', 10)
            pdf.set_x(start_x)
            pdf.cell(40, 6, "Subtotal Bruto:", border=0, align='L')
            pdf.cell(45, 6, fmt_currency(total_bruto), border=0, align='R')
            pdf.ln()
            
            pdf.set_x(start_x)
            pdf.cell(40, 6, sanitize_text(f"Desc. ({texto_descuentos}):"), border=0, align='L')
            pdf.cell(45, 6, f"- {fmt_currency(total_descuento)}", border=0, align='R')
            pdf.ln()
            
            pdf.set_x(start_x)
            pdf.cell(40, 6, "Neto:", border=0, align='L')
            pdf.cell(45, 6, fmt_currency(total_neto), border=0, align='R')
            pdf.ln()
            
            pdf.set_x(start_x)
            pdf.cell(40, 6, "IVA Total:", border=0, align='L')
            pdf.cell(45, 6, fmt_currency(total_iva), border=0, align='R')
            pdf.ln(8)
            
            # TOTAL FINAL (Caja oscura)
            pdf.set_x(start_x)
            pdf.set_fill_color(35, 35, 35) # Gris casi negro
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(40, 10, " TOTAL FINAL", border=0, align='L', fill=True)
            pdf.cell(45, 10, f"{fmt_currency(total_final)} ", border=0, align='R', fill=True)
            
            pdf.set_text_color(0, 0, 0) # Reset color
            pdf.ln(15)

            # ---- NOTAS AL PIE ----
            pdf.set_x(MARGIN_LEFT)
            pdf.set_font("Arial", 'I', 8)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, sanitize_text("(*) Los articulos marcados como OFERTA o de la hoja 'BATERIAS Y CARGADORES' no reciben descuentos adicionales."), ln=True)

            # ---- GUARDAR Y DESCARGAR ----
            fd, path = tempfile.mkstemp(suffix=".pdf")
            try:
                pdf.output(path)
                with open(path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="⬇️ Descargar PDF (Formato Enterprise)",
                    data=pdf_bytes,
                    file_name=f"Pedido_Pro_{sanitize_text(cliente_seleccionado[:20])}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )
                st.success("✅ Documento PDF estructurado generado exitosamente.")
            finally:
                os.close(fd)

else:
    st.info("🛒 El carrito está vacío. Buscá un producto y agregalo al pedido.")

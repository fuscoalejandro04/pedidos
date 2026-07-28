import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile
import os
import glob
import re
import unicodedata

st.set_page_config(page_title="Gestión de Pedidos", layout="wide", initial_sidebar_state="expanded")

st.title("📦 Sistema de Carga de Pedidos")
st.markdown("---")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# ------------------------------------------------------------
# FUNCIÓN PARA NORMALIZAR TEXTO
# ------------------------------------------------------------
def normalize_text(text):
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text.lower()

# ------------------------------------------------------------
# FUNCIÓN CORREGIDA PARA OBTENER INFORMACIÓN DE PRECIO Y CANTIDAD
# ------------------------------------------------------------
def get_product_price_info(row):
    """
    Devuelve:
    - precio_unitario: precio por unidad (si UnidadPrecio es numérico) o precio por lote (si no)
    - step: paso sugerido para la cantidad
    - min_value: valor mínimo sugerido (para unidades sueltas con caja, es la cantidad de la caja)
    - ayuda: texto informativo
    - precio_lote: el precio de lista (precio por lote completo)
    - tipo_cantidad: 'unidades' o 'lotes'
    - cantidad_por_lote: número de unidades por lote (si aplica)
    """
    precio_lista = row['Precio_Lista']
    unidad = str(row.get('UnidadPrecio', '')).strip() if pd.notna(row.get('UnidadPrecio')) else ''
    caja = str(row.get('CantidadPorCaja', '')).strip() if pd.notna(row.get('CantidadPorCaja')) else ''
    embalaje = str(row.get('Embalaje', '')).strip() if pd.notna(row.get('Embalaje')) else ''

    # Intentar convertir unidad a numérico (ej. "100" -> 100.0)
    try:
        unidad_num = float(unidad)
        if unidad_num > 0:
            # Precio de lista es por "unidad_num" unidades → precio unitario
            precio_unitario = precio_lista / unidad_num
            tipo_cantidad = 'unidades'
            cantidad_por_lote = unidad_num
            # Verificar si existe CantidadPorCaja para restringir a múltiplos
            try:
                caja_num = float(caja) if caja else 0
                if caja_num > 0 and caja_num <= unidad_num:
                    # Se vende en cajas de caja_num unidades (múltiplos de caja_num)
                    step = caja_num
                    min_value = caja_num
                    ayuda = f"Venta en cajas de {caja_num} unidades (múltiplos) | Precio unitario: ${precio_unitario:.2f} | Caja: ${precio_lista * (caja_num / unidad_num):,.2f}"
                else:
                    # Sin restricción de caja, cualquier cantidad
                    step = 1.0
                    min_value = 0.0
                    ayuda = f"Precio unitario: ${precio_unitario:.2f} | Presentación de {unidad_num} unidades (${precio_lista:,.2f})"
            except:
                step = 1.0
                min_value = 0.0
                ayuda = f"Precio unitario: ${precio_unitario:.2f} | Presentación de {unidad_num} unidades (${precio_lista:,.2f})"
            return precio_unitario, step, min_value, ayuda, precio_lista, tipo_cantidad, cantidad_por_lote
    except:
        pass

    # UnidadPrecio NO es numérico (ej. "GRANEL", "BOLSA", "JARRA", etc.)
    # El precio de lista es por el lote completo (CantidadPorCaja)
    try:
        caja_num = float(caja) if caja else 0
        if caja_num > 0:
            # El precio unitario es el precio del lote (porque la cantidad es en lotes)
            precio_unitario = precio_lista  # precio por lote
            step = 1.0
            min_value = 0.0
            tipo_cantidad = 'lotes'
            cantidad_por_lote = caja_num
            if embalaje.upper() == "GRANEL":
                ayuda = f"Cantidad en lotes (granel de {caja_num} unidades) | Precio por lote: ${precio_lista:,.2f}"
            else:
                ayuda = f"Cantidad en lotes ({embalaje} de {caja_num} unidades) | Precio por lote: ${precio_lista:,.2f}"
            return precio_unitario, step, min_value, ayuda, precio_lista, tipo_cantidad, cantidad_por_lote
        else:
            # No hay cantidad por caja, asumimos precio unitario = precio de lista
            precio_unitario = precio_lista
            step = 1.0
            min_value = 0.0
            tipo_cantidad = 'unidades'
            cantidad_por_lote = 1
            ayuda = "Precio unitario (sin embalaje definido)"
            return precio_unitario, step, min_value, ayuda, precio_lista, tipo_cantidad, cantidad_por_lote
    except:
        # Si no se puede usar CantidadPorCaja, precio unitario = precio de lista
        precio_unitario = precio_lista
        step = 1.0
        min_value = 0.0
        tipo_cantidad = 'unidades'
        cantidad_por_lote = 1
        ayuda = "Precio unitario"
        return precio_unitario, step, min_value, ayuda, precio_lista, tipo_cantidad, cantidad_por_lote

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

    # Agregar categorías para Einhell
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

    if "KWB" in filename:
        df = df.rename(columns={'Nombre': 'Modelo'})
        for col in ['Codigo', 'Descripcion', 'Modelo', 'Marca', 'Precio_Lista', 'IVA', 'Hoja_Origen']:
            if col not in df.columns:
                df[col] = None
        for extra in ['CantidadPorCaja', 'Embalaje', 'UnidadPrecio']:
            if extra not in df.columns:
                df[extra] = None

    elif "Einhell" in filename:
        if 'Hoja_Origen' not in df.columns:
            df['Hoja_Origen'] = 'Einhell'
        if 'Marca' not in df.columns:
            df['Marca'] = 'Einhell'
        for extra in ['CantidadPorCaja', 'Embalaje', 'UnidadPrecio']:
            if extra not in df.columns:
                df[extra] = None

    elif "Fijaciones" in filename:
        df = df.rename(columns={'PrecioLista': 'Precio_Lista'})
        df['Modelo'] = df['Descripcion']
        if 'Marca' not in df.columns:
            df['Marca'] = 'Fijaciones'
        if 'Hoja_Origen' not in df.columns:
            df['Hoja_Origen'] = 'Fijaciones'
        for extra in ['CantidadPorCaja', 'Embalaje', 'UnidadPrecio']:
            if extra not in df.columns:
                df[extra] = None

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
        for extra in ['CantidadPorCaja', 'Embalaje', 'UnidadPrecio']:
            if extra not in df.columns:
                df[extra] = None

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
        for extra in ['CantidadPorCaja', 'Embalaje', 'UnidadPrecio']:
            if extra not in df.columns:
                df[extra] = None

    required = ['Codigo', 'Descripcion', 'Modelo', 'Marca', 'Precio_Lista', 'IVA', 'Hoja_Origen', 'Herramienta']
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

# ------------------------------------------------------------
# 3. CATÁLOGO Y AGREGADO AL CARRITO
# ------------------------------------------------------------
st.subheader("2. Catálogo de Productos")

has_categorias = 'Categoria_Generica' in df_productos.columns and df_productos['Categoria_Generica'].notna().any()
has_alimentacion = 'Tipo_Alimentacion' in df_productos.columns and df_productos['Tipo_Alimentacion'].notna().any()
has_herramienta = 'Herramienta' in df_productos.columns and df_productos['Herramienta'].notna().any()

num_filtros = 2  # Marca y Búsqueda siempre
if has_categorias:
    num_filtros += 1
if has_alimentacion:
    num_filtros += 1

cols_filtros = st.columns(num_filtros)
col_idx = 0

marcas_disponibles = sorted(df_productos['Marca'].dropna().unique())
marca_filtro = cols_filtros[col_idx].selectbox("Filtrar por Línea / Marca:", options=["Todas"] + marcas_disponibles)
col_idx += 1

if has_categorias:
    categorias_disponibles = sorted(df_productos['Categoria_Generica'].dropna().unique())
    cat_filtro = cols_filtros[col_idx].selectbox("Categoría:", options=["Todas"] + categorias_disponibles)
    col_idx += 1
else:
    cat_filtro = "Todas"

if has_alimentacion:
    alimentacion_disponibles = sorted(df_productos['Tipo_Alimentacion'].dropna().unique())
    alim_filtro = cols_filtros[col_idx].selectbox("Alimentación:", options=["Todas"] + alimentacion_disponibles)
    col_idx += 1
else:
    alim_filtro = "Todas"

busqueda = cols_filtros[-1].text_input("🔍 Buscar por Código, Modelo, Descripción, Marca o Herramienta:")

df_filtrado = df_productos.copy()
if marca_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Marca'] == marca_filtro]
if has_categorias and cat_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Categoria_Generica'] == cat_filtro]
if has_alimentacion and alim_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Tipo_Alimentacion'] == alim_filtro]

if busqueda:
    palabras = [normalize_text(p) for p in busqueda.split()]
    df_filtrado['Codigo_norm'] = df_filtrado['Codigo'].astype(str).apply(normalize_text)
    df_filtrado['Modelo_norm'] = df_filtrado['Modelo'].astype(str).apply(normalize_text)
    df_filtrado['Descripcion_norm'] = df_filtrado['Descripcion'].astype(str).apply(normalize_text)
    df_filtrado['Marca_norm'] = df_filtrado['Marca'].astype(str).apply(normalize_text)
    if has_herramienta:
        df_filtrado['Herramienta_norm'] = df_filtrado['Herramienta'].astype(str).apply(normalize_text)

    def matches_all(row):
        text = f"{row['Codigo_norm']} {row['Modelo_norm']} {row['Descripcion_norm']} {row['Marca_norm']}"
        if has_herramienta:
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
                if has_herramienta and p in row['Herramienta_norm']:
                    score += 3
            return score

        df_filtrado['Relevance'] = df_filtrado.apply(relevance_score, axis=1)
        df_filtrado = df_filtrado.sort_values('Relevance', ascending=False)
        cols_to_drop = ['Codigo_norm', 'Modelo_norm', 'Descripcion_norm', 'Marca_norm']
        if has_herramienta:
            cols_to_drop.append('Herramienta_norm')
        df_filtrado = df_filtrado.drop(columns=cols_to_drop + ['Relevance'])
    else:
        cols_to_drop = ['Codigo_norm', 'Modelo_norm', 'Descripcion_norm', 'Marca_norm']
        if has_herramienta:
            cols_to_drop.append('Herramienta_norm')
        df_filtrado = df_filtrado.drop(columns=cols_to_drop)

st.markdown("##### Agregar al Pedido")

if not df_filtrado.empty:
    df_filtrado['Codigo_Base'] = df_filtrado['Codigo'].astype(str).apply(lambda x: re.sub(r'[^0-9]', '', x))
    df_filtrado['Clave_Producto'] = df_filtrado['Codigo_Base'] + '_' + df_filtrado['Marca']

    productos_unicos = df_filtrado.drop_duplicates(subset=['Clave_Producto']).copy()
    productos_unicos['Descripcion'] = productos_unicos['Descripcion'].fillna('').astype(str)
    productos_unicos['Display'] = productos_unicos.apply(
        lambda row: f"{row['Codigo']} | {row['Marca']} | {row['Descripcion'][:30]}", axis=1
    )
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
                emb = str(row['Embalaje']) if pd.notna(row['Embalaje']) else ''
                caja = str(row['CantidadPorCaja']) if pd.notna(row['CantidadPorCaja']) else ''
                unidad = str(row['UnidadPrecio']) if pd.notna(row['UnidadPrecio']) else ''
                partes = []
                if emb:
                    partes.append(emb)
                if caja:
                    partes.append(f"Caja:{caja}")
                if unidad:
                    partes.append(f"Unidad:{unidad}")
                return " | ".join(partes) if partes else "Presentación estándar"

            presentaciones['Presentacion_Label'] = presentaciones.apply(format_presentacion, axis=1)
            presentacion_opciones = presentaciones['Presentacion_Label'].tolist()
            presentacion_seleccionada = st.selectbox("Elegir presentación:", options=presentacion_opciones)
            prod_data = presentaciones[presentaciones['Presentacion_Label'] == presentacion_seleccionada].iloc[0]
        else:
            prod_data = presentaciones.iloc[0]

        # Obtener información de precio y cantidad
        precio_unitario, step_sugerido, min_value, ayuda_cantidad, precio_lote, tipo_cantidad, cantidad_por_lote = get_product_price_info(prod_data)

        with st.expander("📋 Detalles del producto seleccionado", expanded=True):
            col_det1, col_det2 = st.columns(2)
            col_det1.markdown(f"**Código:** `{prod_data['Codigo']}`")
            col_det1.markdown(f"**Marca:** {prod_data['Marca']}")
            col_det1.markdown(f"**Modelo:** {prod_data['Modelo']}")
            if has_herramienta and pd.notna(prod_data.get('Herramienta')):
                col_det1.markdown(f"**Herramienta:** {prod_data['Herramienta']}")
            if pd.notna(prod_data.get('Categoria_Generica')):
                col_det1.markdown(f"**Categoría:** {prod_data['Categoria_Generica']}")
            if pd.notna(prod_data.get('Tipo_Alimentacion')):
                col_det1.markdown(f"**Alimentación:** {prod_data['Tipo_Alimentacion']}")
            col_det2.markdown(f"**Descripción:** {prod_data['Descripcion']}")

            extra_info = []
            if pd.notna(prod_data.get('Embalaje')):
                extra_info.append(f"**Embalaje:** {prod_data['Embalaje']}")
            if pd.notna(prod_data.get('CantidadPorCaja')):
                extra_info.append(f"**Cant. por Caja:** {prod_data['CantidadPorCaja']}")
            if pd.notna(prod_data.get('UnidadPrecio')):
                extra_info.append(f"**Unidad de Precio:** {prod_data['UnidadPrecio']}")
            if extra_info:
                st.markdown("**Datos de empaque:** " + " | ".join(extra_info))

            precio_oferta = prod_data['Precio_Oferta'] if prod_data['Es_Oferta'] else None
            if prod_data['Es_Oferta']:
                st.markdown(f"**Precio unitario (oferta):** ${precio_oferta:,.2f}")
            else:
                if tipo_cantidad == 'lotes':
                    st.markdown(f"**Precio por lote:** ${precio_lote:,.2f}")
                    st.markdown(f"**Cada lote contiene:** {cantidad_por_lote} unidades")
                    st.markdown(f"**Precio unitario (referencia):** ${precio_lote / cantidad_por_lote:,.2f}")
                else:
                    st.markdown(f"**Precio unitario:** ${precio_unitario:,.2f}")
                    st.markdown(f"**Presentación de:** {cantidad_por_lote} unidades (${precio_lote:,.2f})")
            if prod_data.get('Hoja_Origen') and "BATERÍAS Y CARGADORES" in str(prod_data['Hoja_Origen']).upper():
                st.info("🔋 Este producto es de la hoja BATERÍAS Y CARGADORES y no recibe descuentos adicionales.")

        if prod_data['Es_Oferta']:
            precio_unitario_a_usar = prod_data['Precio_Oferta']
        else:
            precio_unitario_a_usar = precio_unitario

        step_final = float(step_sugerido) if step_sugerido > 0 else 1.0
        min_val = float(min_value) if min_value > 0 else 0.0
        valor_inicial = step_final if step_final > 0 else 1.0

        if tipo_cantidad == 'lotes':
            label_cantidad = f"Cantidad (lotes de {cantidad_por_lote} unidades)"
        else:
            if step_final > 1:
                label_cantidad = f"Cantidad (múltiplos de {step_final} unidades)"
            else:
                label_cantidad = "Cantidad (unidades sueltas)"

        cantidad = col_qty.number_input(
            label_cantidad,
            min_value=min_val,
            value=valor_inicial if min_val > 0 else step_final,
            step=step_final,
            format="%g"
        )

        if ayuda_cantidad:
            st.caption(ayuda_cantidad)

        if col_btn.button("➕ Agregar al Carrito", use_container_width=True):
            if cantidad <= 0:
                st.error("La cantidad debe ser mayor a 0.")
            else:
                if step_final > 1 and min_val > 0:
                    if cantidad % step_final != 0:
                        st.error(f"La cantidad debe ser múltiplo de {step_final} (cajas completas).")
                        st.stop()

                # NUEVO: Verificar si ya existe el mismo producto con la misma presentación
                existing_index = None
                for idx, item in enumerate(st.session_state.carrito):
                    if (item['Codigo'] == str(prod_data['Codigo']) and
                        item.get('Embalaje') == str(prod_data.get('Embalaje', '')) and
                        item.get('CantidadPorCaja') == str(prod_data.get('CantidadPorCaja', '')) and
                        item.get('UnidadPrecio') == str(prod_data.get('UnidadPrecio', ''))):
                        existing_index = idx
                        break

                if existing_index is not None:
                    # Sumar cantidad
                    st.session_state.carrito[existing_index]['Cantidad'] += cantidad
                    st.session_state.carrito[existing_index]['Subtotal_Bruto'] = st.session_state.carrito[existing_index]['Precio_Unitario'] * st.session_state.carrito[existing_index]['Cantidad']
                    st.success(f"¡Cantidad actualizada! {st.session_state.carrito[existing_index]['Codigo']} ahora tiene {st.session_state.carrito[existing_index]['Cantidad']} unidades.")
                else:
                    # Crear nuevo ítem
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
                        "Precio_Presentacion": precio_lote if not prod_data['Es_Oferta'] else prod_data['Precio_Oferta'],
                        "Tipo_Cantidad": tipo_cantidad,
                        "Cantidad_Por_Lote": cantidad_por_lote,
                        "Step": step_final,
                        "Min_Value": min_val
                    })
                    st.success(f"¡Agregado: {cantidad}x {prod_data['Codigo']}!")
else:
    st.info("No se encontraron productos con esa búsqueda.")

st.markdown("---")

# ------------------------------------------------------------
# 4. RESUMEN DEL PEDIDO (CARRITO EDITABLE)
# ------------------------------------------------------------
st.subheader("3. Resumen del Pedido")

if st.session_state.carrito:
    def update_carrito(index, new_cantidad=None):
        if new_cantidad is not None:
            if new_cantidad <= 0:
                st.session_state.carrito.pop(index)
            else:
                # Verificar si el nuevo valor respeta el step (si se guardó)
                step = st.session_state.carrito[index].get('Step', 1)
                min_val = st.session_state.carrito[index].get('Min_Value', 0)
                if step > 1 and min_val > 0:
                    if new_cantidad % step != 0:
                        # Ajustar al múltiplo inferior más cercano
                        new_cantidad = (new_cantidad // step) * step
                        if new_cantidad == 0:
                            st.session_state.carrito.pop(index)
                            st.rerun()
                            return
                        # Mostrar mensaje de advertencia
                        st.warning(f"La cantidad se ajustó a {new_cantidad} (múltiplo de {step}).")
                st.session_state.carrito[index]['Cantidad'] = new_cantidad
                st.session_state.carrito[index]['Subtotal_Bruto'] = st.session_state.carrito[index]['Precio_Unitario'] * new_cantidad
        else:
            st.session_state.carrito.pop(index)
        st.rerun()

    st.markdown("#### Productos en el carrito")
    if st.session_state.carrito:
        for i, item in enumerate(st.session_state.carrito):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 2, 1, 1, 2, 1, 1])
            with col1:
                st.write(f"**{i+1}**")
            with col2:
                tipo = item.get('Tipo_Cantidad', 'unidades')
                if tipo == 'lotes':
                    qty_lote = item.get('Cantidad_Por_Lote', 1)
                    st.write(f"{item['Codigo']} - {str(item.get('Descripcion', ''))[:25]}")
                    st.caption(f"Lotes de {qty_lote} unidades")
                else:
                    step = item.get('Step', 1)
                    if step > 1:
                        st.write(f"{item['Codigo']} - {str(item.get('Descripcion', ''))[:25]}")
                        st.caption(f"Cajas de {step} unidades")
                    else:
                        st.write(f"{item['Codigo']} - {str(item.get('Descripcion', ''))[:30]}")
            with col3:
                st.write(f"${item['Precio_Unitario']:,.2f}")
            with col4:
                # MODIFICADO: usar step y min_value del ítem
                step = item.get('Step', 1)
                min_val = item.get('Min_Value', 0)
                new_qty = st.number_input(
                    "Cant.",
                    min_value=0,
                    value=int(item['Cantidad']),
                    step=int(step) if step >= 1 else 1,
                    key=f"qty_{i}",
                    label_visibility="collapsed"
                )
                if new_qty != item['Cantidad']:
                    update_carrito(i, new_qty)
            with col5:
                st.write(f"${item['Subtotal_Bruto']:,.2f}")
            with col6:
                if st.button("🗑️", key=f"del_{i}", help="Eliminar producto"):
                    update_carrito(i, None)
            with col7:
                emb = item.get('Embalaje', '')
                if emb:
                    st.caption(emb)
            st.markdown("---")

        if st.button("🗑️ Vaciar Carrito completo"):
            st.session_state.carrito = []
            st.rerun()

    st.markdown("#### Bonificaciones y Cierre")
    col_desc1, col_desc2, col_desc3, col_totales = st.columns([1, 1, 1, 2])

    desc_gen = col_desc1.number_input("Desc. General (%)", min_value=0.0, max_value=100.0, value=30.0, step=1.0)
    desc_ad1 = col_desc2.number_input("Desc. Adicional 1 (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
    desc_ad2 = col_desc3.number_input("Desc. Adicional 2 (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)

    multiplicador_desc = (1 - (desc_gen / 100)) * (1 - (desc_ad1 / 100)) * (1 - (desc_ad2 / 100))
    descuentos_usados = [f"-{d}%" for d in [desc_gen, desc_ad1, desc_ad2] if d > 0]
    texto_descuentos = " ".join(descuentos_usados) if descuentos_usados else "Sin bonificación"

    df_carrito = pd.DataFrame(st.session_state.carrito)

    def is_discount_applicable(row):
        if row['Es_Oferta']:
            return False
        if row.get('Hoja_Origen') and "BATERÍAS Y CARGADORES" in str(row['Hoja_Origen']).upper():
            return False
        return True

    def calcular_neto(row):
        if is_discount_applicable(row):
            neto = row['Subtotal_Bruto'] * multiplicador_desc
        else:
            neto = row['Subtotal_Bruto']
        return neto

    df_carrito['Neto_Calculado'] = df_carrito.apply(calcular_neto, axis=1)
    df_carrito['Monto_Descuento'] = df_carrito['Subtotal_Bruto'] - df_carrito['Neto_Calculado']
    df_carrito['Monto_IVA'] = df_carrito['Neto_Calculado'] * df_carrito['IVA']

    total_bruto = df_carrito['Subtotal_Bruto'].sum()
    total_neto = df_carrito['Neto_Calculado'].sum()
    total_iva = df_carrito['Monto_IVA'].sum()
    total_final = total_neto + total_iva
    total_descuento = total_bruto - total_neto

    col_totales.metric("Subtotal Bruto", f"${total_bruto:,.2f}")
    col_totales.metric(f"Descuentos ({texto_descuentos})", f"${total_descuento:,.2f}")
    col_totales.metric("Neto (con descuentos)", f"${total_neto:,.2f}")
    col_totales.metric("IVA Total", f"${total_iva:,.2f}")
    col_totales.metric("Total Final (Inc. IVA)", f"${total_final:,.2f}")

    with st.expander("📊 Detalle de descuentos por producto"):
        detalle = df_carrito[['Codigo', 'Descripcion', 'Cantidad', 'Precio_Unitario', 'Subtotal_Bruto', 'Monto_Descuento', 'Neto_Calculado', 'Monto_IVA']].copy()
        detalle['Monto_Descuento'] = detalle['Monto_Descuento'].apply(lambda x: f"${x:,.2f}" if x > 0 else "$0.00")
        detalle['Neto_Calculado'] = detalle['Neto_Calculado'].apply(lambda x: f"${x:,.2f}")
        detalle['Subtotal_Bruto'] = detalle['Subtotal_Bruto'].apply(lambda x: f"${x:,.2f}")
        detalle['Monto_IVA'] = detalle['Monto_IVA'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(detalle, use_container_width=True)

    st.markdown("---")
    if st.button("📄 Generar PDF del Pedido", type="primary"):
        if cliente_seleccionado is None:
            st.error("Debes seleccionar un cliente antes de generar el PDF.")
            st.stop()

        def fmt_currency(val):
            return f"${val:,.2f}"

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "PROFORMA DE PEDIDO", ln=True, align='C')
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 6, f"Cliente: {cliente_seleccionado}", ln=True)
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 6, f"CUIT: {cli_info.get('C.U.I.T.', '-')} | Condicion: {cli_info.get('FORMA DE PAGO', '-')}", ln=True)
        pdf.cell(0, 6, f"Vendedor: {cli_info.get('NOMB.VENDEDOR', '-')}", ln=True)
        pdf.ln(10)

        pdf.set_font("Arial", 'B', 8)
        pdf.cell(15, 8, "Codigo", border=1)
        pdf.cell(15, 8, "Marca", border=1)
        pdf.cell(18, 8, "Modelo", border=1)
        pdf.cell(30, 8, "Descripcion", border=1)
        if 'Embalaje' in df_carrito.columns and df_carrito['Embalaje'].notna().any():
            pdf.cell(10, 8, "Emb.", border=1)
            pdf.cell(10, 8, "Caja", border=1)
            pdf.cell(12, 8, "Unidad", border=1)
        pdf.cell(10, 8, "Cant", border=1, align='C')
        pdf.cell(15, 8, "P.Unit", border=1, align='R')
        pdf.cell(18, 8, "Subtotal", border=1, align='R')
        pdf.cell(15, 8, "Desc.", border=1, align='R')
        pdf.cell(18, 8, "Neto", border=1, align='R')
        pdf.cell(15, 8, "IVA", border=1, align='R')
        pdf.ln()

        pdf.set_font("Arial", '', 7)
        for _, row in df_carrito.iterrows():
            desc_corta = str(row.get('Descripcion', ''))[:28]
            marca_corta = str(row.get('Marca', ''))[:12]
            modelo_corta = str(row.get('Modelo', ''))[:15]

            pdf.cell(15, 6, str(row.get('Codigo', ''))[:10], border=1)
            pdf.cell(15, 6, marca_corta, border=1)
            pdf.cell(18, 6, modelo_corta, border=1)
            pdf.cell(30, 6, desc_corta, border=1)

            if 'Embalaje' in row and row['Embalaje']:
                pdf.cell(10, 6, str(row['Embalaje'])[:6], border=1)
                pdf.cell(10, 6, str(row['CantidadPorCaja'])[:6], border=1)
                pdf.cell(12, 6, str(row['UnidadPrecio'])[:6], border=1)
            else:
                if 'Embalaje' in df_carrito.columns and df_carrito['Embalaje'].notna().any():
                    pdf.cell(10, 6, "", border=1)
                    pdf.cell(10, 6, "", border=1)
                    pdf.cell(12, 6, "", border=1)

            pdf.cell(10, 6, str(int(row['Cantidad'])) if row['Cantidad'].is_integer() else f"{row['Cantidad']:.1f}", border=1, align='C')
            pdf.cell(15, 6, fmt_currency(row['Precio_Unitario']), border=1, align='R')
            pdf.cell(18, 6, fmt_currency(row['Subtotal_Bruto']), border=1, align='R')
            pdf.cell(15, 6, fmt_currency(row['Monto_Descuento']), border=1, align='R')
            pdf.cell(18, 6, fmt_currency(row['Neto_Calculado']), border=1, align='R')
            pdf.cell(15, 6, fmt_currency(row['Monto_IVA']), border=1, align='R')
            pdf.ln()

        pdf.ln(5)
        pdf.set_font("Arial", 'I', 7)
        pdf.cell(0, 5, "(*) Los articulos marcados como OFERTA o de la hoja 'BATERÍAS Y CARGADORES' no reciben descuentos adicionales.", ln=True)
        pdf.ln(2)

        pdf.set_font("Arial", 'B', 10)
        pdf.cell(150, 6, "Subtotal Bruto (Sin Desc):", align='R')
        pdf.cell(40, 6, fmt_currency(total_bruto), align='R')
        pdf.ln()
        pdf.cell(150, 6, f"Descuentos ({texto_descuentos})", align='R')
        pdf.cell(40, 6, fmt_currency(total_descuento), align='R')
        pdf.ln()
        pdf.cell(150, 6, "Neto:", align='R')
        pdf.cell(40, 6, fmt_currency(total_neto), align='R')
        pdf.ln()
        pdf.cell(150, 6, "IVA Total:", align='R')
        pdf.cell(40, 6, fmt_currency(total_iva), align='R')
        pdf.ln()
        pdf.cell(150, 8, "TOTAL FINAL:", align='R')
        pdf.cell(40, 8, fmt_currency(total_final), align='R')

        fd, path = tempfile.mkstemp(suffix=".pdf")
        try:
            pdf.output(path)
            with open(path, "rb") as f:
                pdf_bytes = f.read()
            st.download_button(
                label="⬇️ Descargar PDF",
                data=pdf_bytes,
                file_name="Pedido_Proforma.pdf",
                mime="application/pdf"
            )
            st.success("PDF generado exitosamente.")
        finally:
            os.close(fd)
else:
    st.info("El carrito está vacío. Buscá un producto y agregalo al pedido.")

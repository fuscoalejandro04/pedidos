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
# FUNCIÓN PARA NORMALIZAR TEXTO (eliminar tildes)
# ------------------------------------------------------------
def normalize_text(text):
    """Elimina tildes y convierte a minúsculas."""
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text.lower()

# ------------------------------------------------------------
# FUNCIÓN PARA OBTENER INFORMACIÓN DE PRECIO Y EMBALAJE
# ------------------------------------------------------------
def get_product_price_info(row):
    """
    Devuelve el precio unitario real, el paso sugerido para la cantidad,
    y un texto de ayuda, basado en UnidadPrecio y CantidadPorCaja.
    También devuelve el precio por la presentación (precio de lista).
    """
    precio_lista = row['Precio_Lista']
    unidad = str(row.get('UnidadPrecio', '')) if pd.notna(row.get('UnidadPrecio')) else ''
    caja = str(row.get('CantidadPorCaja', '')) if pd.notna(row.get('CantidadPorCaja')) else ''
    embalaje = str(row.get('Embalaje', '')) if pd.notna(row.get('Embalaje')) else ''

    # Intentar convertir unidad a numérico
    try:
        unidad_num = float(unidad)
        if unidad_num > 0:
            precio_unitario = precio_lista / unidad_num
            try:
                step = float(caja) if caja else 1.0
            except:
                step = 1.0
            if caja:
                ayuda = f"Sugerido: múltiplos de {step} (caja de {step} unidades)"
            else:
                ayuda = f"Precio por {unidad_num} unidades: ${precio_lista:,.2f}"
            return precio_unitario, step, ayuda, precio_lista
    except:
        pass

    # Si no es numérico, asumimos que el precio es por unidad
    precio_unitario = precio_lista
    try:
        step = float(caja) if caja else 1.0
    except:
        step = 1.0

    if embalaje.upper() == "GRANEL":
        ayuda = "Venta a granel (unidades sueltas)"
    elif embalaje:
        ayuda = f"Embalaje: {embalaje}"
        if caja:
            ayuda += f" | Caja de {caja} unidades"
    else:
        ayuda = "Unidades sueltas"

    return precio_unitario, step, ayuda, precio_lista

# ------------------------------------------------------------
# FUNCIÓN PARA EXTRAER CATEGORÍA Y ALIMENTACIÓN EN EINHELL
# ------------------------------------------------------------
def extract_einhell_categories(herramienta_str):
    """
    Devuelve (categoria_generica, tipo_alimentacion) a partir del campo Herramienta.
    Ejemplo: "ROTOMARTILLO INALÁMBRICO" -> ("Rotomartillo", "Inalámbrica")
    """
    if not isinstance(herramienta_str, str) or pd.isna(herramienta_str):
        return None, None
    h = herramienta_str.upper()
    # Definir palabras clave
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

    # Alimentación
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

    # Buscar archivos de oferta
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
    # ... (igual que antes, con la adición de 'Herramienta')
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
# 3. CATÁLOGO Y AGREGADO AL CARRITO (CON FILTROS MEJORADOS Y SELECCIÓN DE PRESENTACIÓN)
# ------------------------------------------------------------
st.subheader("2. Catálogo de Productos")

# Detectar si existen columnas de categorías
has_categorias = 'Categoria_Generica' in df_productos.columns and df_productos['Categoria_Generica'].notna().any()
has_alimentacion = 'Tipo_Alimentacion' in df_productos.columns and df_productos['Tipo_Alimentacion'].notna().any()
has_herramienta = 'Herramienta' in df_productos.columns and df_productos['Herramienta'].notna().any()

# Configurar columnas para filtros (hasta 4 columnas)
num_filtros = 2  # Marca y Búsqueda siempre
if has_categorias:
    num_filtros += 1
if has_alimentacion:
    num_filtros += 1

cols_filtros = st.columns(num_filtros)
col_idx = 0

# Filtro por Marca
marcas_disponibles = sorted(df_productos['Marca'].dropna().unique())
marca_filtro = cols_filtros[col_idx].selectbox("Filtrar por Línea / Marca:", options=["Todas"] + marcas_disponibles)
col_idx += 1

# Filtro por Categoría (si existe)
if has_categorias:
    categorias_disponibles = sorted(df_productos['Categoria_Generica'].dropna().unique())
    cat_filtro = cols_filtros[col_idx].selectbox("Categoría:", options=["Todas"] + categorias_disponibles)
    col_idx += 1
else:
    cat_filtro = "Todas"

# Filtro por Alimentación (si existe)
if has_alimentacion:
    alimentacion_disponibles = sorted(df_productos['Tipo_Alimentacion'].dropna().unique())
    alim_filtro = cols_filtros[col_idx].selectbox("Alimentación:", options=["Todas"] + alimentacion_disponibles)
    col_idx += 1
else:
    alim_filtro = "Todas"

# Campo de búsqueda (ocupa el resto del ancho)
busqueda = cols_filtros[-1].text_input("🔍 Buscar por Código, Modelo, Descripción, Marca o Herramienta:")

# Aplicar filtros
df_filtrado = df_productos.copy()
if marca_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Marca'] == marca_filtro]
if has_categorias and cat_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Categoria_Generica'] == cat_filtro]
if has_alimentacion and alim_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Tipo_Alimentacion'] == alim_filtro]

# Búsqueda inteligente (incluye Herramienta)
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
    # --- Función para agrupar presentaciones ---
    # Extraer código base (solo dígitos)
    df_filtrado['Codigo_Base'] = df_filtrado['Codigo'].astype(str).apply(lambda x: re.sub(r'[^0-9]', '', x))
    # Agrupar por código base y marca para ofrecer presentaciones
    df_filtrado['Clave_Producto'] = df_filtrado['Codigo_Base'] + '_' + df_filtrado['Marca']

    # Para el dropdown, mostraremos una representación única de cada producto (la primera fila de cada grupo)
    productos_unicos = df_filtrado.drop_duplicates(subset=['Clave_Producto']).copy()
    # Convertir Descripcion a string antes de hacer slicing
    productos_unicos['Descripcion_str'] = productos_unicos['Descripcion'].astype(str)
    productos_unicos['Display'] = productos_unicos.apply(
        lambda row: f"{row['Codigo']} | {row['Marca']} | {row['Descripcion_str'][:30]}", axis=1
    )
    display_options = productos_unicos['Display'].tolist()

    col_sel, col_qty, col_btn = st.columns([3, 1, 1])
    prod_seleccionado_display = col_sel.selectbox("Seleccione el producto:", options=display_options)

    if prod_seleccionado_display:
        # Obtener la clave del producto seleccionado
        prod_row = productos_unicos[productos_unicos['Display'] == prod_seleccionado_display].iloc[0]
        clave_seleccionada = prod_row['Clave_Producto']

        # Obtener todas las presentaciones de este producto
        presentaciones = df_filtrado[df_filtrado['Clave_Producto'] == clave_seleccionada].copy()
        # Ordenar por embalaje o cantidad por caja para tener un orden lógico
        presentaciones = presentaciones.sort_values(['CantidadPorCaja', 'Embalaje'], ascending=[True, True])

        # Si hay más de una presentación, mostrar un selectbox para elegir
        if len(presentaciones) > 1:
            # Crear una descripción de presentación
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
            # Obtener la fila correspondiente
            prod_data = presentaciones[presentaciones['Presentacion_Label'] == presentacion_seleccionada].iloc[0]
        else:
            prod_data = presentaciones.iloc[0]

        # Ahora prod_data es la fila con la presentación elegida
        precio_unitario, step_sugerido, ayuda_cantidad, precio_presentacion = get_product_price_info(prod_data)

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
                st.markdown(f"**Precio unitario:** ${precio_unitario:,.2f}")
                unidad = str(prod_data.get('UnidadPrecio', '')) if pd.notna(prod_data.get('UnidadPrecio')) else ''
                if unidad.isdigit():
                    st.markdown(f"**Precio por {unidad} unidades:** ${precio_presentacion:,.2f}")
            if prod_data.get('Hoja_Origen') and "BATERÍAS Y CARGADORES" in str(prod_data['Hoja_Origen']).upper():
                st.info("🔋 Este producto es de la hoja BATERÍAS Y CARGADORES y no recibe descuentos adicionales.")

        # Determinar precio unitario a usar
        if prod_data['Es_Oferta']:
            precio_unitario_a_usar = prod_data['Precio_Oferta']
        else:
            precio_unitario_a_usar = precio_unitario

        step_final = float(step_sugerido) if step_sugerido > 0 else 1.0
        valor_inicial = float(step_sugerido) if step_sugerido > 0 else 1.0

        cantidad = col_qty.number_input(
            "Cantidad:",
            min_value=0.0,
            value=valor_inicial,
            step=step_final,
            format="%g"
        )

        if ayuda_cantidad:
            st.caption(ayuda_cantidad)

        if col_btn.button("➕ Agregar al Carrito", use_container_width=True):
            if cantidad <= 0:
                st.error("La cantidad debe ser mayor a 0.")
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
                    "Precio_Presentacion": precio_presentacion if not prod_data['Es_Oferta'] else prod_data['Precio_Oferta']
                })
                st.success(f"¡Agregado: {cantidad}x {prod_data['Codigo']}!")
else:
    st.info("No se encontraron productos con esa búsqueda.")

st.markdown("---")

# ------------------------------------------------------------
# 4. RESUMEN DEL PEDIDO (CARRITO EDITABLE Y DETALLE DE DESCUENTOS)
# ------------------------------------------------------------
st.subheader("3. Resumen del Pedido")

if st.session_state.carrito:
    # Función para actualizar el carrito
    def update_carrito(index, new_cantidad=None):
        if new_cantidad is not None:
            if new_cantidad <= 0:
                st.session_state.carrito.pop(index)
            else:
                st.session_state.carrito[index]['Cantidad'] = new_cantidad
                st.session_state.carrito[index]['Subtotal_Bruto'] = st.session_state.carrito[index]['Precio_Unitario'] * new_cantidad
        else:
            st.session_state.carrito.pop(index)
        st.rerun()

    # Mostrar carrito con botones de eliminar y campos de cantidad
    st.markdown("#### Productos en el carrito")
    if st.session_state.carrito:
        for i, item in enumerate(st.session_state.carrito):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 2, 1, 1, 2, 1, 1])
            with col1:
                st.write(f"**{i+1}**")
            with col2:
                st.write(f"{item['Codigo']} - {str(item['Descripcion'])[:30]}")
            with col3:
                st.write(f"${item['Precio_Unitario']:,.2f}")
            with col4:
                new_qty = st.number_input(
                    "Cant.",
                    min_value=0,
                    value=int(item['Cantidad']),
                    step=1,
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

    # Convertir carrito a DataFrame para cálculos
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

    # Mostrar totales
    col_totales.metric("Subtotal Bruto", f"${total_bruto:,.2f}")
    col_totales.metric(f"Descuentos ({texto_descuentos})", f"${total_descuento:,.2f}")
    col_totales.metric("Neto (con descuentos)", f"${total_neto:,.2f}")
    col_totales.metric("IVA Total", f"${total_iva:,.2f}")
    col_totales.metric("Total Final (Inc. IVA)", f"${total_final:,.2f}")

    # Detalle de descuentos por producto (opcional)
    with st.expander("📊 Detalle de descuentos por producto"):
        detalle = df_carrito[['Codigo', 'Descripcion', 'Cantidad', 'Precio_Unitario', 'Subtotal_Bruto', 'Monto_Descuento', 'Neto_Calculado', 'Monto_IVA']].copy()
        detalle['Monto_Descuento'] = detalle['Monto_Descuento'].apply(lambda x: f"${x:,.2f}" if x > 0 else "$0.00")
        detalle['Neto_Calculado'] = detalle['Neto_Calculado'].apply(lambda x: f"${x:,.2f}")
        detalle['Subtotal_Bruto'] = detalle['Subtotal_Bruto'].apply(lambda x: f"${x:,.2f}")
        detalle['Monto_IVA'] = detalle['Monto_IVA'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(detalle, use_container_width=True)

    # 5. EXPORTACIÓN A PDF
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

        # Cabecera de tabla
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
            desc_corta = str(row['Descripcion'])[:28]
            marca_corta = str(row['Marca'])[:12]
            modelo_corta = str(row['Modelo'])[:15]

            pdf.cell(15, 6, str(row['Codigo'])[:10], border=1)
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
        pdf.cell(150, 6, f"Descuentos ({texto_descuentos}):", align='R')
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

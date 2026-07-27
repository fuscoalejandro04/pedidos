import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile
import os
import glob

st.set_page_config(page_title="Gestión de Pedidos", layout="wide", initial_sidebar_state="expanded")

st.title("📦 Sistema de Carga de Pedidos")
st.markdown("---")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# ------------------------------------------------------------
# 1. CARGAR DATOS Y DETECTAR OFERTAS
# ------------------------------------------------------------
@st.cache_data
def load_databases():
    # Cargar clientes (debe existir DB_Clientes_Limpia.xlsx)
    try:
        df_cli = pd.read_excel("DB_Clientes_Limpia.xlsx")
    except FileNotFoundError:
        st.error("No se encontró el archivo DB_Clientes_Limpia.xlsx. Por favor, asegúrate de que exista.")
        st.stop()

    # Lista de archivos de productos a cargar
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
            # Normalizar columnas según el archivo
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

    # 🔴 REGLA CLAVE: Forzar que todos los códigos sean TEXTO y sin espacios
    df_prod['Codigo'] = df_prod['Codigo'].astype(str).str.strip()

    # Asegurar que el precio de lista sea numérico
    df_prod['Precio_Lista'] = pd.to_numeric(df_prod['Precio_Lista'], errors='coerce').fillna(0)
    df_prod['Precio_Oferta'] = 0.0
    df_prod['Es_Oferta'] = False

    # Buscar dinámicamente archivos de oferta en la carpeta
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

                # 🔴 REGLA CLAVE: Forzar el mismo formato de texto en las Ofertas
                df_of_limpio['Codigo'] = df_of_limpio['Codigo'].astype(str).str.strip()
                df_of_limpio['Precio_Promocional'] = pd.to_numeric(df_of_limpio['Precio_Promocional'], errors='coerce').fillna(0)

                # Cruzar con el catálogo maestro
                df_prod = pd.merge(df_prod, df_of_limpio, on='Codigo', how='left')

                # Actualizar los que tienen oferta
                condicion_oferta = df_prod['Precio_Promocional'] > 0
                df_prod.loc[condicion_oferta, 'Precio_Oferta'] = df_prod.loc[condicion_oferta, 'Precio_Promocional']
                df_prod.loc[condicion_oferta, 'Es_Oferta'] = True

                # Limpiar columna temporal
                df_prod = df_prod.drop(columns=['Precio_Promocional'])
        except Exception as e:
            st.sidebar.warning(f"No se pudo procesar el archivo de oferta {archivo}: {e}")

    return df_cli, df_prod


def standardize_product_columns(df, filename):
    """
    Convierte las columnas de cada archivo a un esquema común:
    'Codigo', 'Descripcion', 'Modelo', 'Marca', 'Precio_Lista', 'IVA'
    """
    # Renombrar según el archivo
    if "KWB" in filename:
        # Columnas: Codigo, Nombre, Descripcion, Precio_Lista, IVA, Marca, Hoja_Origen
        df = df.rename(columns={
            'Nombre': 'Modelo'
        })
        # Asegurar que existan todas las columnas necesarias
        for col in ['Codigo', 'Descripcion', 'Modelo', 'Marca', 'Precio_Lista', 'IVA']:
            if col not in df.columns:
                df[col] = None
    elif "Einhell" in filename:
        # Columnas: Codigo, Herramienta, Modelo, Descripcion, Precio_Lista, IVA, Hoja_Origen, Marca
        # Ya tiene todo
        pass
    elif "Fijaciones" in filename:
        # Columnas: Codigo, Descripcion, CantidadPorCaja, Embalaje, UnidadPrecio, PrecioLista, IVA, Hoja_Origen
        df = df.rename(columns={
            'PrecioLista': 'Precio_Lista'
        })
        # No tiene Modelo -> lo dejamos vacío o copiamos de Descripcion
        df['Modelo'] = df['Descripcion']  # o ''
        # Asegurar Marca
        if 'Marca' not in df.columns:
            df['Marca'] = 'Fijaciones'
    elif "Penosil" in filename:
        # Columnas: Artículo, Nombre, Descripcion, Color, Presentacion, PrecioLista, IVA, Hoja_Origen
        df = df.rename(columns={
            'Artículo': 'Codigo',
            'Nombre': 'Modelo',
            'PrecioLista': 'Precio_Lista'
        })
        if 'Marca' not in df.columns:
            df['Marca'] = 'Penosil'
    else:
        # Intento genérico: buscar columnas comunes
        if 'PrecioLista' in df.columns:
            df = df.rename(columns={'PrecioLista': 'Precio_Lista'})
        if 'Artículo' in df.columns:
            df = df.rename(columns={'Artículo': 'Codigo'})
        if 'Nombre' in df.columns and 'Modelo' not in df.columns:
            df['Modelo'] = df['Nombre']

    # Asegurar que las columnas requeridas existan (con valores por defecto si faltan)
    required = ['Codigo', 'Descripcion', 'Modelo', 'Marca', 'Precio_Lista', 'IVA']
    for col in required:
        if col not in df.columns:
            df[col] = None

    # Convertir IVA a numérico (por si viene como string)
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

col_f1, col_f2 = st.columns(2)
marcas_disponibles = sorted(df_productos['Marca'].dropna().unique())
marca_filtro = col_f1.selectbox("Filtrar por Línea / Marca:", options=["Todas"] + marcas_disponibles)
busqueda = col_f2.text_input("🔍 Buscar por Código, Modelo o Descripción:")

df_filtrado = df_productos.copy()
if marca_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Marca'] == marca_filtro]

if busqueda:
    b_up = busqueda.upper()
    df_filtrado = df_filtrado[
        df_filtrado['Codigo'].astype(str).str.upper().str.contains(b_up) |
        df_filtrado['Modelo'].astype(str).str.upper().str.contains(b_up) |
        df_filtrado['Descripcion'].astype(str).str.upper().str.contains(b_up)
    ]

st.markdown("##### Agregar al Pedido")
if not df_filtrado.empty:
    def format_display(row):
        precio = row['Precio_Oferta'] if row['Es_Oferta'] else row['Precio_Lista']
        etiqueta = "🔥 OFERTA NETO | " if row['Es_Oferta'] else ""
        return f"{etiqueta}{row['Codigo']} | {row['Descripcion']} | ${precio:,.2f}"

    df_filtrado['Display'] = df_filtrado.apply(format_display, axis=1)

    col_sel, col_qty, col_btn = st.columns([3, 1, 1])
    prod_seleccionado = col_sel.selectbox("Seleccione el producto:", options=df_filtrado['Display'].tolist())
    cantidad = col_qty.number_input("Cantidad:", min_value=1, value=1, step=1)

    if col_btn.button("➕ Agregar al Carrito", use_container_width=True):
        prod_idx = df_filtrado[df_filtrado['Display'] == prod_seleccionado].index[0]
        prod_data = df_filtrado.loc[prod_idx]

        precio_usar = prod_data['Precio_Oferta'] if prod_data['Es_Oferta'] else prod_data['Precio_Lista']

        st.session_state.carrito.append({
            "Codigo": prod_data['Codigo'],
            "Descripcion": prod_data['Descripcion'],
            "Cantidad": cantidad,
            "Precio_Unitario": precio_usar,
            "Es_Oferta": prod_data['Es_Oferta'],
            "IVA": prod_data['IVA'],
            "Subtotal_Bruto": precio_usar * cantidad
        })
        st.success(f"¡Agregado: {cantidad}x {prod_data['Codigo']}!")
else:
    st.info("No se encontraron productos con esa búsqueda.")

st.markdown("---")

# ------------------------------------------------------------
# 4. RESUMEN DEL PEDIDO Y DESCUENTOS
# ------------------------------------------------------------
st.subheader("3. Resumen del Pedido")

if st.session_state.carrito:
    df_carrito = pd.DataFrame(st.session_state.carrito)

    df_mostrar = df_carrito[['Codigo', 'Descripcion', 'Cantidad', 'Precio_Unitario', 'Es_Oferta', 'Subtotal_Bruto']].copy()
    df_mostrar['Es_Oferta'] = df_mostrar['Es_Oferta'].apply(lambda x: "Sí (Neto)" if x else "No")
    st.dataframe(df_mostrar, use_container_width=True)

    if st.button("🗑️ Vaciar Carrito"):
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

    df_carrito['Neto_Calculado'] = df_carrito.apply(
        lambda row: row['Subtotal_Bruto'] if row['Es_Oferta'] else (row['Subtotal_Bruto'] * multiplicador_desc),
        axis=1
    )
    df_carrito['Monto_IVA'] = df_carrito['Neto_Calculado'] * df_carrito['IVA']

    total_bruto = df_carrito['Subtotal_Bruto'].sum()
    total_neto = df_carrito['Neto_Calculado'].sum()
    total_iva = df_carrito['Monto_IVA'].sum()
    total_final = total_neto + total_iva

    col_totales.metric("Subtotal Bruto", f"${total_bruto:,.2f}")
    col_totales.metric(f"Neto (Desc. aplicados)", f"${total_neto:,.2f}")
    col_totales.metric("Total Final (Inc. IVA)", f"${total_final:,.2f}")

    # 5. EXPORTACIÓN A PDF
    st.markdown("---")
    if st.button("📄 Generar PDF del Pedido", type="primary"):
        if cliente_seleccionado is None:
            st.error("Debes seleccionar un cliente antes de generar el PDF.")
            st.stop()

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

        pdf.set_font("Arial", 'B', 9)
        pdf.cell(25, 8, "Codigo", border=1)
        pdf.cell(85, 8, "Descripcion", border=1)
        pdf.cell(15, 8, "Cant", border=1, align='C')
        pdf.cell(30, 8, "P. Unit", border=1, align='R')
        pdf.cell(35, 8, "Subtotal Neto", border=1, align='R')
        pdf.ln()

        pdf.set_font("Arial", '', 8)
        for _, row in df_carrito.iterrows():
            desc_corta = str(row['Descripcion'])[:45]
            marca_oferta = " (*NETO)" if row['Es_Oferta'] else ""
            desc_final = desc_corta + marca_oferta

            pdf.cell(25, 6, str(row['Codigo']), border=1)
            pdf.cell(85, 6, desc_final, border=1)
            pdf.cell(15, 6, str(row['Cantidad']), border=1, align='C')
            pdf.cell(30, 6, f"${row['Precio_Unitario']:,.2f}", border=1, align='R')
            pdf.cell(35, 6, f"${row['Neto_Calculado']:,.2f}", border=1, align='R')
            pdf.ln()

        pdf.ln(5)
        pdf.set_font("Arial", 'I', 8)
        pdf.cell(0, 5, "(*) Los articulos marcados como NETO no reciben descuentos comerciales adicionales.", ln=True)
        pdf.ln(2)

        pdf.set_font("Arial", 'B', 10)
        pdf.cell(160, 6, "Subtotal Bruto (Sin Desc):", align='R')
        pdf.cell(30, 6, f"${total_bruto:,.2f}", align='R')
        pdf.ln()
        pdf.cell(160, 6, f"Bonificaciones ({texto_descuentos}):", align='R')
        pdf.cell(30, 6, f"${total_neto:,.2f}", align='R')
        pdf.ln()
        pdf.cell(160, 6, "IVA Total:", align='R')
        pdf.cell(30, 6, f"${total_iva:,.2f}", align='R')
        pdf.ln()
        pdf.cell(160, 8, "TOTAL FINAL:", align='R')
        pdf.cell(30, 8, f"${total_final:,.2f}", align='R')

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

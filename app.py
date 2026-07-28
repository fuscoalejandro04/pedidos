# ============================================================
# 3. CATÁLOGO Y AGREGADO AL CARRITO (CON FILTROS DINÁMICOS POR MARCA)
# ============================================================
st.subheader("2. Catálogo de Productos")

# --- Filtro principal: Marca ---
marcas_disponibles = sorted(df_productos['Marca'].dropna().unique())
marca_filtro = st.selectbox("Filtrar por Línea / Marca:", options=["Todas"] + marcas_disponibles)

# --- Determinar qué filtros adicionales mostrar según marca ---
# Configuración de filtros por marca
FILTROS_CONFIG = {
    "Einhell": {
        "Categoria_Generica": {"label": "Categoría", "options": sorted(df_productos[df_productos['Marca'] == "Einhell"]['Categoria_Generica'].dropna().unique())},
        "Tipo_Alimentacion": {"label": "Alimentación", "options": sorted(df_productos[df_productos['Marca'] == "Einhell"]['Tipo_Alimentacion'].dropna().unique())}
    },
    "Fijaciones": {
        "Embalaje": {"label": "Embalaje", "options": sorted(df_productos[df_productos['Marca'] == "Fijaciones"]['Embalaje'].dropna().unique())}
    },
    "KWB": {
        "Hoja_Origen": {"label": "Hoja de origen", "options": sorted(df_productos[df_productos['Marca'] == "KWB"]['Hoja_Origen'].dropna().unique())}
    },
    "Penosil": {
        "Color": {"label": "Color", "options": sorted(df_productos[df_productos['Marca'] == "Penosil"]['Color'].dropna().unique())}
    }
}

# Si la marca seleccionada es "Todas", no mostramos filtros adicionales
if marca_filtro == "Todas":
    filtros_adicionales = {}
else:
    filtros_adicionales = FILTROS_CONFIG.get(marca_filtro, {})

# --- Mostrar filtros adicionales en columnas dinámicas ---
num_extra = len(filtros_adicionales)
# Creamos columnas: una para cada filtro extra + una para búsqueda (ocupa el resto)
if num_extra > 0:
    cols = st.columns([1] * num_extra + [2])  # los filtros extra ocupan 1 parte cada uno, búsqueda 2 partes
else:
    cols = st.columns([1])  # solo búsqueda

# Variables para almacenar valores de filtros
filtro_valores = {}
col_idx = 0
for campo, config in filtros_adicionales.items():
    opciones = config["options"]
    # Asegurar que haya opciones
    if opciones:
        valor = cols[col_idx].selectbox(config["label"], options=["Todas"] + opciones)
        filtro_valores[campo] = valor
        col_idx += 1
    else:
        # Si no hay opciones, no mostrar filtro
        pass

# --- Campo de búsqueda (siempre visible, ocupa la última columna) ---
busqueda = cols[-1].text_input("🔍 Buscar por Código, Modelo, Descripción, Marca o Herramienta:")

# --- Aplicar filtros ---
df_filtrado = df_productos.copy()

# 1. Filtro por marca
if marca_filtro != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Marca'] == marca_filtro]

# 2. Filtros adicionales
for campo, valor in filtro_valores.items():
    if valor != "Todas":
        df_filtrado = df_filtrado[df_filtrado[campo] == valor]

# 3. Búsqueda (normalizada, incluye campos relevantes)
if busqueda:
    palabras = [normalize_text(p) for p in busqueda.split()]
    # Crear columnas normalizadas para búsqueda
    df_filtrado['Codigo_norm'] = df_filtrado['Codigo'].astype(str).apply(normalize_text)
    df_filtrado['Modelo_norm'] = df_filtrado['Modelo'].astype(str).apply(normalize_text)
    df_filtrado['Descripcion_norm'] = df_filtrado['Descripcion'].astype(str).apply(normalize_text)
    df_filtrado['Marca_norm'] = df_filtrado['Marca'].astype(str).apply(normalize_text)
    if 'Herramienta' in df_filtrado.columns:
        df_filtrado['Herramienta_norm'] = df_filtrado['Herramienta'].astype(str).apply(normalize_text)

    # Función que verifica que todas las palabras estén en al menos un campo
    def matches_all(row):
        text = f"{row['Codigo_norm']} {row['Modelo_norm']} {row['Descripcion_norm']} {row['Marca_norm']}"
        if 'Herramienta_norm' in row:
            text += f" {row['Herramienta_norm']}"
        return all(p in text for p in palabras)

    mask = df_filtrado.apply(matches_all, axis=1)
    df_filtrado = df_filtrado.loc[mask].copy()

    if not df_filtrado.empty:
        # Puntuación de relevancia
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
        # Eliminar columnas auxiliares
        cols_aux = ['Codigo_norm', 'Modelo_norm', 'Descripcion_norm', 'Marca_norm']
        if 'Herramienta_norm' in df_filtrado.columns:
            cols_aux.append('Herramienta_norm')
        df_filtrado = df_filtrado.drop(columns=cols_aux + ['Relevance'])
    else:
        # Eliminar columnas auxiliares si el resultado está vacío
        cols_aux = ['Codigo_norm', 'Modelo_norm', 'Descripcion_norm', 'Marca_norm']
        if 'Herramienta_norm' in df_filtrado.columns:
            cols_aux.append('Herramienta_norm')
        df_filtrado = df_filtrado.drop(columns=cols_aux)

# --- Resto del código de agregado al carrito (sin cambios) ---
st.markdown("##### Agregar al Pedido")

if not df_filtrado.empty:
    # ... (código de presentaciones y agregado)
    # Esto es exactamente igual al que tenías antes, solo asegúrate de que use la nueva función get_product_info
    # y que consolide items.
    # Por brevedad, no lo repito aquí, pero deberías mantener la lógica de presentaciones y agregado.
    # Asegúrate de que la variable 'info' se obtenga con get_product_info(prod_data)

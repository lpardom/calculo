import streamlit as st
import pandas as pd
import unicodedata
import io
import zipfile
import os
from functools import lru_cache

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="Simulador Electoral Perú 2026",
    page_icon="🇵🇪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CSS PERSONALIZADO
# ============================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #D91023;
        text-align: center;
        margin-bottom: 0.3rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #555;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .election-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: bold;
        margin: 2px;
    }
    .badge-diputados { background: #1f4e79; color: white; }
    .badge-senado { background: #D91023; color: white; }
    .badge-andino { background: #28a745; color: white; }
    .info-box {
        background-color: #f8f9fa;
        border-left: 4px solid #D91023;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6;
        border-radius: 4px 4px 0 0;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #D91023 !important;
        color: white !important;
    }
    .dataframe th {
        background-color: #D91023;
        color: white;
        font-weight: bold;
        text-align: center;
    }
    .dataframe td { text-align: center; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONFIGURACIONES DE LAS 3 ELECCIONES
# ============================================================
ESCAÑOS_DIPUTADOS_2026 = {
    'AMAZONAS': 2, 'ANCASH': 5, 'APURIMAC': 2, 'AREQUIPA': 6, 'AYACUCHO': 3,
    'CAJAMARCA': 6, 'CALLAO': 4, 'CUSCO': 5, 'HUANCAVELICA': 2, 'HUANUCO': 3,
    'ICA': 4, 'JUNIN': 5, 'LA LIBERTAD': 7, 'LAMBAYEQUE': 5, 'LIMA METROPOLITANA': 32,
    'LIMA PROVINCIAS': 4, 'RESIDENTES EN EL EXTRANJERO': 2, 'LORETO': 4,
    'MADRE DE DIOS': 2, 'MOQUEGUA': 2, 'PASCO': 2, 'PIURA': 7, 'PUNO': 5,
    'SAN MARTIN': 4, 'TACNA': 2, 'TUMBES': 2, 'UCAYALI': 3
}

# SENADO: 60 escaños totales (30 único + 30 múltiple)
ESCAÑOS_SENADO_UNICO = 30
ESCAÑOS_SENADO_MULTIPLE = 30

REGLA_MULTIPLE_SENADO = {
    'AMAZONAS': 1, 'ANCASH': 1, 'APURIMAC': 1, 'AREQUIPA': 1, 'AYACUCHO': 1,
    'CAJAMARCA': 1, 'CALLAO': 1, 'CUSCO': 1, 'HUANCAVELICA': 1, 'HUANUCO': 1,
    'ICA': 1, 'JUNIN': 1, 'LA LIBERTAD': 1, 'LAMBAYEQUE': 1, 'LIMA METROPOLITANA': 2,
    'LIMA PROVINCIAS': 1, 'RESIDENTES EN EL EXTRANJERO': 1, 'LORETO': 1,
    'MADRE DE DIOS': 1, 'MOQUEGUA': 1, 'PASCO': 1, 'PIURA': 1, 'PUNO': 1,
    'SAN MARTIN': 1, 'TACNA': 1, 'TUMBES': 1, 'UCAYALI': 1
}

ESCAÑOS_ANDINO = 5

EXCLUIR = ['VOTOS EN BLANCO', 'VOTOS NULOS']
COL_PARTIDO = 'ORGANIZACION POLÍTICA'
COL_VOTOS = 'CANTIDAD DE VOTOS'

# ============================================================
# FUNCIONES UTILITARIAS
# ============================================================
def eliminar_tildes(texto):
    if not isinstance(texto, str): return texto
    texto = unicodedata.normalize('NFD', texto)
    return texto.encode('ascii', 'ignore').decode("utf-8").upper()

@st.cache_data(show_spinner=False)
def calcular_dhondt(df_votos, num_escaños, col_partido, col_votos):
    if num_escaños <= 0 or df_votos.empty:
        return pd.DataFrame(columns=['Partido', 'Escaños'])
    df_votos = df_votos.copy()
    df_votos[col_votos] = pd.to_numeric(df_votos[col_votos], errors='coerce').fillna(0)
    listado_cocientes = []
    for i in range(1, num_escaños + 1):
        temp = df_votos[[col_partido, col_votos]].copy()
        temp['cociente'] = temp[col_votos] / i
        listado_cocientes.append(temp)
    df_cocientes = pd.concat(listado_cocientes)
    top_escaños = df_cocientes.nlargest(num_escaños, 'cociente')
    res = top_escaños[col_partido].value_counts().reset_index()
    res.columns = ['Partido', 'Escaños']
    return res

def detectar_region(nombre_archivo, diccionario_regiones):
    nombre_normalizado = eliminar_tildes(nombre_archivo)
    region = next((r for r in diccionario_regiones.keys() if eliminar_tildes(r) in nombre_normalizado), None)
    if region is None:
        partes = nombre_archivo.replace('.csv', '').split('_')
        if len(partes) >= 3:
            region = eliminar_tildes(partes[2])
            for r in diccionario_regiones.keys():
                if eliminar_tildes(r) in region or region in eliminar_tildes(r):
                    return r
    return region

def extraer_csvs_de_zip(uploaded_zip):
    csv_files = []
    try:
        with zipfile.ZipFile(uploaded_zip) as z:
            for name in z.namelist():
                if name.lower().endswith('.csv') and not name.startswith('__') and not name.startswith('.'):
                    with z.open(name) as f:
                        content = f.read()
                        csv_files.append({
                            'name': os.path.basename(name),
                            'content': io.BytesIO(content),
                            'full_name': name
                        })
    except Exception as e:
        st.error(f"Error leyendo ZIP: {str(e)}")
    return csv_files

def extraer_csvs_de_rar(uploaded_rar):
    csv_files = []
    try:
        import rarfile
        with rarfile.RarFile(uploaded_rar) as rf:
            for name in rf.namelist():
                if name.lower().endswith('.csv') and not name.startswith('__') and not name.startswith('.'):
                    with rf.open(name) as f:
                        content = f.read()
                        csv_files.append({
                            'name': os.path.basename(name),
                            'content': io.BytesIO(content),
                            'full_name': name
                        })
    except ImportError:
        st.error("Para archivos RAR necesitas: pip install rarfile")
    except Exception as e:
        st.error(f"Error leyendo RAR: {str(e)}")
    return csv_files

def obtener_csvs(uploaded_files, uploaded_zip, uploaded_rar, uploaded_zip_unico=None, uploaded_zip_multiple=None):
    todos_csvs = []

    # Archivos individuales
    if uploaded_files:
        for f in uploaded_files:
            content = f.read()
            todos_csvs.append({
                'name': f.name,
                'content': io.BytesIO(content),
                'source': 'individual'
            })

    # ZIP estándar
    if uploaded_zip:
        st.info(f"Descomprimiendo ZIP: {uploaded_zip.name}...")
        zip_csvs = extraer_csvs_de_zip(uploaded_zip)
        for c in zip_csvs:
            c['source'] = f"ZIP: {uploaded_zip.name}"
        todos_csvs.extend(zip_csvs)

    # RAR estándar
    if uploaded_rar:
        st.info(f"Descomprimiendo RAR: {uploaded_rar.name}...")
        rar_csvs = extraer_csvs_de_rar(uploaded_rar)
        for c in rar_csvs:
            c['source'] = f"RAR: {uploaded_rar.name}"
        todos_csvs.extend(rar_csvs)

    # Para Senado: Distrito Único
    if uploaded_zip_unico:
        st.info(f"Descomprimiendo Distrito Unico: {uploaded_zip_unico.name}...")
        if uploaded_zip_unico.name.lower().endswith('.zip'):
            csvs = extraer_csvs_de_zip(uploaded_zip_unico)
        else:
            csvs = extraer_csvs_de_rar(uploaded_zip_unico)
        for c in csvs:
            c['source'] = f"UNICO: {uploaded_zip_unico.name}"
            c['distrito'] = 'unico'
        todos_csvs.extend(csvs)

    # Para Senado: Distrito Múltiple
    if uploaded_zip_multiple:
        st.info(f"Descomprimiendo Distrito Multiple: {uploaded_zip_multiple.name}...")
        if uploaded_zip_multiple.name.lower().endswith('.zip'):
            csvs = extraer_csvs_de_zip(uploaded_zip_multiple)
        else:
            csvs = extraer_csvs_de_rar(uploaded_zip_multiple)
        for c in csvs:
            c['source'] = f"MULTIPLE: {uploaded_zip_multiple.name}"
            c['distrito'] = 'multiple'
        todos_csvs.extend(csvs)

    return todos_csvs

def procesar_csvs(csv_list, tipo_eleccion):
    datos = {}
    votos_nacionales = []
    archivos_ok = []
    archivos_error = []

    for csv_info in csv_list:
        nombre = csv_info['name']
        distrito = csv_info.get('distrito', 'auto')
        try:
            csv_info['content'].seek(0)
            df = pd.read_csv(csv_info['content'])
            df.columns = df.columns.str.strip()

            if COL_PARTIDO not in df.columns or COL_VOTOS not in df.columns:
                archivos_error.append(f"{nombre}: Columnas requeridas no encontradas")
                continue

            df_agrupado = df.groupby(COL_PARTIDO)[COL_VOTOS].sum().reset_index()
            df_valido = df_agrupado[~df_agrupado[COL_PARTIDO].isin(EXCLUIR)].copy()

            if tipo_eleccion == 'diputados':
                region = detectar_region(nombre, ESCAÑOS_DIPUTADOS_2026)
                if region and region in ESCAÑOS_DIPUTADOS_2026:
                    if region in datos:
                        datos[region] = pd.concat([datos[region], df_valido]).groupby(COL_PARTIDO)[COL_VOTOS].sum().reset_index()
                    else:
                        datos[region] = df_valido
                    votos_nacionales.append(df_valido)
                    archivos_ok.append((region, nombre, csv_info.get('source', 'individual')))
                else:
                    archivos_error.append(f"{nombre}: Region no detectada")

            elif tipo_eleccion == 'senado':
                if distrito == 'unico':
                    if 'unico' in datos:
                        datos['unico'] = pd.concat([datos['unico'], df_valido]).groupby(COL_PARTIDO)[COL_VOTOS].sum().reset_index()
                    else:
                        datos['unico'] = df_valido
                    votos_nacionales.append(df_valido)
                    archivos_ok.append(('DISTRITO UNICO', nombre, csv_info.get('source', 'individual')))
                elif distrito == 'multiple':
                    region = detectar_region(nombre, REGLA_MULTIPLE_SENADO)
                    if region and region in REGLA_MULTIPLE_SENADO:
                        if region in datos:
                            datos[region] = pd.concat([datos[region], df_valido]).groupby(COL_PARTIDO)[COL_VOTOS].sum().reset_index()
                        else:
                            datos[region] = df_valido
                        votos_nacionales.append(df_valido)
                        archivos_ok.append((region, nombre, csv_info.get('source', 'individual')))
                    else:
                        archivos_error.append(f"{nombre}: Region del distrito multiple no detectada")
                else:
                    nombre_norm = eliminar_tildes(nombre)
                    if 'UNICO' in nombre_norm or 'UNICO' in nombre_norm:
                        if 'unico' in datos:
                            datos['unico'] = pd.concat([datos['unico'], df_valido]).groupby(COL_PARTIDO)[COL_VOTOS].sum().reset_index()
                        else:
                            datos['unico'] = df_valido
                        votos_nacionales.append(df_valido)
                        archivos_ok.append(('DISTRITO UNICO', nombre, csv_info.get('source', 'individual')))
                    else:
                        region = detectar_region(nombre, REGLA_MULTIPLE_SENADO)
                        if region and region in REGLA_MULTIPLE_SENADO:
                            if region in datos:
                                datos[region] = pd.concat([datos[region], df_valido]).groupby(COL_PARTIDO)[COL_VOTOS].sum().reset_index()
                            else:
                                datos[region] = df_valido
                            votos_nacionales.append(df_valido)
                            archivos_ok.append((region, nombre, csv_info.get('source', 'individual')))
                        else:
                            archivos_error.append(f"{nombre}: Distrito no detectado")

            elif tipo_eleccion == 'andino':
                votos_nacionales.append(df_valido)
                archivos_ok.append(('NACIONAL', nombre, csv_info.get('source', 'individual')))

        except Exception as e:
            archivos_error.append(f"{nombre}: {str(e)}")

    if tipo_eleccion == 'andino' and votos_nacionales:
        df_consolidado = pd.concat(votos_nacionales).groupby(COL_PARTIDO)[COL_VOTOS].sum().reset_index()
        datos['nacional'] = df_consolidado[~df_consolidado[COL_PARTIDO].isin(EXCLUIR)].copy()

    return datos, votos_nacionales, archivos_ok, archivos_error

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("<h1 style='text-align:center; color:#D91023;'>🇵🇪 PERÚ 2026</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#666;'>Simulador Electoral Integral</p>", unsafe_allow_html=True)
    st.markdown("---")

    st.subheader("🗳️ Tipo de Elección")
    tipo_eleccion = st.radio(
        "Selecciona:",
        options=[
            ("diputados", "🏛️ Diputados (130 escaños)"),
            ("senado", "⚖️ Senado (60 escaños)"),
            ("andino", "🌎 Parlamento Andino (5 escaños)")
        ],
        format_func=lambda x: x[1],
        index=0
    )[0]

    st.markdown("---")
    st.subheader("📁 Carga de Archivos")

    # Variables para archivos
    uploaded_files = None
    uploaded_zip = None
    uploaded_rar = None
    uploaded_zip_unico = None
    uploaded_zip_multiple = None

    if tipo_eleccion == 'senado':
        st.markdown("""
        <div class="warning-box">
        <b>SENADO requiere 2 archivos separados:</b><br>
        1. <b>Distrito Unico</b> (30 escaños)<br>
        2. <b>Distrito Multiple</b> (30 escaños - regiones)
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📦 ZIP/RAR Distrito UNICO", expanded=True):
            uploaded_zip_unico = st.file_uploader(
                "Archivo ZIP/RAR del Distrito Unico",
                type=["zip", "rar"],
                key=f"zip_unico_{tipo_eleccion}"
            )

        with st.expander("📦 ZIP/RAR Distrito MULTIPLE", expanded=True):
            uploaded_zip_multiple = st.file_uploader(
                "Archivo ZIP/RAR del Distrito Multiple",
                type=["zip", "rar"],
                key=f"zip_multiple_{tipo_eleccion}"
            )
    else:
        with st.expander("📄 Subir CSVs individuales", expanded=False):
            uploaded_files = st.file_uploader(
                "Archivos CSV sueltos",
                type="csv",
                accept_multiple_files=True,
                key=f"csv_{tipo_eleccion}"
            )

        with st.expander("📦 Subir ZIP con CSVs", expanded=True):
            uploaded_zip = st.file_uploader(
                "Archivo ZIP (.zip)",
                type="zip",
                key=f"zip_{tipo_eleccion}"
            )

        with st.expander("📦 Subir RAR con CSVs", expanded=False):
            uploaded_rar = st.file_uploader(
                "Archivo RAR (.rar)",
                type="rar",
                key=f"rar_{tipo_eleccion}"
            )
            if uploaded_rar:
                st.info("Nota: Para RAR necesitas `pip install rarfile`")

    st.subheader("📊 Excel de Candidatos (Opcional)")
    uploaded_excel = st.file_uploader(
        "Maestro de candidatos",
        type=["xlsx", "xls"],
        key=f"excel_{tipo_eleccion}"
    )

    st.markdown("---")

    if tipo_eleccion == 'diputados':
        st.markdown("""
        <div class="info-box">
        <b>🏛️ DIPUTADOS</b><br>
        • 130 escaños<br>
        • Doble valla: 5% nacional + 7 escaños distritales<br>
        • Metodo D'Hondt por región<br><br>
        <b>📦 Formato ZIP esperado:</b><br>
        PR-ESP_Diputados_2026_AMAZONAS.csv<br>
        PR-ESP_Diputados_2026_ANCASH.csv<br>
        ... (27 archivos)
        </div>
        """, unsafe_allow_html=True)
    elif tipo_eleccion == 'senado':
        st.markdown("""
        <div class="info-box">
        <b>⚖️ SENADO - 60 ESCAÑOS TOTAL</b><br>
        • <b>Distrito Unico:</b> 30 escaños (nacional)<br>
        • <b>Distrito Multiple:</b> 30 escaños (26 regiones + Residentes)<br>
        • Valla: 5% nacional + 3 escaños<br><br>
        <b>📦 Archivos requeridos:</b><br>
        1. <b>ZIP/RAR Distrito Unico</b><br>
        2. <b>ZIP/RAR Distrito Multiple</b><br><br>
        <b>Formato esperado:</b><br>
        ...Distrito_Electoral_Unico_...<br>
        ...Distrito_Electoral_Multiple_[REGION].csv
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="info-box">
        <b>🌎 PARLAMENTO ANDINO</b><br>
        • 5 escaños<br>
        • Valla simple: 5% nacional<br>
        • Circunscripción única<br><br>
        <b>📦 Formato ZIP esperado:</b><br>
        Cualquier CSV con columnas<br>
        ORGANIZACION POLÍTICA y<br>
        CANTIDAD DE VOTOS
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption("v4.0 - Simulador Integral 2026")

# ============================================================
# HEADER PRINCIPAL
# ============================================================
st.markdown('<div class="main-header">🇵🇪 Simulador Electoral Perú 2026</div>', unsafe_allow_html=True)

if tipo_eleccion == 'diputados':
    st.markdown("<div class='sub-header'><span class='election-badge badge-diputados'>🏛️ DIPUTADOS</span> 130 Escaños · Doble Valla Electoral · D'Hondt</div>", unsafe_allow_html=True)
elif tipo_eleccion == 'senado':
    st.markdown('<div class="sub-header"><span class="election-badge badge-senado">⚖️ SENADO</span> 60 Escaños · 30 Unico + 30 Multiple</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="sub-header"><span class="election-badge badge-andino">🌎 PARLAMENTO ANDINO</span> 5 Escaños · Circunscripción Única</div>', unsafe_allow_html=True)

# ============================================================
# RESUMEN DE ARCHIVOS CARGADOS
# ============================================================
if tipo_eleccion == 'senado':
    todos_csvs = obtener_csvs([], None, None, uploaded_zip_unico, uploaded_zip_multiple)
else:
    todos_csvs = obtener_csvs(uploaded_files or [], uploaded_zip, uploaded_rar)

if todos_csvs:
    st.markdown("<div style='background:#f8f9fa;border:2px dashed #D91023;border-radius:12px;padding:1rem;text-align:center;margin:1rem 0;'>", unsafe_allow_html=True)
    st.markdown(f"**📁 Archivos detectados: {len(todos_csvs)} CSVs**")
    fuentes = {}
    for c in todos_csvs:
        src = c.get('source', 'individual')
        if src not in fuentes:
            fuentes[src] = []
        fuentes[src].append(c['name'])
    for src, files in fuentes.items():
        with st.expander(f"📂 {src} ({len(files)} archivos)"):
            st.markdown("<br>".join([f"• {f}" for f in files]), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# BOTÓN DE PROCESAMIENTO
# ============================================================
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    procesar = st.button("🚀 PROCESAR ELECCIONES", type="primary", use_container_width=True, disabled=(len(todos_csvs) == 0))

# ============================================================
# PROCESAMIENTO PRINCIPAL
# ============================================================
if procesar and todos_csvs:
    with st.spinner(f"Procesando {tipo_eleccion.upper()}..."):
        datos, votos_nac, archivos_ok, archivos_error = procesar_csvs(todos_csvs, tipo_eleccion)

        if archivos_error:
            with st.expander(f"⚠️ Errores ({len(archivos_error)})"):
                for err in archivos_error:
                    st.markdown(f"- {err}")

        if not datos:
            st.error("No se pudieron procesar archivos válidos. Verifica el formato.")
            st.stop()

        # =====================================================
        # LÓGICA: DIPUTADOS
        # =====================================================
        if tipo_eleccion == 'diputados':
            df_nacional = pd.concat(votos_nac).groupby(COL_PARTIDO)[COL_VOTOS].sum().reset_index()
            total_votos = df_nacional[COL_VOTOS].sum()
            pasan_5 = df_nacional[df_nacional[COL_VOTOS] >= (total_votos * 0.05)][COL_PARTIDO].tolist()

            escaños_sim = []
            for region, df_v in datos.items():
                n = ESCAÑOS_DIPUTADOS_2026.get(region, 0)
                if n > 0:
                    escaños_sim.append(calcular_dhondt(df_v, n, COL_PARTIDO, COL_VOTOS))

            df_sim = pd.concat(escaños_sim).groupby('Partido')['Escaños'].sum().reset_index()
            pasan_7 = df_sim[df_sim['Escaños'] >= 7]['Partido'].tolist()
            partidos_aptos = list(set(pasan_5) & set(pasan_7))

            resultados = []
            for region, df_v in datos.items():
                n_esc = ESCAÑOS_DIPUTADOS_2026.get(region, 0)
                df_f = df_v[df_v[COL_PARTIDO].isin(partidos_aptos)].copy()
                if n_esc > 0 and not df_f.empty:
                    df_res = calcular_dhondt(df_f, n_esc, COL_PARTIDO, COL_VOTOS)
                    df_res['Region'] = region
                    resultados.append(df_res)

            df_final = pd.concat(resultados, ignore_index=True)
            cuadro = df_final.pivot(index='Region', columns='Partido', values='Escaños').fillna(0).astype(int)
            totales = cuadro.sum().sort_values(ascending=False)
            cuadro = cuadro.reindex(columns=totales.index.tolist()).sort_index()
            cuadro['TOTAL REGION'] = cuadro.sum(axis=1)
            cuadro.loc['TOTAL NACIONAL'] = cuadro.sum(numeric_only=True)

            total_escaños = int(cuadro.loc['TOTAL NACIONAL', 'TOTAL REGION'])

            # Candidatos
            candidatos = []
            for region, df_v in datos.items():
                res_reg = df_final[df_final['Region'] == region]
                if res_reg.empty: continue
                archivos_reg = [c for c in todos_csvs if eliminar_tildes(c['name']).find(eliminar_tildes(region)) != -1]
                if archivos_reg:
                    dfs = []
                    for c in archivos_reg:
                        c['content'].seek(0)
                        df_temp = pd.read_csv(c['content'])
                        df_temp.columns = df_temp.columns.str.strip()
                        dfs.append(df_temp)
                    df_mesas = pd.concat(dfs)
                    cols_cands = [col for col in df_mesas.columns if col.isdigit() or 'CANDIDATO' in col.upper()]
                    for _, fp in res_reg.iterrows():
                        partido = fp['Partido']
                        num_esc = int(fp['Escaños'])
                        if num_esc > 0:
                            df_p = df_mesas[df_mesas[COL_PARTIDO] == partido]
                            votos_cands = []
                            for col in cols_cands:
                                total = pd.to_numeric(df_p[col], errors='coerce').sum()
                                votos_cands.append({'Candidato': col, 'Votos': total})
                            df_rank = pd.DataFrame(votos_cands)
                            if not df_rank.empty:
                                for _, g in df_rank.nlargest(num_esc, 'Votos').iterrows():
                                    candidatos.append({
                                        'Región': region, 'Partido': partido,
                                        'Candidato/Nro': g['Candidato'], 'Votos Preferenciales': int(g['Votos'])
                                    })
            df_candidatos = pd.DataFrame(candidatos)

        # =====================================================
        # LÓGICA: SENADO (60 escaños = 30 único + 30 múltiple)
        # =====================================================
        elif tipo_eleccion == 'senado':
            df_unico = datos.get('unico', pd.DataFrame())
            datos_mult = {k: v for k, v in datos.items() if k != 'unico'}

            if df_unico.empty:
                st.error("No se encontraron datos del Distrito Unico. Verifica el archivo ZIP/RAR del Distrito Unico.")
                st.stop()
            if not datos_mult:
                st.error("No se encontraron datos del Distrito Multiple. Verifica el archivo ZIP/RAR del Distrito Multiple.")
                st.stop()

            votos_nac_df = pd.concat(votos_nac).groupby(COL_PARTIDO)[COL_VOTOS].sum().reset_index()
            total_v = votos_nac_df[COL_VOTOS].sum()
            pasan_5 = votos_nac_df[votos_nac_df[COL_VOTOS] >= (total_v * 0.05)][COL_PARTIDO].tolist()

            # Simulación para valla: 30 escaños único + suma de múltiple
            sim_u = calcular_dhondt(df_unico, ESCAÑOS_SENADO_UNICO, COL_PARTIDO, COL_VOTOS)
            sim_m = [calcular_dhondt(v, REGLA_MULTIPLE_SENADO.get(k, 1), COL_PARTIDO, COL_VOTOS) for k, v in datos_mult.items()]
            df_sim = pd.concat([sim_u] + sim_m).groupby('Partido')['Escaños'].sum().reset_index()
            pasan_3 = df_sim[df_sim['Escaños'] >= 3]['Partido'].tolist()
            partidos_aptos = list(set(pasan_5) & set(pasan_3))

            # Reparto final: 30 escaños único
            res_u = calcular_dhondt(df_unico[df_unico[COL_PARTIDO].isin(partidos_aptos)], ESCAÑOS_SENADO_UNICO, COL_PARTIDO, COL_VOTOS)

            # Reparto final: 30 escaños múltiple
            res_m = []
            for reg, df_v in datos_mult.items():
                df_f = df_v[df_v[COL_PARTIDO].isin(partidos_aptos)]
                n = REGLA_MULTIPLE_SENADO.get(reg, 1)
                if not df_f.empty:
                    df_r = calcular_dhondt(df_f, n, COL_PARTIDO, COL_VOTOS)
                    df_r['Region'] = reg
                    res_m.append(df_r)

            # Construir matriz
            if res_m:
                matriz_reg = pd.concat(res_m).pivot(index='Region', columns='Partido', values='Escaños').fillna(0).astype(int)
            else:
                matriz_reg = pd.DataFrame()

            fila_mult = matriz_reg.sum().to_frame().T if not matriz_reg.empty else pd.DataFrame()
            if not fila_mult.empty:
                fila_mult.index = ['DISTRITO MULTIPLE (30 escaños)']

            fila_u = res_u.set_index('Partido')['Escaños'].to_frame().T
            fila_u.index = ['DISTRITO UNICO (30 escaños)']

            if not fila_mult.empty:
                total_por_partido = pd.concat([fila_mult, fila_u]).sum().sort_values(ascending=False)
            else:
                total_por_partido = fila_u.sum().sort_values(ascending=False)

            partidos_ord = total_por_partido.index.tolist()

            if not matriz_reg.empty:
                matriz_reg = matriz_reg.reindex(columns=partidos_ord).fillna(0).astype(int)
                fila_mult = fila_mult.reindex(columns=partidos_ord).fillna(0).astype(int)
            fila_u = fila_u.reindex(columns=partidos_ord).fillna(0).astype(int)

            if not matriz_reg.empty:
                cuadro = pd.concat([matriz_reg, fila_mult, fila_u])
            else:
                cuadro = fila_u

            cuadro['TOTAL'] = cuadro.sum(axis=1)

            if not fila_mult.empty:
                cuadro.loc['TOTAL PARTIDO'] = cuadro.loc[['DISTRITO MULTIPLE (30 escaños)', 'DISTRITO UNICO (30 escaños)']].sum()
            else:
                cuadro.loc['TOTAL PARTIDO'] = cuadro.loc['DISTRITO UNICO (30 escaños)']

            total_escaños = int(cuadro.loc['TOTAL PARTIDO', 'TOTAL'])
            df_candidatos = pd.DataFrame()

        # =====================================================
        # LÓGICA: PARLAMENTO ANDINO
        # =====================================================
        else:  # andino
            df_nac = datos.get('nacional', pd.DataFrame())
            total_validos = df_nac[COL_VOTOS].sum()
            partidos_aptos = df_nac[df_nac[COL_VOTOS] >= (total_validos * 0.05)][COL_PARTIDO].tolist()
            df_reparto = df_nac[df_nac[COL_PARTIDO].isin(partidos_aptos)].copy()

            res = calcular_dhondt(df_reparto, ESCAÑOS_ANDINO, COL_PARTIDO, COL_VOTOS)
            res = res.sort_values('Escaños', ascending=False)

            cuadro = res.set_index('Partido').T
            cuadro.index = ['ESCAÑOS']
            cuadro['TOTAL'] = cuadro.sum(axis=1)

            total_escaños = int(cuadro['TOTAL'].iloc[0])
            total_votos = total_validos
            df_candidatos = pd.DataFrame()

        # =====================================================
        # CRUCE CON EXCEL (si aplica)
        # =====================================================
        if uploaded_excel and not df_candidatos.empty and tipo_eleccion == 'diputados':
            try:
                df_maestro = pd.read_excel(uploaded_excel)
                df_maestro.columns = df_maestro.columns.str.strip().str.upper()

                df_candidatos['REGION_KEY'] = df_candidatos['Región'].apply(eliminar_tildes).str.strip()
                df_maestro['REGION_KEY'] = df_maestro['REGION'].apply(eliminar_tildes).str.strip()
                df_candidatos['PARTIDO_KEY'] = df_candidatos['Partido'].apply(eliminar_tildes).str.strip()
                df_maestro['PARTIDO_KEY'] = df_maestro['ORGANIZACION_POLITICA'].apply(eliminar_tildes).str.strip()
                df_candidatos['Candidato/Nro'] = df_candidatos['Candidato/Nro'].astype(str).str.extract(r'(\d+)')
                df_maestro['NUMERO'] = df_maestro['NUMERO'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

                df_maestro_u = df_maestro.drop_duplicates(subset=['REGION_KEY', 'PARTIDO_KEY', 'NUMERO'], keep='first')

                df_merge = pd.merge(
                    df_candidatos,
                    df_maestro_u[['REGION_KEY', 'PARTIDO_KEY', 'NUMERO', 'CANDIDATO']],
                    left_on=['REGION_KEY', 'PARTIDO_KEY', 'Candidato/Nro'],
                    right_on=['REGION_KEY', 'PARTIDO_KEY', 'NUMERO'],
                    how='left'
                )

                df_candidatos = df_merge[['Región', 'Partido', 'Candidato/Nro', 'CANDIDATO', 'Votos Preferenciales']].copy()
                df_candidatos.columns = ['Región', 'Partido', 'N°', 'Nombre del Candidato', 'Votos Preferenciales']
                df_candidatos['Nombre del Candidato'] = df_candidatos['Nombre del Candidato'].fillna('(NO ENCONTRADO)')
            except Exception as e:
                st.warning(f"Error cruzando con Excel: {e}")
                df_candidatos['N°'] = df_candidatos['Candidato/Nro']
                df_candidatos['Nombre del Candidato'] = '(SIN EXCEL)'
                df_candidatos = df_candidatos[['Región', 'Partido', 'N°', 'Nombre del Candidato', 'Votos Preferenciales']]

    # ============================================================
    # MOSTRAR RESULTADOS
    # ============================================================
    st.success(f"Procesamiento completado. {len(archivos_ok)} archivos procesados correctamente.")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Escaños", total_escaños)
    with c2:
        st.metric("Partidos Aptos", len(partidos_aptos))
    with c3:
        if tipo_eleccion == 'diputados':
            st.metric("Regiones", len(datos))
        elif tipo_eleccion == 'senado':
            st.metric("Distritos", len(datos))
        else:
            st.metric("Archivos", len(archivos_ok))
    with c4:
        st.metric("Votos Válidos", f"{total_votos:,.0f}")

    st.markdown("---")

    # TABS: DIPUTADOS
    if tipo_eleccion == 'diputados':
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Escaños por Región", "🏆 Candidatos Electos", "📈 Análisis", "📋 Técnico"])

        with tab1:
            st.subheader("Distribución de Escaños")
            csv_data = cuadro.to_csv().encode('utf-8')
            st.download_button("⬇️ Descargar CSV", csv_data, "diputados_escaños_2026.csv", "text/csv")
            st.dataframe(cuadro, use_container_width=True, height=600)
            st.bar_chart(cuadro.drop('TOTAL NACIONAL').drop('TOTAL REGION', axis=1), height=500)

        with tab2:
            if not df_candidatos.empty:
                st.subheader(f"Candidatos Electos ({len(df_candidatos)})")
                df_cand = df_candidatos.sort_values(['Región', 'Votos Preferenciales'], ascending=[True, False]).reset_index(drop=True)
                df_cand.index = df_cand.index + 1
                csv_cand = df_cand.to_csv().encode('utf-8')
                st.download_button("⬇️ Descargar Listado", csv_cand, "diputados_candidatos_2026.csv", "text/csv")
                st.dataframe(df_cand.style.format({'Votos Preferenciales': '{:,}'}), use_container_width=True, height=600)
            else:
                st.info("No se detectaron candidatos individuales.")

        with tab3:
            st.subheader("Análisis de Vallas")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.markdown("**Valla 5% (Nacional)**")
                df_5 = df_nacional[df_nacional[COL_PARTIDO].isin(pasan_5)].sort_values(COL_VOTOS, ascending=False)
                df_5['%'] = (df_5[COL_VOTOS] / total_votos * 100).round(2)
                st.dataframe(df_5[[COL_PARTIDO, COL_VOTOS, '%']].rename(columns={COL_PARTIDO: 'Partido', COL_VOTOS: 'Votos'}), use_container_width=True)
            with col_a2:
                st.markdown("**Valla 7 Escaños (Distrital)**")
                df_7 = df_sim[df_sim['Partido'].isin(pasan_7)].sort_values('Escaños', ascending=False)
                st.dataframe(df_7, use_container_width=True)
            st.markdown("**Partidos que pasan AMBAS vallas:**")
            for p in sorted(partidos_aptos):
                esc = int(cuadro.loc['TOTAL NACIONAL', p]) if p in cuadro.columns else 0
                st.markdown(f"• **{p}**: {esc} escaños")

        with tab4:
            st.subheader("Resumen Técnico")
            st.markdown(f"""
            **Método:** D'Hondt  
            **Valla:** Doble (5% nacional = {total_votos*0.05:,.0f} votos + 7 escaños distritales)  
            **Partidos en 5%:** {len(pasan_5)}  
            **Partidos en 7:** {len(pasan_7)}  
            **Partidos aptos:** {len(partidos_aptos)}
            """)
            st.subheader("Archivos procesados correctamente")
            for reg, nom, src in archivos_ok:
                st.markdown(f"- **{reg}**: {nom} <span style='color:#999'>({src})</span>", unsafe_allow_html=True)

    # TABS: SENADO
    elif tipo_eleccion == 'senado':
        tab1, tab2, tab3 = st.tabs(["📊 Distribución Senado", "📈 Análisis", "📋 Técnico"])

        with tab1:
            st.subheader("Distribución de Escaños - Senado 2026 (60 total)")
            csv_data = cuadro.to_csv().encode('utf-8')
            st.download_button("⬇️ Descargar CSV", csv_data, "senado_escaños_2026.csv", "text/csv")
            st.dataframe(cuadro, use_container_width=True, height=600)

            # Gráfico de barras por distrito
            st.subheader("Visualización por Distrito")
            df_chart = cuadro.drop('TOTAL PARTIDO', errors='ignore')
            if 'TOTAL' in df_chart.columns:
                df_chart = df_chart[['TOTAL']]
            st.bar_chart(df_chart, height=400)

        with tab2:
            st.subheader("Análisis de Vallas")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.markdown("**Valla 5% (Nacional)**")
                df_5s = votos_nac_df[votos_nac_df[COL_PARTIDO].isin(pasan_5)].sort_values(COL_VOTOS, ascending=False)
                df_5s['%'] = (df_5s[COL_VOTOS] / total_v * 100).round(2)
                st.dataframe(df_5s[[COL_PARTIDO, COL_VOTOS, '%']].rename(columns={COL_PARTIDO: 'Partido', COL_VOTOS: 'Votos'}), use_container_width=True)
            with col_s2:
                st.markdown("**Valla 3 Escaños**")
                df_3s = df_sim[df_sim['Partido'].isin(pasan_3)].sort_values('Escaños', ascending=False)
                st.dataframe(df_3s, use_container_width=True)

            st.markdown("---")
            st.markdown("**Distribución de escaños:**")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.metric("Distrito Único", ESCAÑOS_SENADO_UNICO)
                st.markdown("30 escaños repartidos a nivel nacional")
            with col_d2:
                st.metric("Distrito Múltiple", ESCAÑOS_SENADO_MULTIPLE)
                st.markdown("30 escaños repartidos por regiones")

            st.markdown("---")
            st.markdown("**Partidos aptos:**")
            for p in sorted(partidos_aptos):
                esc = int(cuadro.loc['TOTAL PARTIDO', p]) if p in cuadro.columns else 0
                st.markdown(f"• **{p}**: {esc} escaños")

        with tab3:
            st.subheader("Resumen Técnico")
            st.markdown(f"""
            **Método:** D'Hondt  
            **Distrito Único:** {ESCAÑOS_SENADO_UNICO} escaños  
            **Distrito Múltiple:** {ESCAÑOS_SENADO_MULTIPLE} escaños  
            **Total:** {ESCAÑOS_SENADO_UNICO + ESCAÑOS_SENADO_MULTIPLE} escaños  
            **Valla:** 5% nacional + 3 escaños  
            **Partidos aptos:** {len(partidos_aptos)}
            """)
            st.subheader("Archivos procesados")
            for reg, nom, src in archivos_ok:
                st.markdown(f"- **{reg}**: {nom} <span style='color:#999'>({src})</span>", unsafe_allow_html=True)

            st.subheader("Regiones del Distrito Múltiple")
            df_reg = pd.DataFrame({
                'Región': list(REGLA_MULTIPLE_SENADO.keys()),
                'Escaños': list(REGLA_MULTIPLE_SENADO.values())
            })
            st.dataframe(df_reg, use_container_width=True, height=400)

    # TABS: PARLAMENTO ANDINO
    else:  # andino
        tab1, tab2 = st.tabs(["📊 Escaños Andino", "📋 Técnico"])

        with tab1:
            st.subheader("Distribución - Parlamento Andino 2026")
            csv_data = cuadro.to_csv().encode('utf-8')
            st.download_button("⬇️ Descargar CSV", csv_data, "andino_escaños_2026.csv", "text/csv")
            st.dataframe(cuadro, use_container_width=True, height=400)

            # Gráfico simple
            st.subheader("Visualización")
            df_chart = cuadro.drop('TOTAL', axis=1, errors='ignore')
            st.bar_chart(df_chart.T, height=300)

        with tab2:
            st.subheader("Resumen Técnico")
            st.markdown(f"""
            **Método:** D'Hondt  
            **Escaños:** {ESCAÑOS_ANDINO}  
            **Valla:** 5% nacional ({total_validos*0.05:,.0f} votos)  
            **Partidos aptos:** {len(partidos_aptos)}
            """)
            st.subheader("Archivos procesados")
            for reg, nom, src in archivos_ok:
                st.markdown(f"- {nom} <span style='color:#999'>({src})</span>", unsafe_allow_html=True)

# ============================================================
# ESTADO INICIAL (sin procesar)
# ============================================================
elif procesar and not todos_csvs:
    st.error("Debes subir al menos un archivo CSV, ZIP o RAR.")

else:
    # Estado inicial
    st.markdown("""
    <div class="info-box">
        <h4>👋 Bienvenido al Simulador Electoral Integral Perú 2026</h4>
        <p>Esta aplicación unifica el cálculo de las <b>3 elecciones</b> en una sola plataforma web:</p>
        <ul>
            <li><span class="election-badge badge-diputados">🏛️ DIPUTADOS</span> 130 escaños · D'Hondt · Doble valla</li>
            <li><span class="election-badge badge-senado">⚖️ SENADO</span> 60 escaños · 30 Único + 30 Múltiple</li>
            <li><span class="election-badge badge-andino">🌎 PARLAMENTO ANDINO</span> 5 escaños · Circunscripción única</li>
        </ul>
        <p><b>📦 Novedad:</b> Ahora puedes subir tus archivos en <b>ZIP o RAR</b>.</p>
        <p><b>Para Senado:</b> Se requieren <b>2 archivos separados</b> (Unico y Multiple).</p>
        <p><b>Para comenzar:</b> Selecciona la elección en el panel izquierdo, sube tus archivos y presiona <b>🚀 PROCESAR</b>.</p>
    </div>
    """, unsafe_allow_html=True)

    # Referencias
    col_ref1, col_ref2, col_ref3 = st.columns(3)
    with col_ref1:
        st.subheader("🏛️ Diputados")
        df_ref = pd.DataFrame({'Región': list(ESCAÑOS_DIPUTADOS_2026.keys()), 'Escaños': list(ESCAÑOS_DIPUTADOS_2026.values())})
        st.dataframe(df_ref.sort_values('Escaños', ascending=False).reset_index(drop=True), use_container_width=True, height=300)
    with col_ref2:
        st.subheader("⚖️ Senado")
        st.markdown(f"""
        • **Distrito Único:** {ESCAÑOS_SENADO_UNICO} escaños  
        • **Distrito Múltiple:** {ESCAÑOS_SENADO_MULTIPLE} escaños  
        • **Total:** {ESCAÑOS_SENADO_UNICO + ESCAÑOS_SENADO_MULTIPLE} escaños
        """)
        st.markdown("**Distrito Múltiple por región:**")
        for k, v in REGLA_MULTIPLE_SENADO.items():
            st.markdown(f"  - {k}: {v}")
    with col_ref3:
        st.subheader("🌎 Andino")
        st.markdown(f"""
        • **Escaños:** {ESCAÑOS_ANDINO}  
        • **Valla:** 5% nacional  
        • **Método:** D'Hondt simple
        """)

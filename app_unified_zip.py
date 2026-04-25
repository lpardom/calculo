import streamlit as st
import pandas as pd
import unicodedata
import io
import zipfile
import os
import gc
from pathlib import Path

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
    .main-header { font-size: 2.2rem; font-weight: bold; color: #D91023; text-align: center; }
    .sub-header { font-size: 1.1rem; color: #555; text-align: center; margin-bottom: 1.5rem; }
    .election-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: bold; margin: 2px; }
    .badge-diputados { background: #1f4e79; color: white; }
    .badge-senado { background: #D91023; color: white; }
    .badge-andino { background: #28a745; color: white; }
    .info-box { background-color: #f8f9fa; border-left: 4px solid #D91023; padding: 1rem; margin: 1rem 0; border-radius: 0 8px 8px 0; }
    .success-box { background-color: #e8f8e8; border-left: 4px solid #28a745; padding: 1rem; margin: 1rem 0; border-radius: 0 8px 8px 0; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; border-radius: 4px 4px 0 0; padding: 10px 20px; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #D91023 !important; color: white !important; }
    .dataframe th { background-color: #D91023; color: white; font-weight: bold; text-align: center; }
    .dataframe td { text-align: center; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONFIGURACIONES
# ============================================================
ESCAÑOS_DIPUTADOS_2026 = {
    'AMAZONAS': 2, 'ANCASH': 5, 'APURIMAC': 2, 'AREQUIPA': 6, 'AYACUCHO': 3,
    'CAJAMARCA': 6, 'CALLAO': 4, 'CUSCO': 5, 'HUANCAVELICA': 2, 'HUANUCO': 3,
    'ICA': 4, 'JUNIN': 5, 'LA LIBERTAD': 7, 'LAMBAYEQUE': 5, 'LIMA METROPOLITANA': 32,
    'LIMA PROVINCIAS': 4, 'RESIDENTES EN EL EXTRANJERO': 2, 'LORETO': 4,
    'MADRE DE DIOS': 2, 'MOQUEGUA': 2, 'PASCO': 2, 'PIURA': 7, 'PUNO': 5,
    'SAN MARTIN': 4, 'TACNA': 2, 'TUMBES': 2, 'UCAYALI': 3
}

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
# RUTAS DE ARCHIVOS PRECARGADOS (configura según tu repo)
# ============================================================
# Estas rutas son relativas al directorio de la app en Streamlit Cloud
RUTAS_PRECARGADAS = {
    'diputados': {
        'zip': 'data/diputados_2026.zip',  # Ruta relativa en el repo
        'descripcion': 'Diputados - 130 escaños (27 regiones)'
    },
    'senado_unico': {
        'zip': 'data/senado_unico_2026.zip',
        'descripcion': 'Senado Distrito Unico - 30 escaños'
    },
    'senado_multiple': {
        'zip': 'data/senado_multiple_2026.zip',
        'descripcion': 'Senado Distrito Multiple - 30 escaños (regiones)'
    },
    'andino': {
        'zip': 'data/andino_2026.zip',
        'descripcion': 'Parlamento Andino - 5 escaños'
    }
}

# ============================================================
# FUNCIONES UTILITARIAS
# ============================================================
def eliminar_tildes(texto):
    if not isinstance(texto, str): return texto
    texto = unicodedata.normalize('NFD', texto)
    return texto.encode('ascii', 'ignore').decode("utf-8").upper()

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
    del df_cocientes, top_escaños, listado_cocientes
    gc.collect()
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

def extraer_csvs_de_zip_path(zip_path):
    """Extrae CSVs desde una ruta de archivo ZIP local"""
    csv_files = []
    try:
        if not os.path.exists(zip_path):
            st.error(f"Archivo no encontrado: {zip_path}")
            return csv_files

        with zipfile.ZipFile(zip_path) as z:
            for name in z.namelist():
                if name.lower().endswith('.csv') and not name.startswith('__') and not name.startswith('.'):
                    with z.open(name) as f:
                        content = f.read()
                        csv_files.append({
                            'name': os.path.basename(name),
                            'content': io.BytesIO(content),
                            'source': f"ZIP: {os.path.basename(zip_path)}"
                        })
    except Exception as e:
        st.error(f"Error leyendo {zip_path}: {str(e)}")
    return csv_files

def procesar_csvs(csv_list, tipo_eleccion):
    """Procesa lista de CSVs según el tipo de elección"""
    datos = {}
    votos_nacionales = []
    archivos_ok = []
    archivos_error = []

    for csv_info in csv_list:
        nombre = csv_info['name']
        distrito = csv_info.get('distrito', 'auto')
        try:
            csv_info['content'].seek(0)
            # Leer solo columnas necesarias
            df = pd.read_csv(csv_info['content'], low_memory=False, dtype=str, 
                           usecols=lambda col: col in [COL_PARTIDO, COL_VOTOS] or col.isdigit() or 'CANDIDATO' in col.upper())
            df.columns = df.columns.str.strip()

            if COL_PARTIDO not in df.columns or COL_VOTOS not in df.columns:
                archivos_error.append(f"{nombre}: Columnas requeridas no encontradas")
                continue

            # Procesar solo columnas necesarias
            df = df[[COL_PARTIDO, COL_VOTOS]].copy()
            df[COL_VOTOS] = pd.to_numeric(df[COL_VOTOS], errors='coerce').fillna(0)

            # Agregar a datos acumulados (sin crear copias)
            if tipo_eleccion == 'diputados':
                region = detectar_region(nombre, ESCAÑOS_DIPUTADOS_2026)
                if region and region in ESCAÑOS_DIPUTADOS_2026:
                    if region not in datos:
                        datos[region] = df.groupby(COL_PARTIDO)[COL_VOTOS].sum()
                    else:
                        datos[region] = datos[region].add(df.groupby(COL_PARTIDO)[COL_VOTOS].sum(), fill_value=0)
                    votos_nacionales.append(df.groupby(COL_PARTIDO)[COL_VOTOS].sum())
                    archivos_ok.append((region, nombre, csv_info.get('source', 'individual')))
                else:
                    archivos_error.append(f"{nombre}: Region no detectada")

            elif tipo_eleccion == 'senado':
                if distrito == 'unico':
                    if 'unico' not in datos:
                        datos['unico'] = df.groupby(COL_PARTIDO)[COL_VOTOS].sum()
                    else:
                        datos['unico'] = datos['unico'].add(df.groupby(COL_PARTIDO)[COL_VOTOS].sum(), fill_value=0)
                    votos_nacionales.append(df.groupby(COL_PARTIDO)[COL_VOTOS].sum())
                    archivos_ok.append(('DISTRITO UNICO', nombre, csv_info.get('source', 'individual')))
                elif distrito == 'multiple':
                    region = detectar_region(nombre, REGLA_MULTIPLE_SENADO)
                    if region and region in REGLA_MULTIPLE_SENADO:
                        if region not in datos:
                            datos[region] = df.groupby(COL_PARTIDO)[COL_VOTOS].sum()
                        else:
                            datos[region] = datos[region].add(df.groupby(COL_PARTIDO)[COL_VOTOS].sum(), fill_value=0)
                        votos_nacionales.append(df.groupby(COL_PARTIDO)[COL_VOTOS].sum())
                        archivos_ok.append((region, nombre, csv_info.get('source', 'individual')))
                    else:
                        archivos_error.append(f"{nombre}: Region no detectada")
                else:
                    nombre_norm = eliminar_tildes(nombre)
                    if 'UNICO' in nombre_norm or 'UNICO' in nombre_norm:
                        if 'unico' not in datos:
                            datos['unico'] = df.groupby(COL_PARTIDO)[COL_VOTOS].sum()
                        else:
                            datos['unico'] = datos['unico'].add(df.groupby(COL_PARTIDO)[COL_VOTOS].sum(), fill_value=0)
                        votos_nacionales.append(df.groupby(COL_PARTIDO)[COL_VOTOS].sum())
                        archivos_ok.append(('DISTRITO UNICO', nombre, csv_info.get('source', 'individual')))
                    else:
                        region = detectar_region(nombre, REGLA_MULTIPLE_SENADO)
                        if region and region in REGLA_MULTIPLE_SENADO:
                            if region not in datos:
                                datos[region] = df.groupby(COL_PARTIDO)[COL_VOTOS].sum()
                            else:
                                datos[region] = datos[region].add(df.groupby(COL_PARTIDO)[COL_VOTOS].sum(), fill_value=0)
                            votos_nacionales.append(df.groupby(COL_PARTIDO)[COL_VOTOS].sum())
                            archivos_ok.append((region, nombre, csv_info.get('source', 'individual')))
                        else:
                            archivos_error.append(f"{nombre}: Distrito no detectado")

            elif tipo_eleccion == 'andino':
                votos_nacionales.append(df.groupby(COL_PARTIDO)[COL_VOTOS].sum())
                archivos_ok.append(('NACIONAL', nombre, csv_info.get('source', 'individual')))

            # Liberar memoria INMEDIATAMENTE
            del df
            gc.collect()

        except Exception as e:
            archivos_error.append(f"{nombre}: {str(e)}")

    # Consolidar para Andino
    if tipo_eleccion == 'andino' and votos_nacionales:
        datos['nacional'] = pd.concat(votos_nacionales).groupby(level=0).sum()

    return datos, votos_nacionales, archivos_ok, archivos_error

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("<h1 style='text-align:center; color:#D91023;'>🇵🇪 PERÚ 2026</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#666;'>Simulador Electoral Integral</p>", unsafe_allow_html=True)
    st.markdown("---")

    st.subheader("🗳️ Tipo de Elección")
    tipo_eleccion = st.radio("Selecciona:",
        options=[("diputados", "🏛️ Diputados (130 escaños)"), ("senado", "⚖️ Senado (60 escaños)"), ("andino", "🌎 Parlamento Andino (5 escaños)")],
        format_func=lambda x: x[1], index=0)[0]

    st.markdown("---")
    st.subheader("📁 Configuración de Precarga")

    # Mostrar estado de archivos precargados
    st.markdown("**Archivos en el repositorio:**")
    for key, info in RUTAS_PRECARGADAS.items():
        existe = os.path.exists(info['zip'])
        icon = "✅" if existe else "❌"
        st.markdown(f"{icon} `{info['zip']}`")

    st.markdown("---")
    st.caption("v7.0 - Precarga desde repositorio")

# ============================================================
# HEADER
# ============================================================
st.markdown('<div class="main-header">🇵🇪 Simulador Electoral Perú 2026</div>', unsafe_allow_html=True)

if tipo_eleccion == 'diputados':
    st.markdown('<div class="sub-header"><span class="election-badge badge-diputados">🏛️ DIPUTADOS</span> 130 Escaños · Doble Valla Electoral · DHondt</div>', unsafe_allow_html=True)
elif tipo_eleccion == 'senado':
    st.markdown('<div class="sub-header"><span class="election-badge badge-senado">⚖️ SENADO</span> 60 Escaños · 30 Unico + 30 Multiple</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="sub-header"><span class="election-badge badge-andino">🌎 PARLAMENTO ANDINO</span> 5 Escaños · Circunscripción Única</div>', unsafe_allow_html=True)

# ============================================================
# CARGA AUTOMÁTICA DE ARCHIVOS PRECARGADOS
# ============================================================
if tipo_eleccion == 'senado':
    # Senado necesita 2 archivos
    zip_unico = RUTAS_PRECARGADAS['senado_unico']['zip']
    zip_multiple = RUTAS_PRECARGADAS['senado_multiple']['zip']

    if not os.path.exists(zip_unico) or not os.path.exists(zip_multiple):
        st.error("❌ Archivos precargados no encontrados. Verifica las rutas en el repositorio.")
        st.info("""
        **Estructura esperada en tu repo:**
        ```
        tu-repo/
        ├── app.py
        └── data/
            ├── senado_unico_2026.zip
            └── senado_multiple_2026.zip
        ```
        """)
        st.stop()

    st.info("📦 Cargando archivos precargados del Senado...")
    csvs_unico = extraer_csvs_de_zip_path(zip_unico)
    for c in csvs_unico: c['distrito'] = 'unico'

    csvs_multiple = extraer_csvs_de_zip_path(zip_multiple)
    for c in csvs_multiple: c['distrito'] = 'multiple'

    todos_csvs = csvs_unico + csvs_multiple

else:
    # Diputados o Andino - 1 archivo
    zip_key = 'diputados' if tipo_eleccion == 'diputados' else 'andino'
    zip_path = RUTAS_PRECARGADAS[zip_key]['zip']

    if not os.path.exists(zip_path):
        st.error(f"❌ Archivo precargado no encontrado: `{zip_path}`")
        st.info("""
        **Estructura esperada en tu repo:**
        ```
        tu-repo/
        ├── app.py
        └── data/
            └── diputados_2026.zip  (o andino_2026.zip)
        ```
        """)
        st.stop()

    st.info(f"📦 Cargando archivo precargado: `{zip_path}`...")
    todos_csvs = extraer_csvs_de_zip_path(zip_path)

# Mostrar archivos cargados
if todos_csvs:
    st.success(f"✅ {len(todos_csvs)} archivos CSV cargados desde ZIP precargado")
    with st.expander(f"📂 Archivos cargados ({len(todos_csvs)})"):
        for c in todos_csvs:
            st.markdown(f"• {c['name']}")
else:
    st.error("No se pudieron cargar archivos del ZIP precargado.")
    st.stop()

# ============================================================
# PROCESAMIENTO AUTOMÁTICO
# ============================================================
with st.spinner("⏳ Procesando elecciones..."):
    datos, votos_nac, archivos_ok, archivos_error = procesar_csvs(todos_csvs, tipo_eleccion)

    if archivos_error:
        with st.expander(f"⚠️ Errores ({len(archivos_error)})"):
            for err in archivos_error:
                st.markdown(f"- {err}")

    if not datos:
        st.error("No se pudieron procesar archivos válidos.")
        st.stop()

    st.success(f"✅ {len(archivos_ok)} archivos procesados correctamente.")

    # =====================================================
    # CÁLCULOS ELECTORALES
    # =====================================================

    if tipo_eleccion == 'diputados':
        # Valla doble
        df_nacional = pd.concat(votos_nac).groupby(level=0).sum().reset_index()
        df_nacional.columns = [COL_PARTIDO, COL_VOTOS]
        total_votos = df_nacional[COL_VOTOS].sum()
        pasan_5 = df_nacional[df_nacional[COL_VOTOS] >= (total_votos * 0.05)][COL_PARTIDO].tolist()

        # Simulación para valla 7
        escaños_sim = []
        for region, series in datos.items():
            n = ESCAÑOS_DIPUTADOS_2026.get(region, 0)
            if n > 0:
                df_temp = series.reset_index()
                df_temp.columns = [COL_PARTIDO, COL_VOTOS]
                escaños_sim.append(calcular_dhondt(df_temp, n, COL_PARTIDO, COL_VOTOS))

        df_sim = pd.concat(escaños_sim).groupby('Partido')['Escaños'].sum().reset_index()
        pasan_7 = df_sim[df_sim['Escaños'] >= 7]['Partido'].tolist()
        partidos_aptos = list(set(pasan_5) & set(pasan_7))

        # Reparto final
        resultados = []
        for region, series in datos.items():
            n_esc = ESCAÑOS_DIPUTADOS_2026.get(region, 0)
            df_temp = series.reset_index()
            df_temp.columns = [COL_PARTIDO, COL_VOTOS]
            df_f = df_temp[df_temp[COL_PARTIDO].isin(partidos_aptos)].copy()
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
        for region in datos.keys():
            res_reg = df_final[df_final['Region'] == region]
            if res_reg.empty: continue

            archivos_reg = [c for c in todos_csvs if eliminar_tildes(c['name']).find(eliminar_tildes(region)) != -1]
            if archivos_reg:
                votos_partidos = {}
                for c in archivos_reg:
                    c['content'].seek(0)
                    df_temp = pd.read_csv(c['content'], low_memory=False, dtype=str,
                                        usecols=lambda col: col in [COL_PARTIDO] or col.isdigit() or 'CANDIDATO' in col.upper())
                    df_temp.columns = df_temp.columns.str.strip()

                    for _, fp in res_reg.iterrows():
                        partido = fp['Partido']
                        num_esc = int(fp['Escaños'])
                        if num_esc > 0:
                            if partido not in votos_partidos:
                                votos_partidos[partido] = {}

                            df_p = df_temp[df_temp[COL_PARTIDO] == partido]
                            cols_cands = [col for col in df_temp.columns if col != COL_PARTIDO and (col.isdigit() or 'CANDIDATO' in col.upper())]

                            for col in cols_cands:
                                if col not in votos_partidos[partido]:
                                    votos_partidos[partido][col] = 0
                                votos_partidos[partido][col] += pd.to_numeric(df_p[col], errors='coerce').sum()

                    del df_temp
                    gc.collect()

                for partido, votos_cands in votos_partidos.items():
                    num_esc = int(res_reg[res_reg['Partido'] == partido]['Escaños'].iloc[0])
                    if num_esc > 0:
                        sorted_cands = sorted(votos_cands.items(), key=lambda x: x[1], reverse=True)[:num_esc]
                        for cand, votos in sorted_cands:
                            candidatos.append({'Región': region, 'Partido': partido, 'Candidato/Nro': cand, 'Votos Preferenciales': int(votos)})

        df_candidatos = pd.DataFrame(candidatos)

        del df_nacional, df_sim, df_final, resultados
        gc.collect()

    elif tipo_eleccion == 'senado':
        df_unico = datos.get('unico', pd.Series())
        if not df_unico.empty:
            df_unico = df_unico.reset_index()
            df_unico.columns = [COL_PARTIDO, COL_VOTOS]

        datos_mult = {k: v.reset_index().rename(columns={0: COL_PARTIDO, 1: COL_VOTOS}) for k, v in datos.items() if k != 'unico'}

        if df_unico.empty:
            st.error("No se encontraron datos del Distrito Unico.")
            st.stop()
        if not datos_mult:
            st.error("No se encontraron datos del Distrito Multiple.")
            st.stop()

        votos_nac_df = pd.concat(votos_nac).groupby(level=0).sum().reset_index()
        votos_nac_df.columns = [COL_PARTIDO, COL_VOTOS]
        total_v = votos_nac_df[COL_VOTOS].sum()
        pasan_5 = votos_nac_df[votos_nac_df[COL_VOTOS] >= (total_v * 0.05)][COL_PARTIDO].tolist()

        sim_u = calcular_dhondt(df_unico, ESCAÑOS_SENADO_UNICO, COL_PARTIDO, COL_VOTOS)
        sim_m = [calcular_dhondt(v, REGLA_MULTIPLE_SENADO.get(k, 1), COL_PARTIDO, COL_VOTOS) for k, v in datos_mult.items()]
        df_sim = pd.concat([sim_u] + sim_m).groupby('Partido')['Escaños'].sum().reset_index()
        pasan_3 = df_sim[df_sim['Escaños'] >= 3]['Partido'].tolist()
        partidos_aptos = list(set(pasan_5) & set(pasan_3))

        res_u = calcular_dhondt(df_unico[df_unico[COL_PARTIDO].isin(partidos_aptos)], ESCAÑOS_SENADO_UNICO, COL_PARTIDO, COL_VOTOS)

        res_m = []
        for reg, df_v in datos_mult.items():
            df_f = df_v[df_v[COL_PARTIDO].isin(partidos_aptos)]
            n = REGLA_MULTIPLE_SENADO.get(reg, 1)
            if not df_f.empty:
                df_r = calcular_dhondt(df_f, n, COL_PARTIDO, COL_VOTOS)
                df_r['Region'] = reg
                res_m.append(df_r)

        if res_m:
            matriz_reg = pd.concat(res_m).pivot(index='Region', columns='Partido', values='Escaños').fillna(0).astype(int)
            fila_mult = matriz_reg.sum().to_frame().T
            fila_mult.index = ['DISTRITO MULTIPLE (30 escaños)']
        else:
            matriz_reg = pd.DataFrame()
            fila_mult = pd.DataFrame()

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

        del votos_nac_df, sim_u, sim_m, df_sim, res_u, res_m
        gc.collect()

    else:  # andino
        df_nac = datos.get('nacional', pd.Series())
        total_validos = df_nac.sum()
        partidos_aptos = df_nac[df_nac >= (total_validos * 0.05)].index.tolist()
        df_reparto = df_nac[df_nac.index.isin(partidos_aptos)].reset_index()
        df_reparto.columns = [COL_PARTIDO, COL_VOTOS]

        res = calcular_dhondt(df_reparto, ESCAÑOS_ANDINO, COL_PARTIDO, COL_VOTOS)
        res = res.sort_values('Escaños', ascending=False)

        cuadro = res.set_index('Partido').T
        cuadro.index = ['ESCAÑOS']
        cuadro['TOTAL'] = cuadro.sum(axis=1)

        total_escaños = int(cuadro['TOTAL'].iloc[0])
        total_votos = total_validos
        df_candidatos = pd.DataFrame()

        del df_nac, df_reparto, res
        gc.collect()

# ============================================================
# MOSTRAR RESULTADOS (SIEMPRE VISIBLE)
# ============================================================
if 'cuadro' in locals() and datos:
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total Escaños", total_escaños)
    with c2: st.metric("Partidos Aptos", len(partidos_aptos))
    with c3: st.metric("Regiones" if tipo_eleccion == 'diputados' else "Distritos" if tipo_eleccion == 'senado' else "Archivos", len(datos))
    with c4: st.metric("Votos Válidos", f"{total_votos:,.0f}")

    st.markdown("---")

    # TABS
    if tipo_eleccion == 'diputados':
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Escaños por Región", "🏆 Candidatos Electos", "📈 Análisis", "📋 Técnico"])

        with tab1:
            st.subheader("Distribución de Escaños")
            csv_data = cuadro.to_csv().encode('utf-8')
            st.download_button("⬇️ Descargar CSV", csv_data, "diputados_escaños_2026.csv", "text/csv")
            st.dataframe(cuadro, use_container_width=True, height=600)
            st.bar_chart(cuadro.drop('TOTAL NACIONAL', errors='ignore').drop('TOTAL REGION', axis=1, errors='ignore'), height=500)

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
                df_nac_temp = pd.concat(votos_nac).groupby(level=0).sum().reset_index()
                df_nac_temp.columns = [COL_PARTIDO, COL_VOTOS]
                total_v_temp = df_nac_temp[COL_VOTOS].sum()
                p5 = df_nac_temp[df_nac_temp[COL_VOTOS] >= (total_v_temp * 0.05)][COL_PARTIDO].tolist()
                df_5 = df_nac_temp[df_nac_temp[COL_PARTIDO].isin(p5)].sort_values(COL_VOTOS, ascending=False)
                df_5['%'] = (df_5[COL_VOTOS] / total_v_temp * 100).round(2)
                st.dataframe(df_5[[COL_PARTIDO, COL_VOTOS, '%']].rename(columns={COL_PARTIDO: 'Partido', COL_VOTOS: 'Votos'}), use_container_width=True)
                del df_nac_temp
            with col_a2:
                st.markdown("**Valla 7 Escaños (Distrital)**")
                st.dataframe(pd.DataFrame({'Partido': partidos_aptos, 'Escaños': [int(cuadro.loc['TOTAL NACIONAL', p]) if p in cuadro.columns else 0 for p in partidos_aptos]}), use_container_width=True)
            st.markdown("**Partidos que pasan AMBAS vallas:**")
            for p in sorted(partidos_aptos):
                esc = int(cuadro.loc['TOTAL NACIONAL', p]) if p in cuadro.columns else 0
                st.markdown(f"• **{p}**: {esc} escaños")

        with tab4:
            st.subheader("Resumen Técnico")
            st.markdown(f"""
            **Metodo:** DHondt  
            **Valla:** Doble (5% nacional + 7 escaños distritales)  
            **Partidos aptos:** {len(partidos_aptos)}
            """)
            st.subheader("Archivos procesados")
            for reg, nom, src in archivos_ok:
                st.markdown(f"- **{reg}**: {nom} ({src})")

    elif tipo_eleccion == 'senado':
        tab1, tab2, tab3 = st.tabs(["📊 Distribución Senado", "📈 Análisis", "📋 Técnico"])

        with tab1:
            st.subheader("Distribución de Escaños - Senado 2026 (60 total)")
            csv_data = cuadro.to_csv().encode('utf-8')
            st.download_button("⬇️ Descargar CSV", csv_data, "senado_escaños_2026.csv", "text/csv")
            st.dataframe(cuadro, use_container_width=True, height=600)

        with tab2:
            st.subheader("Análisis de Vallas")
            st.markdown("**Partidos aptos:**")
            for p in sorted(partidos_aptos):
                esc = int(cuadro.loc['TOTAL PARTIDO', p]) if p in cuadro.columns else 0
                st.markdown(f"• **{p}**: {esc} escaños")

        with tab3:
            st.subheader("Resumen Técnico")
            st.markdown(f"""
            **Metodo:** DHondt  
            **Distrito Unico:** {ESCAÑOS_SENADO_UNICO} escaños  
            **Distrito Multiple:** {ESCAÑOS_SENADO_MULTIPLE} escaños  
            **Total:** {ESCAÑOS_SENADO_UNICO + ESCAÑOS_SENADO_MULTIPLE} escaños
            """)
            st.subheader("Archivos procesados")
            for reg, nom, src in archivos_ok:
                st.markdown(f"- **{reg}**: {nom} ({src})")

    else:  # andino
        tab1, tab2 = st.tabs(["📊 Escaños Andino", "📋 Técnico"])

        with tab1:
            st.subheader("Distribución - Parlamento Andino 2026")
            csv_data = cuadro.to_csv().encode('utf-8')
            st.download_button("⬇️ Descargar CSV", csv_data, "andino_escaños_2026.csv", "text/csv")
            st.dataframe(cuadro, use_container_width=True, height=400)

        with tab2:
            st.subheader("Resumen Técnico")
            st.markdown(f"""
            **Metodo:** DHondt  
            **Escaños:** {ESCAÑOS_ANDINO}  
            **Valla:** 5% nacional  
            **Partidos aptos:** {len(partidos_aptos)}
            """)
            st.subheader("Archivos procesados")
            for reg, nom, src in archivos_ok:
                st.markdown(f"- {nom} ({src})")

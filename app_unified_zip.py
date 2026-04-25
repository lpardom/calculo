import streamlit as st
import pandas as pd
import numpy as np
import unicodedata
import io
import zipfile
import os
import gc
import glob
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

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
# CSS PROFESIONAL
# ============================================================
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: 700; color: #1a1a2e; text-align: center; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.1rem; color: #64748b; text-align: center; margin-bottom: 2rem; font-weight: 400; }
    .election-badge { display: inline-block; padding: 6px 16px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; margin: 2px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .badge-diputados { background: linear-gradient(135deg, #1e40af, #3b82f6); color: white; }
    .badge-senado { background: linear-gradient(135deg, #991b1b, #ef4444); color: white; }
    .badge-andino { background: linear-gradient(135deg, #065f46, #10b981); color: white; }
    .card { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; margin-bottom: 1rem; }
    .card-title { font-size: 0.875rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card-value { font-size: 2rem; font-weight: 700; color: #1e293b; }
    .info-box { background: linear-gradient(135deg, #f0f9ff, #e0f2fe); border-left: 4px solid #0ea5e9; padding: 1.25rem; margin: 1rem 0; border-radius: 0 12px 12px 0; }
    .success-box { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border-left: 4px solid #22c55e; padding: 1.25rem; margin: 1rem 0; border-radius: 0 12px 12px 0; }
    .warning-box { background: linear-gradient(135deg, #fefce8, #fef9c3); border-left: 4px solid #eab308; padding: 1.25rem; margin: 1rem 0; border-radius: 0 12px 12px 0; }
    .error-box { background: linear-gradient(135deg, #fef2f2, #fee2e2); border-left: 4px solid #ef4444; padding: 1.25rem; margin: 1rem 0; border-radius: 0 12px 12px 0; }
    .stTabs [data-baseweb="tab-list"] { gap: 12px; }
    .stTabs [data-baseweb="tab"] { background-color: #f1f5f9; border-radius: 8px 8px 0 0; padding: 12px 24px; font-weight: 600; color: #64748b; border: none; }
    .stTabs [aria-selected="true"] { background: linear-gradient(135deg, #1e40af, #3b82f6) !important; color: white !important; box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3); }
    .dataframe th { background: linear-gradient(135deg, #1e40af, #3b82f6); color: white; font-weight: 600; text-align: center; padding: 12px; }
    .dataframe td { text-align: center; padding: 10px; border-bottom: 1px solid #e2e8f0; }
    .dataframe tr:hover td { background-color: #f8fafc; }
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

EXCLUIR = [
    'VOTOS EN BLANCO', 'VOTOS NULOS',
    'VOTOS EN BLANCO ', 'VOTOS NULOS ',
    ' VOTOS EN BLANCO', ' VOTOS NULOS',
    'VOTOS EN BLANCO  ', 'VOTOS NULOS  '
]

COL_PARTIDO = 'ORGANIZACION POLÍTICA'
COL_VOTOS = 'CANTIDAD DE VOTOS'

# ============================================================
# FUNCIONES UTILITARIAS
# ============================================================
def eliminar_tildes(texto):
    if not isinstance(texto, str): 
        return str(texto) if texto is not None else ""
    texto = unicodedata.normalize('NFD', texto)
    return texto.encode('ascii', 'ignore').decode("utf-8").upper().strip()

def calcular_dhondt(df_votos, num_escaños, col_partido, col_votos):
    if num_escaños <= 0 or df_votos.empty:
        return pd.DataFrame(columns=['Partido', 'Escaños'])
    df_votos = df_votos.copy()
    df_votos[col_votos] = pd.to_numeric(df_votos[col_votos], errors='coerce').fillna(0)
    # Filtrar partidos sin votos
    df_votos = df_votos[df_votos[col_votos] > 0]
    if df_votos.empty:
        return pd.DataFrame(columns=['Partido', 'Escaños'])

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
    # Buscar coincidencia exacta primero
    for r in diccionario_regiones.keys():
        if eliminar_tildes(r) in nombre_normalizado:
            return r
    # Fallback: extraer de nombre de archivo tipo PR-ESP_XXX_Region_...
    partes = Path(nombre_archivo).stem.split('_')
    if len(partes) >= 3:
        posible = eliminar_tildes(partes[2])
        for r in diccionario_regiones.keys():
            if eliminar_tildes(r) in posible or posible in eliminar_tildes(r):
                return r
    return None

def extraer_csvs_de_zip_path(zip_path):
    csv_files = []
    try:
        if not os.path.exists(zip_path):
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

def extraer_csvs_de_carpeta(carpeta_path):
    csv_files = []
    try:
        if not os.path.exists(carpeta_path):
            return csv_files
        for archivo in os.listdir(carpeta_path):
            if archivo.lower().endswith('.csv'):
                ruta_completa = os.path.join(carpeta_path, archivo)
                with open(ruta_completa, 'rb') as f:
                    content = f.read()
                    csv_files.append({
                        'name': archivo,
                        'content': io.BytesIO(content),
                        'source': f"Carpeta: {os.path.basename(carpeta_path)}"
                    })
    except Exception as e:
        st.error(f"Error leyendo carpeta {carpeta_path}: {str(e)}")
    return csv_files

def _buscar_archivo_glob(directorio, patron_con_tilde):
    """
    Busca archivos/carpetas usando glob pero normalizando tildes.
    Prueba primero el patrón original, luego sin tildes.
    """
    # Patrón original
    matches = glob.glob(os.path.join(directorio, patron_con_tilde))
    if matches:
        return max(matches, key=os.path.getmtime)

    # Patrón sin tildes
    patron_sin_tilde = eliminar_tildes(patron_con_tilde)
    # glob no soporta regex complejo, así que listamos todo y filtramos
    try:
        todos = os.listdir(directorio)
    except OSError:
        return None

    candidatos = []
    for nombre in todos:
        nombre_sin_tilde = eliminar_tildes(nombre)
        # Convertimos el patrón glob a una comparación simple
        # Reemplazamos * por comodín manual
        partes = patron_sin_tilde.split('*')
        if all(p in nombre_sin_tilde for p in partes if p):
            candidatos.append(os.path.join(directorio, nombre))

    if candidatos:
        return max(candidatos, key=os.path.getmtime)
    return None

def detectar_archivos_locales(tipo_eleccion):
    archivos_encontrados = {}
    directorios_busqueda = ['.', 'data', 'archivos', 'input']

    if tipo_eleccion == 'diputados':
        patrones = ['diputados']
    elif tipo_eleccion == 'senado':
        patrones = ['senado_unico', 'senado_multiple']
    else:
        patrones = ['andino']

    for patron_key in patrones:
        encontrado = False
        for directorio in directorios_busqueda:
            if not os.path.exists(directorio):
                continue

            # Patrones con tildes para búsqueda flexible
            if patron_key == 'senado_unico':
                zip_patron = 'PR-ESP_Senadores*Unico*.zip'
                carpeta_patron = 'PR-ESP_Senadores*Unico*'
            elif patron_key == 'senado_multiple':
                zip_patron = 'PR-ESP_Senadores*Multiple*.zip'
                carpeta_patron = 'PR-ESP_Senadores*Multiple*'
            elif patron_key == 'diputados':
                zip_patron = 'PR-ESP_Diputados_*.zip'
                carpeta_patron = 'PR-ESP_Diputados_*'
            else:  # andino
                zip_patron = 'PR-ESP_Parlamento*Andino*.zip'
                carpeta_patron = 'PR-ESP_Parlamento*Andino*'

            # Buscar ZIP
            zip_path = _buscar_archivo_glob(directorio, zip_patron)
            if zip_path and os.path.isfile(zip_path):
                archivos_encontrados[patron_key] = {'tipo': 'zip', 'ruta': zip_path}
                encontrado = True
                break

            # Buscar Carpeta
            carpeta_path = _buscar_archivo_glob(directorio, carpeta_patron)
            if carpeta_path and os.path.isdir(carpeta_path):
                archivos_encontrados[patron_key] = {'tipo': 'carpeta', 'ruta': carpeta_path}
                encontrado = True
                break

        if not encontrado:
            archivos_encontrados[patron_key] = None

    return archivos_encontrados

# ============================================================
# PROCESAMIENTO CON EXCLUSIÓN CORRECTA DE BLANCOS/NULOS
# ============================================================
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
            df = pd.read_csv(csv_info['content'], low_memory=False, dtype=str)
            df.columns = df.columns.str.strip()

            if COL_PARTIDO not in df.columns or COL_VOTOS not in df.columns:
                archivos_error.append(f"{nombre}: Columnas requeridas no encontradas")
                continue

            # LIMPIAR ESPACIOS EN ORGANIZACION POLITICA
            df[COL_PARTIDO] = df[COL_PARTIDO].str.strip()

            # EXCLUIR BLANCOS Y NULOS
            df_filtrado = df[~df[COL_PARTIDO].isin(EXCLUIR)].copy()

            if df_filtrado.empty:
                archivos_error.append(f"{nombre}: Solo contiene votos en blanco/nulos")
                continue

            df_filtrado[COL_VOTOS] = pd.to_numeric(df_filtrado[COL_VOTOS], errors='coerce').fillna(0)

            if tipo_eleccion == 'diputados':
                region = detectar_region(nombre, ESCAÑOS_DIPUTADOS_2026)
                if region and region in ESCAÑOS_DIPUTADOS_2026:
                    grupo = df_filtrado.groupby(COL_PARTIDO)[COL_VOTOS].sum()
                    if region not in datos:
                        datos[region] = grupo
                    else:
                        datos[region] = datos[region].add(grupo, fill_value=0)
                    votos_nacionales.append(grupo)
                    archivos_ok.append((region, nombre, csv_info.get('source', 'individual')))
                else:
                    archivos_error.append(f"{nombre}: Region no detectada")

            elif tipo_eleccion == 'senado':
                nombre_norm = eliminar_tildes(nombre)

                # Determinar distrito
                if distrito == 'unico' or 'UNICO' in nombre_norm or 'UNICO' in nombre_norm:
                    grupo = df_filtrado.groupby(COL_PARTIDO)[COL_VOTOS].sum()
                    if 'unico' not in datos:
                        datos['unico'] = grupo
                    else:
                        datos['unico'] = datos['unico'].add(grupo, fill_value=0)
                    votos_nacionales.append(grupo)
                    archivos_ok.append(('DISTRITO UNICO', nombre, csv_info.get('source', 'individual')))

                elif distrito == 'multiple' or 'MULTIPLE' in nombre_norm:
                    region = detectar_region(nombre, REGLA_MULTIPLE_SENADO)
                    if region and region in REGLA_MULTIPLE_SENADO:
                        grupo = df_filtrado.groupby(COL_PARTIDO)[COL_VOTOS].sum()
                        if region not in datos:
                            datos[region] = grupo
                        else:
                            datos[region] = datos[region].add(grupo, fill_value=0)
                        votos_nacionales.append(grupo)
                        archivos_ok.append((region, nombre, csv_info.get('source', 'individual')))
                    else:
                        archivos_error.append(f"{nombre}: Region no detectada para múltiple")
                else:
                    archivos_error.append(f"{nombre}: Distrito no detectado (esperado Único/Múltiple)")

            elif tipo_eleccion == 'andino':
                grupo = df_filtrado.groupby(COL_PARTIDO)[COL_VOTOS].sum()
                votos_nacionales.append(grupo)
                archivos_ok.append(('NACIONAL', nombre, csv_info.get('source', 'individual')))

            del df, df_filtrado
            gc.collect()

        except Exception as e:
            archivos_error.append(f"{nombre}: {str(e)}")

    if tipo_eleccion == 'andino' and votos_nacionales:
        datos['nacional'] = pd.concat(votos_nacionales).groupby(level=0).sum()

    return datos, votos_nacionales, archivos_ok, archivos_error

def cruzar_con_excel(df_candidatos, uploaded_excel):
    if uploaded_excel is None or df_candidatos.empty:
        return df_candidatos
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

        df_result = df_merge[['Región', 'Partido', 'Candidato/Nro', 'CANDIDATO', 'Votos Preferenciales']].copy()
        df_result.columns = ['Región', 'Partido', 'N°', 'Nombre del Candidato', 'Votos Preferenciales']
        df_result['Nombre del Candidato'] = df_result['Nombre del Candidato'].fillna('(NO ENCONTRADO EN EXCEL)')

        del df_maestro, df_maestro_u, df_merge
        gc.collect()

        return df_result
    except Exception as e:
        st.warning(f"Error cruzando con Excel: {e}")
        df_candidatos['N°'] = df_candidatos['Candidato/Nro']
        df_candidatos['Nombre del Candidato'] = '(ERROR EN EXCEL)'
        return df_candidatos[['Región', 'Partido', 'N°', 'Nombre del Candidato', 'Votos Preferenciales']]

def generar_imagen_tabla(df, titulo):
    if df.empty:
        fig, ax = plt.subplots(figsize=(8, 2))
        ax.text(0.5, 0.5, 'Sin datos para visualizar', ha='center', va='center', fontsize=12)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        plt.close(fig)
        return buf

    fig, ax = plt.subplots(figsize=(min(20, max(12, len(df.columns) * 2)), min(15, max(8, len(df) * 0.5 + 2))))
    ax.axis('tight')
    ax.axis('off')

    colColours = ['#1e40af'] * len(df.columns)
    cellColours = [['#f8fafc'] * len(df.columns) for _ in range(len(df))]

    for i, idx in enumerate(df.index):
        if 'TOTAL' in str(idx):
            cellColours[i] = ['#e0f2fe'] * len(df.columns)

    tabla = ax.table(cellText=df.values, colLabels=df.columns, rowLabels=df.index,
                    cellLoc='center', loc='center', colColours=colColours,
                    cellColours=cellColours)
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(9)
    tabla.scale(1, 1.5)

    for i in range(len(df.columns)):
        tabla[(0, i)].set_text_props(color='white', fontweight='bold')

    plt.title(titulo, fontsize=14, fontweight='bold', pad=20)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close(fig)
    return buf

# ============================================================
# INICIALIZAR SESSION STATE (CACHÉ PERSISTENTE)
# ============================================================
if 'cache_resultados' not in st.session_state:
    st.session_state.cache_resultados = {}
if 'cache_procesado' not in st.session_state:
    st.session_state.cache_procesado = None
if 'cache_excel' not in st.session_state:
    st.session_state.cache_excel = None

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("<h1 style='text-align:center; color:#1e40af; font-size:1.8rem;'>🇵🇪 PERÚ 2026</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#64748b; font-size:0.9rem;'>Simulador Electoral Integral</p>", unsafe_allow_html=True)
    st.markdown("---")

    st.subheader("🗳️ Tipo de Elección")
    tipo_eleccion = st.radio("Selecciona:",
        options=[("diputados", "🏛️ Diputados (130 escaños)"), ("senado", "⚖️ Senado (60 escaños)"), ("andino", "🌎 Parlamento Andino (5 escaños)")],
        format_func=lambda x: x[1], index=0)[0]

    st.markdown("---")
    st.subheader("📁 Archivos Detectados")

    archivos_locales = detectar_archivos_locales(tipo_eleccion)
    hay_locales = any(v is not None for v in archivos_locales.values())

    if hay_locales:
        st.markdown('<div class="success-box"><b>✅ Archivos detectados</b></div>', unsafe_allow_html=True)
        for key, info in archivos_locales.items():
            if info:
                st.markdown(f"• `{os.path.basename(info['ruta'])}`")
    else:
        st.markdown('<div class="warning-box"><b>⚠️ Sin archivos locales</b></div>', unsafe_allow_html=True)

    with st.expander("📤 Carga Manual", expanded=not hay_locales):
        if tipo_eleccion == 'senado':
            uploaded_zip_unico = st.file_uploader("ZIP Distrito Único", type=["zip"], key=f"manual_unico_{tipo_eleccion}")
            uploaded_zip_multiple = st.file_uploader("ZIP Distrito Múltiple", type=["zip"], key=f"manual_multiple_{tipo_eleccion}")
        else:
            uploaded_zip = st.file_uploader("ZIP con CSVs", type=["zip"], key=f"manual_zip_{tipo_eleccion}")

    st.markdown("---")
    st.subheader("📊 Excel de Candidatos")
    uploaded_excel = st.file_uploader("Maestro (Opcional)", type=["xlsx", "xls"], key=f"excel_{tipo_eleccion}")

    st.markdown("---")
    st.subheader("🔄 Control")
    if st.button("🚀 ACTUALIZAR DATOS", type="primary", use_container_width=True):
        st.session_state.cache_resultados = {}
        st.session_state.cache_procesado = None
        st.session_state.cache_excel = None
        st.rerun()

    st.caption("v11.0 - Detección con tildes + Fix caché")

# ============================================================
# HEADER
# ============================================================
st.markdown('<div class="main-header">🇵🇪 Simulador Electoral Perú 2026</div>', unsafe_allow_html=True)

if tipo_eleccion == 'diputados':
    st.markdown('<div class="sub-header"><span class="election-badge badge-diputados">🏛️ DIPUTADOS</span> 130 Escaños · Doble Valla Electoral · DHondt</div>', unsafe_allow_html=True)
elif tipo_eleccion == 'senado':
    st.markdown('<div class="sub-header"><span class="election-badge badge-senado">⚖️ SENADO</span> 60 Escaños · 30 Único + 30 Múltiple</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="sub-header"><span class="election-badge badge-andino">🌎 PARLAMENTO ANDINO</span> 5 Escaños · Circunscripción Única</div>', unsafe_allow_html=True)

# ============================================================
# VERIFICAR CACHÉ
# ============================================================
cache_key = f"{tipo_eleccion}_{hash(str(archivos_locales))}"

# Inicializar variables por defecto para evitar NameError
datos = {}
votos_nac = []
archivos_ok = []
archivos_error = []
cuadro = pd.DataFrame()
total_escaños = 0
total_votos = 0
partidos_aptos = []
df_candidatos = pd.DataFrame()

if cache_key in st.session_state.cache_resultados and st.session_state.cache_procesado == tipo_eleccion:
    # USAR CACHÉ
    r = st.session_state.cache_resultados[cache_key]
    datos = r.get('datos', {})
    votos_nac = r.get('votos_nac', [])
    archivos_ok = r.get('archivos_ok', [])
    archivos_error = r.get('archivos_error', [])
    cuadro = r.get('cuadro', pd.DataFrame())
    total_escaños = r.get('total_escaños', 0)
    total_votos = r.get('total_votos', 0)
    partidos_aptos = r.get('partidos_aptos', [])
    df_candidatos = r.get('df_candidatos', pd.DataFrame())

    st.success("📦 Mostrando resultados en caché. Presiona '🚀 ACTUALIZAR DATOS' para recalcular.")
else:
    # ============================================================
    # CARGA DE ARCHIVOS
    # ============================================================
    todos_csvs = []

    if hay_locales:
        if tipo_eleccion == 'senado':
            unico_info = archivos_locales.get('senado_unico')
            multiple_info = archivos_locales.get('senado_multiple')

            if unico_info:
                if unico_info['tipo'] == 'zip':
                    csvs = extraer_csvs_de_zip_path(unico_info['ruta'])
                else:
                    csvs = extraer_csvs_de_carpeta(unico_info['ruta'])
                for c in csvs: c['distrito'] = 'unico'
                todos_csvs.extend(csvs)
                st.success(f"✅ Único: `{os.path.basename(unico_info['ruta'])}`")

            if multiple_info:
                if multiple_info['tipo'] == 'zip':
                    csvs = extraer_csvs_de_zip_path(multiple_info['ruta'])
                else:
                    csvs = extraer_csvs_de_carpeta(multiple_info['ruta'])
                for c in csvs: c['distrito'] = 'multiple'
                todos_csvs.extend(csvs)
                st.success(f"✅ Múltiple: `{os.path.basename(multiple_info['ruta'])}`")
        else:
            clave = 'diputados' if tipo_eleccion == 'diputados' else 'andino'
            info = archivos_locales.get(clave)

            if info:
                if info['tipo'] == 'zip':
                    todos_csvs = extraer_csvs_de_zip_path(info['ruta'])
                else:
                    todos_csvs = extraer_csvs_de_carpeta(info['ruta'])
                st.success(f"✅ `{os.path.basename(info['ruta'])}`")

    # Carga manual
    if not todos_csvs:
        st.warning("⚠️ Usando carga manual...")
        if tipo_eleccion == 'senado':
            if 'uploaded_zip_unico' in locals() and uploaded_zip_unico:
                with zipfile.ZipFile(uploaded_zip_unico) as z:
                    for name in z.namelist():
                        if name.lower().endswith('.csv'):
                            with z.open(name) as f:
                                todos_csvs.append({'name': os.path.basename(name), 'content': io.BytesIO(f.read()), 'distrito': 'unico', 'source': 'manual'})
            if 'uploaded_zip_multiple' in locals() and uploaded_zip_multiple:
                with zipfile.ZipFile(uploaded_zip_multiple) as z:
                    for name in z.namelist():
                        if name.lower().endswith('.csv'):
                            with z.open(name) as f:
                                todos_csvs.append({'name': os.path.basename(name), 'content': io.BytesIO(f.read()), 'distrito': 'multiple', 'source': 'manual'})
        else:
            if 'uploaded_zip' in locals() and uploaded_zip:
                with zipfile.ZipFile(uploaded_zip) as z:
                    for name in z.namelist():
                        if name.lower().endswith('.csv'):
                            with z.open(name) as f:
                                todos_csvs.append({'name': os.path.basename(name), 'content': io.BytesIO(f.read()), 'source': 'manual'})

    if not todos_csvs:
        st.error("❌ No se encontraron archivos CSV válidos.")
        st.stop()

    # ============================================================
    # PROCESAMIENTO
    # ============================================================
    with st.spinner("⏳ Procesando..."):
        datos, votos_nac, archivos_ok, archivos_error = procesar_csvs(todos_csvs, tipo_eleccion)

        if archivos_error:
            with st.expander(f"⚠️ Errores ({len(archivos_error)})"):
                for err in archivos_error:
                    st.markdown(f"- {err}")

        if not datos:
            st.error("No se pudieron procesar archivos válidos.")
            st.stop()

        st.success(f"✅ {len(archivos_ok)} archivos procesados.")

        # =====================================================
        # CÁLCULOS
        # =====================================================
        if tipo_eleccion == 'diputados':
            df_nacional = pd.concat(votos_nac).groupby(level=0).sum().reset_index()
            df_nacional.columns = [COL_PARTIDO, COL_VOTOS]
            total_votos = df_nacional[COL_VOTOS].sum()
            pasan_5 = df_nacional[df_nacional[COL_VOTOS] >= (total_votos * 0.05)][COL_PARTIDO].tolist()

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

            resultados_list = []
            for region, series in datos.items():
                n_esc = ESCAÑOS_DIPUTADOS_2026.get(region, 0)
                df_temp = series.reset_index()
                df_temp.columns = [COL_PARTIDO, COL_VOTOS]
                df_f = df_temp[df_temp[COL_PARTIDO].isin(partidos_aptos)].copy()
                if n_esc > 0 and not df_f.empty:
                    df_res = calcular_dhondt(df_f, n_esc, COL_PARTIDO, COL_VOTOS)
                    df_res['Region'] = region
                    resultados_list.append(df_res)

            df_final = pd.concat(resultados_list, ignore_index=True)
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
                if res_reg.empty: 
                    continue

                archivos_reg = [c for c in todos_csvs if eliminar_tildes(c['name']).find(eliminar_tildes(region)) != -1]
                if archivos_reg:
                    votos_partidos = {}
                    for c in archivos_reg:
                        c['content'].seek(0)
                        df_temp = pd.read_csv(c['content'], low_memory=False, dtype=str)
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

            # CRUZAR CON EXCEL
            if uploaded_excel is not None and not df_candidatos.empty:
                df_candidatos = cruzar_con_excel(df_candidatos, uploaded_excel)

            del df_nacional, df_sim, df_final, resultados_list
            gc.collect()

        elif tipo_eleccion == 'senado':
            df_unico = datos.get('unico', pd.Series())
            if not df_unico.empty:
                df_unico = df_unico.reset_index()
                df_unico.columns = [COL_PARTIDO, COL_VOTOS]

            datos_mult = {k: v.reset_index().rename(columns={0: COL_PARTIDO, 1: COL_VOTOS}) for k, v in datos.items() if k != 'unico'}

            if df_unico.empty:
                st.error("❌ No se encontró Distrito Único.")
                st.stop()
            if not datos_mult:
                st.error("❌ No se encontró Distrito Múltiple.")
                st.stop()

            votos_nac_df = pd.concat(votos_nac).groupby(level=0).sum().reset_index()
            votos_nac_df.columns = [COL_PARTIDO, COL_VOTOS]
            total_votos = votos_nac_df[COL_VOTOS].sum()
            pasan_5 = votos_nac_df[votos_nac_df[COL_VOTOS] >= (total_votos * 0.05)][COL_PARTIDO].tolist()

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
                fila_mult.index = ['DISTRITO MÚLTIPLE (30 escaños)']
            else:
                matriz_reg = pd.DataFrame()
                fila_mult = pd.DataFrame()

            fila_u = res_u.set_index('Partido')['Escaños'].to_frame().T
            fila_u.index = ['DISTRITO ÚNICO (30 escaños)']

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
                cuadro.loc['TOTAL PARTIDO'] = cuadro.loc[['DISTRITO MÚLTIPLE (30 escaños)', 'DISTRITO ÚNICO (30 escaños)']].sum()
            else:
                cuadro.loc['TOTAL PARTIDO'] = cuadro.loc['DISTRITO ÚNICO (30 escaños)']

            total_escaños = int(cuadro.loc['TOTAL PARTIDO', 'TOTAL'])
            df_candidatos = pd.DataFrame()

            del votos_nac_df, sim_u, sim_m, df_sim, res_u, res_m
            gc.collect()

        else:  # andino
            df_nac = datos.get('nacional', pd.Series())
            total_votos = float(df_nac.sum()) if not df_nac.empty else 0

            umbral = total_votos * 0.05
            partidos_aptos = df_nac[df_nac >= umbral].index.tolist()

            df_reparto = df_nac[df_nac.index.isin(partidos_aptos)].reset_index()
            df_reparto.columns = [COL_PARTIDO, COL_VOTOS]

            res = calcular_dhondt(df_reparto, ESCAÑOS_ANDINO, COL_PARTIDO, COL_VOTOS)
            res = res.sort_values('Escaños', ascending=False)

            cuadro = res.set_index('Partido').T
            cuadro.index = ['ESCAÑOS']
            cuadro['TOTAL'] = cuadro.sum(axis=1)

            total_escaños = int(cuadro['TOTAL'].iloc[0]) if not cuadro.empty else 0
            df_candidatos = pd.DataFrame()

            del df_nac, df_reparto, res
            gc.collect()

        # GUARDAR EN CACHÉ
        st.session_state.cache_resultados[cache_key] = {
            'datos': datos,
            'votos_nac': votos_nac,
            'archivos_ok': archivos_ok,
            'archivos_error': archivos_error,
            'cuadro': cuadro,
            'total_escaños': total_escaños,
            'total_votos': total_votos,
            'partidos_aptos': partidos_aptos,
            'df_candidatos': df_candidatos
        }
        st.session_state.cache_procesado = tipo_eleccion

# ============================================================
# MOSTRAR RESULTADOS
# ============================================================
# Asegurar que todas las variables existen (desde cálculo o caché)
if cuadro.empty:
    st.warning("No hay resultados para mostrar.")
    st.stop()

# CARDS
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'<div class="card"><div class="card-title">Total Escaños</div><div class="card-value">{total_escaños}</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="card"><div class="card-title">Partidos Aptos</div><div class="card-value">{len(partidos_aptos)}</div></div>', unsafe_allow_html=True)
with col3:
    metric_label = "Regiones" if tipo_eleccion == 'diputados' else "Distritos" if tipo_eleccion == 'senado' else "Archivos"
    metric_value = len(datos) if datos else 0
    st.markdown(f'<div class="card"><div class="card-title">{metric_label}</div><div class="card-value">{metric_value}</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="card"><div class="card-title">Votos Válidos</div><div class="card-value">{total_votos:,.0f}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# TABS CON DESCARGAS CSV + IMAGEN
if tipo_eleccion == 'diputados':
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Escaños por Región", "🏆 Candidatos Electos", "📈 Análisis", "📋 Técnico"])

    with tab1:
        st.subheader("Distribución de Escaños")

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            csv_data = cuadro.to_csv().encode('utf-8')
            st.download_button("📥 Descargar CSV", csv_data, "diputados_escaños_2026.csv", "text/csv", use_container_width=True)
        with col_dl2:
            try:
                img_buf = generar_imagen_tabla(cuadro, "Distribución de Escaños - Diputados 2026")
                st.download_button("🖼️ Descargar Imagen", img_buf, "diputados_escaños_2026.png", "image/png", use_container_width=True)
            except Exception as e:
                st.error(f"Error generando imagen: {e}")

        st.dataframe(cuadro, use_container_width=True, height=600)
        chart_data = cuadro.drop('TOTAL NACIONAL', errors='ignore').drop('TOTAL REGION', axis=1, errors='ignore')
        if not chart_data.empty:
            st.bar_chart(chart_data, height=500)

    with tab2:
        if not df_candidatos.empty:
            st.subheader(f"Candidatos Electos ({len(df_candidatos)})")

            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                csv_cand = df_candidatos.to_csv().encode('utf-8')
                st.download_button("📥 Descargar CSV", csv_cand, "diputados_candidatos_2026.csv", "text/csv", use_container_width=True)
            with col_dl2:
                try:
                    idx_col = 'Región' if 'Región' in df_candidatos.columns else None
                    img_buf = generar_imagen_tabla(df_candidatos.set_index(idx_col) if idx_col else df_candidatos, "Candidatos Electos - Diputados 2026")
                    st.download_button("🖼️ Descargar Imagen", img_buf, "diputados_candidatos_2026.png", "image/png", use_container_width=True)
                except Exception as e:
                    st.error(f"Error generando imagen: {e}")

            st.dataframe(df_candidatos.style.format({'Votos Preferenciales': '{:,}'}), use_container_width=True, height=600)
        else:
            st.info("No se detectaron candidatos individuales.")

    with tab3:
        st.subheader("Análisis de Vallas")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.markdown("**Valla 5% (Nacional)**")
            if votos_nac:
                df_nac_temp = pd.concat(votos_nac).groupby(level=0).sum().reset_index()
                df_nac_temp.columns = [COL_PARTIDO, COL_VOTOS]
                total_v_temp = df_nac_temp[COL_VOTOS].sum()
                p5 = df_nac_temp[df_nac_temp[COL_VOTOS] >= (total_v_temp * 0.05)][COL_PARTIDO].tolist()
                df_5 = df_nac_temp[df_nac_temp[COL_PARTIDO].isin(p5)].sort_values(COL_VOTOS, ascending=False)
                df_5['%'] = (df_5[COL_VOTOS] / total_v_temp * 100).round(2)
                st.dataframe(df_5[[COL_PARTIDO, COL_VOTOS, '%']].rename(columns={COL_PARTIDO: 'Partido', COL_VOTOS: 'Votos'}), use_container_width=True)
                del df_nac_temp
            else:
                st.info("No hay datos de votos nacionales")
        with col_a2:
            st.markdown("**Valla 7 Escaños (Distrital)**")
            valla_7_data = []
            for p in partidos_aptos:
                esc = int(cuadro.loc['TOTAL NACIONAL', p]) if 'TOTAL NACIONAL' in cuadro.index and p in cuadro.columns else 0
                valla_7_data.append({'Partido': p, 'Escaños': esc})
            st.dataframe(pd.DataFrame(valla_7_data), use_container_width=True)
        st.markdown("**Partidos que pasan AMBAS vallas:**")
        for p in sorted(partidos_aptos):
            esc = int(cuadro.loc['TOTAL NACIONAL', p]) if 'TOTAL NACIONAL' in cuadro.index and p in cuadro.columns else 0
            st.markdown(f"• **{p}**: {esc} escaños")

    with tab4:
        st.subheader("Resumen Técnico")
        st.markdown(f"""
        **Método:** DHondt  
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

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            csv_data = cuadro.to_csv().encode('utf-8')
            st.download_button("📥 Descargar CSV", csv_data, "senado_escaños_2026.csv", "text/csv", use_container_width=True)
        with col_dl2:
            try:
                img_buf = generar_imagen_tabla(cuadro, "Distribución de Escaños - Senado 2026")
                st.download_button("🖼️ Descargar Imagen", img_buf, "senado_escaños_2026.png", "image/png", use_container_width=True)
            except Exception as e:
                st.error(f"Error generando imagen: {e}")

        st.dataframe(cuadro, use_container_width=True, height=600)

    with tab2:
        st.subheader("Análisis de Vallas")
        st.markdown("**Partidos aptos:**")
        for p in sorted(partidos_aptos):
            esc = int(cuadro.loc['TOTAL PARTIDO', p]) if 'TOTAL PARTIDO' in cuadro.index and p in cuadro.columns else 0
            st.markdown(f"• **{p}**: {esc} escaños")

    with tab3:
        st.subheader("Resumen Técnico")
        st.markdown(f"""
        **Método:** DHondt  
        **Distrito Único:** {ESCAÑOS_SENADO_UNICO} escaños  
        **Distrito Múltiple:** {ESCAÑOS_SENADO_MULTIPLE} escaños  
        **Total:** {ESCAÑOS_SENADO_UNICO + ESCAÑOS_SENADO_MULTIPLE} escaños
        """)
        st.subheader("Archivos procesados")
        for reg, nom, src in archivos_ok:
            st.markdown(f"- **{reg}**: {nom} ({src})")

else:  # andino
    tab1, tab2 = st.tabs(["📊 Escaños Andino", "📋 Técnico"])

    with tab1:
        st.subheader("Distribución - Parlamento Andino 2026")

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            csv_data = cuadro.to_csv().encode('utf-8')
            st.download_button("📥 Descargar CSV", csv_data, "andino_escaños_2026.csv", "text/csv", use_container_width=True)
        with col_dl2:
            try:
                img_buf = generar_imagen_tabla(cuadro, "Distribución de Escaños - Parlamento Andino 2026")
                st.download_button("🖼️ Descargar Imagen", img_buf, "andino_escaños_2026.png", "image/png", use_container_width=True)
            except Exception as e:
                st.error(f"Error generando imagen: {e}")

        st.dataframe(cuadro, use_container_width=True, height=400)

    with tab2:
        st.subheader("Resumen Técnico")
        st.markdown(f"""
        **Método:** DHondt  
        **Escaños:** {ESCAÑOS_ANDINO}  
        **Valla:** 5% nacional  
        **Partidos aptos:** {len(partidos_aptos)}
        """)
        st.subheader("Archivos procesados")
        for reg, nom, src in archivos_ok:
            st.markdown(f"- {nom} ({src})")

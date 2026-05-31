import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from supabase import create_client, Client

# 1. Configuración de la página web (Ancho completo e interfaz fluida)
st.set_page_config(page_title="Mi ERP Financiero Pro", page_icon="📊", layout="wide")

# --- ESTILOS PERSONALIZADOS (Pestañas claras y sin fondo oscuro) ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    
    /* Tarjetas de métricas: fondo más claro/grisáceo para romper el negro */
    .tarjeta-metrica {
        padding: 14px 18px;
        border-radius: 8px;
        border: 1px solid #3b4252;
        background-color: #2e3440;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .metrica-titulo {
        font-size: 0.85rem;
        font-weight: 600;
        color: #d8dee9;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .metrica-valor {
        font-size: 1.65rem;
        font-weight: 700;
        color: #eceff4;
        white-space: nowrap;
    }
    
    /* Botones de navegación de pestañas (Tabs) en color claro/blanco */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 10px; 
        background-color: transparent !important; /* Quitado el fondo negro de atrás */
        padding: 6px 0px;
    }
    .stTabs [data-baseweb="tab"] { 
        padding: 10px 16px; 
        background-color: #eceff4; /* Blanco/Gris muy claro de base */
        border-radius: 6px;
        color: #2e3440 !important; /* Texto oscuro para contraste radical */
        font-weight: 600;
        transition: all 0.2s ease;
    }
    /* Estilo cuando pasas el ratón o la pestaña está seleccionada */
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #d8dee9;
    }
    .stTabs [aria-selected="true"] {
        background-color: #88c0d0 !important; /* Turquesa para destacar la pestaña activa */
        color: #2e3440 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

# 2. Conexión segura con la base de datos Supabase
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("Error de conexión con los Secrets de Supabase. Verifica la configuración.")
    st.stop()

# 3. Funciones core de lectura y escritura en la nube (Sincronización Directa por Filtro)
def cargar_datos_db():
    try:
        response = supabase.table("erp_balance").select("*").eq("nombre_escenario", "Principal").execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        pass
    return None

def guardar_datos_db(datos_nuevos):
    try:
        # Copiamos el diccionario e inyectamos el nombre de escenario correcto
        payload = datos_nuevos.copy()
        payload["nombre_escenario"] = "Principal"
        
        # Usamos update directo filtrando por el nombre del escenario existente para evitar el conflicto 42P10
        supabase.table("erp_balance").update(payload).eq("nombre_escenario", "Principal").execute()
        st.toast("¡Copia de seguridad guardada en Supabase Cloud! 🚀", icon="💾")
    except Exception as e:
        st.error(f"Error al sincronizar con la nube: {e}")

# Inicialización única desde la Base de Datos al arrancar
if "db_data" not in st.session_state:
    st.session_state.db_data = cargar_datos_db()

db = st.session_state.db_data

# Resguardo local si la base de datos está vacía por primera vez
if not db:
    db = {
        "salario_base": 3200, "liquidez": 15450, 
        "unidades_voo": 5, "unidades_vale": 20, "unidades_pbr": 15,
        "valor_inmuebles": 250000, "otros_activos": 24500
    }

# =====================================================================
# --- SISTEMA DE ALMACENAMIENTO TEMPORAL (SESSION STATE INTERNO) ---
# =====================================================================
if "efectivo_divisas" not in st.session_state:
    st.session_state.efectivo_divisas = {"EUR": float(db.get("liquidez", 15450))}

if "cartera_usuario" not in st.session_state:
    st.session_state.cartera_usuario = {
        "PBR": {"unidades": float(db.get("unidades_pbr", 15)), "precio_compra": 12.50},
        "VALE": {"unidades": float(db.get("unidades_vale", 20)), "precio_compra": 11.20},
        "VOO": {"unidades": float(db.get("unidades_voo", 5)), "precio_compra": 420.00}
    }

if "fincas_usuario" not in st.session_state:
    st.session_state.fincas_usuario = [{"Nombre": "Ático Alicante Centro", "Catastro": "9872023VH5797S0001WX", "Valor": float(db.get("valor_inmuebles", 250000))}]

if "pensiones_usuario" not in st.session_state:
    st.session_state.pensiones_usuario = [
        {"Nombre": "401k USA Plan", "Valor": 45000.0},
        {"Nombre": "Workplace Pension UK", "Valor": 28000.0}
    ]

if "otros_activos_usuario" not in st.session_state:
    st.session_state.otros_activos_usuario = [{"Nombre": "Vehículo Familiar", "Valor": float(db.get("otros_activos", 24500))}]

if "deudas_usuario" not in st.session_state:
    st.session_state.deudas_usuario = [{"Nombre": "Hipoteca Principal", "Valor": 120000.0}]

if "plusvalia_bolsa_real" not in st.session_state:
    st.session_state.plusvalia_bolsa_real = 0.0

st.title("📊 Mi Panel de Control Contable & Proyección Global")

# --- PESTAÑAS CONTABLES ---
tab_balance, tab_proyeccion, tab_fiscalidad = st.tabs([
    "🏛️ Balance & Radar", 
    "📈 Proyección & Estrés", 
    "📑 Tax Alpha e Impuestos"
])

# =====================================================================
# HELPER: CONVERSIÓN DE DIVISAS
# =====================================================================
def obtener_conversion_eur(monto, divisa):
    if divisa == "EUR" or monto == 0:
        return monto
    try:
        ticker_name = f"{divisa}EUR=X"
        ratio = yf.Ticker(ticker_name).history(period="1d")['Close'].iloc[-1]
        return monto * ratio
    except:
        fallbacks = {"USD": 0.92, "GBP": 1.17, "CHF": 1.03}
        return monto * fallbacks.get(divisa, 1.0)

# =====================================================================
# PESTAÑA 1: BALANCE DE SITUACIÓN ACTUAL & RADAR DE REBALANCEO
# =====================================================================
with tab_balance:
    col_izquierda, col_derecha = st.columns([1.1, 1.9])

    with col_izquierda:
        st.header("📥 Entrada de Partidas")
        
        st.subheader("🪙 1. Liquidez de Base")
        c_div1, c_div2 = st.columns([2, 3])
        nueva_divisa = c_div1.selectbox("Añadir divisa extra", ["USD", "GBP", "CHF", "CAD", "AUD", "JPY"])
        if c_div2.button("➕ Agregar Divisa", use_container_width=True):
            if nueva_divisa not in st.session_state.efectivo_divisas:
                st.session_state.efectivo_divisas[nueva_divisa] = 0.0
                st.rerun()
        
        categoria_cash = 0.0
        for div, monto in list(st.session_state.efectivo_divisas.items()):
            c_u, c_b = st.columns([4, 1])
            monto_input = c_u.number_input(f"Saldo en {div}", min_value=0.0, value=float(monto), key=f"cash_{div}", step=500.0)
            st.session_state.efectivo_divisas[div] = monto_input
            
            valor_convertido = obtener_conversion_eur(monto_input, div)
            categoria_cash += valor_convertido
            
            if div != "EUR" and c_b.button("❌", key=f"del_cash_{div}"):
                del st.session_state.efectivo_divisas[div]
                st.rerun()
        st.caption(f"Valor consolidado de la liquidez: `{int(categoria_cash):,} €`")
        
        st.divider()
        st.subheader("📈 2. Cartera Bursátil")
        nuevo_ticker = st.text_input("Ticker (ej: AAPL, VOO, VALE)", key="new_tick").upper().strip()
        if st.button("➕ Añadir Ticker"):
            if nuevo_ticker and nuevo_ticker not in st.session_state.cartera_usuario:
                st.session_state.cartera_usuario[nuevo_ticker] = {"unidades": 1.0, "precio_compra": 10.0}
                st.rerun()
        
        total_bolsa = 0.0
        plusvalia_acumulada_euros = 0.0
        desglose_acciones = []
        info_tickers_cache = {} 
        
        for ticker, datos in list(st.session_state.cartera_usuario.items()):
            st.markdown(f"**Posición en {ticker}**")
            c_uni, c_pr, c_b = st.columns([2.5, 2.5, 1])
            
            unidades = c_uni.number_input(f"U. {ticker}", min_value=0.0, value=float(datos["unidades"]), key=f"uni_{ticker}")
            p_compra = c_pr.number_input(f"Pm. {ticker}", min_value=0.0, value=float(datos["precio_compra"]), key=f"pr_{ticker}")
            
            st.session_state.cartera_usuario[ticker]["unidades"] = unidades
            st.session_state.cartera_usuario[ticker]["precio_compra"] = p_compra
            
            if c_b.button("❌", key=f"del_{ticker}"):
                del st.session_state.cartera_usuario[ticker]
                st.rerun()
            
            if unidades > 0:
                try:
                    tick_info = yf.Ticker(ticker)
                    precio_orig = tick_info.history(period="1d")['Close'].iloc[-1]
                    currency = tick_info.fast_info.get('currency', 'USD')
                    
                    precio_eur = obtener_conversion_eur(precio_orig, currency)
                    valor_posicion = precio_eur * unidades
                    total_bolsa += valor_posicion
                    
                    info_tickers_cache[ticker] = {"precio_eur": precio_eur, "unidades": unidades, "ticker_obj": tick_info}
                    
                    coste_total_orig = p_compra * unidades
                    coste_total_eur = obtener_conversion_eur(coste_total_orig, currency)
                    plusvalia_posicion_eur = valor_posicion - coste_total_eur
                    plusvalia_acumulada_euros += plusvalia_posicion_eur
                    
                    desglose_acciones.append(f"  - **{ticker}**: {unidades:.0f} u. x {precio_orig:.2f} {currency} = `{int(valor_posicion):,} €` (Gain: `{int(plusvalia_posicion_eur):,} €`)")
                except:
                    pass
        
        st.session_state.plusvalia_bolsa_real = max(0.0, plusvalia_acumulada_euros)

        st.divider()
        st.subheader("🏠 3. Activos Inmobiliarios")
        with st.form("form_inmuebles"):
            n_f = st.text_input("Nombre Inmueble / ID", placeholder="Ej. Apartamento Tenerife")
            c_f = st.text_input("Ref. Catastral (Opcional)", max_chars=20)
            v_f = st.number_input("Valor mercado (€)", min_value=0.0, step=5000.0)
            if st.form_submit_button("Añadir Inmueble") and n_f:
                st.session_state.fincas_usuario.append({"Nombre": n_f, "Catastro": c_f.upper().strip() if c_f else "NO APORTADA", "Valor": float(v_f)})
                st.rerun()
        
        categoria_inmobiliario = sum(f['Valor'] for f in st.session_state.fincas_usuario)
        for idx, f in enumerate(st.session_state.fincas_usuario):
            c_inf, c_del = st.columns([4, 1])
            c_inf.caption(f"🏢 *{f['Nombre']}* ({f['Valor']:,} €)")
            if c_del.button("🗑️", key=f"df_{idx}"):
                st.session_state.fincas_usuario.pop(idx); st.rerun()

        st.divider()
        st.subheader("🛡️ 4. Planes de Pensiones")
        with st.form("form_pensiones"):
            n_p = st.text_input("Nombre del Plan", placeholder="Ej. 401k USA o Workplace Pension UK")
            v_p = st.number_input("Valor de Mercado actual (€)", min_value=0.0, step=1000.0)
            if st.form_submit_button("➕ Agregar Plan") and n_p:
                st.session_state.pensiones_usuario.append({"Nombre": n_p, "Valor": float(v_p)})
                st.rerun()
                
        categoria_pensiones = sum(p['Valor'] for p in st.session_state.pensiones_usuario)
        for idx, p in enumerate(st.session_state.pensiones_usuario):
            c_inf, c_del = st.columns([4, 1])
            c_inf.caption(f"💼 *{p['Nombre']}*: `{p['Valor']:,} €`")
            if c_del.button("🗑️", key=f"dp_{idx}"):
                st.session_state.pensiones_usuario.pop(idx); st.rerun()

        st.divider()
        st.subheader("🚗 5. Otros Activos")
        with st.form("form_otros_act"):
            n_o = st.text_input("Concepto Bien")
            v_o = st.number_input("Valor estimado (€)", min_value=0.0, step=1000.0)
            if st.form_submit_button("Añadir Bien") and n_o:
                st.session_state.otros_activos_usuario.append({"Nombre": n_o, "Valor": float(v_o)})
                st.rerun()
        categoria_otros = sum(a['Valor'] for a in st.session_state.otros_activos_usuario)
        for idx, a in enumerate(st.session_state.otros_activos_usuario):
            c_inf, c_del = st.columns([4, 1])
            c_inf.caption(f"📦 *{a['Nombre']}* ({a['Valor']:,} €)")
            if c_del.button("🗑️", key=f"da_del_{idx}"):
                st.session_state.otros_activos_usuario.pop(idx); st.rerun()

        st.divider()
        st.subheader("🔴 6. Pasivos y Deudas")
        with st.form("form_deudas_tab1"):
            n_d = st.text_input("Nombre de la Obligación")
            v_d = st.number_input("Saldo Pendiente (€)", min_value=0.0, step=1000.0)
            if st.form_submit_button("Añadir Deuda") and n_d:
                st.session_state.deudas_usuario.append({"Nombre": n_d, "Valor": float(v_d)})
                st.rerun()
        pasivo_total = sum(d['Valor'] for d in st.session_state.deudas_usuario)
        for idx, d in enumerate(st.session_state.deudas_usuario):
            c_inf, c_del = st.columns([4, 1])
            c_inf.caption(f"💸 *{d['Nombre']}* ({d['Valor']:,} €)")
            if c_del.button("🗑️", key=f"dd_del_{idx}"):
                st.session_state.deudas_usuario.pop(idx); st.rerun()

    with col_derecha:
        st.header("🏛️ Tu Balance de Situación Global")
        activo_total = categoria_cash + total_bolsa + categoria_pensiones + categoria_inmobiliario + categoria_otros
        patrimonio_neto = activo_total - pasivo_total
        pct_cash = (categoria_cash / activo_total * 100) if activo_total > 0 else 0.0

        # BOTONES DE ACCIÓN PRINCIPALES
        c_rec, c_sav = st.columns(2)
        if c_rec.button("🔄 Recalcular Todo el Balance", type="primary", use_container_width=True):
            st.rerun()
        
        if c_sav.button("💾 Guardar Datos en la Nube", type="secondary", use_container_width=True):
            payload = {
                "salario_base": float(db.get("salario_base", 3200)),
                "liquidez": float(categoria_cash),
                "unidades_voo": float(st.session_state.cartera_usuario.get("VOO", {}).get("unidades", 0)),
                "unidades_vale": float(st.session_state.cartera_usuario.get("VALE", {}).get("unidades", 0)),
                "unidades_pbr": float(st.session_state.cartera_usuario.get("PBR", {}).get("unidades", 0)),
                "valor_inmuebles": float(categoria_inmobiliario),
                "otros_activos": float(categoria_otros)
            }
            guardar_datos_db(payload)
            st.session_state.db_data = payload
            
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='tarjeta-metrica'><div class='metrica-titulo'>🟢 Activo Total</div><div class='metrica-valor'>{int(activo_total):,} €</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='tarjeta-metrica'><div class='metrica-titulo'>🔴 Pasivo Total</div><div class='metrica-valor'>{int(pasivo_total):,} €</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='tarjeta-metrica'><div class='metrica-titulo'>💎 Patrimonio Neto</div><div class='metrica-valor'>{int(patrimonio_neto):,} €</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='tarjeta-metrica'><div class='metrica-titulo'>📈 % Cash Global</div><div class='metrica-valor'>{pct_cash:.1f} %</div></div>", unsafe_allow_html=True)
        
        st.divider()
        if activo_total > 0:
            fig = go.Figure(data=[go.Pie(labels=['Cash', 'Bolsa', 'Pensiones', 'Inmobiliario', 'Otros'], values=[categoria_cash, total_bolsa, categoria_pensiones, categoria_inmobiliario, categoria_otros], hole=.4, marker=dict(colors=['#60A5FA', '#A78BFA', '#FBBF24', '#34D399', '#9CA3AF']), textinfo='label+percent')])
            fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, height=240, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        col_act_d, col_pas_d = st.columns(2)
        with col_act_d:
            st.subheader("🟢 Detalle Estructural de Activos")
            st.markdown(f"• **Líquido Base Consolidado:** `{int(categoria_cash):,} €` ({pct_cash:.1f}%)")
            for div, m in st.session_state.efectivo_divisas.items():
                if m > 0: st.markdown(f"  - _Cuenta:_ {m:,} {div}")
            st.markdown(f"• **Portafolio de Bolsa:** `{int(total_bolsa):,} €`")
            for linea in desglose_acciones: st.markdown(linea)
            st.markdown(f"• **Fondos de Previsión / Pensiones:** `{int(categoria_pensiones):,} €`")
            st.markdown(f"• **Patrimonio Inmobiliario:** `{int(categoria_inmobiliario):,} €`")
            st.markdown(f"• **Otros Bienes Físicos:** `{int(categoria_otros):,} €`")
                
        with col_pas_d:
            st.subheader("🔴 Detalle Estructural de Pasivos")
            st.markdown(f"• **Obligaciones Financieras Totales:** `{int(pasivo_total):,} €`")
            for d in st.session_state.deudas_usuario:
                st.markdown(f"  - 💸 _{d['Nombre']}_: `{int(d['Valor']):,} €`")

        st.divider()
        st.subheader("🎯 Radar de Rebalanceo de Activos")
        c_rb1, c_rb2 = st.columns(2)
        target_cash = c_rb1.slider("% Cash Objetivo", 0, 100, 20)
        target_inm = c_rb2.slider("% Inmobiliario Objetivo", 0, 100, 40)
        target_bolsa = 100 - (target_cash + target_inm)
        
        st.info(f"**Asignación Objetivo:** {target_cash}% Cash | {target_inm}% Inmobiliario | {target_bolsa}% Bolsa y Pensiones/Otros")
        
        val_target_cash = activo_total * (target_cash / 100)
        val_target_inm = activo_total * (target_inm / 100)
        val_target_bolsa = activo_total * (target_bolsa / 100)
        
        diff_cash = categoria_cash - val_target_cash
        diff_inm = categoria_inmobiliario - val_target_inm
        diff_bolsa = (total_bolsa + categoria_pensiones + categoria_otros) - val_target_bolsa
        
        def format_alert(diferencia, nombre):
            if diferencia < -1000:
                st.warning(f"⚠️ **Déficit en {nombre}:** Te faltan `{int(abs(diferencia)):,} €` para cumplir tu objetivo.")
            elif diferencia > 1000:
                st.success(f"💰 **Superávit en {nombre}:** Tienes un exceso de `{int(diferencia):,} €`. Capital disponible para reasignar.")
            else:
                st.info(f"✅ **{nombre} equilibrado.** En rango objetivo.")

        format_alert(diff_cash, "Cash")
        format_alert(diff_inm, "Inmobiliario")
        format_alert(diff_bolsa, "Bolsa / Pensiones")

# =====================================================================
# PESTAÑA 2: PROYECCIÓN DINÁMICA AVANZADA & MATRIX MULTIANUAL
# =====================================================================
with tab_proyeccion:
    st.header("📈 Proyección Avanzada y Editor de Rutas Multianuales")
    
    col_flujos, col_simulacion = st.columns([1.2, 1.8])
    
    with col_flujos:
        st.markdown("### 🏢 Módulo de Rendimiento Inmobiliario")
        total_rentas_pasivas_inmo = 0.0
        if not st.session_state.fincas_usuario:
            st.caption("⚠️ No hay inmuebles en la Pestaña 1.")
        else:
            for f in st.session_state.fincas_usuario:
                with st.expander(f"🏢 Analítica: {f['Nombre']}", expanded=True):
                    c_in1, c_in2, c_in3 = st.columns(3)
                    ing_alq = c_in1.number_input("Alquiler/mes (€)", min_value=0.0, value=900.0, key=f"alq_{f['Nombre']}", step=50.0)
                    gto_fijo = c_in2.number_input("Gastos fijos/mes (€)", min_value=0.0, value=150.0, key=f"gto_{f['Nombre']}", step=25.0)
                    cuota_hip = c_in3.number_input("Cuota Hipoteca/mes (€)", min_value=0.0, value=350.0, key=f"hip_{f['Nombre']}", step=50.0)
                    cashflow_neto_mensual = ing_alq - gto_fijo - cuota_hip
                    total_rentas_pasivas_inmo += cashflow_neto_mensual

        st.markdown("### 💸 Radar Automático de Dividendos")
        total_dividendos_mensuales_bolsa = 0.0
        if info_tickers_cache:
            for ticker, info_pos in info_tickers_cache.items():
                try:
                    t_obj = info_pos["ticker_obj"]
                    div_yield_mercado = t_obj.info.get('dividendYield', 0.0)
                    if div_yield_mercado is None: div_yield_mercado = 0.0
                    if div_yield_mercado > 1.0: div_yield_mercado /= 100.0
                    total_dividendos_mensuales_bolsa += (info_pos["precio_eur"] * info_pos["unidades"] * div_yield_mercado) / 12
                except: pass

        st.markdown("### 🛡️ Planificación Activa de Pensiones")
        total_aportacion_mensual_pensiones = 0.0
        total_anual_deducible_pensiones_usuario = 0.0
        if st.session_state.pensiones_usuario:
            for p in st.session_state.pensiones_usuario:
                with st.expander(f"💼 Planificación: {p['Nombre']}", expanded=True):
                    c_pen1, c_pen2 = st.columns(2)
                    aport_user = c_pen1.number_input("Tu aportación/mes (€)", min_value=0.0, value=250.0, key=f"p_user_{p['Nombre']}", step=50.0)
                    aport_employer = c_pen2.number_input("Empleador/mes (€)", min_value=0.0, value=250.0, key=f"p_emp_{p['Nombre']}", step=50.0)
                    total_aportacion_mensual_pensiones += (aport_user + aport_employer)
                    total_anual_deducible_pensiones_usuario += (aport_user * 12)

        st.subheader("🟢 Otros Ingresos & Gastos Base")
        salario_neto_base = st.number_input("Salario Neto Base Mensual (€)", min_value=0.0, value=float(db.get("salario_base", 3200)), step=100.0)
        gastos_vida_base = st.number_input("Gastos de Vida Base Mensuales (€)", min_value=0.0, value=1800.0, step=100.0)
        
        st.divider()
        ahorro_mensual_inicial = (salario_neto_base + total_rentas_pasivas_inmo + total_dividendos_mensuales_bolsa) - gastos_vida_base
        
        tasa_ahorro_i = (ahorro_mensual_inicial / (salario_neto_base + total_rentas_pasivas_inmo + total_dividendos_mensuales_bolsa) * 100) if (salario_neto_base + total_rentas_pasivas_inmo + total_dividendos_mensuales_bolsa) > 0 else 0.0
        roi_e_i = (ahorro_mensual_inicial * 12 / activo_total * 100) if activo_total > 0 else 0.0
        roe_e_i = (ahorro_mensual_inicial * 12 / patrimonio_neto * 100) if patrimonio_neto > 0 else 0.0
        
        c_m1, c_m2 = st.columns(2)
        c_m1.metric("AHORRO MENSUAL NETO (AÑO 1)", f"{ahorro_mensual_inicial:,.2f} €")
        c_m2.metric("🎯 TASA DE AHORRO INITIAL", f"{tasa_ahorro_i:.1f} %")
        c_m3, c_m4 = st.columns(2)
        c_m3.metric("📊 ROI EFECTIVO INICIAL", f"{roi_e_i:.1f} %")
        c_m4.metric("💎 ROE EFECTIVO INICIAL", f"{roe_e_i:.1f} %")

        st.divider()
        st.subheader("🎯 Hito FI/RE (Vivir de Rentas)")
        gasto_anual_fijo_target = gastos_vida_base * 12
        calculo_fi_auto = gasto_anual_fijo_target / 0.04
        
        numero_fi = st.number_input("Objetivo Patrimonial Absoluto (Número FI en €)", min_value=0.0, value=float(calculo_fi_auto), step=25000.0)
        st.markdown(f"Meta configurada activa: **`{int(numero_fi):,} €`**")

    with col_simulacion:
        st.subheader("🚀 Parámetros Globales y Simulación Temporal")
        c_p1, c_p2, c_p3, c_p4, c_p5 = st.columns(5)
        años_sim = c_p1.slider("Años de proyección", 1, 25, 12)
        rent_bolsa = c_p2.slider("Bolsa (%)", 0, 15, 8)
        reval_inm = c_p3.slider("Inmuebles (%)", 0, 10, 3)
        interes_cash = c_p4.slider("💰 Interés Cash (%)", 0.0, 6.0, 3.5, step=0.1)
        pct_inflacion = c_p5.slider("🔥 Inflación (%)", 0.0, 8.0, 2.5, step=0.1)

        with st.expander("🎛️ CONFIGURAR MATRIX EVOLUTIVA ANUAL (EDITAR VALORES POR AÑO)", expanded=True):
            st.caption("Ajusta los flujos estimados para cada año futuro. Puedes simular subidas de salario, caídas de alquileres o compras indexadas.")
            anios_index = [f"Año {i}" for i in range(1, años_sim + 1)]
            data_matrix = {
                "Salario Neto Anual (€)": [int(salario_neto_base * 12)] * años_sim,
                "Rentas Inmo Anuales (€)": [int(total_rentas_pasivas_inmo * 12)] * años_sim,
                "Dividendos Anuales (€)": [int(total_dividendos_mensuales_bolsa * 12)] * años_sim,
                "Gastos Anuales Totales (€)": [int(gastos_vida_base * 12)] * años_sim,
                "Aportación Bolsa Extra (€/año)": [0] * años_sim,
                "Inversión Inmobiliaria Nueva (€/año)": [0] * años_sim
            }
            df_matrix_base = pd.DataFrame(data_matrix, index=anios_index)
            df_matrix_edited = st.data_editor(df_matrix_base, use_container_width=True)

        with st.expander("⚠️ CONFIGURAR ESCENARIOS DE CRISIS"):
            c_str1, c_str2 = st.columns(2)
            activar_crash = c_str1.checkbox("💥 Activar Crashes Bursátiles")
            lista_años_crashes = c_str1.multiselect("¿Años con Crash?", list(range(1, años_sim + 1)), default=[3]) if activar_crash else []
            caida_crash = c_str1.slider("Magnitud Caída (%)", 10, 60, 30, step=5) if activar_crash else 30
            
            activar_vacio = c_str2.checkbox("🏠 Activar Desocupación Inmobiliaria")
            lista_años_vacios = c_str2.multiselect("¿Años con vacío?", list(range(1, años_sim + 1)), default=[2]) if activar_vacio else []
            meses_vacio = c_str2.slider("Meses vacíos en esos años", 1, 12, 6) if activar_vacio else 6

        # --- BUCLE DE CÓMPUTO CIENTÍFICO FINANCIERO ---
        v_cash = float(categoria_cash)
        v_bolsa = float(total_bolsa)
        v_pensiones = float(categoria_pensiones)
        v_inmuebles = float(categoria_inmobiliario)
        v_otros_netos = float(categoria_otros - pasivo_total)
        
        hist_anios = [str(pd.Timestamp.now().year + i) for i in range(años_sim)]
        
        h_cash, h_bolsa, h_pensiones, h_inmuebles, h_otros, h_deflactado, h_nominal_total = [], [], [], [], [], [], []
        h_cf_ahorro_metalico, h_cf_dividendos, h_cf_rentas_inmo, h_cf_interes_acum, h_cf_gastos = [], [], [], [], []

        for idx, anio_label in enumerate(anios_index):
            salario_recibido = df_matrix_edited.loc[anio_label, "Salario Neto Anual (€)"]
            rentas_recibidas = df_matrix_edited.loc[anio_label, "Rentas Inmo Anuales (€)"]
            dividendos_recibidos = df_matrix_edited.loc[anio_label, "Dividendos Anuales (€)"]
            gastos_soportados = df_matrix_edited.loc[anio_label, "Gastos Anuales Totales (€)"]
            
            bolsa_extra = df_matrix_edited.loc[anio_label, "Aportación Bolsa Extra (€/año)"]
            inmo_extra = df_matrix_edited.loc[anio_label, "Inversión Inmobiliaria Nueva (€/año)"]
            
            if activar_vacio and ((idx + 1) in lista_años_vacios):
                rentas_recibidas *= (1.0 - (meses_vacio / 12.0))
            
            intereses_generados_este_anio = v_cash * (interes_cash / 100)
            ingresos_totales_anio = salario_recibido + rentas_recibidas + dividendos_recibidos + intereses_generados_este_anio
            excedente_de_caja_anio = ingresos_totales_anio - gastos_soportados - bolsa_extra - inmo_extra
            
            factor_deflactor = (1 + (pct_inflacion / 100)) ** idx
            
            h_cf_ahorro_metalico.append(max(0.0, salario_recibido) / factor_deflactor)
            h_cf_dividendos.append(dividendos_recibidos / factor_deflactor)
            h_cf_rentas_inmo.append(max(0.0, rentas_recibidas) / factor_deflactor)
            h_cf_interes_acum.append(intereses_generados_este_anio / factor_deflactor)
            h_cf_gastos.append(gastos_soportados / factor_deflactor)
            
            v_cash += excedente_de_caja_anio
            v_bolsa += bolsa_extra
            v_inmuebles += inmo_extra
            
            v_bolsa *= (1 + (rent_bolsa / 100))
            v_pensiones += (total_aportacion_mensual_pensiones * 12)
            v_pensiones *= (1 + (rent_bolsa / 100))
            v_inmuebles *= (1 + (reval_inm / 100))
            
            if activar_crash and ((idx + 1) in lista_años_crashes):
                v_bolsa *= (1.0 - (caida_crash / 100))
                v_pensiones *= (1.0 - (caida_crash / 100))
            
            patrimonio_nominal_total = v_cash + v_bolsa + v_pensiones + v_inmuebles + v_otros_netos
            patrimonio_deflactado = patrimonio_nominal_total / factor_deflactor
            
            h_cash.append(v_cash)
            h_bolsa.append(v_bolsa)
            h_pensiones.append(v_pensiones)
            h_inmuebles.append(v_inmuebles)
            h_otros.append(v_otros_netos)
            h_deflactado.append(patrimonio_deflactado)
            h_nominal_total.append(patrimonio_nominal_total)
            
        mes_cruze = -1
        for idx_c, valor_nom in enumerate(h_nominal_total):
            if valor_nom >= numero_fi:
                mes_cruze = idx_c
                break
        if mes_cruze != -1:
            st.success(f"💎 **Hito de Independencia Financiera Estimado:** Alcanzarás tu Número FI en el año **{hist_anios[mes_cruze]}** (dentro de {mes_cruze+1} años).")
        
        # --- GRÁFICO 1 TÍTULO COMPACTO EN 2 LÍNEAS (t=110) ---
        fig_sim = go.Figure()
        fig_sim.add_trace(go.Scatter(x=hist_anios, y=h_cash, mode='lines', name='💼 Cash / Liquidez', stackgroup='one', line=dict(color='#60A5FA', width=0.5)))
        fig_sim.add_trace(go.Scatter(x=hist_anios, y=h_bolsa, mode='lines', name='📈 Cartera Bolsa', stackgroup='one', line=dict(color='#A78BFA', width=0.5)))
        fig_sim.add_trace(go.Scatter(x=hist_anios, y=h_pensiones, mode='lines', name='🛡️ Planes Pensiones', stackgroup='one', line=dict(color='#FBBF24', width=0.5)))
        fig_sim.add_trace(go.Scatter(x=hist_anios, y=h_inmuebles, mode='lines', name='🏠 Patrimonio Inmobiliario', stackgroup='one', line=dict(color='#34D399', width=0.5)))
        fig_sim.add_trace(go.Scatter(x=hist_anios, y=h_otros, mode='lines', name='📦 Otros Netos', stackgroup='one', line=dict(color='#9CA3AF', width=0.5)))
        fig_sim.add_trace(go.Scatter(x=hist_anios, y=h_deflactado, mode='lines', name='📉 Neto Ajustado a Inflación', line=dict(color='#F87171', width=3, dash='dash')))
        fig_sim.add_trace(go.Scatter(x=hist_anios, y=[numero_fi]*años_sim, mode='lines', name='Target FI/RE', line=dict(color='#E5E7EB', width=2, dash='dot')))
        
        fig_sim.update_layout(
            template="plotly_dark", 
            title=dict(text="Trayectoria Patrimonial Compuesta<br>vs Meta de Independencia Financiera", y=0.96, x=0.5, xanchor="center"),
            margin=dict(t=110, b=160, l=40, r=40), 
            xaxis_title="Año", yaxis_title="Euros (€)",
            legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5),
            height=520
        )
        st.plotly_chart(fig_sim, use_container_width=True)

        st.divider()

        # --- GRÁFICO 2 TÍTULO COMPACTO EN 2 LÍNEAS (t=110) ---
        fig_bar_cf = go.Figure()
        fig_bar_cf.add_bar(x=hist_anios, y=h_cf_ahorro_metalico, name='🪙 Salario / Ingresos Activos', marker_color='#2563EB')
        fig_bar_cf.add_bar(x=hist_anios, y=h_cf_rentas_inmo, name='🏠 Rentas Inmobiliarias Netas', marker_color='#10B981')
        fig_bar_cf.add_bar(x=hist_anios, y=h_cf_dividendos, name='💸 Dividendos Bursátiles', marker_color='#8B5CF6')
        fig_bar_cf.add_bar(x=hist_anios, y=h_cf_interes_acum, name='💰 Intereses del Cash Ganados', marker_color='#F59E0B')
        fig_bar_cf.add_trace(go.Scatter(x=hist_anios, y=h_cf_gastos, mode='lines+markers', name='🔴 Gastos Anuales (Umbral de Vida)', line=dict(color='#EF4444', width=3)))

        fig_bar_cf.update_layout(
            barmode='stack',
            template="plotly_dark",
            title=dict(text="Análisis de Flujos de Caja Anuales Reales<br>(Ajustados a Inflación & Retorno Compuesto)", y=0.96, x=0.5, xanchor="center"),
            margin=dict(t=110, b=160, l=40, r=40),
            xaxis_title="Año",
            yaxis_title="Flujo de Efectivo Real (€ / año)",
            legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5),
            height=520
        )
        st.plotly_chart(fig_bar_cf, use_container_width=True)

# =====================================================================
# PESTAÑA 3: TAX ALPHA E IMPUESTOS
# =====================================================================
with tab_fiscalidad:
    st.header("📑 Planificación Fiscal y Tax Alpha")
    col_tax_inputs, col_tax_results = st.columns([1, 2])
    with col_tax_inputs:
        tipo_irpf_trabajo = st.slider("Tramo IRPF Salario (%)", 0, 50, 37)
        tipo_rentas_inm = st.slider("Impuesto Alquileres (%)", 0, 50, 20)
        tipo_capital_gains = st.slider("Rentas del Ahorro (%)", 0, 30, 21)
        
        plusvalia_b_automatica = st.session_state.plusvalia_bolsa_real
        st.markdown(f"📈 **Plusvalías Bursátiles Latentes (Auto):** `{int(plusvalia_b_automatica):,} €`")
        ganancia_inm_sim = st.number_input("Plusvalía estimada Venta Inmueble (€)", min_value=0.0, value=60000.0)
        st.info(f"🛡️ **Deducción por Planes de Pensiones (Base Imponible):** `{int(total_anual_deducible_pensiones_usuario):,} € / año` introducidos en Tab 2.")
        
    with col_tax_results:
        mordida_salario_anual_real = max(0.0, (salario_neto_base * 12) - total_anual_deducible_pensiones_usuario) * (tipo_irpf_trabajo / 100)
        mordida_alquiler_mes = (total_rentas_pasivas_inmo if total_rentas_pasivas_inmo > 0 else 0.0) * (tipo_rentas_inm / 100)
        m_total_rentas_anual_sim = mordida_salario_anual_real + (mordida_alquiler_mes * 12)
        
        peaje_fiscal_bolsa = plusvalia_b_automatica * (tipo_capital_gains / 100)
        peaje_fiscal_inm = ganancia_inm_sim * (tipo_capital_gains / 100)
        total_peaje_liquidar = peaje_fiscal_bolsa + peaje_fiscal_inm
        ahorro_fiscal_pensiones = total_anual_deducible_pensiones_usuario * (tipo_irpf_trabajo / 100)
        
        c_tx1, c_tx2 = st.columns(2)
        c_tx1.error(f"💸 FACTURA FISCAL ANUAL\n\n`{int(m_total_rentas_anual_sim):,} € / año` s/flujos.")
        c_tx2.warning(f"🧾 PEAJE FISCAL POR LIQUIDAR\n\n`{int(total_peaje_liquidar):,} €` s/plusvalías.")
        if ahorro_fiscal_pensiones > 0:
            st.success(f"🚀 **Tax Alpha Generado:** Tu estrategia de aportación a planes reduce tu factura fiscal del IRPF en **`{int(ahorro_fiscal_pensiones):,} € / año`**.")

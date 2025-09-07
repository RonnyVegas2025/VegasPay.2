
import streamlit as st
import pandas as pd
from io import BytesIO
from helpers import normalize_fechamento, normalize_novos

st.title("📤 Upload")

st.markdown("Envie abaixo os arquivos para esta **sessão**. Eles ficam disponíveis nas demais páginas.")

col1, col2 = st.columns(2)
with col1:
    f_fech = st.file_uploader("Fechamento consolidado — .xlsx", type=["xlsx"], key="fech")
with col2:
    f_novos = st.file_uploader("Novos Comércios — .xlsx", type=["xlsx"], key="novos")

if st.button("Carregar arquivos"):
    try:
        df_fech = pd.read_excel(f_fech) if f_fech else None
        if df_fech is not None:
            df_fech = normalize_fechamento(df_fech)
        st.session_state['fechamento_df'] = df_fech
    except Exception as e:
        st.error(f"Fechamento: erro ao ler: {e}")

    try:
        df_novos = pd.read_excel(f_novos) if f_novos else None
        if df_novos is not None:
            df_novos = normalize_novos(df_novos)
        st.session_state['novos_df'] = df_novos
    except Exception as e:
        st.error(f"Novos Comércios: erro ao ler: {e}")

    st.success("Arquivos carregados para a sessão. Vá para **📊 Vendas & MDR** ou **🆕 Novos Comércios**.")

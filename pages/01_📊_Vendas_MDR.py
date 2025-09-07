
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from helpers import fmt_brl, fmt_pct, normalize_fechamento

st.title("📊 Vendas & MDR — Bloco 1")

df = st.session_state.get('fechamento_df')
if df is None:
    st.info("Envie o **Fechamento consolidado** em **📤 Upload** para visualizar esta página.")
    st.stop()

# ---- Filtros ----
cols = st.columns(5)
with cols[0]:
    mes_sel = st.multiselect("Mês", sorted(df["Mes"].dropna().unique().tolist()) if "Mes" in df.columns else [])
with cols[1]:
    vend_sel = st.multiselect("Vendedor", sorted(df["Vendedor"].dropna().unique().tolist()) if "Vendedor" in df.columns else [])
with cols[2]:
    band_sel = st.multiselect("Bandeira", sorted(df["Bandeira"].dropna().unique().tolist()) if "Bandeira" in df.columns else [])
with cols[3]:
    prod_sel = st.multiselect("Produto", sorted(df["Produto"].dropna().unique().tolist()) if "Produto" in df.columns else [])
with cols[4]:
    cat_sel = st.multiselect("Categoria MCC", sorted(df["Categoria_MCC"].dropna().unique().tolist()) if "Categoria_MCC" in df.columns else [])

base = df.copy()
if 'Mes' in base and mes_sel: base = base[base["Mes"].isin(mes_sel)]
if 'Vendedor' in base and vend_sel: base = base[base["Vendedor"].isin(vend_sel)]
if 'Bandeira' in base and band_sel: base = base[base["Bandeira"].isin(band_sel)]
if 'Produto' in base and prod_sel: base = base[base["Produto"].isin(prod_sel)]
if 'Categoria_MCC' in base and cat_sel: base = base[base["Categoria_MCC"].isin(cat_sel)]

total_vendas = float(base.get("Valor", pd.Series()).sum())
mdr_bruto_r  = float(base.get("MDR (R$) Bruto", pd.Series()).sum())
mdr_liq_tot  = float(base.get("Total MDR (R$) Liquido Vegas Pay", pd.Series()).sum())

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Vendas Brutas (R$)", fmt_brl(total_vendas))
c2.metric("MDR Bruto (R$)", fmt_brl(mdr_bruto_r))
c3.metric("MDR Bruto (%)", fmt_pct((mdr_bruto_r/total_vendas*100) if total_vendas else 0))
c4.metric("MDR Líquido (R$)", fmt_brl(mdr_liq_tot))
c5.metric("MDR Líquido (%)", fmt_pct((mdr_liq_tot/total_vendas*100) if total_vendas else 0))

st.divider()

# Resumo mensal
res_mes = pd.DataFrame()
if "Mes" in base.columns:
    res_mes = base.groupby("Mes", as_index=False).agg(
        **{
            "Vendas_Brutas_R$": ("Valor","sum"),
            "MDR_Bruto_R$": ("MDR (R$) Bruto","sum"),
            "MDR_Liq_Cartoes_R$": ("MDR (R$) Liquido Cartões","sum"),
            "MDR_Liq_Antecip_R$": ("MDR (R$) Liquido Antecipação","sum"),
            "MDR_Liq_PIX_R$": ("MDR (R$) Liquido Pix","sum"),
            "MDR_Liq_Total_R$": ("Total MDR (R$) Liquido Vegas Pay","sum"),
        }
    )
    res_mes["MDR_Bruto_%"] = (res_mes["MDR_Bruto_R$"]/res_mes["Vendas_Brutas_R$"]*100).replace([pd.NA, pd.NaT, float('inf')], 0).fillna(0)
    res_mes["MDR_Líquido_%"] = (res_mes["MDR_Liq_Total_R$"]/res_mes["Vendas_Brutas_R$"]*100).replace([pd.NA, pd.NaT, float('inf')], 0).fillna(0)

st.subheader("Resumo Mensal")
st.dataframe(res_mes.style.format({
    "Vendas_Brutas_R$": fmt_brl, "MDR_Bruto_R$": fmt_brl,
    "MDR_Liq_Cartoes_R$": fmt_brl, "MDR_Liq_Antecip_R$": fmt_brl, "MDR_Liq_PIX_R$": fmt_brl,
    "MDR_Liq_Total_R$": fmt_brl, "MDR_Bruto_%": fmt_pct, "MDR_Líquido_%": fmt_pct
}), use_container_width=True)

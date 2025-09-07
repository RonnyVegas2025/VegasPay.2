
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from helpers import fmt_brl, fmt_pct, ensure_month_str, normalize_novos

st.title("🆕 Novos Comércios — Bloco 2")

df = st.session_state.get('novos_df')
if df is None:
    st.info("Envie o arquivo **Novos Comércios** em **📤 Upload** para visualizar esta página.")
    st.stop()

# base normalized already
base = df.copy()

# optional realized merge, if Fechamento present with CNPJ+Mes+Valor
fech = st.session_state.get('fechamento_df')
realizado = None
if fech is not None and all(c in fech.columns for c in ["CNPJ","Mes","Valor"]):
    # normalize CNPJ numeric
    f2 = fech.copy()
    f2["CNPJ"] = f2["CNPJ"].astype(str).str.replace(r"\D","", regex=True)
    realizado = f2.groupby(["Mes","CNPJ"], as_index=False)["Valor"].sum()
    realizado.rename(columns={"Valor":"Realizado_R$"}, inplace=True)
    base = base.merge(realizado, how="left", on=["Mes","CNPJ"])
    base["Realizado_R$"] = base["Realizado_R$"].fillna(0.0)
else:
    base["Realizado_R$"] = 0.0

# Filters
cols = st.columns(5)
with cols[0]:
    mes_sel = st.multiselect("Mês (cadastro)", sorted(base["Mes"].dropna().unique().tolist()) if "Mes" in base.columns else [])
with cols[1]:
    vend_sel = st.multiselect("Vendedor", sorted(base["Vendedor"].dropna().unique().tolist()) if "Vendedor" in base.columns else [])
with cols[2]:
    uf_sel = st.multiselect("UF", sorted(base["UF"].dropna().unique().tolist()) if "UF" in base.columns else [])
with cols[3]:
    mcc_sel = st.multiselect("MCC", sorted(base["MCC"].dropna().unique().tolist()) if "MCC" in base.columns else [])
with cols[4]:
    cat_sel = st.multiselect("Categoria MCC", sorted(base["Categoria_MCC"].dropna().unique().tolist()) if "Categoria_MCC" in base.columns else [])

f = base.copy()
if mes_sel: f = f[f["Mes"].isin(mes_sel)]
if vend_sel: f = f[f["Vendedor"].isin(vend_sel)]
if uf_sel and "UF" in f.columns: f = f[f["UF"].isin(uf_sel)]
if mcc_sel and "MCC" in f.columns: f = f[f["MCC"].isin(mcc_sel)]
if cat_sel and "Categoria_MCC" in f.columns: f = f[f["Categoria_MCC"].isin(cat_sel)]

# KPIs
qtde = len(f)
prev = float(f.get("Previsão de Mov. Financeira", pd.Series()).sum())
meta70 = float(f.get("Meta 70% da Movimentação ", pd.Series()).sum())
real = float(f.get("Realizado_R$", pd.Series()).sum())
ating = (real/meta70*100) if meta70>0 else 0.0

c1,c2,c3,c4 = st.columns(4)
c1.metric("Qtd. Novos Comércios", f"{qtde:,}".replace(",","."))
c2.metric("Previsão Total (R$)", fmt_brl(prev))
c3.metric("Meta 70% (R$)", fmt_brl(meta70))
c4.metric("Realizado (R$)", fmt_brl(real))

st.metric("Atingimento Meta 70% (%)", fmt_pct(ating))

st.divider()

# Tabela detalhada
cols_show = ["Mes","FANTASIA","CNPJ","Vendedor","UF","MCC","Categoria_MCC","Previsão de Mov. Financeira","Meta 70% da Movimentação ","Realizado_R$"]
cols_show = [c for c in cols_show if c in f.columns]
st.dataframe(
    f[cols_show].style.format({
        "Previsão de Mov. Financeira": fmt_brl,
        "Meta 70% da Movimentação ": fmt_brl,
        "Realizado_R$": fmt_brl
    }),
    use_container_width=True
)

# Resumo por vendedor
if "Vendedor" in f.columns:
    res_v = f.groupby("Vendedor", as_index=False).agg(
        **{
            "Qtd": ("CNPJ","count"),
            "Previsão_R$": ("Previsão de Mov. Financeira","sum"),
            "Meta70_R$": ("Meta 70% da Movimentação ","sum"),
            "Realizado_R$": ("Realizado_R$","sum"),
        }
    )
    res_v["Atingimento_%"] = np.where(res_v["Meta70_R$"]>0, res_v["Realizado_R$"]/res_v["Meta70_R$"]*100, 0.0)
    st.subheader("Resumo por Vendedor")
    st.dataframe(res_v.style.format({
        "Previsão_R$": fmt_brl, "Meta70_R$": fmt_brl,
        "Realizado_R$": fmt_brl, "Atingimento_%": fmt_pct
    }), use_container_width=True)

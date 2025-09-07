
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="VegasPay — Vendas & MDR (Bloco 1)", layout="wide")

# ---------------------- Helpers ----------------------
def fmt_brl(v):
    try:
        return "R$ {:,.2f}".format(float(v)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return v

def fmt_pct(v):
    try:
        return "{:,.2f}%".format(float(v)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return v

@st.cache_data(show_spinner=False)
def carregar_excel(file):
    # Aceita .xlsx enviado pelo uploader; tenta ler "Planilha1" e, se não existir, a primeira aba
    xls = pd.ExcelFile(file)
    sheet = "Planilha1"
    if sheet not in xls.sheet_names:
        sheet = xls.sheet_names[0]
    df = xls.parse(sheet)
    return df

def normalizar_campos(df):
    # Padroniza nomes esperados
    rename_map = {
        "Mês Referencia": "Mes",
        "MCC - Categoria": "Categoria_MCC",
        "Preposto": "Vendedor",
    }
    df = df.rename(columns=rename_map)

    # Garante colunas-chave
    expected = ["Mes","Valor","Bandeira","Produto","Vendedor",
                "MDR (R$) Bruto","MDR (R$) Liquido Cartões","MDR (R$) Liquido Antecipação","MDR (R$) Liquido Pix",
                "Total MDR (R$) Liquido Vegas Pay","Categoria_MCC"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        st.warning("Colunas ausentes: " + ", ".join(missing))

    # Tipos numéricos
    for c in ["Valor","MDR (R$) Bruto","MDR (R$) Liquido Cartões","MDR (R$) Liquido Antecipação",
              "MDR (R$) Liquido Pix","Total MDR (R$) Liquido Vegas Pay"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # Mes como string (YYYY-MM quando possível)
    if "Mes" in df.columns:
        try:
            df["Mes"] = pd.to_datetime(df["Mes"], errors="coerce").dt.to_period("M").astype(str).fillna(df["Mes"].astype(str))
        except Exception:
            df["Mes"] = df["Mes"].astype(str)

    # Normaliza texto
    for c in ["Bandeira","Produto","Vendedor","Categoria_MCC"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    return df

def calcular_resumos(base):
    # Resumo Mensal
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
    res_mes["MDR_Bruto_%"] = np.where(res_mes["Vendas_Brutas_R$"]>0, res_mes["MDR_Bruto_R$"]/res_mes["Vendas_Brutas_R$"]*100, 0.0)
    res_mes["MDR_Líquido_%"] = np.where(res_mes["Vendas_Brutas_R$"]>0, res_mes["MDR_Liq_Total_R$"]/res_mes["Vendas_Brutas_R$"]*100, 0.0)

    # Resumo por Vendedor
    if "Vendedor" in base.columns:
        res_vend = base.groupby(["Mes","Vendedor"], as_index=False).agg(
            **{
                "Vendas_Brutas_R$": ("Valor","sum"),
                "MDR_Bruto_R$": ("MDR (R$) Bruto","sum"),
                "MDR_Liq_Total_R$": ("Total MDR (R$) Liquido Vegas Pay","sum"),
            }
        )
        res_vend["MDR_Líquido_%"] = np.where(res_vend["Vendas_Brutas_R$"]>0, res_vend["MDR_Liq_Total_R$"]/res_vend["Vendas_Brutas_R$"]*100, 0.0)
    else:
        res_vend = pd.DataFrame()

    # Resumo por Bandeira/Produto
    res_bp = base.groupby(["Mes","Bandeira","Produto"], as_index=False).agg(
        **{
            "Vendas_Brutas_R$": ("Valor","sum"),
            "MDR_Bruto_R$": ("MDR (R$) Bruto","sum"),
            "MDR_Liq_Total_R$": ("Total MDR (R$) Liquido Vegas Pay","sum"),
        }
    )
    res_bp["MDR_Líquido_%"] = np.where(res_bp["Vendas_Brutas_R$"]>0, res_bp["MDR_Liq_Total_R$"]/res_bp["Vendas_Brutas_R$"]*100, 0.0)

    return res_mes, res_vend, res_bp

# ---------------------- UI ----------------------
st.title("🧮 Bloco 1 — Vendas & MDR")

with st.expander("Como usar", expanded=True):
    st.markdown("""
    - Envie o **Excel de Fechamento** (mesmo formato da planilha que você me mandou).
    - O app **não recalcula** regras — usa as colunas **líquidas e brutas** já existentes.
    - Depois você pode filtrar por **Mês / Vendedor / Bandeira / Produto / Categoria**.
    - Ao final, pode **baixar um Excel** com os resumos.
    """)

upload = st.file_uploader("Envie o arquivo .xlsx", type=["xlsx"])

if not upload:
    st.info("Aguardando arquivo...")
    st.stop()

df = carregar_excel(upload)
df = normalizar_campos(df)

# Filtros
cols = st.columns(5)
with cols[0]:
    mes_sel = st.multiselect("Mês", sorted(df["Mes"].dropna().unique().tolist()))
with cols[1]:
    vend_sel = st.multiselect("Vendedor", sorted(df["Vendedor"].dropna().unique().tolist()) if "Vendedor" in df.columns else [])
with cols[2]:
    band_sel = st.multiselect("Bandeira", sorted(df["Bandeira"].dropna().unique().tolist()))
with cols[3]:
    prod_sel = st.multiselect("Produto", sorted(df["Produto"].dropna().unique().tolist()))
with cols[4]:
    cat_sel = st.multiselect("Categoria MCC", sorted(df["Categoria_MCC"].dropna().unique().tolist()) if "Categoria_MCC" in df.columns else [])

base = df.copy()
if mes_sel:  base = base[base["Mes"].isin(mes_sel)]
if vend_sel and "Vendedor" in base.columns: base = base[base["Vendedor"].isin(vend_sel)]
if band_sel: base = base[base["Bandeira"].isin(band_sel)]
if prod_sel: base = base[base["Produto"].isin(prod_sel)]
if cat_sel and "Categoria_MCC" in base.columns: base = base[base["Categoria_MCC"].isin(cat_sel)]

# KPIs principais (filtrados)
total_vendas = float(base["Valor"].sum()) if "Valor" in base.columns else 0.0
mdr_bruto_r  = float(base["MDR (R$) Bruto"].sum()) if "MDR (R$) Bruto" in base.columns else 0.0
mdr_liq_tot  = float(base["Total MDR (R$) Liquido Vegas Pay"].sum()) if "Total MDR (R$) Liquido Vegas Pay" in base.columns else 0.0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Vendas Brutas (R$)", fmt_brl(total_vendas))
c2.metric("MDR Bruto (R$)", fmt_brl(mdr_bruto_r))
c3.metric("MDR Bruto (%)", fmt_pct((mdr_bruto_r/total_vendas*100) if total_vendas else 0))
c4.metric("MDR Líquido (R$)", fmt_brl(mdr_liq_tot))
c5.metric("MDR Líquido (%)", fmt_pct((mdr_liq_tot/total_vendas*100) if total_vendas else 0))

st.divider()

# Resumos
res_mes, res_vend, res_bp = calcular_resumos(base)

st.subheader("Resumo Mensal")
st.dataframe(
    res_mes.style.format({
        "Vendas_Brutas_R$": fmt_brl, "MDR_Bruto_R$": fmt_brl,
        "MDR_Liq_Cartoes_R$": fmt_brl, "MDR_Liq_Antecip_R$": fmt_brl, "MDR_Liq_PIX_R$": fmt_brl,
        "MDR_Liq_Total_R$": fmt_brl, "MDR_Bruto_%": fmt_pct, "MDR_Líquido_%": fmt_pct
    }),
    use_container_width=True
)

st.subheader("Resumo por Vendedor")
st.dataframe(
    res_vend.style.format({
        "Vendas_Brutas_R$": fmt_brl, "MDR_Bruto_R$": fmt_brl,
        "MDR_Liq_Total_R$": fmt_brl, "MDR_Líquido_%": fmt_pct
    }),
    use_container_width=True
)

st.subheader("Resumo por Bandeira / Produto")
st.dataframe(
    res_bp.style.format({
        "Vendas_Brutas_R$": fmt_brl, "MDR_Bruto_R$": fmt_brl,
        "MDR_Liq_Total_R$": fmt_brl, "MDR_Líquido_%": fmt_pct
    }),
    use_container_width=True
)

# Exportação
buffer = BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    base.to_excel(writer, sheet_name="Base_Filtrada", index=False)
    res_mes.to_excel(writer, sheet_name="Resumo_Mensal", index=False)
    res_vend.to_excel(writer, sheet_name="Resumo_Vendedor", index=False)
    res_bp.to_excel(writer, sheet_name="Resumo_Bandeira_Produto", index=False)

st.download_button("📥 Baixar Excel (filtro atual)",
                   data=buffer.getvalue(),
                   file_name="vegaspay_bloco1_vendas_mdr.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

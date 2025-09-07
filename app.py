
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="VegasPay — Gestão & Acompanhamento (Single File)", layout="wide")

# =========================
# Helpers
# =========================
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

def ensure_month_str(s):
    return pd.to_datetime(s, errors="coerce").dt.to_period("M").astype(str)

def strip_accents_upper(s: pd.Series) -> pd.Series:
    # remove acentos sem depender de unidecode
    try:
        return (s.astype(str)
                  .str.normalize("NFKD")
                  .str.encode("ascii", "ignore")
                  .str.decode("utf-8")
                  .str.upper()
                  .str.strip())
    except Exception:
        return s.astype(str).str.upper().str.strip()

@st.cache_data(show_spinner=False)
def carregar_excel(file):
    # Lê um .xlsx tentando a aba 'Planilha1', senão pega a primeira.
    xls = pd.ExcelFile(file)
    sheet = "Planilha1" if "Planilha1" in xls.sheet_names else xls.sheet_names[0]
    df = xls.parse(sheet)
    return df

def normalize_fechamento(df):
    # Padroniza fechamento consolidado (planilha que você me enviou).
    rename_map = {
        "Mês Referencia": "Mes",
        "MCC - Categoria": "Categoria_MCC",
        "Preposto": "Vendedor",
    }
    df = df.rename(columns=rename_map).copy()

    # numéricos
    for c in ["Valor","MDR (R$) Bruto","MDR (R$) Liquido Cartões","MDR (R$) Liquido Antecipação",
              "MDR (R$) Liquido Pix","Total MDR (R$) Liquido Vegas Pay"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # mês
    if "Mes" in df.columns:
        try:
            df["Mes"] = ensure_month_str(df["Mes"])
        except Exception:
            df["Mes"] = df["Mes"].astype(str)

    # limpeza de texto
    for c in ["Bandeira","Produto","Vendedor","Categoria_MCC","CNPJ","Estabelecimento","Nome_Fantasia"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    return df

def normalize_novos(df):
    # Padroniza planilha de Novos Comércios (arquivo que você enviou).
    df = df.rename(columns={"Categoria MCC": "Categoria_MCC"}).copy()

    # numéricos
    for c in ["Previsão de Mov. Financeira","Meta 70% da Movimentação "]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # mês de cadastro
    if "Data de Cadastro" in df.columns:
        df["Mes"] = ensure_month_str(df["Data de Cadastro"])

    # limpeza de texto
    for c in ["CNPJ","FANTASIA","MCC","Categoria_MCC","Cidade","UF","Vendedor"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    # CNPJ só dígitos
    if "CNPJ" in df.columns:
        df["CNPJ"] = df["CNPJ"].str.replace(r"\D", "", regex=True)

    return df

def resumo_vendas(base: pd.DataFrame):
    # Gera resumos (mensal, vendedor, bandeira/produto).
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
    res_bp = pd.DataFrame()
    if all(c in base.columns for c in ["Bandeira","Produto"]):
        res_bp = base.groupby(["Mes","Bandeira","Produto"], as_index=False).agg(
            **{
                "Vendas_Brutas_R$": ("Valor","sum"),
                "MDR_Bruto_R$": ("MDR (R$) Bruto","sum"),
                "MDR_Liq_Total_R$": ("Total MDR (R$) Liquido Vegas Pay","sum"),
            }
        )
        res_bp["MDR_Líquido_%"] = np.where(res_bp["Vendas_Brutas_R$"]>0, res_bp["MDR_Liq_Total_R$"]/res_bp["Vendas_Brutas_R$"]*100, 0.0)

    return res_mes, res_vend, res_bp

def cruzar_realizado(novos: pd.DataFrame, fech: pd.DataFrame) -> pd.DataFrame:
    """Casar Realizado (R$) por CNPJ+Mes; se não tiver CNPJ no fechamento, tenta por nome fantasia.
       Evita conflito de nomes usando coluna auxiliar 'Realizado_Match_R$' no merge.
    """
    base = novos.copy()
    base["Realizado_R$"] = 0.0

    if fech is None or len(fech) == 0:
        return base

    # 1) Por CNPJ + Mes
    if {"CNPJ", "Mes", "Valor"}.issubset(fech.columns):
        f2 = fech[["CNPJ", "Mes", "Valor"]].copy()
        f2["CNPJ"] = f2["CNPJ"].astype(str).str.replace(r"\D", "", regex=True)
        g = (f2.groupby(["Mes", "CNPJ"], as_index=False)["Valor"]
               .sum().rename(columns={"Valor": "Realizado_Match_R$"}))
        m = base.merge(g, how="left", on=["Mes", "CNPJ"])
        m["Realizado_R$"] = m["Realizado_R$"].fillna(0.0) + m["Realizado_Match_R$"].fillna(0.0)
        m.drop(columns=["Realizado_Match_R$"], inplace=True)
        return m

    # 2) Por Fantasia/Estabelecimento (normalizando texto)
    name_cols = [c for c in ["FANTASIA", "Nome_Fantasia", "Estabelecimento"] if c in base.columns]
    fech_name_col = next((c for c in ["Nome_Fantasia", "Estabelecimento"] if c in fech.columns), None)

    if name_cols and fech_name_col and {"Mes", "Valor"}.issubset(fech.columns):
        ncol = name_cols[0]
        f2 = fech[[fech_name_col, "Mes", "Valor"]].copy()
        f2[fech_name_col + "_NORM"] = strip_accents_upper(f2[fech_name_col])
        g = (f2.groupby(["Mes", fech_name_col + "_NORM"], as_index=False)["Valor"]
               .sum().rename(columns={"Valor": "Realizado_Match_R$"}))

        m = base.copy()
        m[ncol + "_NORM"] = strip_accents_upper(m[ncol])
        m = m.merge(g, how="left",
                    left_on=["Mes", ncol + "_NORM"],
                    right_on=["Mes", fech_name_col + "_NORM"])
        m["Realizado_R$"] = m["Realizado_R$"].fillna(0.0) + m["Realizado_Match_R$"].fillna(0.0)
        m.drop(columns=[ncol + "_NORM", fech_name_col + "_NORM", "Realizado_Match_R$"], errors="ignore", inplace=True)
        return m

    return base


# =========================
# Navegação (sidebar)
# =========================
page = st.sidebar.radio("Navegação", ["📤 Upload", "📊 Vendas & MDR", "🆕 Novos Comércios"])

# =========================
# Página: Upload
# =========================
if page == "📤 Upload":
    st.title("📤 Upload de Arquivos (Sessão)")

    col1, col2 = st.columns(2)
    with col1:
        f_fech = st.file_uploader("Fechamento consolidado — .xlsx", type=["xlsx"], key="fech")
    with col2:
        f_novos = st.file_uploader("Novos Comércios — .xlsx", type=["xlsx"], key="novos")

    if st.button("Carregar arquivos"):
        try:
            df_fech = carregar_excel(f_fech) if f_fech is not None else None
            if df_fech is not None:
                df_fech = normalize_fechamento(df_fech)
            st.session_state["fechamento_df"] = df_fech
        except Exception as e:
            st.error(f"Fechamento: erro ao ler ({e})")

        try:
            df_novos = carregar_excel(f_novos) if f_novos is not None else None
            if df_novos is not None:
                df_novos = normalize_novos(df_novos)
            st.session_state["novos_df"] = df_novos
        except Exception as e:
            st.error(f"Novos Comércios: erro ao ler ({e})")

        st.success("Arquivos carregados para a sessão! Agora abra **📊 Vendas & MDR** e **🆕 Novos Comércios**.")

# =========================
# Página: Vendas & MDR (Bloco 1)
# =========================
elif page == "📊 Vendas & MDR":
    st.title("📊 Gestão e Acompanhamento — Vegas Pay")

    df = st.session_state.get("fechamento_df")

    if df is None:
        st.info("Envie o **Fechamento consolidado** na página **📤 Upload**.")
        st.stop()

    # Filtros
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
    if "Mes" in base.columns and mes_sel: base = base[base["Mes"].isin(mes_sel)]
    if "Vendedor" in base.columns and vend_sel: base = base[base["Vendedor"].isin(vend_sel)]
    if "Bandeira" in base.columns and band_sel: base = base[base["Bandeira"].isin(band_sel)]
    if "Produto" in base.columns and prod_sel: base = base[base["Produto"].isin(prod_sel)]
    if "Categoria_MCC" in base.columns and cat_sel: base = base[base["Categoria_MCC"].isin(cat_sel)]

    total_vendas = float(base.get("Valor", pd.Series(dtype=float)).sum())
    mdr_bruto_r  = float(base.get("MDR (R$) Bruto", pd.Series(dtype=float)).sum())
    mdr_liq_tot  = float(base.get("Total MDR (R$) Liquido Vegas Pay", pd.Series(dtype=float)).sum())

    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric("Vendas Brutas (R$)", fmt_brl(total_vendas))
    k2.metric("MDR Bruto (R$)", fmt_brl(mdr_bruto_r))
    k3.metric("MDR Bruto (%)", fmt_pct((mdr_bruto_r/total_vendas*100) if total_vendas>0 else 0.0))
    k4.metric("MDR Líquido (R$)", fmt_brl(mdr_liq_tot))
    k5.metric("MDR Líquido (%)", fmt_pct((mdr_liq_tot/total_vendas*100) if total_vendas>0 else 0.0))

    st.divider()

    res_mes, res_vend, res_bp = resumo_vendas(base)

    st.subheader("Resumo Mensal")
    st.dataframe(res_mes.style.format({
        "Vendas_Brutas_R$": fmt_brl, "MDR_Bruto_R$": fmt_brl,
        "MDR_Liq_Cartoes_R$": fmt_brl, "MDR_Liq_Antecip_R$": fmt_brl, "MDR_Liq_PIX_R$": fmt_brl,
        "MDR_Liq_Total_R$": fmt_brl, "MDR_Bruto_%": fmt_pct, "MDR_Líquido_%": fmt_pct
    }), use_container_width=True)

    if not res_vend.empty:
        st.subheader("Resumo por Vendedor")
        st.dataframe(res_vend.style.format({
            "Vendas_Brutas_R$": fmt_brl, "MDR_Bruto_R$": fmt_brl,
            "MDR_Liq_Total_R$": fmt_brl, "MDR_Líquido_%": fmt_pct
        }), use_container_width=True)

    if not res_bp.empty:
        st.subheader("Resumo por Bandeira / Produto")
        st.dataframe(res_bp.style.format({
            "Vendas_Brutas_R$": fmt_brl, "MDR_Bruto_R$": fmt_brl,
            "MDR_Liq_Total_R$": fmt_brl, "MDR_Líquido_%": fmt_pct
        }), use_container_width=True)

    # Exportar
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        base.to_excel(writer, sheet_name="Base_Filtrada", index=False)
        res_mes.to_excel(writer, sheet_name="Resumo_Mensal", index=False)
        if not res_vend.empty: res_vend.to_excel(writer, sheet_name="Resumo_Vendedor", index=False)
        if not res_bp.empty:   res_bp.to_excel(writer, sheet_name="Resumo_Bandeira_Produto", index=False)

    st.download_button("📥 Baixar Excel (Vendas & MDR / filtro atual)",
                       data=buffer.getvalue(),
                       file_name="vegaspay_vendas_mdr.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =========================
# Página: Novos Comércios (Bloco 2)
# =========================
elif page == "🆕 Novos Comércios":
    st.title("🆕 Novos Comércios")

    df_nov = st.session_state.get("novos_df")
    if df_nov is None:
        st.info("Envie o arquivo **Novos Comércios** na página **📤 Upload**.")
        st.stop()

    df_fech = st.session_state.get("fechamento_df")

    base = cruzar_realizado(df_nov, df_fech)

    # Filtros
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
    if vend_sel and "Vendedor" in f.columns: f = f[f["Vendedor"].isin(vend_sel)]
    if uf_sel   and "UF" in f.columns:       f = f[f["UF"].isin(uf_sel)]
    if mcc_sel  and "MCC" in f.columns:      f = f[f["MCC"].isin(mcc_sel)]
    if cat_sel  and "Categoria_MCC" in f.columns: f = f[f["Categoria_MCC"].isin(cat_sel)]

    # KPIs
    qtde = len(f)
    prev = float(f.get("Previsão de Mov. Financeira", pd.Series(dtype=float)).sum())
    meta70 = float(f.get("Meta 70% da Movimentação ", pd.Series(dtype=float)).sum())
    real = float(f.get("Realizado_R$", pd.Series(dtype=float)).sum())
    ating = (real/meta70*100) if meta70>0 else 0.0

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Qtd. Novos Comércios", f"{qtde:,}".replace(",","."))
    c2.metric("Previsão Total (R$)", fmt_brl(prev))
    c3.metric("Meta 70% (R$)", fmt_brl(meta70))
    c4.metric("Realizado (R$)", fmt_brl(real))
    st.metric("Atingimento Meta 70% (%)", fmt_pct(ating))

    st.divider()

    # Tabela detalhada
    cols_show = ["Mes","FANTASIA","CNPJ","Vendedor","UF","MCC","Categoria_MCC",
                 "Previsão de Mov. Financeira","Meta 70% da Movimentação ","Realizado_R$"]
    cols_show = [c for c in cols_show if c in f.columns]
    st.dataframe(f[cols_show].style.format({
        "Previsão de Mov. Financeira": fmt_brl,
        "Meta 70% da Movimentação ": fmt_brl,
        "Realizado_R$": fmt_brl
    }), use_container_width=True)

    # Resumo por Vendedor
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

    # Exportar
    buff2 = BytesIO()
    with pd.ExcelWriter(buff2, engine="openpyxl") as writer:
        f.to_excel(writer, sheet_name="Novos_Filtrado", index=False)
        if "Vendedor" in f.columns:
            res_v.to_excel(writer, sheet_name="Resumo_Vendedor", index=False)
    st.download_button("📥 Baixar Excel (Novos Comércios / filtro atual)",
                       data=buff2.getvalue(),
                       file_name="vegaspay_novos_comercios.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

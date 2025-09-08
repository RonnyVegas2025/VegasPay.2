
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from pathlib import Path

# =======================================
# Config
# =======================================
st.set_page_config(page_title="Gestão e Acompanhamento — Vegas Pay", layout="wide")

APP_TITLE = "Gestão e Acompanhamento — Vegas Pay"

BASE_DIR = Path(__file__).parent
FECH_PATH  = BASE_DIR / "dados" / "Fechamento.xlsx"
NOVOS_PATH = BASE_DIR / "dados" / "Novos_Comercios.xlsx"

# =======================================
# Helpers
# =======================================
def header(subtitle: str = ""):
    st.title(APP_TITLE)
    if subtitle:
        st.caption(subtitle)

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
    try:
        return (s.astype(str)
                  .str.normalize("NFKD")
                  .str.encode("ascii", "ignore")
                  .str.decode("utf-8")
                  .str.upper()
                  .str.strip())
    except Exception:
        return s.astype(str).str.upper().str.strip()

def pick_col(df: pd.DataFrame, candidates):
    return next((c for c in candidates if c in df.columns), None)

@st.cache_data(show_spinner=False)
def carregar_excel(file):
    xls = pd.ExcelFile(file)
    sheet = "Planilha1" if "Planilha1" in xls.sheet_names else xls.sheet_names[0]
    df = xls.parse(sheet)
    return df

def normalize_fechamento(df):
    rename_map = {
        "Mês Referencia": "Mes",
        "MCC - Categoria": "Categoria_MCC",
        "Preposto": "Vendedor",
        "CNPJ Estabelecimento": "CNPJ",
        "Estabelecimento": "Nome_Fantasia",
    }
    df = df.rename(columns=rename_map).copy()

    # Tipos
    for c in ["Valor","MDR (R$) Bruto","MDR (R$) Liquido Cartões","MDR (R$) Liquido Antecipação",
              "MDR (R$) Liquido Pix","Total MDR (R$) Liquido Vegas Pay"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # Mês
    if "Mes" in df.columns:
        try:
            df["Mes"] = ensure_month_str(df["Mes"])
        except Exception:
            df["Mes"] = df["Mes"].astype(str)

    # Texto
    for c in ["Bandeira","Produto","Vendedor","Categoria_MCC","CNPJ","Nome_Fantasia","Cidade","UF"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    # CNPJ só dígitos
    if "CNPJ" in df.columns:
        df["CNPJ"] = df["CNPJ"].str.replace(r"\D", "", regex=True)

    return df

def normalize_novos(df):
    df = df.rename(columns={"Categoria MCC": "Categoria_MCC"}).copy()

    # numéricos (suporta col meta com ou sem espaço final)
    meta_col = pick_col(df, ["Meta 70% da Movimentação ", "Meta 70% da Movimentação"])
    if "Previsão de Mov. Financeira" in df.columns:
        df["Previsão de Mov. Financeira"] = pd.to_numeric(df["Previsão de Mov. Financeira"], errors="coerce").fillna(0.0)
    if meta_col:
        df[meta_col] = pd.to_numeric(df[meta_col], errors="coerce").fillna(0.0)

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
       Usa coluna auxiliar 'Realizado_Match_R$' para evitar conflitos de nomes.
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

    # 2) Por Fantasia/Estabelecimento
    name_cols = [c for c in ["FANTASIA", "Nome_Fantasia"] if c in base.columns]
    fech_name_col = next((c for c in ["Nome_Fantasia"] if c in fech.columns), None)

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

def movimentacao_por_comercio(novos_filtrado: pd.DataFrame, fech: pd.DataFrame) -> pd.DataFrame:
    """Tabela de movimentação financeira por comércio (respeita os filtros de Novos).
       Junta por CNPJ (prioridade) ou por Nome_Fantasia.
       Retorna: Vendas Brutas, MDR Bruto R$, MDR Líquido R$, e % sobre as vendas.
    """
    if fech is None or len(fech) == 0 or len(novos_filtrado) == 0:
        return pd.DataFrame()

    fe = normalize_fechamento(fech.copy())
    fe_cols_ok = {"Valor", "MDR (R$) Bruto", "Total MDR (R$) Liquido Vegas Pay"}.issubset(fe.columns)
    if not fe_cols_ok:
        return pd.DataFrame()

    # normaliza chaves
    fe["CNPJ"] = fe.get("CNPJ", pd.Series([""]*len(fe))).astype(str).str.replace(r"\D", "", regex=True)
    novos = novos_filtrado.copy()
    novos["CNPJ"] = novos.get("CNPJ", pd.Series([""]*len(novos))).astype(str).str.replace(r"\D", "", regex=True)

    # 1) agregação por CNPJ no fechamento
    agg_cnpj = (fe.groupby("CNPJ", as_index=False)
                  .agg(Vendas_Brutas_R$=("Valor","sum"),
                       MDR_Bruto_R$=("MDR (R$) Bruto","sum"),
                       MDR_Liq_R$=("Total MDR (R$) Liquido Vegas Pay","sum")))

    # 2) agregação por nome no fechamento (se houver)
    if "Nome_Fantasia" in fe.columns:
        fe["Nome_FANT_NORM"] = strip_accents_upper(fe["Nome_Fantasia"])
        agg_nome = (fe.groupby("Nome_FANT_NORM", as_index=False)
                      .agg(Vendas_Brutas_R$=("Valor","sum"),
                           MDR_Bruto_R$=("MDR (R$) Bruto","sum"),
                           MDR_Liq_R$=("Total MDR (R$) Liquido Vegas Pay","sum")))
    else:
        agg_nome = pd.DataFrame(columns=["Nome_FANT_NORM","Vendas_Brutas_R$","MDR_Bruto_R$","MDR_Liq_R$"])

    # 3) monta base de Novos com chaves de match
    base = novos[["FANTASIA","CNPJ","Vendedor","Cidade","UF","Categoria_MCC"]].copy()
    if "FANTASIA" not in base.columns:
        base["FANTASIA"] = novos.get("Nome_Fantasia", "")
    base["Nome_FANT_NORM"] = strip_accents_upper(base["FANTASIA"])

    # 4) merge por CNPJ (prioritário) e depois completa por Nome
    out = base.merge(agg_cnpj, how="left", on="CNPJ")
    out = out.merge(agg_nome, how="left", on="Nome_FANT_NORM", suffixes=("", "_via_nome"))

    # escolhe o melhor disponível entre CNPJ e nome
    for col in ["Vendas_Brutas_R$","MDR_Bruto_R$","MDR_Liq_R$"]:
        via_nome = col + "_via_nome"
        out[col] = out[col].fillna(out.get(via_nome))
        out.drop(columns=[c for c in [via_nome] if c in out.columns], inplace=True)

    # percentuais
    out["MDR_Bruto_%"] = np.where(out["Vendas_Brutas_R$"]>0, out["MDR_Bruto_R$"]/out["Vendas_Brutas_R$"]*100, 0.0)
    out["MDR_Liq_%"]   = np.where(out["Vendas_Brutas_R$"]>0, out["MDR_Liq_R$"]/out["Vendas_Brutas_R$"]*100, 0.0)

    # ordena por maior venda
    out = out.sort_values("Vendas_Brutas_R$", ascending=False, ignore_index=True)
    return out

# =======================================
# Data bootstrap (repo by default)
# =======================================
@st.cache_data(show_spinner=False)
def carregar_fixos():
    f  = normalize_fechamento(pd.read_excel(FECH_PATH))
    n  = normalize_novos(pd.read_excel(NOVOS_PATH))
    return f, n

def ensure_data_loaded():
    if "fechamento_df" not in st.session_state or "novos_df" not in st.session_state:
        f, n = carregar_fixos()
        st.session_state["fechamento_df"] = f
        st.session_state["novos_df"]      = n
        st.session_state["data_source"]   = "repo"

ensure_data_loaded()

# =======================================
# Auth (admin)
# =======================================
def check_admin() -> bool:
    """Senha em Streamlit Cloud (Settings → Secrets): ADMIN_PASS=..."""
    saved = st.secrets.get("ADMIN_PASS", "")
    if not saved:
        return False
    if "is_admin" in st.session_state:
        return st.session_state["is_admin"]
    with st.sidebar.expander("🔐 Admin"):
        pwd = st.text_input("Senha do admin", type="password")
        if st.button("Entrar"):
            st.session_state["is_admin"] = (pwd == saved)
    return st.session_state.get("is_admin", False)

# =======================================
# Navegação
# =======================================
pages = ["📤 Upload", "📊 Vendas & MDR", "🆕 Novos Comércios"]
page = st.sidebar.radio("Navegação", pages)

fonte = "Repositório (dados/)" if st.session_state.get("data_source") == "repo" else "Uploads da sessão"
st.sidebar.caption(f"Fonte: **{fonte}**")

# =======================================
# Página: Upload (admin)
# =======================================
if page == "📤 Upload":
    header("📤 Upload (admin)")

    if not check_admin():
        st.info("Área restrita. Para atualizar os dados semanais, entre com a senha do admin no menu lateral.")
        st.stop()

    cA, cB = st.columns(2)
    with cA:
        if st.button("🔄 Recarregar dados do repositório"):
            f, n = carregar_fixos()
            st.session_state["fechamento_df"] = f
            st.session_state["novos_df"]      = n
            st.session_state["data_source"]   = "repo"
            st.success("Carregado a partir de dados/ (repositório).")

    with cB:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as wr:
            st.session_state["fechamento_df"].to_excel(wr, "Fechamento", index=False)
            st.session_state["novos_df"].to_excel(wr, "Novos_Comercios", index=False)
        st.download_button("📥 Baixar dados atuais", buf.getvalue(),
                           file_name="vegaspay_dados_atuais.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        f_fech = st.file_uploader("Fechamento — .xlsx", type=["xlsx"], key="fech")
    with col2:
        f_nov  = st.file_uploader("Novos Comércios — .xlsx", type=["xlsx"], key="novos")

    if st.button("🚚 Usar uploads nesta sessão"):
        ok = False
        if f_fech:
            try:
                st.session_state["fechamento_df"] = normalize_fechamento(pd.read_excel(f_fech)); ok = True
            except Exception as e:
                st.error(f"Fechamento: erro ao ler ({e})")
        if f_nov:
            try:
                st.session_state["novos_df"] = normalize_novos(pd.read_excel(f_nov)); ok = True
            except Exception as e:
                st.error(f"Novos Comércios: erro ao ler ({e})")
        if ok:
            st.session_state["data_source"] = "session"
            st.success("Uploads carregados (somente nesta sessão). Abra outras páginas para visualizar.")
        else:
            st.info("Envie pelo menos um dos arquivos.")

    st.info("""
**Como publicar para todos (1x/semana):**
1) No GitHub, substitua os arquivos em **`dados/`** mantendo os nomes:
   `Fechamento.xlsx` e `Novos_Comercios.xlsx`.
2) Volte aqui e clique **🔄 Recarregar dados do repositório**.
""")

# =======================================
# Página: Vendas & MDR (Bloco 1)
# =======================================
elif page == "📊 Vendas & MDR":
    header("📊 Vendas & MDR — Bloco 1")

    df = st.session_state.get("fechamento_df")
    if df is None or len(df)==0:
        st.info("Nenhum dado carregado. Carregue via repositório (dados/) ou Upload (admin).")
        st.stop()

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

# =======================================
# Página: Novos Comércios (Bloco 2)
# =======================================
elif page == "🆕 Novos Comércios":
    header("🆕 Novos Comércios — Bloco 2")

    df_nov = st.session_state.get("novos_df")
    df_fech = st.session_state.get("fechamento_df")

    if df_nov is None or len(df_nov)==0:
        st.info("Nenhum dado de Novos Comércios carregado. Carregue via repositório (dados/) ou Upload (admin).")
        st.stop()

    base = cruzar_realizado(df_nov, df_fech)

    # -------- Filtros (NOVOS) --------
    cols = st.columns(6)
    with cols[0]:
        mes_sel = st.multiselect("Mês (cadastro)", sorted(base["Mes"].dropna().unique().tolist()) if "Mes" in base.columns else [])
    with cols[1]:
        vend_sel = st.multiselect("Vendedor", sorted(base["Vendedor"].dropna().unique().tolist()) if "Vendedor" in base.columns else [])
    with cols[2]:
        cidade_sel = st.multiselect("Cidade", sorted(base["Cidade"].dropna().unique().tolist()) if "Cidade" in base.columns else [])
    with cols[3]:
        uf_sel = st.multiselect("UF", sorted(base["UF"].dropna().unique().tolist()) if "UF" in base.columns else [])
    with cols[4]:
        cat_sel = st.multiselect("Categoria MCC", sorted(base["Categoria_MCC"].dropna().unique().tolist()) if "Categoria_MCC" in base.columns else [])
    with cols[5]:
        nome_filtro = st.text_input("Nome do Comércio (contém)", "")

    f = base.copy()
    if mes_sel: f = f[f["Mes"].isin(mes_sel)]
    if vend_sel and "Vendedor" in f.columns: f = f[f["Vendedor"].isin(vend_sel)]
    if cidade_sel and "Cidade" in f.columns: f = f[f["Cidade"].isin(cidade_sel)]
    if uf_sel   and "UF" in f.columns:       f = f[f["UF"].isin(uf_sel)]
    if cat_sel  and "Categoria_MCC" in f.columns: f = f[f["Categoria_MCC"].isin(cat_sel)]
    if nome_filtro and "FANTASIA" in f.columns:
        mask = strip_accents_upper(f["FANTASIA"]).str.contains(strip_accents_upper(pd.Series([nome_filtro]))[0], na=False)
        f = f[mask]

    # -------- KPIs --------
    meta_col = pick_col(f, ["Meta 70% da Movimentação ", "Meta 70% da Movimentação"])
    qtd  = len(f)
    prev = float(f.get("Previsão de Mov. Financeira", pd.Series(dtype=float)).sum())
    meta = float(f.get(meta_col, pd.Series(dtype=float)).sum()) if meta_col else 0.0
    real = float(f.get("Realizado_R$", pd.Series(dtype=float)).sum())
    ating = (real/meta*100) if meta>0 else 0.0

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Qtd. Novos Comércios", f"{qtd:,}".replace(",","."))
    c2.metric("Previsão Total (R$)", fmt_brl(prev))
    c3.metric("Meta 70% (R$)", fmt_brl(meta))
    c4.metric("Realizado (R$)", fmt_brl(real))
    st.metric("Atingimento Meta 70% (%)", fmt_pct(ating))

    st.divider()

    # -------- Tabela principal (Novos) --------
    cols_show = ["Mes","FANTASIA","CNPJ","Vendedor","Cidade","UF","Categoria_MCC",
                 "Previsão de Mov. Financeira"]
    if meta_col and meta_col not in cols_show: cols_show.append(meta_col)
    cols_show += ["Realizado_R$"]
    cols_show = [c for c in cols_show if c in f.columns]
    st.subheader("Detalhe dos Novos Comércios (filtrados)")
    st.dataframe(f[cols_show].style.format({
        "Previsão de Mov. Financeira": fmt_brl,
        "Realizado_R$": fmt_brl,
        meta_col: fmt_brl if meta_col else fmt_brl
    }), use_container_width=True)

    # -------- Nova Tabela: Movimentação Financeira --------
    st.subheader("Movimentação Financeira — Comércios filtrados")
    mov = movimentacao_por_comercio(f, df_fech)
    if mov.empty:
        st.info("Sem movimentação encontrada no Fechamento para os comércios filtrados.")
    else:
        mov_fmt = mov.copy()
        st.dataframe(mov_fmt.style.format({
            "Vendas_Brutas_R$": fmt_brl, "MDR_Bruto_R$": fmt_brl,
            "MDR_Liq_R$": fmt_brl, "MDR_Bruto_%": fmt_pct, "MDR_Liq_%": fmt_pct
        }), use_container_width=True)

        # download
        buff2 = BytesIO()
        with pd.ExcelWriter(buff2, engine="openpyxl") as writer:
            f.to_excel(writer, sheet_name="Novos_Filtrado", index=False)
            mov.to_excel(writer, sheet_name="Movimentacao_Comercios", index=False)
        st.download_button("📥 Baixar Excel (Novos + Movimentação / filtro atual)",
                           data=buff2.getvalue(),
                           file_name="vegaspay_novos_movimentacao.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

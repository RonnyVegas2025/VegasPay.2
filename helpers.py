
import pandas as pd
import numpy as np

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

def normalize_fechamento(df):
    # renames and numeric coercions
    rename_map = {
        "Mês Referencia": "Mes",
        "Preposto": "Vendedor",
        "MCC - Categoria": "Categoria_MCC",
    }
    df = df.rename(columns=rename_map).copy()
    # numeric
    for c in ["Valor","MDR (R$) Bruto","MDR (R$) Liquido Cartões","MDR (R$) Liquido Antecipação",
              "MDR (R$) Liquido Pix","Total MDR (R$) Liquido Vegas Pay"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    # month
    if "Mes" in df.columns:
        try:
            df["Mes"] = ensure_month_str(df["Mes"])
        except Exception:
            df["Mes"] = df["Mes"].astype(str)
    # text
    for c in ["Bandeira","Produto","Vendedor","Categoria_MCC","CNPJ"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df

def normalize_novos(df):
    # Expected columns:
    # 'CNPJ','FANTASIA','MCC','Categoria MCC','Cidade','UF','Vendedor','Data de Cadastro',
    # 'Previsão de Mov. Financeira','Meta 70% da Movimentação '
    df = df.rename(columns={"Categoria MCC":"Categoria_MCC"}).copy()
    # numerics
    for c in ["Previsão de Mov. Financeira","Meta 70% da Movimentação "]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    # dates -> month
    if "Data de Cadastro" in df.columns:
        df["Mes"] = ensure_month_str(df["Data de Cadastro"])
    # text cleanup
    for c in ["CNPJ","FANTASIA","MCC","Categoria_MCC","Cidade","UF","Vendedor"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    # remove non-digits in CNPJ
    if "CNPJ" in df.columns:
        df["CNPJ"] = df["CNPJ"].str.replace(r"\D","", regex=True)
    return df

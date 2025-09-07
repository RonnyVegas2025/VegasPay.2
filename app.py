
import streamlit as st

st.set_page_config(page_title="VegasPay — Gestão & Acompanhamento", layout="wide")

st.title("🏠 VegasPay — Gestão & Acompanhamento")

st.markdown("""
Bem-vindo! Use o menu **Pages** (canto superior esquerdo) para navegar:

- **📤 Upload** — envie os arquivos: Fechamento consolidado e Novos Comércios.
- **📊 Vendas & MDR** — KPIs e resumos a partir do **Fechamento** (Bloco 1).
- **🆕 Novos Comércios** — pipeline, previsão vs. realizado por vendedor (Bloco 2).
""")

st.info("Dica: se você acabou de subir arquivos em **📤 Upload**, esta sessão já os enxerga nas outras páginas.")

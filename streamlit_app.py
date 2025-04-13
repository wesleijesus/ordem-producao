import streamlit as st
import pandas as pd
import gspread
import json
from io import StringIO
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# ========================
# 1. Autenticacao com Google Sheets
# ========================
creds_dict = json.loads(st.secrets["google_service_account"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# IDs e abas
sheet_id = "1UuQGybYpctVCOq5xhR_26THJOEk9jfdytLW1Be2HfRs"
sheet_ordens = client.open_by_key(sheet_id).worksheet("Ordem_Producao_V2")

# ========================
# 2. Funcoes auxiliares
# ========================
def get_next_order_number():
    values = sheet_ordens.col_values(1)[1:]
    if not values:
        return "ORD0001"
    last = sorted(values)[-1]
    num = int(last.replace("ORD", "")) + 1
    return f"ORD{num:04}"

def salvar_ordem(numero, data, status, itens):
    for item in itens:
        row = [numero, data, status, item['SKU'], item['Qtd Solicitada'], item['Qtd Recebida'], item['Custo Unitario'], item['Custo Total']]
        sheet_ordens.append_row(row, value_input_option="USER_ENTERED")

def carregar_ordens():
    data = sheet_ordens.get_all_records()
    return pd.DataFrame(data)

def atualizar_ordem(numero, novos_itens):
    df = carregar_ordens()
    indices = df[df['Numero'] == numero].index.tolist()
    for i in reversed(indices):
        sheet_ordens.delete_rows(i + 2)  # +2 por conta do cabeçalho
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    salvar_ordem(numero, data_atual, "Rascunho", novos_itens)

def promover_ordem(numero):
    cell_list = sheet_ordens.findall(numero)
    for cell in cell_list:
        col_status = cell.col + 2
        sheet_ordens.update_cell(cell.row, col_status, "Promovida")

# ========================
# 3. Interface com Streamlit
# ========================
st.title("📆 Ordem de Produção")

aba = st.sidebar.radio("Menu", ["Criar Ordem", "Listar Ordens", "Editar Ordem", "Promover Ordem"])

if aba == "Criar Ordem":
    st.subheader("Criar nova ordem")
    numero = get_next_order_number()
    data = datetime.now().strftime("%d/%m/%Y %H:%M")
    st.markdown(f"**Número da Ordem:** `{numero}`")

    qtd_itens = st.number_input("Quantos itens?", 1, 10, 1)
    itens = []
    for i in range(qtd_itens):
        with st.expander(f"Item {i+1}"):
            sku = st.text_input(f"SKU {i+1}", key=f"sku_{i}")
            qtd_sol = st.number_input(f"Quantidade Solicitada", 0, key=f"qtd_sol_{i}")
            qtd_rec = st.number_input(f"Quantidade Recebida", 0, key=f"qtd_rec_{i}")
            custo_unit = st.number_input(f"Custo Unitário R$", 0.0, key=f"custo_{i}")
            total = qtd_rec * custo_unit
            itens.append({"SKU": sku, "Qtd Solicitada": qtd_sol, "Qtd Recebida": qtd_rec, "Custo Unitario": custo_unit, "Custo Total": total})

    if st.button("Salvar Ordem"):
        salvar_ordem(numero, data, "Rascunho", itens)
        st.success("Ordem salva com sucesso!")

elif aba == "Listar Ordens":
    st.subheader("Todas as ordens")
    df = carregar_ordens()
    st.dataframe(df)

elif aba == "Editar Ordem":
    df = carregar_ordens()
    ordens_editaveis = df[df['Status'] == 'Rascunho']['Numero'].unique()
    ordem_selecionada = st.selectbox("Selecione a ordem para editar", ordens_editaveis)

    if ordem_selecionada:
        df_ordem = df[df['Numero'] == ordem_selecionada]
        itens = []
        for i, row in df_ordem.iterrows():
            with st.expander(f"Item {i+1}"):
                sku = st.text_input("SKU", value=row['SKU'], key=f"edit_sku_{i}")
                qtd_sol = st.number_input("Qtd Solicitada", value=int(row['Qtd Solicitada']), key=f"edit_qtd_sol_{i}")
                qtd_rec = st.number_input("Qtd Recebida", value=int(row['Qtd Recebida']), key=f"edit_qtd_rec_{i}")
                custo_unit = st.number_input("Custo Unitário", value=float(row['Custo Unitario']), key=f"edit_custo_{i}")
                total = qtd_rec * custo_unit
                itens.append({"SKU": sku, "Qtd Solicitada": qtd_sol, "Qtd Recebida": qtd_rec, "Custo Unitario": custo_unit, "Custo Total": total})

        if st.button("Atualizar Ordem"):
            atualizar_ordem(ordem_selecionada, itens)
            st.success("Ordem atualizada com sucesso!")

elif aba == "Promover Ordem":
    df = carregar_ordens()
    ordens_para_promover = df[df['Status'] == 'Rascunho']['Numero'].unique()
    ordem = st.selectbox("Selecione a ordem para promover", ordens_para_promover)
    if st.button("Promover"):
        promover_ordem(ordem)
        st.success("Ordem promovida com sucesso!")

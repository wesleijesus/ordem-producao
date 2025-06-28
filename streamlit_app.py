import streamlit as st
import pandas as pd
import gspread
import json
import math
import requests
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode


usuarios = {
    "streamlit-aggrid": {"senha": "Gabriel", "perfil": "Criador"},
    "Jaqueline": {"senha": "123456", "perfil": "Validador"},
}



if "usuario" not in st.session_state:
    st.session_state["usuario"] = None
    st.session_state["perfil"] = None

if not st.session_state["usuario"]:
    st.title("🔐 Login")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if usuario in usuarios and senha == usuarios[usuario]["senha"]:
            st.session_state["usuario"] = usuario
            st.session_state["perfil"] = usuarios[usuario]["perfil"]
            st.rerun()  # 🔁 Use este aqui agora

        else:
            st.error("Usuário ou senha inválidos")
    st.stop()

# ========================
# Header com usuário logado e botão logout
# ========================
st.sidebar.markdown(f"👤 Logado como: `{st.session_state['usuario']}`")
if st.sidebar.button("🔓 Sair"):
    st.session_state.clear()
    st.rerun()

# ========================
# 1. Autenticacao com Google Sheets s
# ========================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["google_service_account"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# IDs e abas
sheet_id = "1UuQGybYpctVCOq5xhR_26THJOEk9jfdytLW1Be2HfRs"
sheet_ordens = client.open_by_key(sheet_id).worksheet("Ordem_Producao_V2")

# Carrega produtos acabados com cache
@st.cache_data
def carregar_produtos():
    aba = client.open_by_key(sheet_id).worksheet("Produto_Acabado")
    dados = aba.get_all_values()
    df = pd.DataFrame(dados[1:], columns=dados[0])
    df = df.rename(columns={
        "SKU Principal": "SKU",
        "Descricao": "Descricao",
        "Custo Unitario": "Custo",
        "ID Principal": "ID"
    })

    """st.write("🔍 Produto filtrado por SKU 'ALMCAPLIN597'")
    sku_filtro = "ALMCAPLIN597"
    produto_filtrado = df[df["SKU"].str.strip().str.upper() == sku_filtro]
    st.write(produto_filtrado)"""

    #df["Custo"] = pd.to_numeric(df["Custo"], errors="coerce").fillna(0)
    return df[["SKU", "Descricao", "Custo", "ID"]]

df_produtos = carregar_produtos()
df_produtos = df_produtos[["ID", "SKU", "Descricao", "Custo"]]

# Conversões
#df_produtos["Custo"] = pd.to_numeric(df_produtos["Custo"], errors="coerce")
#produto_filtrado = df_produtos[df_produtos["SKU"].str.strip().str.upper() == sku_filtro]

# ========================
# 2. Funcoes auxiliares
# ========================
def get_next_order_number():
    dados = sheet_ordens.get_all_values()[1:]
    values = [row[0] for row in dados if row and row[0].startswith("ORD")]
    if not values:
        return "ORD0001"
    last = sorted(values)[-1]
    num = int(last.replace("ORD", "")) + 1
    return f"ORD{num:04}"

def altura_dinamica(df, min_altura=300, max_altura=1000, altura_linha=35):
    linhas = len(df)
    return max(min_altura, min(linhas * altura_linha, max_altura))


def salvar_ordem(numero, data, status, itens):
    linhas = []
    for item in itens:
        row = [numero, data, status, item["ID"], item["SKU"], item["Qtd Solicitada"],
               item["Qtd Recebida"], item["Custo Unitario"], item["Custo Total"]]
        linhas.append(row)
    sheet_ordens.append_rows(linhas, value_input_option="USER_ENTERED")

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


def buscar_componentes_do_produto(id_produto_acabado):
    try:
        sheet_componentes = client.open_by_key(sheet_id).worksheet("Componentes")
        dados = sheet_componentes.get_all_values()
        df_componentes = pd.DataFrame(dados[1:], columns=dados[0])
        df_filtrado = df_componentes[
            (df_componentes["ID_PRINCIPAL"] == str(id_produto_acabado)) &
            (df_componentes["Tipo_produto"].str.strip().str.lower() != "Servico")
        ].copy()
        #df_filtrado["QTD"] = pd.to_numeric(df_filtrado["QTD"], errors="coerce").fillna(0)
        df_filtrado["QTD"] = (
            df_filtrado["QTD"]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .astype(float)
            .fillna(0)
        )        
        #df_filtrado["CUSTO_UNITARIO"] = pd.to_numeric(df_filtrado["CUSTO_UNITARIO"], errors="coerce").fillna(0)
        df_filtrado["CUSTO_UNITARIO"] = (
            df_filtrado["CUSTO_UNITARIO"]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .astype(float)
            .fillna(0)
        )        
        return df_filtrado[["ID_COMPONENTE", "QTD", "CUSTO_UNITARIO"]]
    except Exception as e:
        st.error(f"Erro ao buscar componentes do produto {id_produto_acabado}: {e}")
        return pd.DataFrame()


def promover_ordem(numero_ordem):
    # === CONFIGURAÇÕES ===
    sheet_id = "1RzVio4Ux1dr4kwAN5TXNnef0hIfSE2Wy7-ZKo1zwOvU"
    config_tab = "Config"
    #aba_ordens_nome = "Ordem_Producao_V2"
    deposito_id = 10157139483
    bling_client_id = '2cf1b14469e775e27b9cdb1904722bfae15195e9'
    bling_secret_key = 'f6c48348e237ee126b9ab567e941d2cacff685d1e0eb98d46a06f5801fdf'
    bling_token_url = "https://www.bling.com.br/Api/v3/oauth/token"
    estoque_url = "https://www.bling.com.br/Api/v3/estoques"

    # === AUTENTICAÇÃO GOOGLE SHEETS ===
    #scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    #creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(sheet_id)
    aba_config = sheet.worksheet(config_tab)
    aba_ordens = sheet_ordens

    # === TOKEN ATUAL ===
    access_token = aba_config.acell("B3").value
    refresh_token = aba_config.acell("B4").value
    pedido_compra_url = "https://www.bling.com.br/Api/v3/pedidos/compras"
    

    def refresh_access_token():
        resp = requests.post(bling_token_url, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": bling_client_id,
            "client_secret": bling_secret_key
        })
        resp.raise_for_status()
        new_token = resp.json()["access_token"]
        aba_config.update("B3", new_token)
        return new_token

    def get_headers():
        nonlocal access_token
        headers = {"Authorization": f"Bearer {access_token}"}
        test = requests.get("https://www.bling.com.br/Api/v3/usuarios/me", headers=headers)
        if test.status_code == 401:
            access_token = refresh_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
        return headers

    def safe_float(v):
        try:
            f = float(v)
            return 0 if math.isnan(f) or math.isinf(f) else f
        except:
            return 0

    headers = get_headers()

    # === BUSCA ITENS DA ORDEM ===
    dados = sheet_ordens.get_all_values()
    df = pd.DataFrame(dados[1:], columns=dados[0])
    ordem_itens = df[df["Numero"] == str(numero_ordem)]

    if ordem_itens.empty:
        st.error("⚠️ Ordem não encontrada.")
        return
    st.write(f"[DEBUG] vai comecar o try")
    # === AGRUPA PEDIDO DE COMPRA ===
    try:
        fornecedor_id = ordem_itens["ID_FORNECEDOR"].iloc[0]
        forma_pagamento_id = "2204196"
        data_hoje = datetime.now().strftime("%d/%m/%Y")
        itens = []
        total_produtos = 0

        for _, row in ordem_itens.iterrows():
            try:
                produto_id = int(row["ID"])
                qtd = float(row["Qtd Recebida"])
                custo = float(row["Custo Unitario"])
                total_produtos += qtd * custo

                itens.append({
                    "descricao": row["Descricao"],
                    "valor": custo,
                    "codigoFornecedor": "",
                    "unidade": "UN",
                    "quantidade": qtd,
                    "aliquotaIPI": 0,
                    "descricaoDetalhada": "",
                    "produto": {
                        "id": produto_id,
                        "codigo": row["SKU"]
                    }
                })

            except Exception as e:
                st.warning(f"Erro no item {row['SKU']}: {e}")

        # Agora sim, criar o pedido de compra com todos os itens juntos
        payload = {
            "fornecedor": {"id": fornecedor_id},
            "itens": itens,
            "data": data_hoje,
            "dataPrevista": data_hoje,
            "totalProdutos": total_produtos,
            "ordemCompra": "pedfornecedor",
            "situacao": {"valor": 0},
            "observacoesInternas": f"Ordem de produção #{numero_ordem}",
            "parcelas": [{
                "valor": total_produtos,
                "dataVencimento": "17/05/2025",
                "observacao": f"Ordem de Producao {numero_ordem}",
                "formaPagamento": {"id": forma_pagamento_id}
            }]
        }

        st.write(f"[DEBUG] PAYLOAD FINAL: {payload}")
        r = requests.post(pedido_compra_url, headers=headers, json=payload)
        r.raise_for_status()

        # Baixa dos componentes
        for _, row in ordem_itens.iterrows():
            produto_id = int(row["ID"])
            qtd = float(row["Qtd Recebida"])
            componentes = buscar_componentes_do_produto(produto_id)
            for _, comp in componentes.iterrows():
                id_componente = int(comp["ID_COMPONENTE"])
                qtd_comp = float(comp["QTD"]) * qtd
                payload_comp = {
                    "deposito": {"id": deposito_id},
                    "operacao": "S",
                    "produto": {"id": id_componente},
                    "quantidade": qtd_comp,
                    "preco": comp["CUSTO_UNITARIO"],
                    "custo": comp["CUSTO_UNITARIO"],
                    "observacoes": f"Baixa de componente da Ordem #{numero_ordem}"
                }
                requests.post(estoque_url, headers=headers, json=payload_comp)

        # Atualiza status
        for i in range(1, len(dados)):
            if dados[i][0] == str(numero_ordem):
                dados[i][2] = "Promovida"
        aba_ordens.update("A2", dados[1:])
        st.success(f"✅ Pedido de compra criado e ordem #{numero_ordem} promovida com sucesso!")

    except Exception as e:
        st.error(f"❌ Erro ao promover ordem: {e}")


# ========================
# 3. Interface com Streamlit
# ========================
st.title("📆 Ordem de Produção")

abas = ["Criar Ordem", "Listar Ordens", "Editar Ordem", "Promover Ordem"]
if st.session_state["perfil"] == "Validador":
    abas.append("Validar Ordem")

aba = st.sidebar.radio("Menu", abas)

#aba = st.sidebar.radio("Menu", ["Criar Ordem", "Listar Ordens", "Editar Ordem", "Promover Ordem"])

if aba == "Criar Ordem":
    st.subheader("Criar nova ordem")
    numero = get_next_order_number()
    data = datetime.now().strftime("%d/%m/%Y %H:%M")
    st.markdown(f"**Número da Ordem:** `{numero}`")

    st.subheader("Itens da Ordem (planilha editável)")

    nova_linha = {
        "SKU": "",
        "ID": "",
        "Descricao": "",
        "Qtd Solicitada": 0,
        "Custo Unitario": 0.0,
        "Qtd Recebida": "",
        "Custo Total": 0.0
    }

    if "itens" not in st.session_state:
        st.session_state["itens"] = [nova_linha.copy()]

    if st.button("+ Adicionar item"):
        st.session_state["itens"].append(nova_linha.copy())


    
    df_itens = pd.DataFrame(st.session_state["itens"])


    # Converte o custo para float antes de passar ao AgGrid
    df_itens["Custo Unitario"] = (
        df_itens["Custo Unitario"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .astype(float)
        .round(2)
    )
    # Grid AgGrid
    gb = GridOptionsBuilder.from_dataframe(df_itens)
    gb.configure_columns(["Descricao", "Custo Unitario", "Custo Total", "Qtd Recebida", "ID"], editable=False)
    gb.configure_columns(["SKU", "Qtd Solicitada"], editable=True)
    gb.configure_grid_options(stopEditingWhenCellsLoseFocus=True)
    gb.configure_grid_options(enableCellChangeFlash=True)
    gb.configure_default_column(resizable=True, wrapText=True, autoHeight=True)
    gb.configure_grid_options(domLayout='normal')
    grid_options = gb.build()

    grid_response = AgGrid(
        df_itens,
        gridOptions=grid_options,
        enable_enterprise_modules=False,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=True,
        height=400,
    )

    df_editado = grid_response["data"]

    # 🔄 Validação dos itens via SKU
    if st.button("🔄 Validar Itens"):
        df_final = df_editado.copy()
        for i in df_final.index:
            sku = str(df_final.at[i, "SKU"]).strip().upper()
            produto = df_produtos[df_produtos["SKU"].str.strip().str.upper() == sku]

            if not produto.empty:
                try:
                    valor_bruto = str(produto.iloc[0]["Custo"]).replace(",", ".").strip()
                    custo_unitario = float(valor_bruto) if valor_bruto else 0.0
                except:
                    custo_unitario = 0.0

                df_final.at[i, "Descricao"] = produto.iloc[0]["Descricao"]
                df_final.at[i, "Custo Unitario"] = custo_unitario
                df_final.at[i, "ID"] = produto.iloc[0]["ID"]

                try:
                    qtd = float(df_final.at[i, "Qtd Solicitada"])
                    df_final.at[i, "Custo Total"] = round(qtd * custo_unitario, 2)
                except:
                    df_final.at[i, "Custo Total"] = 0.0
            else:
                df_final.at[i, "Descricao"] = "❌ SKU inválido"
                df_final.at[i, "Custo Unitario"] = 0.0
                df_final.at[i, "Custo Total"] = 0.0
                df_final.at[i, "ID"] = 0

        st.session_state["itens"] = df_final.to_dict("records")
        st.success("Itens validados com sucesso.")

        # 📦 Pré-visualização com os itens atualizados (validados)
        st.subheader("📦 Pré-visualização da Ordem")
        df_preview = pd.DataFrame(st.session_state.get("itens", df_editado.to_dict("records")))
        altura = altura_dinamica(df_preview)
        st.dataframe(df_preview, use_container_width=True, height=altura)


    #st.dataframe(df_editado, use_container_width=True)


def safe_float(v):
    try:
        f = float(v)
        return 0 if math.isnan(f) or math.isinf(f) else f
    except:
        return 0

if st.button("Salvar Ordem"):
    try:
        df_final = pd.DataFrame(st.session_state["itens"])
        for i in df_final.index:
            sku = str(df_final.at[i, "SKU"]).strip().upper()
            produto = df_produtos[df_produtos["SKU"].str.strip().str.upper() == sku]

            if not produto.empty:
                try:
                    valor_bruto = str(produto.iloc[0]["Custo"]).replace(",", ".").strip()
                    custo_unitario = float(valor_bruto) if valor_bruto else 0.0
                except:
                    custo_unitario = 0.0

                df_final.at[i, "Descricao"] = produto.iloc[0]["Descricao"]
                df_final.at[i, "Custo Unitario"] = custo_unitario
                df_final.at[i, "ID"] = produto.iloc[0]["ID"]

                try:
                    qtd = float(df_final.at[i, "Qtd Solicitada"])
                    df_final.at[i, "Custo Total"] = round(qtd * custo_unitario, 2)
                except:
                    df_final.at[i, "Custo Total"] = 0.0
            else:
                df_final.at[i, "Descricao"] = "❌ SKU inválido"
                df_final.at[i, "Custo Unitario"] = 0.0
                df_final.at[i, "Custo Total"] = 0.0
                df_final.at[i, "ID"] = 0

        # Grava na planilha
        sheet_ordens = client.open_by_key(sheet_id).worksheet("Ordem_Producao_V2")
        dados_existentes = sheet_ordens.get_all_values()
        df_existente = pd.DataFrame(dados_existentes[1:], columns=dados_existentes[0]) if dados_existentes else pd.DataFrame()

        novo_numero = 1
        if not df_existente.empty and "Numero" in df_existente.columns:
            numeros = pd.to_numeric(df_existente["Numero"], errors="coerce").dropna()
            novo_numero = int(numeros.max()) + 1 if not numeros.empty else 1

        data_hoje = datetime.now().strftime("%Y-%m-%d")
        status = "Rascunho"

        linhas = []
        for _, row in df_final.iterrows():
            linhas.append([
                str(novo_numero),
                data_hoje,
                status,
                row["ID"],
                row["SKU"],
                row["Descricao"],
                safe_float(row["Qtd Solicitada"]),
                safe_float(row.get("Qtd Recebida", 0)),
                safe_float(row["Custo Unitario"]),
                safe_float(row["Custo Total"]),
                "", "", "", "", ""  # colunas adicionais em branco
            ])

        sheet_ordens.append_rows(linhas, value_input_option="USER_ENTERED")
        st.success(f"✅ Ordem #{novo_numero} salva com sucesso!")
        st.session_state["itens"] = None

    except Exception as e:
        st.error(f"Erro ao salvar ordem: {e}")

elif aba == "Listar Ordens":
    st.subheader("Todas as ordens")
    df = carregar_ordens()

    if "Custo Unitario" in df.columns:
        df["Custo Unitario"] = (
            df["Custo Unitario"]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0.0)
        )
        df["Custo Unitario Formatado"] = df["Custo Unitario"].apply(
            lambda x: f"{x:.2f}".replace(".", ",")

        )

    # Exibe só as colunas desejadas
    st.dataframe(
        df[["Numero", "SKU", "Qtd Solicitada", "Custo Unitario Formatado"]],
        use_container_width=True
    )


elif aba == "Editar Ordem":
    df = carregar_ordens()
    
    ordem_selecionada = st.selectbox("Selecione a ordem para editar", df["Numero"].unique())

    if ordem_selecionada:
        df_ordem = df[df['Numero'] == ordem_selecionada].copy()

        # Converte custo unitário para número
   #     if "Custo Unitario" in df_ordem.columns:
      #      df_ordem["Custo Unitario"] = df_ordem["Custo Unitario"].astype(str).str.replace(",", ".").astype(float)


        status_atual = df_ordem["Status"].iloc[0]
        st.markdown(f"📄 Status atual: **{status_atual}**")

        aba_ordens = client.open_by_key(sheet_id).worksheet("Ordem_Producao_V2")
        dados = aba_ordens.get_all_values()

        # ==== Se for "Aprovada", permitir iniciar fabricação ====
        if status_atual == "Aprovada":
            st.markdown("### 🏭 Iniciar Fabricação")
            aba_fabricantes = client.open_by_key(sheet_id).worksheet("Fabricantes")
            dados_fab = aba_fabricantes.get_all_values()
            df_fab = pd.DataFrame(dados_fab[1:], columns=dados_fab[0])
            try:
                df_fab = pd.DataFrame(dados_fab[1:], columns=dados_fab[0])
                if "Nome" in df_fab.columns and "ID" in df_fab.columns:
                    fabricantes_dict = dict(zip(df_fab["Nome"], df_fab["ID"]))
                else:
                    st.warning("⚠️ A aba 'Fabricantes' não possui colunas 'Nome' e 'ID'.")
                    fabricantes_dict = {}
            except Exception as e:
                st.error(f"❌ Erro ao processar os fabricantes: {e}")
                fabricantes_dict = {}

            data_inicio = st.date_input("Data Início da Fabricação")
            data_fim = st.date_input("Data Fim da Fabricação")
            fabricante_nome = st.selectbox("Selecione o fabricante", list(fabricantes_dict.keys()))

            if st.button("▶️ Iniciar Fabricação"):
                try:
                    fabricante_id = fabricantes_dict[fabricante_nome]
                    for i in range(1, len(dados)):
                        if dados[i][0] == str(ordem_selecionada):
                            dados[i][2] = "Em Fabricacao"
                            dados[i][10] = data_inicio.strftime("%d/%m/%Y")  # Coluna K - Data Início
                            dados[i][11] = data_fim.strftime("%d/%m/%Y")     # Coluna L - Data Fim
                            dados[i][13] = fabricante_nome                   # Coluna N - Nome do Fabricante
                            dados[i][14] = fabricante_id                    # Coluna O - ID do Fabricante
                    aba_ordens.update("A2", dados[1:])
                    st.success("✅ Ordem movida para 'Em Fabricação'")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao iniciar fabricação: {e}")

        # ==== Se for "Em Fabricação", permitir iniciar conferência ====
        elif status_atual == "Em Fabricacao":
            if st.button("📦 Iniciar Conferência"):
                for i in range(1, len(dados)):
                    if dados[i][0] == str(ordem_selecionada):
                        dados[i][2] = "Em Conferencia"
                aba_ordens.update("A2", dados[1:])
                st.success("✅ Ordem movida para 'Em Conferência'")
                st.rerun()

        # ==== Se for "Em Conferência", editar Qtd Recebida e permitir Fechar ====
        elif status_atual == "Em Conferencia":
            df_ordem["Qtd Recebida"] = df_ordem["Qtd Solicitada"]
            df_ordem["Custo Total"] = df_ordem["Qtd Solicitada"].astype(float) * df_ordem["Custo Unitario"].astype(float)
            altura = altura_dinamica(df_ordem)
            df_editado = st.data_editor(
                df_ordem,
                num_rows="dynamic",
                use_container_width=True,
                height=altura,
                hide_index=True,
                column_config={
                    "Descricao": st.column_config.TextColumn(disabled=True),
                    "Custo Unitario": st.column_config.NumberColumn(disabled=True),
                    "Custo Total": st.column_config.NumberColumn(disabled=True),
                    "ID": st.column_config.TextColumn(disabled=True),
                    "Qtd Solicitada": st.column_config.NumberColumn(disabled=True),
                    "Qtd Recebida": st.column_config.NumberColumn(disabled=False),
                }
            )

            if st.button("✅ Fechar Conferência"):
                try:
                    atualizados = []
                    for _, row in df_editado.iterrows():
                        id_item = str(row["ID"])
                        qtd_recebida = str(row["Qtd Recebida"])
                        for i in range(1, len(dados)):
                            if dados[i][0] == str(ordem_selecionada) and dados[i][3] == id_item:
                                dados[i][7] = qtd_recebida  # Coluna H
                                atualizados.append((dados[i][1], id_item, qtd_recebida))
                    for i in range(1, len(dados)):
                        if dados[i][0] == str(ordem_selecionada):
                            dados[i][2] = "Conferida"
                            dados[i][12] = st.session_state["usuario"]
                    aba_ordens.update("A2", dados[1:])
                    st.success(f"✅ {len(atualizados)} item(s) atualizados. Conferência finalizada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao fechar conferência: {e}")

        # ==== Se for Rascunho, permitir edição ====
        elif status_atual == "Rascunho":
            df_ordem = df_ordem[["ID", "SKU", "Descricao", "Qtd Solicitada", "Qtd Recebida", "Custo Unitario"]]
            df_ordem["Custo Total"] = df_ordem["Qtd Solicitada"].astype(float) * df_ordem["Custo Unitario"].astype(float)
            altura = altura_dinamica(df_ordem)
            st.write("Perfil:", st.session_state.get("perfil"))
            df_editado = st.data_editor(
                df_ordem,
                num_rows="dynamic",
                use_container_width=True,
                height=altura,
                hide_index=True,
                column_config={
                    "Descricao": st.column_config.TextColumn(disabled=True),
                    "Custo Unitario": st.column_config.NumberColumn(disabled=True),
                    "Custo Total": st.column_config.NumberColumn(disabled=True),
                    "ID": st.column_config.TextColumn(disabled=True),
                    "Qtd Recebida": st.column_config.NumberColumn(disabled=True),
                }
            )

            # Atualiza campos automáticos
            for i in df_editado.index:
                sku = df_editado.at[i, "SKU"]
                if sku:
                    produto = df_produtos[df_produtos["SKU"] == sku]
                    if not produto.empty:
                        df_editado.at[i, "Descricao"] = produto.iloc[0]["Descricao"]
                        df_editado.at[i, "Custo Unitario"] = produto.iloc[0]["Custo"]
                        df_editado.at[i, "ID"] = produto.iloc[0]["ID"]
                        try:
                            qtd = float(df_editado.at[i, "Qtd Solicitada"])
                            df_editado.at[i, "Custo Total"] = qtd * produto.iloc[0]["Custo Unitario"]
                        except:
                            df_editado.at[i, "Custo Total"] = 0.0
                    else:
                        df_editado.at[i, "Descricao"] = "❌ SKU inválido"
                        df_editado.at[i, "Custo Unitario"] = 0.0
                        df_editado.at[i, "Custo Total"] = 0.0
                        df_editado.at[i, "ID"] = 0

            if st.button("Atualizar Ordem"):
                try:
                    dados = aba_ordens.get_all_values()
                    cabecalho = dados[0]
                    linhas = [linha + [''] * (len(cabecalho) - len(linha)) for linha in dados[1:]]
                    df_atual = pd.DataFrame(linhas, columns=cabecalho)

                    df_nova = df_atual[df_atual["Numero"] != str(ordem_selecionada)]
                    data_hoje = datetime.now().strftime("%Y-%m-%d")

                    novos_itens = []
                    for _, row in df_editado.iterrows():
                        qtd = safe_float(row["Qtd Solicitada"])
                        custo = safe_float(row["Custo Unitario"])
                        total = qtd * custo
                        novos_itens.append([
                            str(ordem_selecionada),
                            data_hoje,
                            "Rascunho",
                            row["ID"],
                            row["SKU"],
                            row["Descricao"],
                            qtd,
                            0,
                            custo,
                            total,
                            "",                         # Data Inicio Fabricacao
                            "",                         # Data Fim
                            "",                         # Recebido por
                            "",                         # Fabricante
                            ""                          # ID_FORNECEDOR
                        ])

                    df_final = pd.concat([df_nova, pd.DataFrame(novos_itens, columns=df_atual.columns)], ignore_index=True)
                    aba_ordens.clear()
                    aba_ordens.append_row(list(df_atual.columns))
                    aba_ordens.append_rows(df_final.values.tolist(), value_input_option="USER_ENTERED")
                    st.success("✅ Ordem atualizada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar ordem: {e}")

            if st.button("🔒 Enviar para Validação"):
                try:
                    for i in range(1, len(dados)):
                        if dados[i][0] == str(ordem_selecionada):
                            dados[i][2] = "Em Validacao"
                    aba_ordens.update("A2", dados[1:])
                    st.success("✅ Ordem movida para 'Em Validação'")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao enviar para validação: {e}")
            # Botão de aprovação (somente para validadores)

        elif status_atual == "Em Validacao" and st.session_state.get("perfil") == "Validador":
            st.markdown("### 🔎 Revisão da Ordem")

            # Recria o df_editado
            df_ordem = df_ordem[["ID", "SKU", "Descricao", "Qtd Solicitada", "Qtd Recebida", "Custo Unitario"]]
            df_ordem["Custo Total"] = df_ordem["Qtd Solicitada"].astype(float) * df_ordem["Custo Unitario"].astype(float)
            altura = altura_dinamica(df_ordem)

            df_editado = st.data_editor(
                df_ordem,
                num_rows="dynamic",
                use_container_width=True,
                height=altura,
                hide_index=True,
                column_config={
                    "Descricao": st.column_config.TextColumn(disabled=True),
                    "Custo Unitario": st.column_config.NumberColumn(disabled=True),
                    "Custo Total": st.column_config.NumberColumn(disabled=True),
                    "ID": st.column_config.TextColumn(disabled=True),
                    "Qtd Recebida": st.column_config.NumberColumn(disabled=True),
                }
            )

            if st.button("✅ Aprovar Ordem"):
                try:
                    dados = aba_ordens.get_all_values()
                    cabecalho = dados[0]
                    linhas = [linha + [''] * (len(cabecalho) - len(linha)) for linha in dados[1:]]
                    df_atual = pd.DataFrame(linhas, columns=cabecalho)

                    df_nova = df_atual[df_atual["Numero"] != str(ordem_selecionada)]
                    data_hoje = datetime.now().strftime("%Y-%m-%d")

                    novos_itens = []
                    for _, row in df_editado.iterrows():
                        qtd = safe_float(row["Qtd Solicitada"])
                        custo = safe_float(row["Custo Unitario"])
                        total = qtd * custo
                        novos_itens.append([
                            str(ordem_selecionada),  # Numero
                            data_hoje,               # Data
                            "Aprovada",              # Status
                            row["ID"],
                            row["SKU"],
                            row["Descricao"],
                            qtd,
                            safe_float(row.get("Qtd Recebida", 0)),
                            custo,
                            total,
                            "", "", "", "", ""  # campos adicionais
                        ])

                    df_final = pd.concat([df_nova, pd.DataFrame(novos_itens, columns=df_atual.columns)], ignore_index=True)
                    aba_ordens.clear()
                    aba_ordens.append_row(list(df_atual.columns))
                    aba_ordens.append_rows(df_final.values.tolist(), value_input_option="USER_ENTERED")

                    st.success("✅ Ordem aprovada com sucesso!")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Erro ao aprovar ordem: {e}")
        else:
            # Qualquer outro status = somente visualização
            df_ordem["Custo Total"] = df_ordem["Qtd Solicitada"].astype(float) * df_ordem["Custo Unitario"].astype(float)
            altura = altura_dinamica(df_ordem)
            st.dataframe(df_ordem, use_container_width=True, height=altura)


elif aba == "Promover Ordem":
    df = carregar_ordens()
    ordens_para_promover = df[df['Status'] == 'Conferida']['Numero'].unique()
    ordem = st.selectbox("Selecione a ordem para promover", ordens_para_promover)
    if st.button("Promover"):
        promover_ordem(ordem)
        st.success("Ordem promovida com sucesso!")
elif aba == "Validar Ordem":
    st.subheader("✅ Aprovar Ordens de Produção")
    df = carregar_ordens()
    pendentes = df[df['Status'] == 'Em Validacao']['Numero'].unique()
    ordem = st.selectbox("Selecione a ordem para aprovar", pendentes)

    if st.button("Aprovar Ordem"):
        try:
            aba_ordens = client.open_by_key(sheet_id).worksheet("Ordem_Producao_V2")
            dados = aba_ordens.get_all_values()

            for i in range(1, len(dados)):
                if dados[i][0] == str(ordem):
                    dados[i][2] = "Aprovada"  # Coluna C
            aba_ordens.update("A2", dados[1:])
            st.success("✅ Ordem aprovada com sucesso!")
        except Exception as e:
            st.error(f"Erro ao aprovar ordem: {e}")

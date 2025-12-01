import streamlit as st
import gspread
import pandas as pd
import altair as alt # <-- NOVIDADE: Importação do Altair para gráficos

st.set_page_config(
    page_title="Dashboard de Preços Chevrolet", # <-- Novo título para a aba
    page_icon="📊", # <-- Novo ícone (Emoji de gráfico)
    layout="wide" # Garante que o conteúdo ocupe toda a largura da tela
)

# --- CONSTANTES GERAIS ---
ROW_HEIGHT = 35 
HEADER_HEIGHT = 35


# 1. FUNÇÃO DE INJEÇÃO DE CSS (TEMA ESCURO RESTAURADO + FILTROS NEUTROS)
def inject_custom_css():
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #0E1117;
            color: white;
        }
        h1, h2, h3 {
            color: white;
        }
        h1 {
            text-align: center;
        }
        div[data-testid="stCaptionContainer"] {
            text-align: center;
            color: #CCCCCC;
        }
        span[data-baseweb="tag"] {
            background-color: #495057 !important; 
            color: white !important;
            border: none !important;
        }
        div.stButton > button:first-child {
            white-space: nowrap; 
        }
        .block-container {
            padding-top: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
inject_custom_css()


# --- DADOS DA PLANILHA ---
SHEET_ID = "1fa4HLFfjIFKHjHBuxW_ymHkahVPzeoB_XlHNJMaNCg8"
SHEET_NAME = "Chevrolet Preços"

st.title("🚗 Tabela de Preços Chevrolet (Google Sheets)")
st.caption("Dados carregados diretamente do Google Sheets usando st.secrets.")


# Função de carregamento com cache
@st.cache_data(ttl=600)  
def load_data_from_sheet():
    try:
        credentials = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials)
        spreadsheet = gc.open_by_key(SHEET_ID)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        df = pd.DataFrame(worksheet.get_all_records())
        df['Ano'] = pd.to_numeric(df['Ano'], errors='coerce').fillna(0).astype(int)
        
        # 💡 Garante que a coluna de preço seja numérica para o gráfico/cálculo
        # Remove R$, pontos e vírgulas para conversão.
        df['Preço Numérico'] = pd.to_numeric(
            df['Preço (R$)'].astype(str).str.replace(r'[R$.,]', '', regex=True), 
            errors='coerce'
        )
        
        return df
    
    except KeyError:
        st.error("❌ Erro de Configuração: O segredo 'gcp_service_account' não foi encontrado.")
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erro ao acessar o Google Sheets: {e}")
        st.warning("Verifique se o email de serviço foi adicionado como 'Leitor' na planilha.")
        return pd.DataFrame()


# --- EXECUÇÃO DO APLICATIVO ---
df = load_data_from_sheet()

if not df.empty:
    
    # SEÇÃO DE FILTROS INTERATIVOS
    st.markdown("---")
    st.subheader("Filtros de Dados")
    
    filter_col1, filter_col2 = st.columns(2)
    
    with filter_col1:
        all_models = sorted(df['Modelo'].unique())
        selected_models = st.multiselect("Selecione o(s) Modelo(s) de Carro:", options=all_models, default=all_models)

    with filter_col2:
        all_years = sorted(df['Ano'].unique())
        selected_years = st.multiselect("Selecione o(s) Ano(s) de Fabricação:", options=all_years, default=all_years)

    df_filtered = df[
        (df['Modelo'].isin(selected_models)) &
        (df['Ano'].isin(selected_years))
    ].copy() # Usar .copy() para evitar SettingWithCopyWarning do Pandas

    
    # SEÇÃO DE MÉTRICAS (KPIs)
    if not df_filtered.empty:
        total_carros = len(df_filtered)
        
        # Usa a coluna 'Preço Numérico' criada na função de cache
        prices = df_filtered['Preço Numérico']
        preco_medio = prices.mean()
        preco_max = prices.max()
             
        
        st.markdown("## Resumo das Métricas")
        
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        
        with metric_col1:
            st.metric(label="🚗 Total de Carros Filtrados", value=f"{total_carros} Unidades")
            
        with metric_col2:
            value_medio = f"R$ {preco_medio:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") if preco_medio > 0 else "N/A"
            st.metric(label="💰 Preço Médio (R$)", value=value_medio)
            
        with metric_col3:
            value_max = f"R$ {preco_max:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") if preco_max > 0 else "N/A"
            st.metric(label="🔝 Preço Máximo (R$)", value=value_max)
            
        st.markdown("---") 


        # =============================================================
        # 3. NOVIDADE: GRÁFICO DE BARRAS DE PREÇO MÉDIO
        # =============================================================
        st.markdown("## Visualização: Preço Médio por Modelo")

        # 1. Agrupar os dados filtrados por Modelo e calcular a média do Preço Numérico
        df_chart = df_filtered.groupby('Modelo')['Preço Numérico'].mean().reset_index()
        df_chart.columns = ['Modelo', 'Preço Médio (R$)']
        
        # 2. Criar o gráfico Altair
        chart = alt.Chart(df_chart).mark_bar().encode(
            # Eixo X: Modelo (Ordena por Preço Médio)
            x=alt.X('Modelo', sort='-y'), 
            # Eixo Y: Preço Médio
            y=alt.Y('Preço Médio (R$)', title='Preço Médio (R$)'),
            # Cor: Usar o Preço Médio para intensidade
            color=alt.Color('Preço Médio (R$)', scale=alt.Scale(range='ramp')),
            # Tooltip: Exibe os valores ao passar o mouse
            tooltip=['Modelo', alt.Tooltip('Preço Médio (R$)', format=',.2f')]
        ).properties(
            title='Comparação de Preço Médio entre Modelos Selecionados'
        ).interactive() # Permite zoom e pan

        # 3. Exibir o gráfico no Streamlit
        st.altair_chart(chart, use_container_width=True)

        st.markdown("---") 
    
    # EXIBIÇÃO DA TABELA (DATAFRAME)
    st.subheader(f"Dados da Aba: {SHEET_NAME} (Linhas exibidas: {len(df_filtered)})")
    
    calculated_height = (len(df_filtered) * ROW_HEIGHT) + HEADER_HEIGHT

    st.dataframe(df_filtered.drop(columns=['Preço Numérico'], errors='ignore'), # Remove a coluna auxiliar do preço
                 use_container_width=True, 
                 hide_index=True, 
                 height=calculated_height) 
    
    # Botão de Recarregar
    st.markdown("---") 
    col_left, col_center, col_right = st.columns([3, 4, 3])
    
    with col_center:
        if st.button(
            "🔄 Recarregar Dados", 
            help="Clique para buscar a versão mais recente dos dados da planilha."
        ):
            load_data_from_sheet.clear()
            st.rerun() 
            
else:
    st.warning("Não foi possível carregar os dados ou o filtro retornou zero resultados.")
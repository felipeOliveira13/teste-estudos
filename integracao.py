import streamlit as st
import gspread
import pandas as pd

# --- DADOS DA PLANILHA ---
SHEET_ID = "1fa4HLFfjIFKHjHBuxW_ymHkahVPzeoB_XlHNJMaNCg8"
SHEET_NAME = "Chevrolet Preços"

# Título do Aplicativo Streamlit
st.title("🚗 Tabela de Preços Chevrolet (Google Sheets)")
st.caption("Dados carregados diretamente do Google Sheets usando st.secrets.")


# Função para carregar os dados. O cache garante que a planilha
# só será lida a cada 10 minutos (ttl=600).
# O nome da função é importante, pois o Streamlit a usa como chave de cache.
@st.cache_data(ttl=600)  
def load_data_from_sheet():
    try:
        credentials = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials)
        
        # Abrir planilha e aba
        spreadsheet = gc.open_by_key(SHEET_ID)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        
        # Ler dados da aba e converter para DataFrame
        df = pd.DataFrame(worksheet.get_all_records())
        
        return df
    
    except KeyError:
        st.error("❌ Erro de Configuração: O segredo 'gcp_service_account' não foi encontrado.")
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erro ao acessar o Google Sheets: {e}")
        st.warning("Verifique se o email de serviço foi adicionado como 'Leitor' na planilha.")
        return pd.DataFrame()


# --- NOVO BOTÃO DE RECARREGAMENTO ---
# 1. Cria um contêiner para posicionar o botão acima dos dados.
with st.container():
    col1, col2 = st.columns([1, 4])
    
    # 2. Define a lógica do botão.
    with col1:
        if st.button("🔄 Recarregar Dados"):
            # A linha mágica: Limpa o cache da função específica.
            load_data_from_sheet.clear()
            st.rerun() # Opcional, mas garante o recarregamento imediato
        
    with col2:
        st.info("Clique para buscar a versão mais recente dos dados da planilha.")
        

# --- EXECUÇÃO DO APLICATIVO ---
df = load_data_from_sheet()

if not df.empty:
    st.subheader(f"Dados da Aba: {SHEET_NAME} (Total de linhas: {len(df)})")
    st.dataframe(df)
else:
    st.warning("Não foi possível carregar os dados. Verifique os logs de erro acima.")
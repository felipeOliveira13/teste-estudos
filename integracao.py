import streamlit as st
import gspread
import pandas as pd
# As bibliotecas 'os', 'sys', 'oauth2client.service_account' e 'print' 
# para logs de erro foram removidas, pois o Streamlit trata o fluxo de forma diferente, 
# usando 'st.error' e 'st.warning' para feedback ao usuário.

# --- DADOS DA PLANILHA ---
# ⚠️ IMPORTANTE: CONFIRA SE O NOME DA ABA ESTÁ EXATAMENTE CORRETO
SHEET_ID = "1fa4HLFfjIFKHjHBuxW_ymHkahVPzeoB_XlHNJMaNCg8"
SHEET_NAME = "Chevrolet Preços"

# Título do Aplicativo Streamlit
st.title("🚗 Tabela de Preços Chevrolet (Google Sheets)")
st.caption("Dados carregados diretamente do Google Sheets usando st.secrets.")

# Função para carregar os dados. O cache garante que o Sheets só será lido 
# a cada 10 minutos ou quando o código for alterado.
@st.cache_data(ttl=600)  # ttl=600 segundos (10 minutos)
def load_data_from_sheet():
    try:
        # 1. Carrega as credenciais da seção 'gcp_service_account' do st.secrets
        # Este dicionário é fornecido pelo seu arquivo .streamlit/secrets.toml
        # ou pela configuração de segredos do Streamlit Cloud.
        credentials = st.secrets["gcp_service_account"]
        
        # 2. Autenticação com gspread
        # O gspread já está preparado para aceitar o dicionário de credenciais
        gc = gspread.service_account_from_dict(credentials)
        
        # 3. Abrir planilha e aba
        spreadsheet = gc.open_by_key(SHEET_ID)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        
        # 4. Ler dados da aba e converter para DataFrame
        df = pd.DataFrame(worksheet.get_all_records())
        
        return df
    
    except KeyError:
        # Erro de credenciais (se o segredo não foi configurado corretamente)
        st.error("❌ Erro de Configuração: O segredo 'gcp_service_account' não foi encontrado.")
        st.info("Por favor, certifique-se de que colou o conteúdo TOML na seção 'Secrets' do Streamlit Cloud.")
        return pd.DataFrame()
        
    except Exception as e:
        # Outros erros (ex: permissão negada, planilha não encontrada, nome da aba incorreto)
        st.error(f"❌ Erro ao acessar o Google Sheets: {e}")
        st.warning("Verifique se o email de serviço foi adicionado como 'Leitor' na planilha.")
        return pd.DataFrame()


# --- EXECUÇÃO DO APLICATIVO ---
df = load_data_from_sheet()

if not df.empty:
    st.subheader(f"Dados da Aba: {SHEET_NAME} (Total de linhas: {len(df)})")
    # Exibe o DataFrame como uma tabela interativa no Streamlit
    st.dataframe(df)
else:
    st.warning("Não foi possível carregar os dados. Verifique os logs de erro acima.")
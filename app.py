import streamlit as st
import gspread
import pandas as pd
import altair as alt
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import os

# ----------------------------------------------------------------------
# 1. FUNÇÕES DE CONEXÃO E SEGURANÇA (Passo 2.2)
# ----------------------------------------------------------------------

# --- ESTADO DA SESSÃO ---
# Inicializa o estado de login se ainda não existir
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None

# --- CONEXÃO BD ---
# Esta função garante que a conexão seja aberta apenas uma vez.
@st.cache_resource
def init_connection():
    try:
        db_config = st.secrets["db_credentials"]
        return psycopg2.connect(
            database=db_config["database"],
            user=db_config["username"],
            password=db_config["password"],
            host=db_config["host"],
            port=db_config["port"]
        )
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

# Tenta criar a conexão
conn = init_connection()

# --- FUNÇÕES DE SEGURANÇA (BCRYPT) ---
def hash_password(password):
    # Gera um hash seguro da senha
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')

def verify_password(password, hashed_password):
    # Verifica se a senha corresponde ao hash
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

# --- FUNÇÕES DE GERENCIAMENTO DE USUÁRIOS (BD) ---
def get_user(email):
    if not conn: return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            return user
    except Exception as e:
        st.error(f"Erro ao buscar usuário no BD: {e}")
        return None

def create_user(email, password, name):
    if not conn: return "Falha na conexão com o banco de dados."
    password_hash = hash_password(password)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s)",
                (email, password_hash, name)
            )
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return "Email já cadastrado."
    except Exception as e:
        conn.rollback()
        return f"Erro ao criar usuário: {e}"

# ----------------------------------------------------------------------
# 2. CONFIGURAÇÃO, CSS E DADOS (Seu Código Existente)
# ----------------------------------------------------------------------

st.set_page_config(
    page_title="Dashboard de Preços Chevrolet",
    page_icon="📊",
    layout="wide"
)

# --- CONSTANTES GERAIS ---
ROW_HEIGHT = 35 
HEADER_HEIGHT = 35

# --- FUNÇÃO DE INJEÇÃO DE CSS (MANTIDA) ---
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
        
        # Garante que a coluna de preço seja numérica para o gráfico/cálculo
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


# ----------------------------------------------------------------------
# 3. LÓGICA DE AUTENTICAÇÃO E NAVEGAÇÃO
# ----------------------------------------------------------------------

# ⚠️ DEFINIÇÃO DOS DOMÍNIOS PERMITIDOS ⚠️
DOMINIOS_PERMITIDOS = ["botafogo.com.br", "gmail.com"]


# --- FUNÇÕES DA INTERFACE ---
def render_login():
    st.title("🔒 Acesso Restrito")
    
    # Se a conexão falhou, exibe um erro e impede o login
    if not conn:
        st.error("Serviço de autenticação indisponível. Verifique as credenciais do banco de dados.")
        return

    with st.form("login_form"):
        email = st.text_input("Email", key="login_email").lower()
        password = st.text_input("Senha", type="password", key="login_password")
        submit_button = st.form_submit_button("Entrar")

        if submit_button:
            if email and password:
                user = get_user(email)
                if user:
                    if verify_password(password, user['password_hash']):
                        st.session_state.logged_in = True
                        st.session_state.user_email = user['email']
                        st.session_state.user_name = user['name']
                        st.success(f"Bem-vindo(a), {user['name']}!")
                        st.rerun()
                    else:
                        st.error("Email ou senha incorretos.")
                else:
                    st.error("Email ou senha incorretos.")
            else:
                st.warning("Preencha todos os campos.")

    st.markdown("---")
    st.markdown("Ainda não tem conta? Clique no menu lateral (☰) e escolha **Cadastrar**.")


def render_register():
    st.title("✍️ Cadastro de Novo Usuário")
    st.info(f"O cadastro é restrito a e-mails com os domínios: **{'** ou **'.join(DOMINIOS_PERMITIDOS)}**.")
    
    if not conn:
        st.error("Serviço de autenticação indisponível. Verifique as credenciais do banco de dados.")
        return

    with st.form("register_form"):
        name = st.text_input("Nome Completo")
        email = st.text_input("Email Corporativo").lower()
        password = st.text_input("Senha", type="password")
        password_confirm = st.text_input("Confirme a Senha", type="password")
        submit_button = st.form_submit_button("Cadastrar")

        if submit_button:
            # 1. Validação de Domínio
            is_domain_allowed = any(email.endswith(f"@{domain}") for domain in DOMINIOS_PERMITIDOS)
            
            if not is_domain_allowed:
                st.error(f"O email deve pertencer a um dos domínios permitidos: {', '.join(DOMINIOS_PERMITIDOS)}.")
            # 2. Validação de Campos/Senhas
            elif not (name and email and password and password_confirm):
                st.error("Preencha todos os campos.")
            elif password != password_confirm:
                st.error("As senhas não coincidem.")
            elif len(password) < 6:
                st.error("A senha deve ter no mínimo 6 caracteres.")
            # 3. Criação do Usuário
            else:
                result = create_user(email, password, name)
                if result is True:
                    st.success("Cadastro realizado com sucesso! Faça login na página principal.")
                else:
                    st.error(f"Falha no cadastro: {result}")

# --- CONTROLE PRINCIPAL DA APLICAÇÃO ---

if st.session_state.logged_in:
    # SEÇÃO PROTEGIDA: DASHBOARD
    st.sidebar.button("🔓 Logout", on_click=lambda: st.session_state.update(logged_in=False, user_email=None, user_name=None))
    st.sidebar.success(f"Logado como: {st.session_state.user_name}")

    # --- EXECUÇÃO DO APLICATIVO ---
    df = load_data_from_sheet()

    if not df.empty:
        
        st.title("🚗 Tabela de Preços (Google Sheets)")
        st.caption("Dados carregados diretamente do Google Sheets usando st.secrets.")

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
        ].copy() 

        
        # SEÇÃO DE MÉTRICAS (KPIs)
        if not df_filtered.empty:
            total_carros = len(df_filtered)
            
            prices = df_filtered['Preço Numérico']
            preco_medio = prices.mean()
            preco_max = prices.max()
            
            st.markdown("## Resumo das Métricas")
            
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            
            # Formatação dos valores para o formato R$ brasileiro
            def format_currency(value):
                if value > 0:
                    # Substitui vírgula por underline temporariamente, ponto por vírgula, e underline por ponto
                    return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
                return "N/A"
            
            with metric_col1:
                st.metric(label="🚗 Total de Carros Filtrados", value=f"{total_carros} Unidades")
                
            with metric_col2:
                st.metric(label="💰 Preço Médio (R$)", value=format_currency(preco_medio))
                
            with metric_col3:
                st.metric(label="🔝 Preço Máximo (R$)", value=format_currency(preco_max))
                
            st.markdown("---") 


            # =============================================================
            # GRÁFICO DE BARRAS DE PREÇO MÉDIO (ALTAIR)
            # =============================================================
            st.markdown("## Visualização: Preço Médio por Modelo")

            df_chart = df_filtered.groupby('Modelo')['Preço Numérico'].mean().reset_index()
            df_chart.columns = ['Modelo', 'Preço Médio (R$)']
            
            # Gráfico
            chart = alt.Chart(df_chart).mark_bar().encode(
                x=alt.X('Modelo', sort='-y'), 
                y=alt.Y('Preço Médio (R$)', title='Preço Médio (R$)'),
                color=alt.Color('Preço Médio (R$)', scale=alt.Scale(range='ramp')),
                tooltip=['Modelo', alt.Tooltip('Preço Médio (R$)', format=',.2f')]
            ).properties(
                title='Comparação de Preço Médio entre Modelos Selecionados'
            ).interactive() 

            st.altair_chart(chart, use_container_width=True)

            st.markdown("---") 
        
        # EXIBIÇÃO DA TABELA (DATAFRAME)
        st.subheader(f"Dados da Aba: {SHEET_NAME} (Linhas exibidas: {len(df_filtered)})")
        
        calculated_height = (len(df_filtered) * ROW_HEIGHT) + HEADER_HEIGHT

        st.dataframe(df_filtered.drop(columns=['Preço Numérico'], errors='ignore'), 
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

else:
    # SEÇÃO PÚBLICA (Login/Registro)
    menu = st.sidebar.radio("Selecione a Ação", ["Login", "Cadastrar"])

    if menu == "Login":
        render_login()
    elif menu == "Cadastrar":
        render_register()
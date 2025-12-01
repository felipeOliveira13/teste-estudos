import streamlit as st
import gspread
import pandas as pd
import altair as alt
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import os

# --- VARIÁVEIS DE CONFIGURAÇÃO ---
EMAIL_DOMAINS = ["botafogos.com.br", "gmail.com"]

# --- FUNÇÃO DE CONEXÃO COM O BANCO DE DADOS ---

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados PostgreSQL (Supabase) usando parâmetros explícitos de rede e SSL."""
    
    db_config = st.secrets.get("db_credentials")
    
    if not db_config:
        st.error("❌ Erro de Configuração: O bloco [db_credentials] não foi encontrado no secrets.toml.")
        return None
        
    conn = None
    try:
        # Tenta a conexão usando parâmetros explícitos para garantir que o psycopg2 use o HOST e a PORTA
        # O 'sslmode=require' é obrigatório para o Supabase no Streamlit
        conn = psycopg2.connect(
            database=db_config['database'],
            user=db_config['username'],
            password=db_config['password'],
            host=db_config['host'],
            port=db_config['port'],
            sslmode='require' 
        )
        return conn
    except psycopg2.OperationalError as e:
        # Se falhar, mostra o erro
        st.error(f"❌ Erro Crítico de Conexão: O banco de dados recusou a conexão. Verifique o firewall, credenciais e o status do banco. Detalhes: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Ocorreu um erro inesperado na conexão com o banco de dados: {e}")
        return None

# --- FUNÇÕES DE SEGURANÇA ---

def hash_password(password):
    """Gera o hash da senha usando bcrypt."""
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')

def check_password(password, hashed_password):
    """Verifica se a senha fornecida corresponde ao hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_user_table(conn):
    """Cria a tabela 'users' se ela não existir."""
    if conn is None:
        return
        
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)
        conn.commit()
        st.success("Tabela de usuários verificada/criada com sucesso. Tente Cadastrar.")
    except Exception as e:
        st.error(f"Erro ao criar a tabela de usuários: {e}")
    finally:
        if cur: cur.close()

def register_user(conn, username, email, password):
    """Registra um novo usuário no banco de dados."""
    if conn is None:
        return False, "Falha na conexão com o banco de dados."

    cur = None
    try:
        cur = conn.cursor()
        hashed_password = hash_password(password)
        
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, hashed_password)
        )
        conn.commit()
        return True, "Usuário registrado com sucesso! Você pode fazer login agora."
    except psycopg2.IntegrityError:
        return False, "Erro: Nome de usuário ou e-mail já existe."
    except Exception as e:
        return False, f"Erro ao registrar usuário: {e}"
    finally:
        if cur: cur.close()

def authenticate_user(conn, username, password):
    """Autentica o usuário e retorna o hash da senha e o ID."""
    if conn is None:
        return None, "Falha na conexão com o banco de dados."

    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT password_hash FROM users WHERE username = %s",
            (username,)
        )
        user_data = cur.fetchone()
        
        if user_data:
            if check_password(password, user_data['password_hash']):
                return True, "Login bem-sucedido!"
            else:
                return False, "Senha incorreta."
        else:
            return False, "Usuário não encontrado."
    except Exception as e:
        return False, f"Erro durante a autenticação: {e}"
    finally:
        if cur: cur.close()

# --- FUNÇÕES DE CARREGAMENTO DE DADOS (EXISTENTES) ---

SHEET_ID = "1fa4HLFfjIFKHjHBuxW_ymHkahVPzeoB_XlHNJMaNCg8"
SHEET_NAME = "Chevrolet Preços"

@st.cache_data(ttl=600)
def load_data_from_sheet():
    # ... (Sua função de carregamento de dados do Google Sheets)
    try:
        credentials = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials)
        spreadsheet = gc.open_by_key(SHEET_ID)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        df = pd.DataFrame(worksheet.get_all_records())
        df['Ano'] = pd.to_numeric(df['Ano'], errors='coerce').fillna(0).astype(int)
        
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

# --- LAYOUT DAS PÁGINAS ---

def login_page():
    st.subheader("Login de Usuário")
    with st.form("login_form"):
        username = st.text_input("Nome de Usuário")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")

        if submitted:
            conn = get_db_connection()
            if conn:
                success, message = authenticate_user(conn, username, password)
                if success:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.success(f"Bem-vindo, {username}!")
                    st.rerun()
                else:
                    st.error(message)
                conn.close()

def register_page():
    st.subheader("Cadastro de Novo Usuário")
    st.info(f"O cadastro é restrito a e-mails com os domínios: {', '.join(EMAIL_DOMAINS)}.")

    with st.form("register_form"):
        username = st.text_input("Nome de Usuário")
        email = st.text_input("E-mail")
        password = st.text_input("Senha", type="password")
        password_confirm = st.text_input("Confirmar Senha", type="password")
        submitted = st.form_submit_button("Cadastrar")

        if submitted:
            # 1. Validação de Domínio de E-mail
            if not any(email.endswith(f"@{domain}") for domain in EMAIL_DOMAINS):
                st.error("E-mail inválido. Use um dos domínios permitidos.")
            # 2. Validação de Senha
            elif password != password_confirm:
                st.error("As senhas não coincidem.")
            elif len(password) < 6:
                st.error("A senha deve ter pelo menos 6 caracteres.")
            else:
                conn = get_db_connection()
                if conn:
                    # Tenta registrar o usuário
                    success, message = register_user(conn, username, email, password)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                    conn.close()


def main_app():
    st.title("🚗 Tabela de Preços Chevrolet (Google Sheets)")
    
    # Exibe o usuário logado
    st.sidebar.success(f"Logado como: {st.session_state.get('username', 'Usuário')}")
    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False
        st.session_state["username"] = None
        st.rerun()

    st.caption("Dados carregados diretamente do Google Sheets usando st.secrets.")

    # Carrega os dados (função protegida por cache)
    df = load_data_from_sheet()

    if not df.empty:
        st.subheader(f"Dados da Aba: {SHEET_NAME} (Total de linhas: {len(df)})")
        
        # --- FILTROS DE DADOS ---
        st.markdown("### Filtros de Dados")
        col_model, col_year = st.columns(2)

        with col_model:
            selected_models = st.multiselect(
                "Selecione o(s) Modelo(s) de Carro:",
                options=df['Modelo'].unique(),
                default=df['Modelo'].unique()
            )
        
        with col_year:
            selected_years = st.multiselect(
                "Selecione o(s) Ano(s) de Fabricação:",
                options=df['Ano'].unique(),
                default=df['Ano'].unique()
            )
        
        # Aplica o filtro
        df_filtered = df[
            (df['Modelo'].isin(selected_models)) &
            (df['Ano'].isin(selected_years))
        ]

        if df_filtered.empty:
            st.warning("Não foi possível carregar os dados ou o filtro retornou zero resultados.")
        else:
            # --- TABELA DE DADOS ---
            st.dataframe(df_filtered[['Modelo', 'Ano', 'Preço (R$)']])
            
            # --- GRÁFICO (Exemplo) ---
            st.subheader("Gráfico de Preços por Ano")
            
            # Agrupa por ano e calcula a média do preço
            df_plot = df_filtered.groupby('Ano')['Preço Numérico'].mean().reset_index()
            df_plot.columns = ['Ano', 'Preço Médio (R$)']

            # Cria o gráfico Altair
            chart = alt.Chart(df_plot).mark_line(point=True).encode(
                x=alt.X('Ano:O', title='Ano de Fabricação'), # 'O' for Ordinal
                y=alt.Y('Preço Médio (R$)', title='Preço Médio (R$)', axis=alt.Axis(format='$,.0f')),
                tooltip=['Ano', alt.Tooltip('Preço Médio (R$)', format='$,.0f')]
            ).properties(
                title='Preço Médio dos Carros Selecionados por Ano'
            ).interactive() # Permite zoom e pan

            st.altair_chart(chart, use_container_width=True)

    # Botão de recarga para forçar a busca de novos dados
    st.button("Recarregar Dados", on_click=load_data_from_sheet.clear)


# --- LÓGICA DE NAVEGAÇÃO PRINCIPAL ---

# 1. Inicialização do Session State
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Login"

# 2. Tela principal
if st.session_state["logged_in"]:
    main_app()
else:
    # Mostra a tela de login/cadastro
    st.title("🔐 Autenticação de Usuário")
    
    st.sidebar.subheader("Selecione a Ação")
    action = st.sidebar.radio(" ", ("Login", "Cadastrar"))

    # Verifica a conexão no início, antes de renderizar a tela de login/cadastro
    conn = get_db_connection()
    if conn:
        conn.close()
        # Se a conexão for bem-sucedida, garante que a tabela existe
        with get_db_connection() as conn_init:
            create_user_table(conn_init)
        
        if action == "Login":
            login_page()
        elif action == "Cadastrar":
            register_page()
            
    # Mensagem de erro de conexão aparecerá dentro da get_db_connection() se falhar.
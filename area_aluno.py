import streamlit as st
import pyrebase
import time
import json
from google.cloud import firestore
from google.oauth2 import service_account

# 1. Configuração da Página
st.set_page_config(page_title="Área do Aluno - Redação", page_icon="📝", layout="centered")

# 2. Configuração do Firebase Auth (Login)
firebaseConfig = {
  "apiKey": "AIzaSyBBxjGQkN_b-keKwXw9KQq-W8l76D6C2zA",
  "authDomain": "plataforma-redacao-de0f3.firebaseapp.com",
  "projectId": "plataforma-redacao-de0f3",
  "storageBucket": "plataforma-redacao-de0f3.firebasestorage.app",
  "messagingSenderId": "105466681652",
  "appId": "1:105466681652:web:13438e4cbd600a1c3a2d61",
  "databaseURL": "" 
}

# Inicialização segura do Auth
@st.cache_resource
def iniciar_firebase():
    return pyrebase.initialize_app(firebaseConfig)

# Inicialização segura do Firestore (Banco de Dados)
@st.cache_resource
def iniciar_firestore():
    # Puxa a chave JSON que você colou nos Secrets do Streamlit Cloud
    info_chave = json.loads(st.secrets["firebase_service_account"])
    credenciais = service_account.Credentials.from_service_account_info(info_chave)
    return firestore.Client(credentials=credenciais, project=info_chave['project_id'])

firebase = iniciar_firebase()
auth = firebase.auth()
db = iniciar_firestore()

# Inicializando o estado de login
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'email_usuario' not in st.session_state:
    st.session_state.email_usuario = ""

# ==========================================
# ESTRUTURA PRINCIPAL DO APP
# ==========================================

# Se NÃO estiver logado, mostra APENAS a tela de login
if st.session_state.logado == False:
    st.title("🔐 Acesso à Plataforma")
    aba1, aba2 = st.tabs(["Login", "Cadastrar"])

    with aba1:
        with st.form("login_form"):
            email_input = st.text_input("E-mail")
            senha_input = st.text_input("Senha", type="password")
            btn_login = st.form_submit_button("Entrar", type="primary")

            if btn_login:
                try:
                    user = auth.sign_in_with_email_and_password(email_input, senha_input)
                    st.session_state.logado = True
                    st.session_state.email_usuario = email_input
                    st.success("Login realizado! Entrando...")
                    time.sleep(0.5) 
                    st.rerun()
                except Exception as e:
                    if "RerunException" not in str(type(e)):
                        st.error("E-mail ou senha incorretos. Tente novamente.")

    with aba2:
        with st.form("signup_form"):
            email_novo = st.text_input("Novo E-mail")
            senha_nova = st.text_input("Nova Senha", type="password")
            btn_criar = st.form_submit_button("Criar Conta")

            if btn_criar:
                try:
                    auth.create_user_with_email_and_password(email_novo, senha_nova)
                    st.success("Conta criada! Agora faça o login na aba ao lado.")
                except:
                    st.error("Erro ao criar conta. Verifique os dados.")

# Se ESTIVER logado, mostra APENAS a área do aluno
elif st.session_state.logado == True:
    # --- Sidebar ---
    st.sidebar.title("Painel do Aluno")
    st.sidebar.info(f"Logado como:\n{st.session_state.email_usuario}")
    
    if st.sidebar.button("Sair da Conta"):
        st.session_state.logado = False
        st.session_state.email_usuario = ""
        st.rerun()

    # --- Conteúdo Principal ---
    st.title("📝 Envio de Redação")
    
    tema = st.selectbox("Selecione o tema:", ["Escolha...", "Impactos da IA", "Saúde Mental"])
    
    if tema != "Escolha...":
        with st.form("envio_redacao"):
            texto = st.text_area("Sua redação:", height=400)
            enviar = st.form_submit_button("Enviar para Correção", type="primary")
            
            if enviar:
                if len(texto) > 100:
                    try:
                        # Criando o registro da redação
                        nova_redacao = {
                            "aluno_email": st.session_state.email_usuario,
                            "tema": tema,
                            "texto": texto,
                            "data_envio": firestore.SERVER_TIMESTAMP,
                            "status": "Pendente",
                            "nota_final": 0
                        }
                        
                        # Salva no Firestore na coleção 'redacoes'
                        db.collection("redacoes").add(nova_redacao)
                        
                        st.success("🚀 Redação enviada com sucesso! Agora é só aguardar o corretor.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erro ao salvar no banco de dados: {e}")
                else:
                    st.warning("O texto está muito curto para ser uma redação (mínimo 100 caracteres).")

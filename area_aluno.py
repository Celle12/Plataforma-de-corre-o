import streamlit as st
import pyrebase

# 1. Configuração da Página
st.set_page_config(page_title="Área do Aluno - Redação", page_icon="📝", layout="centered")

# 2. Configuração do Firebase
firebaseConfig = {
  "apiKey": "AIzaSyBBxjGQkN_b-keKwXw9KQq-W8l76D6C2zA",
  "authDomain": "plataforma-redacao-de0f3.firebaseapp.com",
  "projectId": "plataforma-redacao-de0f3",
  "storageBucket": "plataforma-redacao-de0f3.firebasestorage.app",
  "messagingSenderId": "105466681652",
  "appId": "1:105466681652:web:13438e4cbd600a1c3a2d61",
  "databaseURL": "" 
}

# Inicialização segura do Firebase
@st.cache_resource
def iniciar_firebase():
    return pyrebase.initialize_app(firebaseConfig)

firebase = iniciar_firebase()
auth = firebase.auth()

# Inicializando o estado de login
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'email_usuario' not in st.session_state:
    st.session_state.email_usuario = ""

# ==========================================
# LÓGICA DE TRANSIÇÃO DE TELAS
# ==========================================

if not st.session_state.logado:
    st.title("🔐 Acesso à Plataforma")
    aba1, aba2 = st.tabs(["Login", "Cadastrar"])

    with aba1:
        # Criando um formulário para o Login
        with st.form("form_login"):
            email_login = st.text_input("E-mail")
            senha_login = st.text_input("Senha", type="password")
            botao_entrar = st.form_submit_button("Entrar", type="primary")
            
            if botao_entrar:
                try:
                    usuario = auth.sign_in_with_email_and_password(email_login, senha_login)
                    st.session_state.logado = True
                    st.session_state.email_usuario = email_login
                    st.rerun() 
                except:
                    st.error("E-mail ou senha incorretos. Verifique seus dados.")

    with aba2:
        # Criando um formulário para o Cadastro
        with st.form("form_cadastro"):
            email_cadastro = st.text_input("Novo E-mail")
            senha_cadastro = st.text_input("Nova Senha", type="password", help="Mínimo 6 caracteres")
            botao_cadastrar = st.form_submit_button("Criar Minha Conta")
            
            if botao_cadastrar:
                try:
                    auth.create_user_with_email_and_password(email_cadastro, senha_cadastro)
                    st.success("Conta criada com sucesso! Agora você pode fazer login.")
                except Exception as e:
                    st.error("Erro ao cadastrar. Verifique o e-mail ou se a senha tem 6+ caracteres.")

else:
    # --- TELA DO ALUNO ---
    st.sidebar.title("Meu Painel")
    st.sidebar.write(f"👤 **Usuário:**\n{st.session_state.email_usuario}")
    st.sidebar.divider()
    
    if st.sidebar.button("Sair da Conta"):
        st.session_state.logado = False
        st.session_state.email_usuario = ""
        st.rerun()

    st.title("📝 Envio de Redação")
    st.write("Selecione o tema desejado e envie seu texto para a nossa equipe.")

    st.subheader("1. Tema da Redação")
    temas_disponiveis = [
        "Selecione um tema...", 
        "Os impactos da IA na educação", 
        "Desigualdade social no Brasil",
        "Saúde mental na adolescência"
    ]
    tema_escolhido = st.selectbox("Sobre o que você vai escrever hoje?", temas_disponiveis)

    if tema_escolhido != "Selecione um tema...":
        st.subheader("2. Envie seu Texto")
        # Também podemos usar form aqui para garantir o envio correto do texto longo
        with st.form("form_redacao"):
            texto_redacao = st.text_area("Digite ou cole sua redação aqui:", height=350)
            botao_enviar = st.form_submit_button("Enviar para Correção", type="primary")
            
            if botao_enviar:
                if len(texto_redacao) > 100:
                    st.success("🚀 Redação enviada com sucesso!")
                    st.balloons()
                else:
                    st.warning("Seu texto está muito curto para uma redação.")

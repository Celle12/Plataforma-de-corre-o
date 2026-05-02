import streamlit as st
import pyrebase

# 1. Configuração da Página
st.set_page_config(page_title="Área do Aluno - Redação", page_icon="📝", layout="centered")

# 2. Configuração do Firebase
# Mantive as chaves que você enviou
firebaseConfig = {
  "apiKey": "AIzaSyBBxjGQkN_b-keKwXw9KQq-W8l76D6C2zA",
  "authDomain": "plataforma-redacao-de0f3.firebaseapp.com",
  "projectId": "plataforma-redacao-de0f3",
  "storageBucket": "plataforma-redacao-de0f3.firebasestorage.app",
  "messagingSenderId": "105466681652",
  "appId": "1:105466681652:web:13438e4cbd600a1c3a2d61",
  "databaseURL": "" 
}

# Conectando ao Firebase
# Usamos o cache do streamlit para não ficar reinicializando o app toda hora
@st.cache_resource
def iniciar_firebase():
    return pyrebase.initialize_app(firebaseConfig)

firebase = iniciar_firebase()
auth = firebase.auth()

# 3. Inicializando o estado de login
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'email_usuario' not in st.session_state:
    st.session_state.email_usuario = ""

# ==========================================
# LÓGICA DE TRANSIÇÃO DE TELAS
# ==========================================

if not st.session_state.logado:
    # --- TELA DE LOGIN / CADASTRO ---
    st.title("🔐 Acesso à Plataforma")
    aba1, aba2 = st.tabs(["Login", "Cadastrar"])

    with aba1:
        email_login = st.text_input("E-mail", key="login_email")
        senha_login = st.text_input("Senha", type="password", key="login_senha")
        if st.button("Entrar", type="primary"):
            try:
                usuario = auth.sign_in_with_email_and_password(email_login, senha_login)
                st.session_state.logado = True
                st.session_state.email_usuario = email_login
                st.rerun() 
            except:
                st.error("E-mail ou senha incorretos. Verifique seus dados.")

    with aba2:
        email_cadastro = st.text_input("Novo E-mail", key="cad_email")
        senha_cadastro = st.text_input("Nova Senha", type="password", key="cad_senha", help="Mínimo 6 caracteres")
        if st.button("Criar Minha Conta"):
            try:
                auth.create_user_with_email_and_password(email_cadastro, senha_cadastro)
                st.success("Conta criada com sucesso! Agora clique na aba 'Login' acima.")
            except:
                st.error("Erro ao cadastrar. Verifique se o e-mail é válido ou se já possui conta.")

else:
    # --- TELA DO ALUNO (SÓ APARECE QUANDO LOGADO) ---
    st.sidebar.title("Meu Painel")
    st.sidebar.write(f"👤 **Usuário:**\n{st.session_state.email_usuario}")
    st.sidebar.divider()
    
    if st.sidebar.button("Sair da Conta"):
        st.session_state.logado = False
        st.session_state.email_usuario = ""
        st.rerun()

    st.title("📝 Envio de Redação")
    st.write("Selecione o tema desejado e envie seu texto para a nossa equipe de corretores.")

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
        texto_redacao = st.text_area("Digite ou cole sua redação aqui:", height=350, placeholder="Mínimo de 10 linhas...")
        
        if st.button("Enviar para Correção", type="primary"):
            if len(texto_redacao) > 100:
                # Aqui no futuro conectaremos com o Firestore
                st.success("🚀 Redação enviada com sucesso! Você receberá a correção em breve.")
                st.balloons()
            else:
                st.warning("Seu texto parece muito curto. Tente escrever um pouco mais antes de enviar.")

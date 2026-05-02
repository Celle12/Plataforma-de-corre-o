import streamlit as st
import pyrebase

# 1. Configuração da Página
st.set_page_config(page_title="Área do Aluno - Redação", page_icon="📝", layout="centered")

# 2. Configuração do Firebase (COLE SUAS CHAVES AQUI)
firebaseConfig = {
  "apiKey": "SUA_API_KEY_AQUI",
  "authDomain": "SEU_PROJETO.firebaseapp.com",
  "projectId": "SEU_PROJETO",
  "storageBucket": "SEU_PROJETO.appspot.com",
  "messagingSenderId": "NUMERO",
  "appId": "SEU_APP_ID",
  "databaseURL": "" # Se não tiver, pode deixar vazio
}

# Conectando ao Firebase
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

# 3. Criando o "Crachá" de Login (Session State)
if 'logado' not in st.session_state:
    st.session_state.logado = False

# ==========================================
# TELA DE LOGIN / CADASTRO
# ==========================================
if not st.session_state.logado:
    st.title("🔐 Acesso à Plataforma")
    aba1, aba2 = st.tabs(["Login", "Cadastrar"])

    with aba1:
        email_login = st.text_input("E-mail")
        senha_login = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            try:
                # Tenta fazer o login no Firebase
                usuario = auth.sign_in_with_email_and_password(email_login, senha_login)
                st.session_state.logado = True
                st.session_state.email_usuario = email_login
                st.rerun() # Recarrega a página para entrar no app
            except:
                st.error("E-mail ou senha incorretos.")

    with aba2:
        email_cadastro = st.text_input("Novo E-mail")
        senha_cadastro = st.text_input("Nova Senha", type="password", help="Mínimo 6 caracteres")
        if st.button("Criar Conta"):
            try:
                # Cria o usuário no Firebase
                auth.create_user_with_email_and_password(email_cadastro, senha_cadastro)
                st.success("Conta criada! Agora vá na aba de Login para entrar.")
            except:
                st.error("Erro ao criar conta. Verifique se o e-mail é válido e a senha tem 6+ caracteres.")

# ==========================================
# TELA DO ALUNO (SÓ APARECE SE LOGADO)
# ==========================================
if st.session_state.logado:
    st.sidebar.title("Meu Painel")
    st.sidebar.write(f"👤 {st.session_state.email_usuario}")
    st.sidebar.divider()
    
    # Botão de Sair
    if st.sidebar.button("Sair da Conta"):
        st.session_state.logado = False
        st.rerun()

    # --- AQUI VEM O CÓDIGO DA REDAÇÃO QUE FIZEMOS ANTES ---
    st.title("📝 Envio de Redação")
    st.write("Escolha o tema da semana e envie seu texto para correção.")

    st.subheader("1. Tema da Redação")
    temas_disponiveis = ["Selecione um tema...", "Os impactos da IA na educação", "Desigualdade social no Brasil"]
    tema_escolhido = st.selectbox("Qual tema você vai escrever?", temas_disponiveis)

    if tema_escolhido != "Selecione um tema...":
        st.subheader("2. Envie seu Texto")
        texto_redacao = st.text_area("Cole ou digite sua redação:", height=300)
        
        if st.button("Enviar Redação", type="primary"):
            st.success("✅ Redação enviada! (Integração de salvar no banco em breve)")

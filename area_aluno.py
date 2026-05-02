import streamlit as st
import pyrebase
import time
import json
from google.cloud import firestore, storage
from google.oauth2 import service_account

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

# Inicialização dos Clientes (Firestore e Storage)
@st.cache_resource
def iniciar_servicos():
    info_chave = json.loads(st.secrets["firebase_service_account"])
    credenciais = service_account.Credentials.from_service_account_info(info_chave)
    
    # Cliente Firestore
    db = firestore.Client(credentials=credenciais, project=info_chave['project_id'])
    
    # Cliente Storage
    storage_client = storage.Client(credentials=credenciais, project=info_chave['project_id'])
    bucket = storage_client.bucket(firebaseConfig["storageBucket"])
    
    return db, bucket

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
db, bucket = iniciar_servicos()

# Inicialização do session_state
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'email_usuario' not in st.session_state:
    st.session_state.email_usuario = ""
if 'nome_usuario' not in st.session_state:
    st.session_state.nome_usuario = ""

# --- LÓGICA DE ACESSO ---
if st.session_state.logado == False:
    st.title("🔐 Acesso à Plataforma")
    aba1, aba2 = st.tabs(["Login", "Cadastrar"])
    
    with aba1:
        with st.form("login_form"):
            email_input = st.text_input("E-mail")
            senha_input = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", type="primary"):
                try:
                    user = auth.sign_in_with_email_and_password(email_input, senha_input)
                    
                    # BUSCA O NOME NO FIRESTORE (Alteração 1)
                    doc_ref = db.collection("usuarios").document(email_input).get()
                    if doc_ref.exists:
                        st.session_state.nome_usuario = doc_ref.to_dict().get("nome")
                    else:
                        st.session_state.nome_usuario = email_input # Caso não encontre, usa o e-mail

                    st.session_state.logado = True
                    st.session_state.email_usuario = email_input
                    st.rerun()
                except Exception as e:
                    if "RerunException" not in str(type(e)):
                        st.error("Dados incorretos.")
    
    with aba2:
        with st.form("signup_form"):
            # NOVO CAMPO DE NOME (Alteração 2)
            nome_completo = st.text_input("Nome Completo")
            email_novo = st.text_input("Novo E-mail")
            senha_nova = st.text_input("Nova Senha", type="password")
            
            if st.form_submit_button("Criar Conta"):
                if nome_completo and email_novo and senha_nova:
                    try:
                        auth.create_user_with_email_and_password(email_novo, senha_nova)
                        
                        # SALVA O NOME VINCULADO AO E-MAIL NO FIRESTORE
                        db.collection("usuarios").document(email_novo).set({
                            "nome": nome_completo,
                            "email": email_novo
                        })
                        
                        st.success("Conta criada! Agora faça o login na aba ao lado.")
                    except:
                        st.error("Erro ao criar conta. Verifique se o e-mail é válido.")
                else:
                    st.warning("Por favor, preencha todos os campos.")

# --- ÁREA DO ALUNO ---
elif st.session_state.logado == True:
    st.sidebar.title("Painel do Aluno")
    # Mostra o nome real se estiver disponível
    exibir_nome = st.session_state.nome_usuario if st.session_state.nome_usuario else st.session_state.email_usuario
    st.sidebar.info(f"👤 {exibir_nome}")
    
    if st.sidebar.button("Sair da Conta"):
        st.session_state.logado = False
        st.rerun()

    st.title("📝 Envio de Redação")
    tema = st.selectbox("Selecione o tema:", ["Escolha...", "Impactos da IA", "Saúde Mental"])
    
    if tema != "Escolha...":
        st.subheader("Como você quer enviar sua redação?")
        metodo = st.radio("Escolha o formato:", ["Digitar Texto", "Anexar Arquivo (Foto/PDF)"], horizontal=True)

        with st.form("envio_redacao", clear_on_submit=True):
            if metodo == "Digitar Texto":
                texto_redacao = st.text_area("Sua redação:", height=350)
                arquivo_upload = None
            else:
                texto_redacao = ""
                arquivo_upload = st.file_uploader("Selecione a foto ou PDF da sua redação", type=["png", "jpg", "jpeg", "pdf"])

            enviar = st.form_submit_button("Enviar para Correção", type="primary")
            
            if enviar:
                try:
                    url_arquivo = ""
                    tipo_envio = "texto"

                    if metodo == "Anexar Arquivo (Foto/PDF)" and arquivo_upload:
                        nome_blob = f"redacoes/{st.session_state.email_usuario}_{int(time.time())}_{arquivo_upload.name}"
                        blob = bucket.blob(nome_blob)
                        blob.upload_from_file(arquivo_upload)
                        url_arquivo = blob.public_url
                        tipo_envio = "arquivo"
                    
                    # PACOTE DE DADOS COM O NOME DO ALUNO (Alteração 3)
                    nova_redacao = {
                        "aluno_nome": st.session_state.nome_usuario, # Nome agora vai aqui
                        "aluno_email": st.session_state.email_usuario,
                        "tema": tema,
                        "texto": texto_redacao,
                        "url_arquivo": url_arquivo,
                        "caminho_storage": nome_blob,
                        "tipo": tipo_envio,
                        "data_envio": firestore.SERVER_TIMESTAMP,
                        "status": "Pendente",
                        "nota_final": 0
                    }
                    
                    if texto_redacao or url_arquivo:
                        db.collection("redacoes").add(nova_redacao)
                        st.success("🚀 Redação enviada com sucesso!")
                        st.balloons()
                    else:
                        st.warning("Por favor, preencha o texto ou anexe um arquivo.")
                        
                except Exception as e:
                    st.error(f"Erro ao enviar: {e}")

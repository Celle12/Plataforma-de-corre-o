import streamlit as st
import json
import time
from io import BytesIO
from PIL import Image, ImageDraw
from google.cloud import firestore, storage
from google.oauth2 import service_account
from streamlit_image_coordinates import streamlit_image_coordinates
from urllib.parse import unquote

# 1. Configuração e Conexão
st.set_page_config(page_title="Painel do Corretor", page_icon="⚖️", layout="wide")

@st.cache_resource
def iniciar_servicos():
    info_chave = json.loads(st.secrets["firebase_service_account"])
    credenciais = service_account.Credentials.from_service_account_info(info_chave)
    db = firestore.Client(credentials=credenciais, project=info_chave['project_id'])
    storage_client = storage.Client(credentials=credenciais, project=info_chave['project_id'])
    bucket = storage_client.bucket("plataforma-redacao-de0f3.firebasestorage.app")
    return db, bucket

db, bucket = iniciar_servicos()

# 2. Estado da Sessão (Para guardar os cliques)
if "pontos_correcao" not in st.session_state:
    st.session_state.pontos_correcao = []

st.title("⚖️ Sistema de Correção por Pontos")

# 3. Busca de Redações
redacoes_ref = db.collection("redacoes").where("status", "==", "Pendente").stream()
lista = [{**r.to_dict(), 'id': r.id} for r in redacoes_ref]

if not lista:
    st.info("Tudo corrigido por aqui! ☕")
else:
    escolha = st.selectbox("Selecione a redação:", [f"{r['aluno_nome']} - {r['tema']}" for r in lista])
    redacao = next(r for r in lista if f"{r['aluno_nome']} - {r['tema']}" == escolha)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.write("### 📝 Folha de Redação")
        st.info("💡 Clique na imagem onde encontrar um erro para marcar um ponto.")
        
        # 1. Tenta pegar o caminho ou a URL com segurança
        caminho = redacao.get('caminho_storage')
        url_full = redacao.get('url_arquivo', '')

        # 2. Se o caminho estiver vazio, tentamos extrair da URL (o fallback que tínhamos antes)
        if not caminho and url_full:
            from urllib.parse import unquote
            bucket_name = "plataforma-redacao-de0f3.firebasestorage.app"
            if bucket_name in url_full:
                caminho = unquote(url_full.split(bucket_name + "/")[-1].split("?")[0])

        if caminho:
            try:
                # Download da Imagem usando o caminho recuperado
                blob = bucket.blob(caminho)
                img_bytes = blob.download_as_bytes()
                img = Image.open(BytesIO(img_bytes))
                
                # ... (resto do código do desenho dos pontos e streamlit_image_coordinates)
            except Exception as e:
                st.error(f"Erro ao acessar arquivo no Storage: {e}")
        else:
            st.error("Não foi possível encontrar o rastro desse arquivo no banco de dados.")

    with col2:
        st.write("### 📊 Notas e Feedback")
        with st.form("form_final"):
            n1 = st.number_input("C1", 0, 200, 160, 40)
            n2 = st.number_input("C2", 0, 200, 160, 40)
            
            # Gerar campos de texto dinâmicos para cada ponto clicado
            comentarios = []
            for i, ponto in enumerate(st.session_state.pontos_correcao):
                txt = st.text_input(f"Erro no ponto {i+1} (x:{ponto['x']})", key=f"txt_{i}")
                comentarios.append({"posicao": ponto, "texto": txt})
            
            feedback = st.text_area("Feedback Geral")
            
            if st.form_submit_button("Enviar Correção"):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida",
                    "anotacoes": comentarios,
                    "nota_final": n1+n2,
                    "feedback": feedback
                })
                st.session_state.pontos_correcao = []
                st.success("Enviado!")
                time.sleep(1); st.rerun()

        if st.button("Limpar Marcas"):
            st.session_state.pontos_correcao = []
            st.rerun()

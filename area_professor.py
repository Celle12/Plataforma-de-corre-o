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

# 2. Estado da Sessão
if "pontos_correcao" not in st.session_state:
    st.session_state.pontos_correcao = []

st.title("⚖️ Sistema de Correção por Pontos")

# 3. Busca de Redações
redacoes_ref = db.collection("redacoes").where("status", "==", "Pendente").stream()
lista = [{**r.to_dict(), 'id': r.id} for r in redacoes_ref]

if not lista:
    st.info("Tudo corrigido por aqui! ☕")
else:
    escolha = st.selectbox("Selecione a redação:", [f"{r.get('aluno_nome', 'Sem Nome')} - {r.get('tema', 'Sem Tema')}" for r in lista])
    redacao = next(r for r in lista if f"{r.get('aluno_nome', 'Sem Nome')} - {r.get('tema', 'Sem Tema')}" == escolha)

    # --- AJUSTE DE LAYOUT: Coluna da direita mais estreita ---
    col1, col2 = st.columns([3.5, 1])

    with col1:
        st.write("### 📝 Folha de Redação")
        st.info("💡 Clique na imagem para marcar um erro.")
        
        caminho = redacao.get('caminho_storage')
        url_full = redacao.get('url_arquivo', '')

        if not caminho and url_full:
            bucket_name = "plataforma-redacao-de0f3.firebasestorage.app"
            if bucket_name in url_full:
                caminho = unquote(url_full.split(bucket_name + "/")[-1].split("?")[0])

        if caminho:
            try:
                blob = bucket.blob(caminho)
                img_bytes = blob.download_as_bytes()
                img_original = Image.open(BytesIO(img_bytes)).convert("RGB")
                
                # Largura de 1000px mantida conforme sua aprovação
                LARGURA_CALIBRADA = 1000 
                w_orig, h_orig = img_original.size
                altura_calibrada = int(LARGURA_CALIBRADA * (h_orig / w_orig))
                
                img_para_exibir = img_original.resize((LARGURA_CALIBRADA, altura_calibrada))
                draw = ImageDraw.Draw(img_para_exibir)
                
                # Desenhar marcas robustas
                for i, ponto in enumerate(st.session_state.pontos_correcao):
                    x, y = ponto["x"], ponto["y"]
                    raio = 18
                    draw.ellipse([x-raio, y-raio, x+raio, y+raio], fill="red", outline="white", width=4)
                    draw.text((x-5, y-8), str(i+1), fill="white")

                # Captura coordenadas em escala 1:1
                value = streamlit_image_coordinates(img_para_exibir, key="editor_precisao_v3")

                if value:
                    novo_ponto = {"x": value["x"], "y": value["y"]}
                    if novo_ponto not in st.session_state.pontos_correcao:
                        st.session_state.pontos_correcao.append(novo_ponto)
                        st.rerun()

            except Exception as e:
                st.error(f"Erro de calibração: {e}")
        else:
            st.error("Arquivo não encontrado no Storage.")

    with col2:
        st.write("### 📊 Notas")
        if st.button("Limpar marcas 🗑️"):
            st.session_state.pontos_correcao = []
            st.rerun()

        with st.form("form_final"):
            st.write("#### Competências (0-200)")
            n1 = st.number_input("C1", 0, 200, 160, 40)
            n2 = st.number_input("C2", 0, 200, 160, 40)
            n3 = st.number_input("C3", 0, 200, 160, 40)
            n4 = st.number_input("C4", 0, 200, 160, 40)
            n5 = st.number_input("C5", 0, 200, 160, 40)
            
            st.divider()
            
            comentarios_lista = []
            if st.session_state.pontos_correcao:
                st.write("#### 💬 Comentários")
                for i, ponto in enumerate(st.session_state.pontos_correcao):
                    txt = st.text_input(f"Erro {i+1}", key=f"txt_{i}")
                    comentarios_lista.append({"x": ponto['x'], "y": ponto['y'], "texto": txt})
            
            feedback_geral = st.text_area("Feedback Geral")
            
            if st.form_submit_button("Enviar Correção", type="primary"):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida",
                    "anotacoes_detalhadas": comentarios_lista,
                    "notas": [n1, n2, n3, n4, n5],
                    "nota_final": n1+n2+n3+n4+n5,
                    "feedback_geral": feedback_geral,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.session_state.pontos_correcao = []
                st.success("✅ Enviado!")
                time.sleep(1.5)
                st.rerun()

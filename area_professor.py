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

# 2. Estado da Sessão (Para guardar os cliques e não perder ao recarregar)
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

    col1, col2 = st.columns([2, 1])

    with col1:
        st.write("### 📝 Folha de Redação")
        st.info("💡 Clique na imagem para marcar um erro. Cada clique vira um campo de comentário ao lado.")
        
        caminho = redacao.get('caminho_storage')
        url_full = redacao.get('url_arquivo', '')

        if not caminho and url_full:
            bucket_name = "plataforma-redacao-de0f3.firebasestorage.app"
            if bucket_name in url_full:
                caminho = unquote(url_full.split(bucket_name + "/")[-1].split("?")[0])

        if caminho:
            try:
                # Download e abertura da imagem
                blob = bucket.blob(caminho)
                img_bytes = blob.download_as_bytes()
                img = Image.open(BytesIO(img_bytes))
                
                # --- PARTE NOVA: DESENHAR OS PONTOS ---
                # Criamos uma cópia para desenhar as bolinhas vermelhas
                img_com_pontos = img.copy()
                draw = ImageDraw.Draw(img_com_pontos)
                
                for i, ponto in enumerate(st.session_state.pontos_correcao):
                    x, y = ponto["x"], ponto["y"]
                    # Desenha um círculo vermelho com borda branca
                    draw.ellipse([x-10, y-10, x+10, y+10], fill="red", outline="white", width=2)
                    draw.text((x+12, y-12), str(i+1), fill="red") # Número do erro

                # Exibe a imagem e captura o próximo clique
                # Definimos a largura para 800 para ficar confortável no dashboard
                value = streamlit_image_coordinates(img_com_pontos, width=800, key="editor_redacao")

                # Se o usuário clicou, salva o ponto e recarrega a página para mostrar a bolinha
                if value:
                    novo_ponto = {"x": value["x"], "y": value["y"]}
                    if novo_ponto not in st.session_state.pontos_correcao:
                        st.session_state.pontos_correcao.append(novo_ponto)
                        st.rerun()

            except Exception as e:
                st.error(f"Erro ao carregar imagem: {e}")
        else:
            st.error("Arquivo não encontrado no Storage.")

    with col2:
        st.write("### 📊 Notas e Feedback")
        # Botão para resetar caso o professor erre o clique
        if st.button("Limpar todas as marcas 🗑️"):
            st.session_state.pontos_correcao = []
            st.rerun()

        with st.form("form_final"):
            st.write("#### Competências (0-200)")
            n1 = st.number_input("C1 - Gramática", 0, 200, 160, 40)
            n2 = st.number_input("C2 - Repertório", 0, 200, 160, 40)
            n3 = st.number_input("C3 - Organização", 0, 200, 160, 40)
            n4 = st.number_input("C4 - Coesão", 0, 200, 160, 40)
            n5 = st.number_input("C5 - Proposta", 0, 200, 160, 40)
            
            st.divider()
            
            # Comentários por ponto
            comentarios_lista = []
            if st.session_state.pontos_correcao:
                st.write("#### 💬 Comentários por Erro")
                for i, ponto in enumerate(st.session_state.pontos_correcao):
                    txt = st.text_input(f"Erro {i+1}", placeholder="Ex: Cuidado com a vírgula aqui...", key=f"txt_{i}")
                    comentarios_lista.append({"x": ponto['x'], "y": ponto['y'], "texto": txt})
            
            feedback_geral = st.text_area("Feedback Geral para o Aluno")
            
            if st.form_submit_button("Enviar Correção Final", type="primary"):
                if not feedback_geral:
                    st.warning("Por favor, escreva um feedback geral antes de enviar.")
                else:
                    db.collection("redacoes").document(redacao['id']).update({
                        "status": "Corrigida",
                        "anotacoes_detalhadas": comentarios_lista,
                        "notas": [n1, n2, n3, n4, n5],
                        "nota_final": n1+n2+n3+n4+n5,
                        "feedback_geral": feedback_geral,
                        "data_correcao": firestore.SERVER_TIMESTAMP
                    })
                    st.session_state.pontos_correcao = [] # Limpa para a próxima
                    st.success("Redação corrigida com sucesso! 🚀")
                    time.sleep(2)
                    st.rerun()

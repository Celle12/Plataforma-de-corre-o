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
if "ponto_para_comentar" not in st.session_state:
    st.session_state.ponto_para_comentar = None

# --- FUNÇÃO DO POP-UP (MODAL) ---
@st.dialog("📝 Adicionar Comentário")
def modal_comentario():
    index = st.session_state.ponto_para_comentar
    st.write(f"**Marcando o Erro {index + 1}**")
    
    # Busca o texto atual (se existir)
    texto_atual = st.session_state.pontos_correcao[index].get('texto', "")
    novo_texto = st.text_area("Descreva o erro ou dê uma sugestão:", value=texto_atual, height=150)
    
    if st.button("Salvar e Continuar", type="primary", use_container_width=True):
        st.session_state.pontos_correcao[index]['texto'] = novo_texto
        st.session_state.ponto_para_comentar = None # Fecha o gatilho
        st.rerun()

# --- VERIFICA SE PRECISA ABRIR O POP-UP ---
if st.session_state.ponto_para_comentar is not None:
    modal_comentario()

# --- ABAS ---
tab_correcao, tab_temas = st.tabs(["🖋️ Corrigir Redações", "📋 Gerenciar Temas"])

with tab_correcao:
    st.title("⚖️ Sistema de Correção")
    redacoes_ref = db.collection("redacoes").where("status", "==", "Pendente").stream()
    lista = [{**r.to_dict(), 'id': r.id} for r in redacoes_ref]

    if not lista:
        st.info("Tudo corrigido por aqui! ☕")
    else:
        escolha = st.selectbox("Selecione a redação:", [f"{r.get('aluno_nome', 'Sem Nome')} - {r.get('tema', 'Sem Tema')}" for r in lista])
        redacao = next(r for r in lista if f"{r.get('aluno_nome', 'Sem Nome')} - {r.get('tema', 'Sem Tema')}" == escolha)

        # --- ÁREA DA REDAÇÃO ---
        st.write("### 📝 Folha de Redação")
        
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
                
                LARGURA = 1000 
                w_orig, h_orig = img_original.size
                img_para_exibir = img_original.resize((LARGURA, int(LARGURA * (h_orig / w_orig))))
                draw = ImageDraw.Draw(img_para_exibir)
                
                for i, ponto in enumerate(st.session_state.pontos_correcao):
                    x, y, raio = ponto["x"], ponto["y"], 12
                    draw.ellipse([x-raio, y-raio, x+raio, y+raio], fill="red", outline="white", width=3)
                    draw.text((x-4, y-6), str(i+1), fill="white")

                # Captura do Clique
                value = streamlit_image_coordinates(img_para_exibir, key="editor_v7")

                if value:
                    novo_ponto = {"x": value["x"], "y": value["y"], "texto": ""}
                    if novo_ponto not in st.session_state.pontos_correcao:
                        st.session_state.pontos_correcao.append(novo_ponto)
                        # GATILHO PARA O POP-UP: Define qual índice deve ser comentado
                        st.session_state.ponto_para_comentar = len(st.session_state.pontos_correcao) - 1
                        st.rerun()

            except Exception as e:
                st.error(f"Erro ao carregar imagem: {e}")

        st.divider()

        # --- PAINEL DE NOTAS ---
        st.write("### 📊 Painel de Avaliação")
        
        with st.expander("🚫 Negar Correção"):
            motivo = st.selectbox("Motivo:", ["Imagem desfocada", "Ilegível", "Folha em branco", "Arquivo incorreto"])
            obs = st.text_input("Observação:")
            if st.button("Confirmar Negativa", use_container_width=True):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Negada", "motivo_negativa": motivo, "obs_negativa": obs,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.session_state.pontos_correcao = []
                st.rerun()

        st.divider()

        if st.button("Limpar Marcas 🗑️"):
            st.session_state.pontos_correcao = []
            st.rerun()

        with st.form("form_final"):
            st.write("#### Competências (0-200)")
            c1, c2, c3, c4, c5 = st.columns(5)
            # Melhoria 1: Step=20
            n1 = c1.number_input("C1", 0, 200, 160, 20)
            n2 = c2.number_input("C2", 0, 200, 160, 20)
            n3 = c3.number_input("C3", 0, 200, 160, 20)
            n4 = c4.number_input("C4", 0, 200, 160, 20)
            n5 = c5.number_input("C5", 0, 200, 160, 20)
            
            st.write("#### 💬 Comentários para Revisão")
            st.caption("Os comentários aparecem aqui para ajustes finos após o pop-up.")
            
            comentarios_lista = []
            if st.session_state.pontos_correcao:
                for i, ponto in enumerate(st.session_state.pontos_correcao):
                    # Mantém o campo aqui para edição posterior, como solicitado
                    txt = st.text_input(f"Erro {i+1}", value=ponto.get('texto', ""), key=f"edit_{i}")
                    comentarios_lista.append({"x": ponto['x'], "y": ponto['y'], "texto": txt})
            else:
                st.info("Nenhum ponto marcado.")

            feedback_geral = st.text_area("Feedback Geral para o Aluno", height=150)
            
            if st.form_submit_button("Enviar Correção Completa", type="primary", use_container_width=True):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida",
                    "anotacoes_detalhadas": comentarios_lista,
                    "notas": [n1, n2, n3, n4, n5],
                    "nota_final": n1+n2+n3+n4+n5,
                    "feedback_geral": feedback_geral,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.session_state.pontos_correcao = []
                st.success("✅ Correção enviada!")
                time.sleep(1.5); st.rerun()

# ==========================================
# ABA 2: GERENCIAMENTO DE TEMAS
# ==========================================
with tab_temas:
    st.title("📋 Gerenciador de Temas")
    with st.form("form_novo_tema", clear_on_submit=True):
        novo_tema = st.text_input("Título do Novo Tema")
        arquivo_apoio = st.file_uploader("Texto de Apoio (PDF)", type=["pdf"])
        
        if st.form_submit_button("Salvar Tema", type="primary"):
            if novo_tema.strip():
                url_pdf = ""
                if arquivo_apoio:
                    nome_blob = f"textos_apoio/{int(time.time())}_{arquivo_apoio.name}"
                    blob = bucket.blob(nome_blob)
                    blob.upload_from_file(arquivo_apoio, content_type="application/pdf")
                    blob.make_public()
                    url_pdf = blob.public_url

                db.collection("temas").add({
                    "nome": novo_tema.strip(),
                    "url_apoio": url_pdf,
                    "data_criacao": firestore.SERVER_TIMESTAMP
                })
                st.success("✅ Tema adicionado!")
                time.sleep(1); st.rerun()

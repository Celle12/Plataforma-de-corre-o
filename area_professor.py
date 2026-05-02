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
def modal_comentario(index):
    st.write(f"### Erro {index + 1}")
    
    # Pegamos o texto atual para não perder nada
    ponto_atual = st.session_state.pontos_correcao[index]
    
    # Usamos uma chave única para este campo de texto
    comentario_temp = st.text_area("Descreva o erro:", 
                                  value=ponto_atual.get('texto', ""), 
                                  height=150,
                                  key=f"temp_text_{index}")
    
    if st.button("Confirmar e Fechar", type="primary", use_container_width=True):
        # Salvamos o texto diretamente no ponto dentro da lista
        st.session_state.pontos_correcao[index]['texto'] = comentario_temp
        # Limpamos o gatilho ANTES do rerun
        st.session_state.ponto_para_comentar = None
        st.rerun()

# --- ABAS ---
tab_correcao, tab_temas = st.tabs(["🖋️ Corrigir Redações", "📋 Gerenciar Temas"])

with tab_correcao:
    st.title("⚖️ Sistema de Correção")
    
    # DISPARADOR DO MODAL: Deve vir antes de carregar o resto da UI
    if st.session_state.ponto_para_comentar is not None:
        modal_comentario(st.session_state.ponto_para_comentar)

    # Busca de Redações
    redacoes_ref = db.collection("redacoes").where("status", "==", "Pendente").stream()
    lista = [{**r.to_dict(), 'id': r.id} for r in redacoes_ref]

    if not lista:
        st.info("Tudo corrigido! ☕")
    else:
        escolha = st.selectbox("Selecione a redação:", [f"{r.get('aluno_nome')} - {r.get('tema')}" for r in lista])
        redacao = next(r for r in lista if f"{r.get('aluno_nome')} - {r.get('tema')}" == escolha)

        # --- ÁREA DA IMAGEM ---
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
                img_edit = img_original.resize((LARGURA, int(LARGURA * (img_original.size[1] / img_original.size[0]))))
                draw = ImageDraw.Draw(img_edit)
                
                for i, p in enumerate(st.session_state.pontos_correcao):
                    x, y, r = p["x"], p["y"], 12
                    draw.ellipse([x-r, y-r, x+r, y+r], fill="red", outline="white", width=3)
                    draw.text((x-4, y-6), str(i+1), fill="white")

                # Captura do clique
                value = streamlit_image_coordinates(img_edit, key="editor_v9")

                if value:
                    novo_p = {"x": value["x"], "y": value["y"], "texto": ""}
                    if novo_p not in st.session_state.pontos_correcao:
                        st.session_state.pontos_correcao.append(novo_p)
                        st.session_state.ponto_para_comentar = len(st.session_state.pontos_correcao) - 1
                        st.rerun()

            except Exception as e:
                st.error(f"Erro: {e}")

        st.divider()

        # --- ÁREA DE NOTAS E REVISÃO ---
        st.write("### 📊 Avaliação e Notas")
        
        if st.button("Limpar Marcas 🗑️"):
            st.session_state.pontos_correcao = []
            st.rerun()

        # Usamos o formulário APENAS para o envio final
        with st.form("form_final"):
            c1, c2, c3, c4, c5 = st.columns(5)
            n1 = c1.number_input("C1", 0, 200, 160, 20)
            n2 = c2.number_input("C2", 0, 200, 160, 20)
            n3 = c3.number_input("C3", 0, 200, 160, 20)
            n4 = c4.number_input("C4", 0, 200, 160, 20)
            n5 = c5.number_input("C5", 0, 200, 160, 20)
            
            st.write("#### 📝 Revisão dos Comentários")
            
            # Reconstruímos a lista para garantir que os dados do modal apareçam aqui
            lista_final_anotacoes = []
            if st.session_state.pontos_correcao:
                for i, ponto in enumerate(st.session_state.pontos_correcao):
                    # Aqui é onde o texto digitado no modal DEVE aparecer
                    txt_revisao = st.text_input(f"Comentário do Erro {i+1}", 
                                                value=ponto.get('texto', ""), 
                                                key=f"final_edit_{i}")
                    lista_final_anotacoes.append({"x": ponto['x'], "y": ponto['y'], "texto": txt_revisao})
            else:
                st.info("Nenhum erro marcado ainda.")

            feedback_geral = st.text_area("Feedback Geral")
            
            if st.form_submit_button("Enviar Correção Completa", type="primary", use_container_width=True):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida",
                    "anotacoes_detalhadas": lista_final_anotacoes,
                    "notas": [n1, n2, n3, n4, n5],
                    "nota_final": n1+n2+n3+n4+n5,
                    "feedback_geral": feedback_geral,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.session_state.pontos_correcao = []
                st.success("✅ Correção enviada!")
                time.sleep(1); st.rerun()

# --- ABA DE TEMAS ---
with tab_temas:
    st.title("📋 Gerenciar Temas")
    with st.form("novo_tema"):
        nome_t = st.text_input("Tema:")
        pdf_t = st.file_uploader("PDF:", type=["pdf"])
        if st.form_submit_button("Cadastrar"):
            if nome_t:
                url_pdf = ""
                if pdf_t:
                    blob = bucket.blob(f"textos_apoio/{int(time.time())}_{pdf_t.name}")
                    blob.upload_from_file(pdf_t, content_type="application/pdf")
                    blob.make_public()
                    url_pdf = blob.public_url
                db.collection("temas").add({"nome": nome_t, "url_apoio": url_pdf, "data_criacao": firestore.SERVER_TIMESTAMP})
                st.success("Salvo!")
                time.sleep(1); st.rerun()

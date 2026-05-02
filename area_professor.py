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

# 2. Estado da Sessão (Source of Truth)
if "pontos_correcao" not in st.session_state:
    st.session_state.pontos_correcao = []
if "ponto_para_comentar" not in st.session_state:
    st.session_state.ponto_para_comentar = None

# --- FUNÇÃO DO POP-UP (MODAL) ---
@st.dialog("📝 Adicionar Comentário")
def modal_comentario():
    index = st.session_state.ponto_para_comentar
    # Garante que estamos editando o ponto certo
    ponto_atual = st.session_state.pontos_correcao[index]
    
    st.write(f"### Erro {index + 1}")
    # Campo de texto que carrega o que já existe (se houver)
    novo_texto = st.text_area("O que o aluno precisa corrigir aqui?", 
                              value=ponto_atual.get('texto', ""), 
                              height=150,
                              key="input_modal_temp")
    
    if st.button("Salvar Comentário", type="primary", use_container_width=True):
        # Atualiza o comentário no estado global ANTES de fechar
        st.session_state.pontos_correcao[index]['texto'] = novo_texto
        # Limpa o gatilho e força o fechamento do modal
        st.session_state.ponto_para_comentar = None
        st.rerun()

# --- ABAS ---
tab_correcao, tab_temas = st.tabs(["🖋️ Corrigir Redações", "📋 Gerenciar Temas"])

with tab_correcao:
    # Verifica se deve abrir o modal (Colocado aqui para garantir o fluxo)
    if st.session_state.ponto_para_comentar is not None:
        modal_comentario()

    st.title("⚖️ Sistema de Correção")
    redacoes_ref = db.collection("redacoes").where("status", "==", "Pendente").stream()
    lista = [{**r.to_dict(), 'id': r.id} for r in redacoes_ref]

    if not lista:
        st.info("Tudo corrigido por aqui! ☕")
    else:
        escolha = st.selectbox("Selecione a redação:", [f"{r.get('aluno_nome', 'Sem Nome')} - {r.get('tema', 'Sem Tema')}" for r in lista])
        redacao = next(r for r in lista if f"{r.get('aluno_nome', 'Sem Nome')} - {r.get('tema', 'Sem Tema')}" == escolha)

        # --- EXIBIÇÃO DA IMAGEM ---
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

                value = streamlit_image_coordinates(img_edit, key="editor_v8")

                if value:
                    novo_p = {"x": value["x"], "y": value["y"], "texto": ""}
                    if novo_p not in st.session_state.pontos_correcao:
                        st.session_state.pontos_correcao.append(novo_p)
                        # Define o índice para o pop-up e recarrega para abrir
                        st.session_state.ponto_para_comentar = len(st.session_state.pontos_correcao) - 1
                        st.rerun()

            except Exception as e:
                st.error(f"Erro no carregamento: {e}")

        st.divider()

        # --- PAINEL DE NOTAS ---
        st.write("### 📊 Avaliação Final")
        
        with st.expander("🚫 Negar Arquivo"):
            motivo = st.selectbox("Motivo:", ["Imagem Ilegível", "Folha em Branco", "Arquivo Errado"])
            if st.button("Confirmar Negativa"):
                db.collection("redacoes").document(redacao['id']).update({"status": "Negada", "motivo_negativa": motivo})
                st.session_state.pontos_correcao = []
                st.rerun()

        if st.button("Limpar Todas as Marcas 🗑️"):
            st.session_state.pontos_correcao = []
            st.rerun()

        with st.form("form_final"):
            st.write("#### Notas (20 em 20)")
            c1, c2, c3, c4, c5 = st.columns(5)
            n1 = c1.number_input("C1", 0, 200, 160, 20)
            n2 = c2.number_input("C2", 0, 200, 160, 20)
            n3 = c3.number_input("C3", 0, 200, 160, 20)
            n4 = c4.number_input("C4", 0, 200, 160, 20)
            n5 = c5.number_input("C5", 0, 200, 160, 20)
            
            st.write("#### 📝 Revisão dos Comentários")
            
            # Reconstroi a lista de comentários para garantir persistência
            comentarios_atualizados = []
            if st.session_state.pontos_correcao:
                for i, ponto in enumerate(st.session_state.pontos_correcao):
                    # O segredo: 'value' puxa do session_state, mas o 'key' garante que o Streamlit não perca o dado
                    txt_editado = st.text_input(f"Erro {i+1}", 
                                                value=ponto.get('texto', ""), 
                                                key=f"input_final_{i}")
                    comentarios_atualizados.append({"x": ponto['x'], "y": ponto['y'], "texto": txt_editado})
            else:
                st.info("Marque pontos na imagem para comentar.")

            feedback_geral = st.text_area("Conclusão/Feedback Geral", height=100)
            
            if st.form_submit_button("Finalizar e Enviar Correção", type="primary", use_container_width=True):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida",
                    "anotacoes_detalhadas": comentarios_atualizados,
                    "notas": [n1, n2, n3, n4, n5],
                    "nota_final": n1+n2+n3+n4+n5,
                    "feedback_geral": feedback_geral,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.session_state.pontos_correcao = []
                st.success("✅ Enviado!")
                time.sleep(1); st.rerun()

# ==========================================
# ABA 2: TEMAS
# ==========================================
with tab_temas:
    st.title("📋 Gerenciar Temas")
    with st.form("novo_tema", clear_on_submit=True):
        nome_t = st.text_input("Novo Tema:")
        pdf_t = st.file_uploader("PDF de Apoio:", type=["pdf"])
        if st.form_submit_button("Cadastrar"):
            if nome_t:
                url_pdf = ""
                if pdf_t:
                    blob = bucket.blob(f"textos_apoio/{int(time.time())}_{pdf_t.name}")
                    blob.upload_from_file(pdf_t, content_type="application/pdf")
                    blob.make_public()
                    url_pdf = blob.public_url
                db.collection("temas").add({"nome": nome_t, "url_apoio": url_pdf, "data_criacao": firestore.SERVER_TIMESTAMP})
                st.success("Tema salvo!")
                time.sleep(1); st.rerun()

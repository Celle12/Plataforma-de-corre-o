import streamlit as st
import streamlit.components.v1 as components
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
if "ultimo_clique" not in st.session_state:
    st.session_state.ultimo_clique = None

# --- FUNÇÃO DO POP-UP (MODAL) ---
@st.dialog("📝 Adicionar Comentário")
def modal_comentario(index):
    st.write(f"### Erro {index + 1}")
    ponto_atual = st.session_state.pontos_correcao[index]
    
    comentario_temp = st.text_area("Descreva o erro:", 
                                  value=ponto_atual.get('texto', ""), 
                                  height=150,
                                  key=f"modal_field_{index}")
    
    if st.button("Confirmar e Fechar", type="primary", use_container_width=True):
        st.session_state.pontos_correcao[index]['texto'] = comentario_temp
        st.session_state.ponto_para_comentar = None
        st.rerun()

# --- ABAS ---
tab_correcao, tab_temas = st.tabs(["🖋️ Corrigir Redações", "📋 Gerenciar Temas"])

with tab_correcao:
    # --- HACK DE JAVASCRIPT PARA MANTER O TOPO ---
    # Isso impede que o app "pule" para o rodapé após fechar o pop-up
    components.html(
        """
        <script>
        var mainSection = window.parent.document.querySelector('section.main');
        if (mainSection) {
            mainSection.scrollTo({ top: 0, behavior: 'instant' });
        }
        </script>
        """,
        height=0,
    )

    if st.session_state.ponto_para_comentar is not None:
        modal_comentario(st.session_state.ponto_para_comentar)

    st.title("⚖️ Sistema de Correção")
    
    redacoes_ref = db.collection("redacoes").where("status", "==", "Pendente").stream()
    lista = [{**r.to_dict(), 'id': r.id} for r in redacoes_ref]

    if not lista:
        st.info("Tudo corrigido por aqui! ☕")
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

                value = streamlit_image_coordinates(img_edit, key="editor_v11")

                if value and value != st.session_state.ultimo_clique:
                    st.session_state.ultimo_clique = value
                    novo_p = {"x": value["x"], "y": value["y"], "texto": ""}
                    st.session_state.pontos_correcao.append(novo_p)
                    st.session_state.ponto_para_comentar = len(st.session_state.pontos_correcao) - 1
                    st.rerun()

            except Exception as e:
                st.error(f"Erro: {e}")

        st.divider()

        # --- PAINEL FINAL ---
        if st.button("Limpar Marcas 🗑️"):
            st.session_state.pontos_correcao = []
            st.session_state.ultimo_clique = None
            st.rerun()

        with st.form("form_envio"):
            st.write("#### Notas e Revisão")
            c1, c2, c3, c4, c5 = st.columns(5)
            n1 = c1.number_input("C1", 0, 200, 160, 20)
            n2 = c2.number_input("C2", 0, 200, 160, 20)
            n3 = c3.number_input("C3", 0, 200, 160, 20)
            n4 = c4.number_input("C4", 0, 200, 160, 20)
            n5 = c5.number_input("C5", 0, 200, 160, 20)
            
            st.write("#### 💬 Comentários Adicionados")
            lista_final = []
            for i, p in enumerate(st.session_state.pontos_correcao):
                txt = st.text_input(f"Erro {i+1}", value=p.get('texto', ""), key=f"f_input_{i}")
                lista_final.append({"x": p['x'], "y": p['y'], "texto": txt})

            fb_geral = st.text_area("Feedback Geral")
            
            if st.form_submit_button("Enviar Correção Completa", type="primary", use_container_width=True):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida",
                    "anotacoes_detalhadas": lista_final,
                    "notas": [n1, n2, n3, n4, n5],
                    "nota_final": sum([n1, n2, n3, n4, n5]),
                    "feedback_geral": fb_geral,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.session_state.pontos_correcao = []
                st.session_state.ultimo_clique = None
                st.success("✅ Enviado com sucesso!")
                time.sleep(1); st.rerun()

# --- ABA DE TEMAS ---
with tab_temas:
    st.title("📋 Gerenciar Temas")
    with st.form("n_tema"):
        nome_t = st.text_input("Tema:")
        pdf_t = st.file_uploader("PDF:", type=["pdf"])
        if st.form_submit_button("Salvar"):
            if nome_t:
                url_p = ""
                if pdf_t:
                    blob = bucket.blob(f"textos_apoio/{int(time.time())}_{pdf_t.name}")
                    blob.upload_from_file(pdf_t, content_type="application/pdf")
                    blob.make_public()
                    url_p = blob.public_url
                db.collection("temas").add({"nome": nome_t, "url_apoio": url_p, "data_criacao": firestore.SERVER_TIMESTAMP})
                st.success("Salvo!"); time.sleep(1); st.rerun()

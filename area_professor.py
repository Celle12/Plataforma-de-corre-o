import streamlit as st
import json
import time
from io import BytesIO
from PIL import Image
from google.cloud import firestore, storage
from google.oauth2 import service_account
from streamlit_drawable_canvas import st_canvas
from urllib.parse import unquote

# 1. Configuração da Página
st.set_page_config(page_title="Painel do Corretor", page_icon="⚖️", layout="wide")

# 2. Conexão com Firestore e Storage
@st.cache_resource
def iniciar_servicos():
    info_chave = json.loads(st.secrets["firebase_service_account"])
    credenciais = service_account.Credentials.from_service_account_info(info_chave)
    db = firestore.Client(credentials=credenciais, project=info_chave['project_id'])
    storage_client = storage.Client(credentials=credenciais, project=info_chave['project_id'])
    bucket = storage_client.bucket("plataforma-redacao-de0f3.firebasestorage.app")
    return db, bucket

db, bucket = iniciar_servicos()

# 3. Estilização das Competências
COMPETENCIAS = {
    "C1 - Gramática": "#0000FF33", "C2 - Repertório": "#00FF0033",
    "C3 - Argumentação": "#FFFF0033", "C4 - Coesão": "#FFA50033", "C5 - Proposta": "#FF000033"
}

st.title("⚖️ Painel de Correção Profissional")

# 4. Listagem de Redações Pendentes
redacoes_ref = db.collection("redacoes").where("status", "==", "Pendente").stream()
lista_redacoes = [ {**r.to_dict(), 'id': r.id} for r in redacoes_ref ]

if not lista_redacoes:
    st.info("Nenhuma redação pendente por enquanto! ☕")
else:
    opcoes = {f"{r.get('aluno_nome', 'Sem Nome')} - {r['tema']}": r for r in lista_redacoes}
    escolha = st.selectbox("Selecione uma redação para corrigir:", list(opcoes.keys()))
    redacao = opcoes[escolha]

    col1, col2 = st.columns([2, 1])
    canvas_result = None

    with col1:
        st.write("### 📝 Folha de Redação")
        
        if redacao.get('tipo') == 'arquivo':
            try:
                url_full = redacao.get('url_arquivo', '')
                nome_arquivo_storage = redacao.get('caminho_storage')
                if not nome_arquivo_storage and url_full:
                    bucket_name = "plataforma-redacao-de0f3.firebasestorage.app"
                    nome_arquivo_storage = unquote(url_full.split(bucket_name + "/")[-1].split("?")[0])

                blob = bucket.blob(nome_arquivo_storage)
                conteudo_bytes = blob.download_as_bytes()
                
                img_original = Image.open(BytesIO(conteudo_bytes))
                largura_display = 800
                w_orig, h_orig = img_original.size
                altura_display = int(largura_display * (h_orig / w_orig))
                
                comp_selecionada = st.radio("Selecione a competência:", list(COMPETENCIAS.keys()), horizontal=True)
                cor_pincel = COMPETENCIAS[comp_selecionada]

                # --- CSS PARA TORNAR O VIDRO TRANSPARENTE E TRAVAR A IMAGEM ---
                st.markdown(f"""
                    <style>
                    /* 1. Torna a imagem intocável (evita o fantasma) */
                    div[data-testid="stImage"] img {{
                        pointer-events: none;
                        user-select: none;
                        -webkit-user-drag: none;
                    }}
                    /* 2. Força o componente de desenho a ser 100% transparente */
                    iframe {{
                        background: transparent !important;
                    }}
                    .stCanvas {{
                        background: transparent !important;
                        margin-top: -{altura_display + 48}px;
                        z-index: 10;
                    }}
                    </style>
                """, unsafe_allow_html=True)

                # Passo 1: Mostra a imagem (Camada de Baixo)
                st.image(img_original, width=largura_display)
                
                # Passo 2: Canvas Transparente (Camada de Cima)
                canvas_result = st_canvas(
                    fill_color=cor_pincel,
                    stroke_width=1,
                    stroke_color="#000",
                    background_color="rgba(255, 255, 255, 0)", # Transparência absoluta
                    update_streamlit=True,
                    height=altura_display,
                    width=largura_display,
                    drawing_mode="rect",
                    key="canvas_crystal_clear",
                )
                
            except Exception as e:
                st.error(f"Erro ao carregar: {e}")
        else:
            st.text_area("Texto da Redação:", redacao.get('texto'), height=500, disabled=True)

    with col2:
        st.write("### 📊 Notas e Comentários")
        with st.form("form_correcao"):
            # Sliders de notas
            n1 = st.slider("C1", 0, 200, 0, 40); n2 = st.slider("C2", 0, 200, 0, 40)
            n3 = st.slider("C3", 0, 200, 0, 40); n4 = st.slider("C4", 0, 200, 0, 40)
            n5 = st.slider("C5", 0, 200, 0, 40)
            
            comentarios_caixinhas = []
            if canvas_result and canvas_result.json_data:
                objetos = canvas_result.json_data["objects"]
                if objetos:
                    for i, obj in enumerate(objetos):
                        comentario = st.text_input(f"Destaque {i+1}", key=f"coment_{i}")
                        comentarios_caixinhas.append({
                            "id_caixa": i, "comentario": comentario,
                            "posicao": {"left": obj['left'], "top": obj['top'], "color": obj['fill']}
                        })

            feedback_geral = st.text_area("Feedback Geral:", height=100)

            if st.form_submit_button("Finalizar Correção", type="primary"):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida",
                    "notas": [n1, n2, n3, n4, n5],
                    "nota_final": n1+n2+n3+n4+n5,
                    "feedback_geral": feedback_geral,
                    "anotacoes_detalhadas": comentarios_caixinhas,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.success("✅ Sucesso!")
                time.sleep(1); st.rerun()

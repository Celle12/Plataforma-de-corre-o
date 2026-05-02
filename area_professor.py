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

# 3. Estilização
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
                    if bucket_name in url_full:
                        nome_arquivo_storage = unquote(url_full.split(bucket_name + "/")[-1].split("?")[0])
                    elif "/o/" in url_full:
                        nome_arquivo_storage = unquote(url_full.split("/o/")[1].split("?")[0])

                blob = bucket.blob(nome_arquivo_storage)
                conteudo_bytes = blob.download_as_bytes()
                
                if nome_arquivo_storage.lower().endswith(".pdf"):
                    st.warning("⚠️ PDF detectado.")
                    st.download_button("📥 Baixar PDF", conteudo_bytes, file_name="redacao.pdf")
                else:
                    img_original = Image.open(BytesIO(conteudo_bytes))
                    largura_alvo = 800
                    w, h = img_original.size
                    altura_alvo = int(largura_alvo * (h / w))
                    
                    comp_selecionada = st.radio("Competência:", list(COMPETENCIAS.keys()), horizontal=True)
                    cor_pincel = COMPETENCIAS[comp_selecionada]

                    st.info("💡 Desenhe sobre os erros.")

                    # --- O TRUQUE DE MESTRE (CSS) ---
                    # Este código impede que a imagem seja arrastada e garante o alinhamento
                    st.markdown(f"""
                        <style>
                        .stImage img {{
                            user-select: none;
                            -webkit-user-drag: none;
                            pointer-events: none;
                        }}
                        /* Tenta sobrepor o canvas milimetricamente */
                        [data-testid="stVerticalBlock"] > div:nth-child(2) {{
                            margin-top: -{altura_alvo + 45}px;
                        }}
                        </style>
                    """, unsafe_allow_html=True)

                    # 1. Exibe a imagem de fundo (agora protegida pelo CSS)
                    st.image(img_original, width=largura_alvo)
                    
                    # 2. Canvas Transparente por cima
                    canvas_result = st_canvas(
                        fill_color=cor_pincel,
                        stroke_width=1,
                        stroke_color="#000",
                        background_color="rgba(0, 0, 0, 0)", 
                        update_streamlit=True,
                        height=altura_alvo,
                        width=largura_alvo,
                        drawing_mode="rect",
                        key="canvas_transparente_v2",
                    )
            except Exception as e:
                st.error(f"Erro ao carregar: {e}")
        else:
            st.text_area("Texto:", redacao.get('texto'), height=500, disabled=True)

    with col2:
        st.write("### 📊 Notas e Comentários")
        with st.form("form_correcao"):
            n1 = st.slider("C1", 0, 200, 0, 40); n2 = st.slider("C2", 0, 200, 0, 40)
            n3 = st.slider("C3", 0, 200, 0, 40); n4 = st.slider("C4", 0, 200, 0, 40)
            n5 = st.slider("C5", 0, 200, 0, 40)
            
            comentarios_caixinhas = []
            if canvas_result and canvas_result.json_data:
                objetos = canvas_result.json_data["objects"]
                for i, obj in enumerate(objetos):
                    comentario = st.text_input(f"Comentário {i+1}", key=f"c_{i}")
                    comentarios_caixinhas.append({
                        "id_caixa": i, "comentario": comentario,
                        "posicao": {"left": obj['left'], "top": obj['top'], "color": obj['fill']}
                    })

            feedback = st.text_area("Feedback Geral:", height=100)

            if st.form_submit_button("Enviar Correção", type="primary"):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida",
                    "notas": [n1, n2, n3, n4, n5],
                    "nota_final": n1+n2+n3+n4+n5,
                    "feedback_geral": feedback,
                    "anotacoes_detalhadas": comentarios_caixinhas,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.success("✅ Sucesso!")
                time.sleep(1); st.rerun()

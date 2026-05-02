import streamlit as st
import json
import time
from io import BytesIO
from PIL import Image
from google.cloud import firestore, storage
from google.oauth2 import service_account
from streamlit_drawable_canvas import st_canvas
from urllib.parse import unquote
import base64
from io import BytesIO

def converter_imagem_para_base64(img_pil):
    """Converte a imagem PIL para uma string Base64 para o Canvas."""
    buffered = BytesIO()
    img_pil.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

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
            # Processamento da imagem (mantendo o redimensionamento que já fizemos)
            img_original = Image.open(BytesIO(conteudo_bytes))
            largura_display = 800
            w, h = img_original.size
            altura_display = int(largura_display * (h / w))
            img_redimensionada = img_original.resize((largura_display, altura_display))
            
            # A MÁGICA: Transformamos a imagem em código
            imagem_b64 = converter_imagem_para_base64(img_redimensionada)
            
            # Agora o st_canvas recebe a imagem DIRETAMENTE no parâmetro background_image
            canvas_result = st_canvas(
                fill_color=cor_pincel,
                stroke_width=1,
                stroke_color="#000",
                background_image=imagem_b64, # Aqui a imagem entra como dado, não como arquivo
                update_streamlit=True,
                height=altura_display,
                width=largura_display,
                drawing_mode="rect",
                key="canvas_integrado_v1",
            )
            
        except Exception as e:
            st.error(f"Erro ao processar imagem: {e}")
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

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
                # Localização do arquivo
                url_full = redacao.get('url_arquivo', '')
                nome_arquivo_storage = redacao.get('caminho_storage')
                if not nome_arquivo_storage and url_full:
                    bucket_name = "plataforma-redacao-de0f3.firebasestorage.app"
                    nome_arquivo_storage = unquote(url_full.split(bucket_name + "/")[-1].split("?")[0])

                blob = bucket.blob(nome_arquivo_storage)
                conteudo_bytes = blob.download_as_bytes()
                
                if nome_arquivo_storage.lower().endswith(".pdf"):
                    st.warning("⚠️ PDF detectado. Baixe para corrigir.")
                    st.download_button("📥 Baixar PDF", conteudo_bytes, file_name="redacao.pdf")
                else:
                    imagem_pil = Image.open(BytesIO(conteudo_bytes))
                    
                    # Otimização visual: Mantendo a proporção (ou forçando 4:5 se desejar)
                    largura_alvo = 800
                    w, h = imagem_pil.size
                    altura_alvo = int(largura_alvo * (h / w))
                    
                    comp_selecionada = st.radio("Competência:", list(COMPETENCIAS.keys()), horizontal=True)
                    cor_pincel = COMPETENCIAS[comp_selecionada]

                    # --- A SOLUÇÃO CIRÚRGICA: CSS GRID STACK ---
                    # Isso cria uma "pilha" onde a imagem fica embaixo e o canvas em cima.
                    st.markdown(f"""
                        <style>
                        .canvas-stack {{
                            display: grid;
                            grid-template-areas: "overlay";
                            width: {largura_alvo}px;
                            height: {altura_alvo}px;
                        }}
                        .canvas-stack > * {{
                            grid-area: overlay;
                        }}
                        /* Bloqueia o arrasto da imagem fantasma */
                        .canvas-stack img {{
                            pointer-events: none;
                            user-select: none;
                        }}
                        /* Garante que o canvas seja transparente e fique no topo */
                        .canvas-stack .stCanvas {{
                            z-index: 10;
                            background-color: transparent !important;
                        }}
                        </style>
                    """, unsafe_allow_html=True)

                    st.markdown('<div class="canvas-stack">', unsafe_allow_html=True)
                    
                    # 1. Imagem de Fundo (Nativa e Segura)
                    st.image(imagem_pil, width=largura_alvo)
                    
                    # 2. Canvas para Desenho (Sem background_image para evitar erros)
                    canvas_result = st_canvas(
                        fill_color=cor_pincel,
                        stroke_width=1,
                        stroke_color="#000",
                        background_color="rgba(0,0,0,0)",
                        update_streamlit=True,
                        height=altura_alvo,
                        width=largura_alvo,
                        drawing_mode="rect",
                        key="canvas_stack_final",
                    )
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.info("💡 Desenhe sobre os erros diretamente na imagem acima.")

            except Exception as e:
                st.error(f"Erro na visualização: {e}")
        else:
            st.text_area("Texto:", redacao.get('texto'), height=500, disabled=True)

    with col2:
        st.write("### 📊 Notas e Comentários")
        with st.form("form_correcao"):
            n1 = st.slider("C1 - Gramática", 0, 200, 0, 40)
            n2 = st.slider("C2 - Repertório", 0, 200, 0, 40)
            n3 = st.slider("C3 - Organização", 0, 200, 0, 40)
            n4 = st.slider("C4 - Coesão", 0, 200, 0, 40)
            n5 = st.slider("C5 - Proposta", 0, 200, 0, 40)
            
            comentarios_caixinhas = []
            if canvas_result and canvas_result.json_data:
                objetos = canvas_result.json_data["objects"]
                for i, obj in enumerate(objetos):
                    comentario = st.text_input(f"Destaque {i+1}", key=f"c_{i}")
                    comentarios_caixinhas.append({
                        "id_caixa": i, "comentario": comentario,
                        "posicao": {"left": obj['left'], "top": obj['top'], "color": obj['fill']}
                    })

            feedback = st.text_area("Feedback Geral:", height=150)

            if st.form_submit_button("Finalizar Correção", type="primary"):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida",
                    "notas": [n1, n2, n3, n4, n5],
                    "nota_final": n1+n2+n3+n4+n5,
                    "feedback_geral": feedback,
                    "anotacoes_detalhadas": comentarios_caixinhas,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.success("✅ Correção enviada com sucesso!")
                time.sleep(1); st.rerun()

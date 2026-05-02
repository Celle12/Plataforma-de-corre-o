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
    "C1 - Gramática": "#0000FF33",  # Azul
    "C2 - Repertório": "#00FF0033", # Verde
    "C3 - Argumentação": "#FFFF0033", # Amarelo
    "C4 - Coesão": "#FFA50033",    # Laranja
    "C5 - Proposta": "#FF000033"   # Vermelho
}

st.title("⚖️ Painel de Correção Profissional")

# 4. Listagem de Redações Pendentes
st.subheader("📥 Redações Aguardando Correção")
redacoes_ref = db.collection("redacoes").where("status", "==", "Pendente").stream()
lista_redacoes = []

for r in redacoes_ref:
    dado = r.to_dict()
    dado['id'] = r.id
    lista_redacoes.append(dado)

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
                url_da_imagem = redacao.get('url_arquivo', '')
                nome_arquivo_storage = None

                # Busca do caminho do arquivo no Storage
                if redacao.get('caminho_storage'):
                    nome_arquivo_storage = redacao.get('caminho_storage')
                elif url_da_imagem:
                    bucket_name = "plataforma-redacao-de0f3.firebasestorage.app"
                    if bucket_name in url_da_imagem:
                        nome_arquivo_storage = unquote(url_da_imagem.split(bucket_name + "/")[-1].split("?")[0])
                    elif "/o/" in url_da_imagem:
                        nome_arquivo_storage = unquote(url_da_imagem.split("/o/")[1].split("?")[0])

                if not nome_arquivo_storage:
                    raise Exception("Caminho do arquivo não identificado.")

                # Baixa a imagem real para calcular as dimensões
                blob = bucket.blob(nome_arquivo_storage)
                conteudo_bruto = blob.download_as_bytes()
                
                if nome_arquivo_storage.lower().endswith(".pdf"):
                    st.warning("⚠️ Arquivo PDF detectado.")
                    st.download_button("📥 Baixar PDF", conteudo_bruto, file_name=f"redacao_{redacao.get('aluno_nome')}.pdf")
                else:
                    # USAMOS A IMAGEM REAL AQUI (Apenas para medir)
                    imagem_para_medir = Image.open(BytesIO(conteudo_bruto))
                    largura_tela = 800
                    proporcao = imagem_para_medir.height / imagem_para_medir.width
                    altura_tela = int(largura_tela * proporcao)
                    
                    comp_selecionada = st.radio("Selecione a competência:", list(COMPETENCIAS.keys()), horizontal=True)
                    cor_pincel = COMPETENCIAS[comp_selecionada]

                    st.info("💡 Desenhe retângulos sobre os erros.")
                    
                    # NO CANVAS USAMOS A URL (Texto) PARA O FUNDO
                    canvas_result = st_canvas(
                        fill_color=cor_pincel,
                        stroke_width=1,
                        stroke_color="#000",
                        background_image=url_da_imagem, 
                        update_streamlit=True,
                        height=altura_tela,
                        width=largura_tela,
                        drawing_mode="rect",
                        key="canvas_corretor",
                    )
            except Exception as e:
                st.error(f"Erro ao carregar o arquivo: {e}")
        else:
            st.text_area("Texto da Redação:", redacao.get('texto'), height=500, disabled=True)

    with col2:
        st.write("### 📊 Notas e Comentários")
        
        with st.form("form_correcao"):
            n1 = st.slider("C1 - Gramática", 0, 200, 0, 40)
            n2 = st.slider("C2 - Repertório", 0, 200, 0, 40)
            n3 = st.slider("C3 - Organização", 0, 200, 0, 40)
            n4 = st.slider("C4 - Coesão", 0, 200, 0, 40)
            n5 = st.slider("C5 - Proposta", 0, 200, 0, 40)
            
            st.divider()
            
            comentarios_caixinhas = []
            if canvas_result and canvas_result.json_data:
                objetos = canvas_result.json_data["objects"]
                if objetos:
                    st.write("#### 💬 Comentários nos destaques:")
                    for i, obj in enumerate(objetos):
                        cor_hex = obj['fill']
                        comentario = st.text_input(f"Destaque {i+1}", key=f"coment_{i}")
                        comentarios_caixinhas.append({
                            "id_caixa": i,
                            "comentario": comentario,
                            "posicao": {
                                "left": obj['left'],
                                "top": obj['top'],
                                "width": obj['width'],
                                "height": obj['height'],
                                "color": cor_hex
                            }
                        })

            st.divider()
            feedback_geral = st.text_area("Feedback Geral Final:", height=150)

            if st.form_submit_button("Finalizar e Enviar", type="primary"):
                nota_total = n1 + n2 + n3 + n4 + n5
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida",
                    "notas": [n1, n2, n3, n4, n5],
                    "nota_final": nota_total,
                    "feedback_geral": feedback_geral,
                    "anotacoes_detalhadas": comentarios_caixinhas,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.success("✅ Correção enviada!")
                time.sleep(1)
                st.rerun()

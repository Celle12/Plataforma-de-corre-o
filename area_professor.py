import streamlit as st
import json
import time
import requests
from io import BytesIO
from PIL import Image
from google.cloud import firestore, storage  # Adicionado storage
from google.oauth2 import service_account
from streamlit_drawable_canvas import st_canvas
from urllib.parse import unquote

# 1. Configuração da Página
st.set_page_config(page_title="Painel do Corretor", page_icon="⚖️", layout="wide")

# 2. Conexão com Firestore e Storage (Uso de credenciais diretas)
@st.cache_resource
def iniciar_servicos():
    info_chave = json.loads(st.secrets["firebase_service_account"])
    credenciais = service_account.Credentials.from_service_account_info(info_chave)
    
    # Cliente do Banco de Dados
    db = firestore.Client(credentials=credenciais, project=info_chave['project_id'])
    
    # Cliente do Storage (Cofre de arquivos)
    storage_client = storage.Client(credentials=credenciais, project=info_chave['project_id'])
    bucket = storage_client.bucket("plataforma-redacao-de0f3.firebasestorage.app")
    
    return db, bucket

db, bucket = iniciar_servicos()

# 3. Estilização das Competências e Cores
COMPETENCIAS = {
    "C1 - Gramática": "#0000FF33",  # Azul
    "C2 - Repertório": "#00FF0033", # Verde
    "C3 - Argumentação": "#FFFF0033", # Amarelo
    "C4 - Coesão": "#FFA50033",    # Laranja
    "C5 - Proposta": "#FF000033"   # Vermelho
}

# --- TELA PRINCIPAL ---
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
    canvas_result = None # Inicializa para evitar erros de referência

    with col1:
        st.write("### 📝 Folha de Redação")
        
        if redacao.get('tipo') == 'arquivo':
            url_full = redacao['url_arquivo']
            
            try:
                # 1. Pega tudo que está entre '/o/' e '?'
                caminho_codificado = url_full.split("/o/")[1].split("?")[0]
                
                # 2. O 'unquote' resolve o %2F virando / e o %40 virando @ de uma vez só!
                nome_arquivo_storage = unquote(caminho_codificado)

                # 3. Agora busca o arquivo real
                blob = bucket.blob(nome_arquivo_storage)
                conteudo_arquivo = blob.download_as_bytes()
                
                
                # (O restante do código de verificação de PDF e Canvas continua o mesmo daqui para baixo)
                blob = bucket.blob(nome_arquivo_storage)
                conteudo_arquivo = blob.download_as_bytes()
                
                # VERIFICAÇÃO DE PDF
                if ".pdf" in url_full.lower():
                    st.warning("⚠️ Esta redação é um PDF. O sistema de 'caixinhas' funciona apenas em fotos (JPG/PNG).")
                    st.download_button("📥 Baixar PDF para Corrigir Offline", conteudo_arquivo, file_name=f"redacao_{redacao.get('aluno_nome')}.pdf")
                else:
                    # Carrega como imagem se não for PDF
                    img = Image.open(BytesIO(conteudo_arquivo))
                    
                    comp_selecionada = st.radio("Selecione a competência para marcar na imagem:", list(COMPETENCIAS.keys()), horizontal=True)
                    cor_pincel = COMPETENCIAS[comp_selecionada]

                    st.info("💡 Desenhe retângulos sobre os erros na imagem.")
                    canvas_result = st_canvas(
                        fill_color=cor_pincel,
                        stroke_width=1,
                        stroke_color="#000",
                        background_image=img,
                        update_streamlit=True,
                        height=img.height * (800 / img.width),
                        width=800,
                        drawing_mode="rect",
                        key="canvas_corretor",
                    )
            except Exception as e:
                st.error(f"Erro ao carregar o arquivo do Storage: {e}")
        else:
            # Caso seja texto digitado
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
            # Só processa caixinhas se o canvas existir (não for PDF/Texto)
            if canvas_result and canvas_result.json_data:
                objetos = canvas_result.json_data["objects"]
                if objetos:
                    st.write("#### 💬 Comentários nos destaques:")
                    for i, obj in enumerate(objetos):
                        cor_hex = obj['fill']
                        comentario = st.text_input(f"Comentário para o Destaque {i+1}", key=f"coment_{i}")
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
                st.success("✅ Correção enviada com sucesso!")
                time.sleep(1)
                st.rerun()

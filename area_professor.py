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

st.markdown("""
    <style>
    [data-testid="column"] { padding-right: 25px !important; }
    .img-container { overflow-x: auto; border-right: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def iniciar_servicos():
    info_chave = json.loads(st.secrets["firebase_service_account"])
    credenciais = service_account.Credentials.from_service_account_info(info_chave)
    db = firestore.Client(credentials=credenciais, project=info_chave['project_id'])
    storage_client = storage.Client(credentials=credenciais, project=info_chave['project_id'])
    bucket = storage_client.bucket("plataforma-redacao-de0f3.firebasestorage.app")
    return db, bucket

db, bucket = iniciar_servicos()

if "pontos_correcao" not in st.session_state:
    st.session_state.pontos_correcao = []

tab_correcao, tab_temas = st.tabs(["🖋️ Corrigir Redações", "📋 Gerenciar Temas"])

# ==========================================
# ABA 1: CORREÇÃO DE REDAÇÕES
# ==========================================
with tab_correcao:
    st.title("⚖️ Sistema de Correção por Pontos")

    redacoes_ref = db.collection("redacoes").where("status", "==", "Pendente").stream()
    lista = [{**r.to_dict(), 'id': r.id} for r in redacoes_ref]

    if not lista:
        st.info("Tudo corrigido por aqui! ☕")
    else:
        escolha = st.selectbox("Selecione a redação:", [f"{r.get('aluno_nome', 'Sem Nome')} - {r.get('tema', 'Sem Tema')}" for r in lista])
        redacao = next(r for r in lista if f"{r.get('aluno_nome', 'Sem Nome')} - {r.get('tema', 'Sem Tema')}" == escolha)

        st.write("### 📝 Folha de Redação")
        st.info("💡 Clique na imagem para marcar um erro. A caixa de comentário aparecerá logo abaixo.")
        
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
                
                LARGURA_CALIBRADA = 1000 
                w_orig, h_orig = img_original.size
                altura_calibrada = int(LARGURA_CALIBRADA * (h_orig / w_orig))
                
                img_para_exibir = img_original.resize((LARGURA_CALIBRADA, altura_calibrada))
                draw = ImageDraw.Draw(img_para_exibir)
                
                for i, ponto in enumerate(st.session_state.pontos_correcao):
                    x, y = ponto["x"], ponto["y"]
                    raio = 12
                    draw.ellipse([x-raio, y-raio, x+raio, y+raio], fill="red", outline="white", width=3)
                    draw.text((x-4, y-6), str(i+1), fill="white")

                value = streamlit_image_coordinates(img_para_exibir, key="editor_v6_vertical")

                if value:
                    novo_ponto = {"x": value["x"], "y": value["y"]}
                    if novo_ponto not in st.session_state.pontos_correcao:
                        st.session_state.pontos_correcao.append(novo_ponto)
                        st.rerun()

            except Exception as e:
                st.error(f"Erro ao carregar imagem: {e}")

        st.divider()

        st.write("### 📊 Painel de Avaliação")

        with st.expander("🚫 Negar Correção (Problemas com o arquivo)"):
            st.warning("Use esta opção se a redação não puder ser avaliada.")
            motivo = st.selectbox(
                "Selecione o motivo da negativa:",
                ["Problema técnico na imagem", "Letra ilegível", "Imagem muito desfocada", "Folha em branco", "Arquivo incorreto"]
            )
            obs_negativa = st.text_input("Observação para o aluno (opcional):")
            
            if st.button("Confirmar Negativa", type="secondary", use_container_width=True):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Negada", "motivo_negativa": motivo, "obs_negativa": obs_negativa,
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.session_state.pontos_correcao = []
                st.error(f"Redação marcada como 'Negada' por: {motivo}")
                time.sleep(1.5); st.rerun()

        st.divider()

        col_btn1, _ = st.columns([1, 5])
        with col_btn1:
            if st.button("Limpar Marcas 🗑️"):
                st.session_state.pontos_correcao = []
                st.rerun()

        with st.form("form_final_vertical"):
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: n1 = st.number_input("C1", 0, 200, 160, 20)
            with c2: n2 = st.number_input("C2", 0, 200, 160, 20)
            with c3: n3 = st.number_input("C3", 0, 200, 160, 20)
            with c4: n4 = st.number_input("C4", 0, 200, 160, 20)
            with c5: n5 = st.number_input("C5", 0, 200, 160, 20)
            
            st.write("#### 💬 Detalhamento dos Erros")
            comentarios_lista = []
            if st.session_state.pontos_correcao:
                for i, ponto in enumerate(st.session_state.pontos_correcao):
                    txt = st.text_input(f"Comentário para o Erro {i+1}", key=f"txt_v_{i}")
                    comentarios_lista.append({"x": ponto['x'], "y": ponto['y'], "texto": txt})
            else:
                st.info("Nenhum ponto marcado na imagem ainda.")

            feedback_geral = st.text_area("Feedback Geral para o Aluno", height=150)
            
            _, col_sub, _ = st.columns([2, 1, 2])
            if col_sub.form_submit_button("Enviar Correção Completa", type="primary", use_container_width=True):
                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida", "anotacoes_detalhadas": comentarios_lista,
                    "notas": [n1, n2, n3, n4, n5], "nota_final": n1+n2+n3+n4+n5,
                    "feedback_geral": feedback_geral, "data_correcao": firestore.SERVER_TIMESTAMP
                })
                st.session_state.pontos_correcao = []
                st.success("✅ Correção finalizada e enviada!")
                time.sleep(1.5); st.rerun()

# ==========================================
# ABA 2: GERENCIAMENTO DE TEMAS
# ==========================================
with tab_temas:
    st.title("📋 Gerenciador de Temas")
    st.write("Adicione novos temas e textos de apoio (PDF).")
    
    with st.form("form_novo_tema", clear_on_submit=True):
        novo_tema = st.text_input("Título do Novo Tema", placeholder="Ex: Caminhos para combater a intolerância...")
        
        # NOVO: Uploader de PDF
        arquivo_apoio = st.file_uploader("Texto de Apoio (Anexe um PDF) - Opcional", type=["pdf"])
        
        if st.form_submit_button("Salvar Tema", type="primary"):
            if novo_tema.strip() != "":
                url_pdf = ""
                # Se o professor enviou um PDF, fazemos o upload pro Storage
                if arquivo_apoio:
                    nome_blob = f"textos_apoio/{int(time.time())}_{arquivo_apoio.name}"
                    blob = bucket.blob(nome_blob)
                    blob.upload_from_file(arquivo_apoio, content_type="application/pdf")
                    url_pdf = blob.public_url # Pega o link gerado

                db.collection("temas").add({
                    "nome": novo_tema.strip(),
                    "url_apoio": url_pdf, # Salva o link no banco
                    "data_criacao": firestore.SERVER_TIMESTAMP
                })
                st.success("✅ Tema adicionado com sucesso!")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("O título do tema não pode estar vazio.")

    st.write("---")
    st.write("#### Temas Cadastrados")
    temas_salvos = db.collection("temas").order_by("data_criacao", direction=firestore.Query.DESCENDING).stream()
    
    temas_encontrados = False
    for t in temas_salvos:
        temas_encontrados = True
        dados = t.to_dict()
        nome = dados.get('nome')
        url = dados.get('url_apoio')
        
        # Mostra o tema e um clipe se tiver PDF
        if url:
            st.markdown(f"- 📎 **{nome}** ([Ver PDF]({url}))")
        else:
            st.markdown(f"- {nome}")
            
    if not temas_encontrados:
        st.info("Nenhum tema personalizado cadastrado ainda.")

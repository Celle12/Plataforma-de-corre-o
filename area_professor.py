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
    
    comentario_temp = st.text_area("O que está errado?", 
                                  value=ponto_atual.get('texto', ""), 
                                  height=150)
    
    if st.button("Salvar e Fechar", type="primary", use_container_width=True):
        st.session_state.pontos_correcao[index]['texto'] = comentario_temp
        st.session_state[f"f_input_{index}"] = comentario_temp
        st.session_state.ponto_para_comentar = None
        st.rerun()

# --- ABAS ---
tab_correcao, tab_temas = st.tabs(["🖋️ Corrigir Redações", "📋 Gerenciar Temas"])

with tab_correcao:
    components.html(
        """<script>
            var scroll_helper = function() {
                var el = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
                if (el) { el.scrollTo(0, 0); }
            }
            scroll_helper(); setTimeout(scroll_helper, 100);
        </script>""", height=0
    )

    if st.session_state.ponto_para_comentar is not None:
        modal_comentario(st.session_state.ponto_para_comentar)

    st.title("⚖️ Sistema de Correção")
    
    redacoes_ref = db.collection("redacoes").where("status", "==", "Pendente").stream()
    lista = [{**r.to_dict(), 'id': r.id} for r in redacoes_ref]

    if not lista:
        st.info("Tudo corrigido! ☕")
    else:
        escolha = st.selectbox("Selecione a redação:", [f"{r.get('aluno_nome')} - {r.get('tema')}" for r in lista])
        redacao = next(r for r in lista if f"{r.get('aluno_nome')} - {r.get('tema')}" == escolha)

        # --- ÁREA DA IMAGEM ---
        st.write("#### 📝 Folha de Redação")
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
                img_orig = Image.open(BytesIO(img_bytes)).convert("RGB")
                
                LARGURA = 1000 
                img_edit = img_orig.resize((LARGURA, int(LARGURA * (img_orig.size[1]/img_orig.size[0]))))
                draw = ImageDraw.Draw(img_edit)
                
                for i, p in enumerate(st.session_state.pontos_correcao):
                    x, y, r = p["x"], p["y"], 12
                    draw.ellipse([x-r, y-r, x+r, y+r], fill="red", outline="white", width=3)
                    draw.text((x-4, y-6), str(i+1), fill="white")

                value = streamlit_image_coordinates(img_edit, key="editor_v17")

                if value and value != st.session_state.ultimo_clique:
                    st.session_state.ultimo_clique = value
                    novo_p = {"x": value["x"], "y": value["y"], "texto": ""}
                    st.session_state.pontos_correcao.append(novo_p)
                    st.session_state.ponto_para_comentar = len(st.session_state.pontos_correcao) - 1
                    st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

        st.divider()

        # --- PAINEL DE AVALIAÇÃO ---
        st.write("#### 📊 Painel de Avaliação")
        
        if st.button("Limpar Marcas 🗑️"):
            chaves_para_limpar = [k for k in st.session_state.keys() if k.startswith("f_input_")]
            for k in chaves_para_limpar: del st.session_state[k]
            st.session_state.pontos_correcao = []
            st.session_state.ultimo_clique = None
            st.rerun()

        with st.form("form_final_v17"):
            st.write("**Notas (Competências 1 a 5)**")
            c1, c2, c3, c4, c5 = st.columns(5)
            n1 = c1.number_input("C1", 0, 200, 160, 20)
            n2 = c2.number_input("C2", 0, 200, 160, 20)
            n3 = c3.number_input("C3", 0, 200, 160, 20)
            n4 = c4.number_input("C4", 0, 200, 160, 20)
            n5 = c5.number_input("C5", 0, 200, 160, 20)
            
            st.write("**📝 Revisão dos Comentários**")
            
            # ATENÇÃO: Aqui geramos as caixas, mas a captura real acontece DENTRO do form_submit_button
            if st.session_state.pontos_correcao:
                for i, p in enumerate(st.session_state.pontos_correcao):
                    st.text_input(f"Comentário {i+1}", 
                                  value=st.session_state.get(f"f_input_{i}", p.get('texto', "")),
                                  key=f"f_input_{i}")
            else:
                st.info("Clique na imagem acima para marcar os erros.")

            fb_geral = st.text_area("Feedback Geral")
            
            # --- O MOMENTO DO ENVIO (A CORREÇÃO ESTÁ AQUI) ---
            if st.form_submit_button("Enviar Correção Completa", type="primary", use_container_width=True):
                
                lista_final_envio = []
                # Construímos a lista "pescando" o que está AGORA nas caixinhas do Streamlit
                for i, p in enumerate(st.session_state.pontos_correcao):
                    # Ele vai buscar o valor atualizado que você acabou de digitar lá embaixo
                    texto_editado_final = st.session_state.get(f"f_input_{i}", p.get('texto', ""))
                    lista_final_envio.append({"x": p['x'], "y": p['y'], "texto": texto_editado_final})

                db.collection("redacoes").document(redacao['id']).update({
                    "status": "Corrigida", 
                    "anotacoes_detalhadas": lista_final_envio, # Lista nova enviada!
                    "notas": [n1, n2, n3, n4, n5], 
                    "nota_final": sum([n1, n2, n3, n4, n5]),
                    "feedback_geral": fb_geral, 
                    "data_correcao": firestore.SERVER_TIMESTAMP
                })
                
                # Limpeza geral após o envio
                chaves_para_limpar = [k for k in st.session_state.keys() if k.startswith("f_input_")]
                for k in chaves_para_limpar: del st.session_state[k]
                st.session_state.pontos_correcao = []
                st.session_state.ultimo_clique = None
                st.success("✅ Enviado com as edições finais!"); time.sleep(1); st.rerun()

# --- ABA DE TEMAS ---
with tab_temas:
    st.title("📋 Gerenciar Temas")
    with st.expander("➕ Adicionar Novo Tema", expanded=True):
        with st.form("form_tema_v17", clear_on_submit=True):
            nome_t = st.text_input("Nome do Tema:")
            pdf_t = st.file_uploader("PDF de Apoio (Opcional):", type=["pdf"])
            if st.form_submit_button("Cadastrar Tema", type="primary"):
                if nome_t.strip():
                    url_pdf = ""
                    if pdf_t:
                        b = bucket.blob(f"textos_apoio/{int(time.time())}_{pdf_t.name}")
                        b.upload_from_file(pdf_t, content_type="application/pdf")
                        b.make_public(); url_pdf = b.public_url
                    db.collection("temas").add({"nome": nome_t.strip(), "url_apoio": url_pdf, "data_criacao": firestore.SERVER_TIMESTAMP})
                    st.success("Tema salvo com sucesso!")
                    time.sleep(1); st.rerun()
                else: st.warning("O nome do tema não pode ficar em branco.")
    st.divider()
    st.write("### 🗑️ Temas Cadastrados")
    temas_ref = db.collection("temas").order_by("data_criacao", direction=firestore.Query.DESCENDING).stream()
    temas_lista = [{**t.to_dict(), 'id': t.id} for t in temas_ref]
    if not temas_lista:
        st.info("Nenhum tema cadastrado ainda.")
    else:
        for t in temas_lista:
            col_texto, col_btn = st.columns([0.85, 0.15])
            with col_texto:
                icone_pdf = "📎" if t.get('url_apoio') else "📝"
                st.write(f"{icone_pdf} **{t.get('nome')}**")
            with col_btn:
                if st.button("Excluir", key=f"del_{t['id']}", use_container_width=True):
                    db.collection("temas").document(t['id']).delete()
                    st.error(f"Tema excluído: {t.get('nome')}")
                    time.sleep(1); st.rerun()
            st.write("---")

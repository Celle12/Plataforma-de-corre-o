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

# --- FUNÇÃO DO POP-UP ---
@st.dialog("📝 Adicionar Comentário")
def modal_comentario(index):
    st.write(f"### Erro {index + 1}")
    ponto_atual = st.session_state.pontos_correcao[index]
    comentario_temp = st.text_area("O que está errado?", value=ponto_atual.get('texto', ""), height=150)
    if st.button("Salvar e Fechar", type="primary", use_container_width=True):
        st.session_state.pontos_correcao[index]['texto'] = comentario_temp
        st.session_state[f"f_input_{index}"] = comentario_temp
        st.session_state.ponto_para_comentar = None
        st.rerun()

# --- ABAS ---
tab_correcao, tab_temas, tab_gestao = st.tabs(["🖋️ Corrigir Redações", "📋 Temas", "📂 Gestão de Redações"])

# ==========================================
# ABA 1: CORREÇÃO
# ==========================================
with tab_correcao:
    components.html("""<script>var s = window.parent.document.querySelector('[data-testid="stAppViewContainer"]'); if(s){s.scrollTo(0,0);}setTimeout(function(){if(s){s.scrollTo(0,0);}},100);</script>""", height=0)
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

        st.write("#### 📝 Folha de Redação")
        caminho = redacao.get('caminho_storage')
        url_full = redacao.get('url_arquivo', '')
        if not caminho and url_full:
            bucket_name = "plataforma-redacao-de0f3.firebasestorage.app"
            if bucket_name in url_full: caminho = unquote(url_full.split(bucket_name + "/")[-1].split("?")[0])

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

                value = streamlit_image_coordinates(img_edit, key="editor_v18")
                if value and value != st.session_state.ultimo_clique:
                    st.session_state.ultimo_clique = value
                    st.session_state.pontos_correcao.append({"x": value["x"], "y": value["y"], "texto": ""})
                    st.session_state.ponto_para_comentar = len(st.session_state.pontos_correcao) - 1
                    st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

        st.divider()
        if st.button("Limpar Marcas 🗑️"):
            for k in [k for k in st.session_state.keys() if k.startswith("f_input_")]: del st.session_state[k]
            st.session_state.pontos_correcao = []; st.session_state.ultimo_clique = None; st.rerun()

        with st.form("form_final_v18"):
            st.write("**Notas (C1 a C5)**")
            c1, c2, c3, c4, c5 = st.columns(5)
            n1, n2, n3, n4, n5 = [col.number_input(f"C{i+1}", 0, 200, 160, 20) for i, col in enumerate([c1, c2, c3, c4, c5])]
            
            st.write("**📝 Revisão dos Comentários**")
            if st.session_state.pontos_correcao:
                for i, p in enumerate(st.session_state.pontos_correcao):
                    st.text_input(f"Comentário {i+1}", value=st.session_state.get(f"f_input_{i}", p.get('texto', "")), key=f"f_input_{i}")
            else: st.info("Marque erros na imagem.")

            fb_geral = st.text_area("Feedback Geral")
            if st.form_submit_button("Enviar Correção Completa", type="primary", use_container_width=True):
                lista_final = []
                for i, p in enumerate(st.session_state.pontos_correcao):
                    lista_final.append({"x": p['x'], "y": p['y'], "texto": st.session_state.get(f"f_input_{i}", p.get('texto', ""))})
                db.collection("redacoes").document(redacao['id']).update({"status": "Corrigida", "anotacoes_detalhadas": lista_final, "notas": [n1, n2, n3, n4, n5], "nota_final": sum([n1, n2, n3, n4, n5]), "feedback_geral": fb_geral, "data_correcao": firestore.SERVER_TIMESTAMP})
                for k in [k for k in st.session_state.keys() if k.startswith("f_input_")]: del st.session_state[k]
                st.session_state.pontos_correcao = []; st.session_state.ultimo_clique = None; st.success("✅ Enviado!"); time.sleep(1); st.rerun()

# ==========================================
# ABA 2: TEMAS
# ==========================================
with tab_temas:
    st.title("📋 Gerenciar Temas")
    with st.expander("➕ Adicionar Novo Tema", expanded=True):
        with st.form("form_tema_v18", clear_on_submit=True):
            nome_t = st.text_input("Nome do Tema:")
            pdf_t = st.file_uploader("PDF de Apoio:", type=["pdf"])
            if st.form_submit_button("Cadastrar", type="primary"):
                if nome_t.strip():
                    url_p = ""
                    if pdf_t:
                        b = bucket.blob(f"textos_apoio/{int(time.time())}_{pdf_t.name}")
                        b.upload_from_file(pdf_t, content_type="application/pdf"); b.make_public(); url_p = b.public_url
                    db.collection("temas").add({"nome": nome_t.strip(), "url_apoio": url_p, "data_criacao": firestore.SERVER_TIMESTAMP})
                    st.success("Salvo!"); time.sleep(1); st.rerun()
    
    st.divider(); st.write("### 🗑️ Temas Atuais")
    temas_lista = [{**t.to_dict(), 'id': t.id} for t in db.collection("temas").order_by("data_criacao", direction=firestore.Query.DESCENDING).stream()]
    for t in temas_lista:
        c_txt, c_btn = st.columns([0.85, 0.15])
        c_txt.write(f"{'📎' if t.get('url_apoio') else '📝'} **{t.get('nome')}**")
        if c_btn.button("Excluir", key=f"del_t_{t['id']}", use_container_width=True):
            db.collection("temas").document(t['id']).delete(); st.rerun()

# ==========================================
# ABA 3: GESTÃO DE REDAÇÕES (NOVA!)
# ==========================================
with tab_gestao:
    st.title("📂 Gestão de Banco de Redações")
    st.write("Visualize e limpe o histórico de envios da plataforma.")
    
    status_filtro = st.multiselect("Filtrar por Status:", ["Pendente", "Corrigida", "Negada"], default=["Pendente", "Corrigida", "Negada"])
    
    # Busca todas as redações
    red_ref = db.collection("redacoes").order_by("data_envio", direction=firestore.Query.DESCENDING).stream()
    todas_redacoes = [{**r.to_dict(), 'id': r.id} for r in red_ref]
    
    # Filtra localmente para facilitar
    redacoes_filtradas = [r for r in todas_redacoes if r.get('status') in status_filtro]

    if not redacoes_filtradas:
        st.info("Nenhuma redação encontrada com esses filtros.")
    else:
        st.write(f"Exibindo **{len(redacoes_filtradas)}** redações.")
        
        for r in redacoes_filtradas:
            with st.expander(f"👤 {r.get('aluno_nome')} | 📄 {r.get('tema')} | 🏷️ {r.get('status')}"):
                col1, col2 = st.columns([0.7, 0.3])
                
                with col1:
                    st.write(f"**E-mail:** {r.get('aluno_email')}")
                    data = r.get('data_envio')
                    st.write(f"**Enviada em:** {data.strftime('%d/%m/%Y %H:%M') if data else 'Sem data'}")
                    if r.get('status') == "Corrigida":
                        st.write(f"**Nota Final:** {r.get('nota_final')}")
                
                with col2:
                    # BOTÃO DE EXCLUIR DEFINITIVO
                    if st.button("🗑️ Excluir Definitivamente", key=f"excluir_red_{r['id']}", use_container_width=True):
                        try:
                            # 1. Tenta apagar o arquivo no Storage primeiro
                            caminho_st = r.get('caminho_storage')
                            if caminho_st:
                                blob = bucket.blob(caminho_st)
                                if blob.exists():
                                    blob.delete()
                            
                            # 2. Apaga o registro no Firestore
                            db.collection("redacoes").document(r['id']).delete()
                            
                            st.success("Redação e arquivo removidos com sucesso!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")

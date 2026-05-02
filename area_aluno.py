import streamlit as st
import pyrebase
import time
import json
import plotly.graph_objects as go
from io import BytesIO
from PIL import Image
from google.cloud import firestore, storage
from google.oauth2 import service_account
from urllib.parse import unquote

# 1. Configuração da Página
st.set_page_config(page_title="Área do Aluno - Redação", page_icon="📝", layout="wide")

# 2. Configuração do Firebase
firebaseConfig = {
  "apiKey": "AIzaSyBBxjGQkN_b-keKwXw9KQq-W8l76D6C2zA",
  "authDomain": "plataforma-redacao-de0f3.firebaseapp.com",
  "projectId": "plataforma-redacao-de0f3",
  "storageBucket": "plataforma-redacao-de0f3.firebasestorage.app",
  "messagingSenderId": "105466681652",
  "appId": "1:105466681652:web:13438e4cbd600a1c3a2d61",
  "databaseURL": "" 
}

@st.cache_resource
def iniciar_servicos():
    info_chave = json.loads(st.secrets["firebase_service_account"])
    credenciais = service_account.Credentials.from_service_account_info(info_chave)
    db = firestore.Client(credentials=credenciais, project=info_chave['project_id'])
    storage_client = storage.Client(credentials=credenciais, project=info_chave['project_id'])
    bucket = storage_client.bucket(firebaseConfig["storageBucket"])
    return db, bucket

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
db, bucket = iniciar_servicos()

# Inicialização do session_state
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'email_usuario' not in st.session_state:
    st.session_state.email_usuario = ""
if 'nome_usuario' not in st.session_state:
    st.session_state.nome_usuario = ""

# --- LÓGICA DE ACESSO ---
if not st.session_state.logado:
    st.title("🔐 Acesso à Plataforma")
    aba1, aba2 = st.tabs(["Login", "Cadastrar"])
    
    with aba1:
        email_input = st.text_input("E-mail", key="login_email_final")
        senha_input = st.text_input("Senha", type="password", key="login_senha_final")
        
        if st.button("Entrar", type="primary", key="btn_entrar"):
            if email_input and senha_input:
                try:
                    user = auth.sign_in_with_email_and_password(email_input, senha_input)
                    doc = db.collection("usuarios").document(email_input).get()
                    st.session_state.nome_usuario = doc.to_dict().get("nome") if doc.exists else email_input
                    st.session_state.email_usuario = email_input
                    st.session_state.logado = True
                    st.rerun()
                except Exception:
                    st.error("E-mail ou senha incorretos.")
            else:
                st.warning("Preencha todos os campos.")
    
    with aba2:
        with st.form("signup_form_final"):
            nome_completo = st.text_input("Nome Completo")
            email_novo = st.text_input("Novo E-mail")
            senha_nova = st.text_input("Nova Senha", type="password")
            if st.form_submit_button("Criar Conta"):
                if nome_completo and email_novo and senha_nova:
                    try:
                        auth.create_user_with_email_and_password(email_novo, senha_nova)
                        db.collection("usuarios").document(email_novo).set({"nome": nome_completo, "email": email_novo})
                        st.success("Conta criada! Agora faça login na aba ao lado.")
                    except:
                        st.error("Erro ao criar conta.")

# --- ÁREA LOGADA ---
else:
    st.sidebar.title("Painel do Aluno")
    st.sidebar.info(f"👤 {st.session_state.nome_usuario}")
    
    if st.sidebar.button("Sair da Conta"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    tab_envio, tab_status = st.tabs(["🚀 Enviar Nova Redação", "📂 Acompanhar Minhas Redações"])

    # --- TAB DE ENVIO ---
    with tab_envio:
        st.title("📝 Envio de Redação")
        tema = st.selectbox("Selecione o tema:", ["Escolha...", "Impactos da IA", "Saúde Mental", "Escolaridades"])
        
        if tema != "Escolha...":
            metodo = st.radio("Formato:", ["Digitar Texto", "Anexar Arquivo"], horizontal=True)
            with st.form("envio_redacao", clear_on_submit=True):
                if metodo == "Digitar Texto":
                    texto_redacao = st.text_area("Sua redação:", height=300)
                    arquivo_upload = None
                else:
                    texto_redacao = ""
                    arquivo_upload = st.file_uploader("Selecione a foto", type=["png", "jpg", "jpeg"])

                if st.form_submit_button("Enviar para Correção", type="primary"):
                    if texto_redacao or arquivo_upload:
                        url_arquivo, nome_blob = "", ""
                        if arquivo_upload:
                            nome_blob = f"redacoes/{st.session_state.email_usuario}_{int(time.time())}.jpg"
                            blob = bucket.blob(nome_blob)
                            blob.upload_from_file(arquivo_upload)
                            url_arquivo = blob.public_url
                        
                        db.collection("redacoes").add({
                            "aluno_nome": st.session_state.nome_usuario,
                            "aluno_email": st.session_state.email_usuario,
                            "tema": tema,
                            "texto": texto_redacao,
                            "url_arquivo": url_arquivo,
                            "caminho_storage": nome_blob,
                            "tipo": "arquivo" if arquivo_upload else "texto",
                            "data_envio": firestore.SERVER_TIMESTAMP,
                            "status": "Pendente"
                        })
                        st.success("Enviado com sucesso!")
                        st.balloons()
                    else:
                        st.warning("Adicione conteúdo antes de enviar.")

    # --- TAB DE STATUS E VISUALIZAÇÃO INTERATIVA ---
    with tab_status:
        st.title("📂 Histórico de Correções")
        
        redacoes_query = db.collection("redacoes").where("aluno_email", "==", st.session_state.email_usuario).stream()
        minhas_redacoes = [{**r.to_dict(), 'id': r.id} for r in redacoes_query]

        if not minhas_redacoes:
            st.info("Você ainda não tem redações enviadas.")
        else:
            minhas_redacoes.sort(key=lambda x: x.get('data_envio') or 0, reverse=True)
            escolha = st.selectbox("Selecione a redação:", [f"{r['tema']} - {r['status']}" for r in minhas_redacoes])
            r = next(red for red in minhas_redacoes if f"{red['tema']} - {red['status']}" == escolha)

            st.divider()

            if r['status'] == "Pendente":
                st.warning("⏳ Sua redação está na fila de correção. Aguarde o professor.")

            elif r['status'] == "Negada":
                st.error(f"❌ Problema: {r.get('motivo_negativa')}")
                st.info(f"**Obs:** {r.get('obs_negativa')}")
                novo_arq = st.file_uploader("Reenviar foto nítida:", type=["jpg", "png", "jpeg"], key="reenvio")
                if st.button("Confirmar Reenvio"):
                    if novo_arq:
                        nome_blob = f"redacoes/{st.session_state.email_usuario}_RE_{int(time.time())}.jpg"
                        blob = bucket.blob(nome_blob)
                        blob.upload_from_file(novo_arq)
                        db.collection("redacoes").document(r['id']).update({
                            "url_arquivo": blob.public_url,
                            "caminho_storage": nome_blob,
                            "status": "Pendente",
                            "motivo_negativa": firestore.DELETE_FIELD
                        })
                        st.success("Reenviado!")
                        time.sleep(1); st.rerun()

            elif r['status'] == "Corrigida":
                st.success(f"🎉 Nota Final: {r.get('nota_final', 0)}")
                notas = r.get('notas', [0,0,0,0,0])
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("C1", notas[0]); c2.metric("C2", notas[1]); c3.metric("C3", notas[2])
                c4.metric("C4", notas[3]); c5.metric("C5", notas[4])

                t_img, t_com = st.tabs(["🖼️ Ver Folha Interativa", "💬 Resumo dos Comentários"])
                
                with t_img:
                    # Lógica robusta de busca da imagem (Igual a do professor)
                    caminho = r.get('caminho_storage')
                    url_full = r.get('url_arquivo', '')
                    if not caminho and url_full:
                        bucket_name = "plataforma-redacao-de0f3.firebasestorage.app"
                        if bucket_name in url_full:
                            caminho = unquote(url_full.split(bucket_name + "/")[-1].split("?")[0])

                    if caminho:
                        try:
                            # 1. Baixar a imagem original
                            blob = bucket.blob(caminho)
                            img_bytes = blob.download_as_bytes()
                            img = Image.open(BytesIO(img_bytes)).convert("RGB")
                            
                            # 2. Calibrar para 1000px (A MESMA MIRA DO PROFESSOR)
                            LARGURA = 1000
                            w_orig, h_orig = img.size
                            ALTURA = int(LARGURA * (h_orig / w_orig))
                            img = img.resize((LARGURA, ALTURA))

                            # 3. Criar gráfico interativo com Plotly
                            fig = go.Figure()
                            
                            # Adicionar a imagem como fundo (papel de parede)
                            fig.add_layout_image(
                                dict(
                                    source=img, xref="x", yref="y",
                                    x=0, y=0, sizex=LARGURA, sizey=ALTURA,
                                    sizing="stretch", opacity=1, layer="below"
                                )
                            )

                            # Ajustar os eixos (Y invertido para bater com a imagem)
                            fig.update_xaxes(visible=False, range=[0, LARGURA])
                            fig.update_yaxes(visible=False, range=[ALTURA, 0], scaleanchor="x", scaleratio=1)

                            # 4. Adicionar os pontos com hover (etiquetas flutuantes)
                            anotacoes = r.get('anotacoes_detalhadas', [])
                            if anotacoes:
                                xs = [a['x'] for a in anotacoes]
                                ys = [a['y'] for a in anotacoes]
                                numeros = [str(i+1) for i in range(len(anotacoes))]
                                
                                # O texto que vai aparecer no "balãozinho" quando passar o mouse
                                textos_hover = [f"<b>Erro {i+1}</b><br>{a['texto']}" for i, a in enumerate(anotacoes)]

                                fig.add_trace(go.Scatter(
                                    x=xs, y=ys,
                                    mode='markers+text',
                                    text=numeros,
                                    textposition="middle center",
                                    textfont=dict(color='white', size=14, family="Arial Black"),
                                    marker=dict(size=26, color='rgba(255, 0, 0, 0.9)', line=dict(color='white', width=3)),
                                    hovertext=textos_hover,
                                    hoverinfo="text", # Mostra só o texto programado
                                    showlegend=False
                                ))

                            # Remover margens para focar 100% na redação
                            fig.update_layout(
                                margin=dict(l=0, r=0, t=0, b=0),
                                height=ALTURA,
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                hovermode="closest"
                            )

                            # Renderizar o gráfico no Streamlit
                            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                        except Exception as e:
                            st.error(f"Erro ao carregar a imagem interativa: {e}")
                    else:
                        st.info("Nenhuma imagem atrelada a esta redação. Foi enviada como texto?")
                        st.text_area("Texto enviado:", r.get('texto'), height=300, disabled=True)

                with t_com:
                    st.info(f"**Feedback Geral:** {r.get('feedback_geral', 'Sem feedback geral.')}")
                    st.divider()
                    st.write("### 📍 Detalhamento dos Erros")
                    for i, anot in enumerate(r.get('anotacoes_detalhadas', [])):
                        st.write(f"**Erro {i+1}:** {anot['texto']}")

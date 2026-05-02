import streamlit as st

# 1. Configuração inicial da página
st.set_page_config(page_title="Área do Aluno - Redação", page_icon="📝", layout="centered")

# 2. Barra Lateral (Simulando o Login do Firebase)
st.sidebar.title("Meu Painel")
st.sidebar.write("👤 Bem-vindo(a), Aluno!")
st.sidebar.write("Créditos: 3 redações")
st.sidebar.divider()
st.sidebar.button("Sair da Conta")

# 3. Cabeçalho Principal
st.title("📝 Envio de Redação")
st.write("Escolha o tema da semana e envie seu texto para correção.")

# 4. Seleção de Tema
st.subheader("1. Tema da Redação")
temas_disponiveis = [
    "Selecione um tema...",
    "Os impactos da inteligência artificial na educação",
    "Caminhos para combater a desigualdade social no Brasil",
    "A preservação da saúde mental na era digital"
]
tema_escolhido = st.selectbox("Qual tema você vai escrever?", temas_disponiveis)

# 5. Área de Envio (Só aparece se o aluno escolher um tema válido)
if tema_escolhido != "Selecione um tema...":
    st.subheader("2. Envie seu Texto")
    
    # Opção para digitar ou enviar arquivo
    metodo_envio = st.radio("Como você prefere enviar?", ["Digitar aqui", "Enviar Arquivo (Foto/PDF)"])
    
    if metodo_envio == "Digitar aqui":
        texto_redacao = st.text_area("Cole ou digite sua redação:", height=300, placeholder="Escreva seu texto aqui. Lembre-se de estruturar em introdução, desenvolvimento e conclusão.")
        
        if st.button("Enviar Redação", type="primary"):
            if len(texto_redacao) > 50: # Verificação básica
                # Aqui entrará a conexão para salvar no Firebase Firestore
                st.success("✅ Redação enviada com sucesso! Acompanhe o status no seu painel.")
                st.balloons()
            else:
                st.error("⚠️ O texto está muito curto. Digite a redação completa antes de enviar.")
                
    elif metodo_envio == "Enviar Arquivo (Foto/PDF)":
        arquivo_redacao = st.file_uploader("Arraste ou selecione seu arquivo", type=["pdf", "png", "jpg", "jpeg"])
        
        if st.button("Enviar Arquivo", type="primary"):
            if arquivo_redacao is not None:
                # Aqui entrará a conexão para salvar no Firebase Storage
                st.success(f"✅ Arquivo {arquivo_redacao.name} enviado com sucesso!")
                st.balloons()
            else:
                st.error("⚠️ Por favor, anexe um arquivo antes de clicar em enviar.")

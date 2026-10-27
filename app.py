import json
import streamlit as st
import unicodedata
from groq import Groq

# ==========================================
# CONFIGURAÇÃO DA PÁGINA (DEVE SER A 1ª COISA)
# ==========================================
st.set_page_config(
    page_title="Sommelier Terrazza 40",
    page_icon="🍷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==========================================
# CSS PERSONALIZADO (O SEGREDO DO DESIGN)
# ==========================================
st.markdown("""
    <style>
    /* Fonte mais elegante (Google Fonts) */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&family=Lato:wght@400;700&display=swap');
    
    /* Muda a cor de fundo para um tom escuro elegante */
    .stApp {
        background-color: #1a1a1a;
        color: #e0e0e0;
        font-family: 'Lato', sans-serif;
    }
    
    /* Estiliza o Título Principal */
    h1 {
        font-family: 'Playfair Display', serif;
        color: #d4af37 !important; /* Dourado */
        text-align: center;
        margin-bottom: 0px;
    }
    
    /* Esconde o menu padrão do Streamlit e o rodapé */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Estiliza as caixas de mensagem do chat */
    .stChatMessage {
        background-color: #2a2a2a;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
        border-left: 4px solid #d4af37;
    }
    
    /* Deixa a caixa de digitar mais bonita */
    .stChatInput {
        border-top: 1px solid #333;
        background-color: #1a1a1a;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CONFIGURAÇÕES (GROQ E JSON)
# ==========================================
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

@st.cache_data
def carregar_carta():
    with open("carta_vinhos.json", "r", encoding="utf-8") as f:
        return json.load(f)

carta = carregar_carta()

def normalizar_texto(texto):
    if not texto: return ""
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.lower().replace("-", " ").strip()

SYSTEM_PROMPT = """
Você é o Sommelier Virtual do Terrazza 40 (Curitiba).
Seja extremamente educado, elegante e objetivo.

Sempre que o cliente pedir uma sugestão, um vinho específico, ou citar uma palavra-chave, use a ferramenta `buscar_vinhos`.
REGRA DE OURO: NUNCA invente vinhos, safras ou preços.
Recomende no máximo 3 vinhos. Informe: Nome, Safra, País, Uva e Preço.
 
REGRA DE RESUMO: Use o campo "descricao" retornado pela ferramenta para criar um resumo curto (máximo 2 frases), destacando o sabor.

FORMATO OBRIGATÓRIO:
**Nome do Vinho**
Safra: X | País: Y | Uva: Z | Volume: W ml | Preço: R$ V
![Nome do Vinho](URL_DA_IMAGEM_AQUI)
*Resumo:* [Seu resumo]
"""

def buscar_vinhos(nome=None, tipo=None, pais=None, preco_max=None, uva=None, secao=None):
    resultados = []
    for v in carta["vinhos"]:
        if nome and normalizar_texto(nome) not in normalizar_texto(v.get("nome", "")): continue
        if secao and normalizar_texto(secao) not in normalizar_texto(v.get("secao_carta", "")): continue
        if tipo and v.get("tipo") != tipo: continue
        if pais and v.get("pais") != pais: continue
        if uva and not any(normalizar_texto(uva) in normalizar_texto(u) for u in v.get("uvas", [])): continue
        if preco_max and v.get("preco_brl") and v["preco_brl"] > preco_max: continue
        resultados.append(v)
    
    if not resultados:
        return [{"status": "vazio", "mensagem": "Nenhum vinho encontrado."}]

    resumo_vinhos = []
    for v in resultados[:3]:
        resumo_vinhos.append({
            "nome": v["nome"], "safra": v["safra"], "pais": v["pais"],
            "uvas": v["uvas"], "volume_ml": v.get("volume_ml", 750),
            "preco_brl": v["preco_brl"], "imagem_url": v.get("imagem_url"),
            "descricao": v.get("descricao", "")
        })
    return resumo_vinhos

tools = [{
    "type": "function",
    "function": {
        "name": "buscar_vinhos",
        "description": "Busca vinhos na carta do restaurante",
        "parameters": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"}, "secao": {"type": "string"},
                "tipo": {"type": "string", "enum": ["tinto", "branco", "rose", "espumante", "champagne"]},
                "pais": {"type": "string"}, "preco_max": {"type": "number"}, "uva": {"type": "string"}
            }
        }
    }
}]

def limpar_mensagens(historico):
    return [{"role": m["role"], **{k: v for k, v in m.items() if k != "role" and v is not None}} for m in historico]

# ==========================================
# CABEÇALHO VISUAL (BANNER)
# ==========================================
# Você pode trocar esta URL por uma foto real do Terrazza 40 ou da adega
url_banner = "https://images.unsplash.com/photo-1506377247377-2a5b3b417ebb?q=80&w=1000&auto=format&fit=crop"
st.image(url_banner, use_container_width=True)
st.markdown("<h1>Terrazza 40</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #888;'>Sommelier Virtual • Bigorrilho, Curitiba</p>", unsafe_allow_html=True)
st.divider()

# ==========================================
# HISTÓRICO DO CHAT
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

for msg in st.session_state.messages[1:]:
    if msg.get("role") in ["system", "tool"]: continue
    if msg.get("role") == "assistant" and msg.get("tool_calls"): continue
    
    # Define o avatar de cada um
    avatar_user = "🧑‍🍳" 
    avatar_assistant = "🍷"
    
    current_avatar = avatar_user if msg["role"] == "user" else avatar_assistant
    
    with st.chat_message(msg["role"], avatar=current_avatar):
        if msg.get("content"):
            st.markdown(msg["content"])

# ==========================================
# INPUT DO USUÁRIO
# ==========================================
if prompt := st.chat_input("Olá! Qual vinho posso servir para você hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍🍳"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🍷"):
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=limpar_mensagens(st.session_state.messages),
            tools=tools,
            tool_choice="auto",
            max_tokens=500 
        )
        
        msg = response.choices[0].message
        msg_dict = msg.model_dump(exclude_none=True)
        st.session_state.messages.append(msg_dict)
        
        if msg_dict.get("tool_calls"):
            for tool_call in msg_dict["tool_calls"]:
                args = json.loads(tool_call["function"]["arguments"])
                vinhos_encontrados = buscar_vinhos(**args)
                
                st.session_state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": "buscar_vinhos",
                    "content": json.dumps(vinhos_encontrados, ensure_ascii=False)
                })
            
            response2 = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=limpar_mensagens(st.session_state.messages),
                tools=tools,
                max_tokens=800
            )
            final_msg = response2.choices[0].message
            final_msg_dict = final_msg.model_dump(exclude_none=True)
            
            texto_final = final_msg.content if final_msg.content else "Desculpe, não consegui formular uma resposta."
            final_msg_dict["content"] = texto_final
            st.session_state.messages.append(final_msg_dict)
            
            st.markdown(texto_final)
        else:
            st.markdown(msg.content)

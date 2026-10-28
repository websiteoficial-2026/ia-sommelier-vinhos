import json
import streamlit as st
import unicodedata
from groq import Groq

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E DESIGN
# ==========================================
st.set_page_config(page_title="Sommelier SKY", page_icon="🍷", layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&family=Lato:wght@400;700&display=swap');
    .stApp { background-color: #1a1a1a; color: #e0e0e0; font-family: 'Lato', sans-serif; }
    h1 { font-family: 'Playfair Display', serif; color: #d4af37 !important; text-align: center; margin-bottom: 0px; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stChatMessage { background-color: #2a2a2a; border-radius: 10px; padding: 10px; margin-bottom: 10px; border-left: 4px solid #d4af37; }
    .stChatInput { border-top: 1px solid #333; background-color: #1a1a1a; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CONEXÃO COM GROQ E JSON
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

# ==========================================
# 3. PROMPT ESTRATÉGICO (COM REGRA DE TAÇA)
# ==========================================
SYSTEM_PROMPT = """
Você é o Sommelier Virtual nas Alturas. 
Seja educado e objetivo. NUNCA invente vinhos, safras ou preços.

ESTRATÉGIA DE BUSCA:
1. Se o cliente pedir "taça" ou "por taça", use o parâmetro `volume_ml=187`.
2. Se o cliente pedir um estilo (ex: "tinto suave", "frutado"), use `termo_busca`.
3. Se a primeira busca retornar vazio, TENTE OUTRA BUSCA com sinônimos antes de responder.

FORMATO OBRIGATÓRIO DA RESPOSTA:
**Nome do Vinho**
Safra: X | País: Y | Uva: Z | Volume: W ml | Preço: R$ V
![Nome do Vinho](URL_DA_IMAGEM_AQUI)
*Resumo:* [Resumo de 1 frase baseado na descrição original]
"""

# ==========================================
# 4. FERRAMENTA DE BUSCA (AGORA COM VOLUME ML)
# ==========================================
def buscar_vinhos(termo_busca=None, tipo=None, pais=None, preco_max=None, uva=None, secao=None, volume_ml=None):
    resultados = []
    for v in carta["vinhos"]:
        if termo_busca:
            termo = normalizar_texto(termo_busca)
            texto_vinho = normalizar_texto(v.get("nome", "") + " " + v.get("descricao", "") + " " + v.get("secao_carta", ""))
            if termo not in texto_vinho: continue

        if tipo and v.get("tipo") != tipo: continue
        if pais and v.get("pais") != pais: continue
        if uva and not any(normalizar_texto(uva) in normalizar_texto(u) for u in v.get("uvas", [])): continue
        if secao and normalizar_texto(secao) not in normalizar_texto(v.get("secao_carta", "")): continue
        if preco_max and v.get("preco_brl") and v["preco_brl"] > preco_max: continue
        
        # Filtro específico para taça (187ml) ou outros volumes
        if volume_ml:
            vol_vinho = v.get("volume_ml", 750)
            if vol_vinho != volume_ml: continue
            
        resultados.append(v)
    
    if not resultados:
        return [{"status": "vazio", "mensagem": "Nenhum vinho encontrado."}]

    resumo_vinhos = []
    for v in resultados[:5]: # Aumentei para 5 opções
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
                "termo_busca": {"type": "string", "description": "Palavra-chave (ex: suave, doce, frutado)"},
                "tipo": {"type": "string", "enum": ["tinto", "branco", "rose", "espumante", "champagne"]},
                "secao": {"type": "string", "description": "Seção exata (ex: Doce, Démi-sec)"},
                "pais": {"type": "string"}, 
                "preco_max": {"type": "number"}, 
                "uva": {"type": "string"},
                "volume_ml": {"type": "number", "description": "Volume exato em ml. Use 187 para buscar vinhos por taça."}
            }
        }
    }
}]

def limpar_mensagens(historico):
    return [{"role": m["role"], **{k: v for k, v in m.items() if k != "role" and v is not None}} for m in historico]

# ==========================================
# 5. CABEÇALHO E HISTÓRICO VISUAL
# ==========================================
url_banner = "https://uploads.onecompiler.io/43v37pq3s/1793175043296/imagem_sommelier.webp"
st.image(url_banner, use_container_width=True)
st.markdown("<h1>WINE WORLD</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #888;'>Sommelier Virtual • Nas Alturas, Curitiba</p>", unsafe_allow_html=True)
st.divider()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

for msg in st.session_state.messages[1:]:
    if msg.get("role") in ["system", "tool"]: continue
    if msg.get("role") == "assistant" and msg.get("tool_calls"): continue
    
    current_avatar = "🧑‍🍳" if msg["role"] == "user" else "🍷"
    with st.chat_message(msg["role"], avatar=current_avatar):
        if msg.get("content"):
            st.markdown(msg["content"])

# ==========================================
# 6. CHAT E RESPOSTA (LOOP DE BUSCA)
# ==========================================
if prompt := st.chat_input("Qual vinho posso servir para você hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user", avatar="🧑‍🍳"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🍷"):
        
        # O modelo correto é o Llama 3.3! O Qwen quebra por limite de tokens.
        for tentativa in range(3): 
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile", 
                messages=limpar_mensagens(st.session_state.messages),
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
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
            else:
                texto_final = msg_dict.get("content", "Desculpe, não encontrei essa opção.")
                st.markdown(texto_final)
                break

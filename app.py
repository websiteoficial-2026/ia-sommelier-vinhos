import json
import streamlit as st
import unicodedata
from groq import Groq

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Sommelier Terrazza 40",
    page_icon="🍷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. CSS PERSONALIZADO (DESIGN PREMIUM)
# ==========================================
st.markdown("""
    <style>
    /* Importa fontes elegantes */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&family=Lato:wght@400;700&display=swap');
    
    /* Fundo escuro do app */
    .stApp {
        background-color: #1a1a1a;
        color: #e0e0e0;
        font-family: 'Lato', sans-serif;
    }
    
    /* Título principal em Dourado */
    h1 {
        font-family: 'Playfair Display', serif;
        color: #d4af37 !important;
        text-align: center;
        margin-bottom: 0px;
    }
    
    /* Esconde menus do Streamlit */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    
    /* Caixas de mensagem do chat */
    .stChatMessage {
        background-color: #2a2a2a;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
        border-left: 4px solid #d4af37;
    }
    
    /* Barra de digitar */
    .stChatInput {
        border-top: 1px solid #333;
        background-color: #1a1a1a;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. CONEXÃO COM GROQ E LEITURA DO JSON
# ==========================================
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

@st.cache_data
def carregar_carta():
    with open("carta_vinhos.json", "r", encoding="utf-8") as f:
        return json.load(f)

carta = carregar_carta()

# ==========================================
# 4. FUNÇÃO PARA LIMPAR ACENTOS E HÍFENS
# ==========================================
def normalizar_texto(texto):
    if not texto: return ""
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.lower().replace("-", " ").strip()

# ==========================================
# 5. PROMPT DO SOMMELIER (REGRAS ATUALIZADAS)
# ==========================================
SYSTEM_PROMPT = """
Você é o Sommelier Virtual do Terrazza 40 (Curitiba). Seja educado, elegante e objetivo.

REGRA DE OURO 1 (SILÊNCIO): NUNCA escreva seus pensamentos, dúvidas ou raciocínios no chat. Apenas chame a ferramenta e responda ao cliente. Se não achar, diga "Não encontrei, mas posso te oferecer...".

REGRA DE OURO 2 (BUSCA CORRETA): 
- Se o cliente pedir "vinho doce", "sobremesa" ou similar, use a ferramenta `buscar_vinhos` passando o parâmetro `secao="Doce"`.
- Se o cliente pedir um tipo específico de uva, país ou preço, use os parâmetros correspondentes.
- NUNCA invente vinhos, safras ou preços.
- Recomende no máximo 3 vinhos. Informe: Nome, Safra, País, Uva e Preço.

REGRA DE RESUMO: Use o campo "descricao" retornado pela ferramenta para criar um resumo curto (máximo 2 frases), destacando o sabor.

FORMATO OBRIGATÓRIO PARA CADA VINHO:
**Nome do Vinho**
Safra: X | País: Y | Uva: Z | Volume: W ml | Preço: R$ V
![Nome do Vinho](URL_DA_IMAGEM_AQUI)
*Resumo:* [Seu resumo]
"""

# ==========================================
# 6. FERRAMENTA DE BUSCA (FILTROS DO JSON)
# ==========================================
def buscar_vinhos(nome=None, tipo=None, pais=None, preco_max=None, uva=None, secao=None):
    resultados = []
    for v in carta["vinhos"]:
        # Filtra por nome
        if nome and normalizar_texto(nome) not in normalizar_texto(v.get("nome", "")): 
            continue
        # Filtra por seção (Doce, Brut, etc)
        if secao and normalizar_texto(secao) not in normalizar_texto(v.get("secao_carta", "")): 
            continue
        if tipo and v.get("tipo") != tipo: 
            continue
        if pais and v.get("pais") != pais: 
            continue
        if uva and not any(normalizar_texto(uva) in normalizar_texto(u) for u in v.get("uvas", [])): 
            continue
        if preco_max and v.get("preco_brl") and v["preco_brl"] > preco_max: 
            continue
        
        resultados.append(v)
    
    if not resultados:
        return [{"status": "vazio", "mensagem": "Nenhum vinho encontrado."}]

    resumo_vinhos = []
    for v in resultados[:3]: # Traz no máximo 3 vinhos
        resumo_vinhos.append({
            "nome": v["nome"], 
            "safra": v["safra"], 
            "pais": v["pais"],
            "uvas": v["uvas"], 
            "volume_ml": v.get("volume_ml", 750),
            "preco_brl": v["preco_brl"], 
            "imagem_url": v.get("imagem_url"),
            "descricao": v.get("descricao", "") # Envia a descrição para a IA resumir
        })
    return resumo_vinhos

# ==========================================
# 7. CONFIGURAÇÃO DA FERRAMENTA (TOOLS)
# ==========================================
tools = [{
    "type": "function",
    "function": {
        "name": "buscar_vinhos",
        "description": "Busca vinhos na carta do restaurante",
        "parameters": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome ou marca do vinho"},
                "secao": {"type": "string", "description": "Seção da carta (ex: Doce, Démi-sec, Nature, Brut)"},
                "tipo": {"type": "string", "enum": ["tinto", "branco", "rose", "espumante", "champagne"]},
                "pais": {"type": "string"}, 
                "preco_max": {"type": "number"}, 
                "uva": {"type": "string"}
            }
        }
    }
}]

# ==========================================
# 8. FUNÇÃO PARA LIMPAR O HISTÓRICO DE MENSAGENS
# ==========================================
def limpar_mensagens(historico):
    return [{"role": m["role"], **{k: v for k, v in m.items() if k != "role" and v is not None}} for m in historico]

# ==========================================
# 9. CABEÇALHO VISUAL DO APP
# ==========================================
url_banner = "https://images.unsplash.com/photo-1506377247377-2a5b3b417ebb?q=80&w=1000&auto=format&fit=crop"
st.image(url_banner, use_container_width=True)
st.markdown("<h1>Terrazza 40</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #888;'>Sommelier Virtual • Bigorrilho, Curitiba</p>", unsafe_allow_html=True)
st.divider()

# ==========================================
# 10. HISTÓRICO DO CHAT NA TELA
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

for msg in st.session_state.messages[1:]:
    if msg.get("role") in ["system", "tool"]: 
        continue
    if msg.get("role") == "assistant" and msg.get("tool_calls"): 
        continue
    
    current_avatar = "🧑‍🍳" if msg["role"] == "user" else "🍷"
    
    with st.chat_message(msg["role"], avatar=current_avatar):
        if msg.get("content"):
            st.markdown(msg["content"])

# ==========================================
# 11. INPUT DO USUÁRIO E RESPOSTA DA IA
# ==========================================
if prompt := st.chat_input("Olá! Qual vinho posso servir para você hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user", avatar="🧑‍🍳"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🍷"):
        # Primeira chamada: IA decide se precisa buscar na carta
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
        
        # Se a IA decidiu buscar na ferramenta
        if msg_dict.get("tool_calls"):
            for tool_call in msg_dict["tool_calls"]:
                args = json.loads(tool_call["function"]["arguments"])
                vinhos_encontrados = buscar_vinhos(**args)
                
                # Salva o resultado da busca no histórico
                st.session_state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": "buscar_vinhos",
                    "content": json.dumps(vinhos_encontrados, ensure_ascii=False)
                })
            
            # Segunda chamada: IA lê o resultado e escreve a resposta final
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
            
            # Exibe a resposta na tela
            st.markdown(texto_final)
        else:
            # Se a IA apenas conversou (não precisou buscar)
            st.markdown(msg.content)

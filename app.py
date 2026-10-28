import json
import streamlit as st
import unicodedata
from groq import Groq

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E DESIGN
# ==========================================
st.set_page_config(page_title="Sommelier Terrazza 40", page_icon="🍷", layout="centered")

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
# 3. PROMPT DIRETO E OBJETIVO
# ==========================================
SYSTEM_PROMPT = """
Você é o Sommelier Virtual do Terrazza 40. 
Seja EXTREMAMENTE objetivo, profissional e direto. NÃO faça rodeios, não faça perguntas de volta a menos que seja estritamente necessário. Não escreva seus pensamentos.

REGRA DE OURO: NUNCA invente vinhos, safras ou preços. Use APENAS os dados retornados pela ferramenta `buscar_vinhos`.
Se a ferramenta retornar vazio, diga apenas: "Não temos essa opção na carta no momento."

INSTRUÇÃO DE BUSCA:
- Se o cliente pedir "tinto suave", "vinho suave", ou "doce", use o parâmetro `termo_busca="suave"` ou `termo_busca="doce"`.
- Se o cliente pedir por um tipo, use `tipo="tinto"`, `tipo="branco"`, etc.
- Recomende no máximo 3 vinhos. Informe: Nome, Safra, País, Uva e Preço.

FORMATO OBRIGATÓRIO DA RESPOSTA:
**Nome do Vinho**
Safra: X | País: Y | Uva: Z | Volume: W ml | Preço: R$ V
![Nome do Vinho](URL_DA_IMAGEM_AQUI)
*Resumo:* [Resumo de 1 frase baseado na descrição original]
"""

# ==========================================
# 4. FERRAMENTA DE BUSCA ATUALIZADA
# ==========================================
def buscar_vinhos(termo_busca=None, tipo=None, pais=None, preco_max=None, uva=None, secao=None):
    resultados = []
    for v in carta["vinhos"]:
        # Busca geral (verifica se a palavra está no nome, descrição ou seção)
        if termo_busca:
            termo = normalizar_texto(termo_busca)
            texto_vinho = normalizar_texto(v.get("nome", "") + " " + v.get("descricao", "") + " " + v.get("secao_carta", ""))
            if termo not in texto_vinho:
                continue

        if tipo and v.get("tipo") != tipo: continue
        if pais and v.get("pais") != pais: continue
        if uva and not any(normalizar_texto(uva) in normalizar_texto(u) for u in v.get("uvas", [])): continue
        if secao and normalizar_texto(secao) not in normalizar_texto(v.get("secao_carta", "")): continue
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
                "termo_busca": {"type": "string", "description": "Palavra-chave para buscar no nome, descrição ou seção (ex: suave, doce, frutado)"},
                "tipo": {"type": "string", "enum": ["tinto", "branco", "rose", "espumante", "champagne"]},
                "secao": {"type": "string", "description": "Seção exata da carta (ex: Doce, Démi-sec)"},
                "pais": {"type": "string"}, "preco_max": {"type": "number"}, "uva": {"type": "string"}
            }
        }
    }
}]

def limpar_mensagens(historico):
    return [{"role": m["role"], **{k: v for k, v in m.items() if k != "role" and v is not None}} for m in historico]

# ==========================================
# 5. CABEÇALHO E HISTÓRICO
# ==========================================
url_banner = "https://images.unsplash.com/photo-1506377247377-2a5b3b417ebb?q=80&w=1000&auto=format&fit=crop"
st.image(url_banner, use_container_width=True)
st.markdown("<h1>Terrazza 40</h1>", unsafe_allow_html=True)
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
# 6. CHAT E RESPOSTA
# ==========================================
if prompt := st.chat_input("Qual vinho posso servir para você hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user", avatar="🧑‍🍳"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🍷"):
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=limpar_mensagens(st.session_state.messages),
            tools=tools,
            tool_choice="auto",
            temperature=0.0, # Temperatura 0 impede que ele invente!
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
                temperature=0.0, # Temperatura 0 aqui também
                max_tokens=600
            )
            final_msg = response2.choices[0].message
            final_msg_dict = final_msg.model_dump(exclude_none=True)
            
            texto_final = final_msg.content if final_msg.content else "Desculpe, não encontrei essa opção."
            final_msg_dict["content"] = texto_final
            st.session_state.messages.append(final_msg_dict)
            
            st.markdown(texto_final)
        else:
            st.markdown(msg.content)

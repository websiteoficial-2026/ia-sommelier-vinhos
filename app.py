import json
import streamlit as st
from groq import Groq

# ==========================================
# CONFIGURAÇÕES (GROQ)
# ==========================================
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

@st.cache_data
def carregar_carta():
    with open("carta_vinhos.json", "r", encoding="utf-8") as f:
        return json.load(f)

carta = carregar_carta()

# ==========================================
# PROMPT DO SOMMELIER (ADICIONADO O VOLUME)
# ==========================================
SYSTEM_PROMPT = """
Você é o Sommelier Virtual do Terrazza 40 (Curitiba).
Seja simpático, direto e objetivo.
Sempre que o cliente pedir uma sugestão, use a ferramenta `buscar_vinhos`.
Se a ferramenta retornar uma lista vazia ou um aviso de que não há vinhos, avise o cliente educadamente e ofereça uma alternativa (ex: outro tipo de vinho).
Recomende no máximo 3 vinhos. Informe: Nome, Safra, País, Uva e Preço.

FORMATO OBRIGATÓRIO PARA CADA VINHO RECOMENDADO:
**Nome do Vinho**
Safra: X | País: Y | Uva: Z | Volume: W ml | Preço: R$ V
![Nome do Vinho](URL_DA_IMAGEM_AQUI)
Breve descrição ou motivo da sugestão.

(Substitua URL_DA_IMAGEM_AQUI pelo link contido em "imagem_url" e W pelo valor de "volume_ml" que a ferramenta retornar).
Se a ferramenta não retornar nenhum vinho, avise o cliente educadamente.
"""

# ==========================================
# FERRAMENTA DE BUSCA (ENVIANDO O VOLUME PARA A IA)
# ==========================================
def buscar_vinhos(tipo=None, pais=None, preco_max=None, uva=None):
    resultados = []
    for v in carta["vinhos"]:
        if tipo and v.get("tipo") != tipo: continue
        if pais and v.get("pais") != pais: continue
        if uva and not any(uva.lower() in u.lower() for u in v.get("uvas", [])): continue
        if preco_max and v.get("preco_brl") and v["preco_brl"] > preco_max: continue
        resultados.append(v)
    
    if not resultados:
        return [{"status": "vazio", "mensagem": "Nenhum vinho encontrado."}]

    resumo_vinhos = []
    for v in resultados[:3]:
        resumo_vinhos.append({
            "nome": v["nome"],
            "safra": v["safra"],
            "pais": v["pais"],
            "uvas": v["uvas"],
            "volume_ml": v.get("volume_ml", 750), # 🚨 AQUI: Enviando o volume
            "preco_brl": v["preco_brl"],
            "imagem_url": v.get("imagem_url")
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
                "tipo": {"type": "string", "enum": ["tinto", "branco", "rose", "espumante", "champagne"]},
                "pais": {"type": "string"},
                "preco_max": {"type": "number"},
                "uva": {"type": "string"}
            }
        }
    }
}]

def limpar_mensagens(historico):
    msgs_limpas = []
    for m in historico:
        msg_limpa = {"role": m["role"]}
        if "content" in m and m["content"]: msg_limpa["content"] = m["content"]
        if "tool_calls" in m: msg_limpa["tool_calls"] = m["tool_calls"]
        if "tool_call_id" in m: msg_limpa["tool_call_id"] = m["tool_call_id"]
        if "name" in m: msg_limpa["name"] = m["name"]
        msgs_limpas.append(msg_limpa)
    return msgs_limpas

# ==========================================
# INTERFACE STREAMLIT
# ==========================================
st.title("🍷 Sommelier Virtual - Terrazza 40")
st.write("Olá! Sou seu sommelier pessoal. Qual tipo de vinho você procura hoje?")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

for msg in st.session_state.messages[1:]:
    if msg.get("role") in ["system", "tool"]:
        continue
    if msg.get("role") == "assistant" and msg.get("tool_calls"):
        continue
        
    with st.chat_message(msg["role"]):
        if msg.get("content"):
            st.markdown(msg["content"])

if prompt := st.chat_input("Ex: Quero um tinto argentino até R$ 150"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
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
                model="llama-3.3-70b-versatile",
                messages=limpar_mensagens(st.session_state.messages),
                tools=tools,
                max_tokens=600
            )
            final_msg = response2.choices[0].message
            final_msg_dict = final_msg.model_dump(exclude_none=True)
            
            texto_final = final_msg.content if final_msg.content else "Desculpe, não consegui formular uma resposta."
            
            final_msg_dict["content"] = texto_final
            st.session_state.messages.append(final_msg_dict)
            
            st.markdown(texto_final)
        else:
            st.markdown(msg.content)

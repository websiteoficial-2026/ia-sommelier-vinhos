import json
import streamlit as st
from groq import Groq

client = Groq(api_key=st.secrets["GROQ_API_KEY"])

@st.cache_data
def carregar_carta():
    with open("carta_vinhos.json", "r", encoding="utf-8") as f:
        return json.load(f)

carta = carregar_carta()

SYSTEM_PROMPT = """
Você é o Sommelier Virtual do Terrazza 40 (Curitiba).
Seja simpático, direto e objetivo.
Sempre que o cliente pedir uma sugestão, use a ferramenta `buscar_vinhos`.
Se a ferramenta retornar uma lista vazia ou um aviso de que não há vinhos, avise o cliente educadamente e ofereça uma alternativa (ex: outro tipo de vinho).
Recomende no máximo 3 vinhos. Informe: Nome, Safra, País, Uva e Preço.

FORMATO OBRIGATÓRIO DA RESPOSTA:
Para cada vinho recomendado, use o seguinte formato:
**Nome do Vinho**
Safra: X | País: Y | Uva: Z | Preço: R$ W
![Nome do Vinho](URL_DA_IMAGEM_AQUI)
Breve descrição ou motivo da sugestão.
"""

def buscar_vinhos(tipo=None, pais=None, preco_max=None, uva=None):
    resultados = []
    for v in carta["vinhos"]:
        if tipo and v.get("tipo") != tipo: continue
        if pais and v.get("pais") != pais: continue
        if uva and not any(uva.lower() in u.lower() for u in v.get("uvas", [])): continue
        if preco_max and v.get("preco_brl") and v["preco_brl"] > preco_max: continue
        resultados.append(v)
    
    # 🚨 SE NÃO ACHAR NADA, AVISA A IA
    if not resultados:
        return [{"status": "vazio", "mensagem": "Nenhum vinho encontrado com esses filtros."}]

    resumo_vinhos = []
    for v in resultados[:3]:
        resumo_vinhos.append({
            "nome": v["nome"],
            "safra": v["safra"],
            "pais": v["pais"],
            "uvas": v["uvas"],
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

st.title("🍷 Sommelier Virtual - Terrazza 40")
st.write("Olá! Sou seu sommelier pessoal. Qual tipo de vinho você procura hoje?")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

for msg in st.session_state.messages[1:]:
    # 🚨 IGNORA MENSAGENS INTERNAS DO SISTEMA E DA FERRAMENTA
    if msg.get("role") in ["system", "tool"]:
        continue
        
    # Ignora as chamadas de função (tool_calls) feitas pelo assistente
    if msg.get("role") == "assistant" and msg.get("tool_calls"):
        continue
        
    with st.chat_message(msg["role"]):
        if msg.get("content"):
            st.markdown(msg["content"])
        if msg.get("imagem_url"):
            for img_url in msg["imagem_url"]:
                st.image(img_url, width=150)

if prompt := st.chat_input("Ex: Quero um tinto argentino até R$ 150"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
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
                max_tokens=500
            )
            final_msg = response2.choices[0].message
            final_msg_dict = final_msg.model_dump(exclude_none=True)
            
            # 🚨 SE A IA NÃO RESPONDER TEXTO, COLOCAMOS UMA MENSAGEM PADRÃO
            texto_final = final_msg.content if final_msg.content else "Desculpe, não consegui formular uma resposta. Pode tentar reformular a pergunta?"
            
            # Só adiciona imagens se houver vinhos válidos
            if vinhos_encontrados and "status" not in vinhos_encontrados[0]:
                final_msg_dict["imagem_url"] = [v["imagem_url"] for v in vinhos_encontrados if v.get("imagem_url")]
            
            final_msg_dict["content"] = texto_final
            st.session_state.messages.append(final_msg_dict)
            
            st.markdown(texto_final)
            
            # 🚨 APAGUE OU COMENTE ESTE BLOCO ABAIXO (O for das imagens)
            # if vinhos_encontrados and "status" not in vinhos_encontrados[0]:
            #     for v in vinhos_encontrados:
            #         if v.get("imagem_url"):
            #             st.image(v["imagem_url"], width=100, caption=v["nome"])
            
            else:
            st.markdown(msg.content)

import json
import streamlit as st
import unicodedata
import uuid
from groq import Groq
from supabase import create_client

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
# 2. CONEXÃO COM SUPABASE (MEMÓRIA)
# ==========================================
@st.cache_resource
def get_supabase_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase_client()

# ID do usuário persistido em ?uid=... na URL.
# Sobrevive a refresh e é bookmarkável. UUID não é dado pessoal.
if "uid" not in st.query_params:
    st.query_params["uid"] = str(uuid.uuid4())
USER_ID = st.query_params["uid"]


def carregar_historico(user_id: str, limite: int = 20):
    """Traz as últimas mensagens do usuário (ordem cronológica)."""
    try:
        res = (
            supabase.table("chat_history")
            .select("role, message")
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .limit(limite)
            .execute()
        )
        return [{"role": r["role"], "content": r["message"]} for r in res.data]
    except Exception as e:
        st.warning(f"Não foi possível carregar o histórico: {e}")
        return []


def salvar_mensagem(user_id: str, role: str, content: str):
    """Persiste uma mensagem. Ignora conteúdo vazio (ex: assistant com tool_calls)."""
    if not content:
        return
    try:
        supabase.table("chat_history").insert({
            "user_id": user_id,
            "role": role,
            "message": content,
        }).execute()
    except Exception as e:
        st.warning(f"Não foi possível salvar a mensagem: {e}")


def limpar_historico(user_id: str):
    try:
        supabase.table("chat_history").delete().eq("user_id", user_id).execute()
    except Exception as e:
        st.warning(f"Não foi possível limpar o histórico: {e}")


# ==========================================
# 3. CONEXÃO COM GROQ E JSON
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
# 4. PROMPT ESTRATÉGICO (COM REGRA DE TAÇA)
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
# 5. FERRAMENTA DE BUSCA
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

        if volume_ml:
            vol_vinho = v.get("volume_ml", 750)
            if vol_vinho != volume_ml: continue

        resultados.append(v)

    if not resultados:
        return [{"status": "vazio", "mensagem": "Nenhum vinho encontrado."}]

    resumo_vinhos = []
    for v in resultados[:5]:
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
# 6. CABEÇALHO E HISTÓRICO VISUAL
# ==========================================
url_banner = "https://uploads.onecompiler.io/43v37pq3s/1793175043296/imagem_sommelier.webp"
st.image(url_banner, use_container_width=True)
st.markdown("<h1>WINE WORLD</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #888;'>Sommelier Virtual • Nas Alturas, Curitiba</p>", unsafe_allow_html=True)
st.divider()

# Sidebar: identidade + botão de reset
with st.sidebar:
    st.caption(f"Sessão: `{USER_ID[:8]}…`")
    if st.button("🧹 Nova conversa", use_container_width=True):
        limpar_historico(USER_ID)
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.rerun()

# Carrega histórico do Supabase na primeira execução da sessão
if "messages" not in st.session_state:
    historico_salvo = carregar_historico(USER_ID)
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}] + historico_salvo

# Renderiza histórico
for msg in st.session_state.messages[1:]:
    if msg.get("role") in ["system", "tool"]: continue
    if msg.get("role") == "assistant" and msg.get("tool_calls"): continue

    current_avatar = "🧑‍🍳" if msg["role"] == "user" else "🍷"
    with st.chat_message(msg["role"], avatar=current_avatar):
        if msg.get("content"):
            st.markdown(msg["content"])

# ==========================================
# 7. CHAT E RESPOSTA (LOOP DE BUSCA)
# ==========================================
if prompt := st.chat_input("Qual vinho posso servir para você hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    salvar_mensagem(USER_ID, "user", prompt)

    with st.chat_message("user", avatar="🧑‍🍳"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🍷"):
        for tentativa in range(3):
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=limpar_mensagens(st.session_state.messages),
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=1200,  # subido de 500 (estava truncando os cards de vinho)
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
                salvar_mensagem(USER_ID, "assistant", texto_final)
                break

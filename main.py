import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from anthropic import Anthropic
from supabase import create_client, Client
from keybert import KeyBERT

kw_model = KeyBERT()

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
PORT = int(os.environ.get('PORT', 8443))

WEBHOOK_URL = f"{os.getenv('RAILWAY_WEBHOOK_URL')}/"

anthropic = Anthropic(api_key=CLAUDE_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def extreure_paraules_clau(pregunta, top_n=5):
    keywords = kw_model.extract_keywords(
        pregunta,
        keyphrase_ngram_range=(1, 1),
        stop_words='spanish',
        top_n=top_n
    )
    return [kw[0] for kw in keywords]

def guardar_missatge(update: Update, context: CallbackContext):
    print("Entro a guardar missatges")
    if update.message and update.message.text:
        supabase.table("missatges").insert({
            "usuari": update.message.from_user.first_name,
            "text": update.message.text,
            "data": update.message.date.isoformat(),
            "grup_id": str(update.message.chat_id)
        }).execute()

def resumir(update: Update, context: CallbackContext):
    
    parts = update.message.text.strip().split()

    if len(parts) > 1:
        try:
            quantitat = int(parts[1])
        except ValueError:
            update.message.reply_text("El valor ha de ser un número. Exemple: /resumen 100")
            return
    else:
        update.message.reply_text("Escribe el número de mensajes después de /resumen, por eejemplo: /resumen 100")
        return

    grup_id = str(update.message.chat_id)
    resposta = supabase.table("missatges")\
        .select("usuari, text")\
        .order("data", desc=True)\
        .limit(quantitat)\
        .execute()

    missatges = resposta.data[::-1]

    if not missatges:
        update.message.reply_text("Encara no hi ha prou missatges guardats per fer un resum.")
        return

    bloc_text = "\n".join([f"{m['usuari']}: {m['text']}" for m in missatges])
    print(quantitat)
    print(resposta)
    print(bloc_text)
    update.message.reply_text("Generando resumen...")

    try:
        resposta_claude = anthropic.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[
                {"role": "user", "content": f"Haz un resumen claro y coherente en español de la siguiente conversación de un grupo:\n\n{bloc_text}"}
            ]
        )
        update.message.reply_text(resposta_claude.content[0].text.strip())
    except Exception as e:
        update.message.reply_text("Error resumiendo ")
        print(e)

def resposta(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    parts = text.split(maxsplit=1)

    if len(parts) > 1:
        pregunta = parts[1]
        quantitat = 1000
    else:
        update.message.reply_text("Escribe tu pregunta después de /respuesta, por ejemplo: /respuesta ¿Están ya las notas?")
        return
    
    grup_id = str(update.message.chat_id)
    resposta = supabase.table("missatges")\
        .select("usuari, text")\
        .order("data", desc=True)\
        .limit(quantitat)\
        .execute()

    missatges = resposta.data[::-1]

    if not missatges:
        update.message.reply_text("Encara no hi ha prou missatges guardats per fer un resum.")
        return

    # Obtenim paraules clau de la pregunta
    paraules_clau = extreure_paraules_clau(pregunta, top_n=5)

    # Busquem els missatges que continguin les paraules clau (amb context)
    def filtrar_per_paraules_clau_amb_context(paraules_clau, missatges, finestra=10):
        indexos_seleccionats = set()
        for i, m in enumerate(missatges):
            if any(paraula in m['text'].lower() for paraula in paraules_clau):
                inici = max(0, i - finestra)
                final = min(len(missatges), i + finestra + 1)
                indexos_seleccionats.update(range(inici, final))
        return [missatges[i] for i in sorted(indexos_seleccionats)]

    missatges_relevants = filtrar_per_paraules_clau_amb_context(paraules_clau, missatges)

    bloc_text = "\n".join([f"{m['usuari']}: {m['text']}" for m in missatges_relevants])
    
    print(quantitat)
    print(resposta)
    print(bloc_text)
    update.message.reply_text("Buscando respuesta...")

    try:
        resposta_claude = anthropic.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[
                {"role": "user", "content": f"Busca la respuesta a la pregunta {pregunta} en la siguiente conversación:\n\n{bloc_text}. Si no la encuentras, dame una respuesta igualmente, pero recuérdame que la respuesta no está en la conversación."}
            ]
        )
        update.message.reply_text(resposta_claude.content[0].text.strip())
    except Exception as e:
        update.message.reply_text("Error resumint amb Claude ")
        print(e)

def missatge_general(update: Update, context: CallbackContext):
    text = update.message.text.strip()

    if text.startswith("/resumen"):
        resumir(update, context)

    elif text.startswith("/respuesta"):
        resposta(update, context)

    else:
        guardar_missatge(update, context) 

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & Filters.chat_type.groups, missatge_general))

    updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=WEBHOOK_URL + TOKEN
    )

    print("Bot funcionant amb webhook...")
    updater.idle()

if __name__ == '__main__':
    main()

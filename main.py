import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from anthropic import Anthropic
from supabase import create_client, Client

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
PORT = int(os.environ.get('PORT', 8443))  # Railway exposa aquest port

WEBHOOK_URL = f"{os.getenv('RAILWAY_WEBHOOK_URL')}/"  # El domini Railway, sense /bot...

anthropic = Anthropic(api_key=CLAUDE_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    print("Handler de /missmi activat")
    try:
        quantitat = int(context.args[0]) if context.args else 50
    except ValueError:
        update.message.reply_text("Has d'escriure un número després de /missmi, com ara: /missmi 100")
        return

    grup_id = str(update.message.chat_id)
    resposta = supabase.table("missatges")\
        .select("usuari, text")\
        .eq("grup_id", grup_id)\
        .order("data", desc=True)\
        .limit(quantitat)\
        .execute()

    missatges = resposta.data[::-1]

    if not missatges:
        update.message.reply_text("Encara no hi ha prou missatges guardats per fer un resum.")
        return

    bloc_text = "\n".join([f"{m['usuari']}: {m['text']}" for m in missatges])
    update.message.reply_text("Generant resum amb Claude...")

    try:
        resposta_claude = anthropic.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[
                {"role": "user", "content": f"Haz un resumen claro de la siguiente conversación de un grupo de Telegram, pero de modo informal:\n\n{bloc_text}"}
            ]
        )
        update.message.reply_text(resposta_claude.content[0].text.strip())
    except Exception as e:
        update.message.reply_text("Error resumint amb Claude 😢")
        print(e)

def debug(update: Update, context: CallbackContext):
    print("DEBUG - Missatge rebut:", update.message.text)
    print("Entities:", update.message.entities)

def missatge_general(update: Update, context: CallbackContext):
    text = update.message.text.strip()

    if text.startswith("/resumen"):
        print("Interceptat resumen manualment")
        resumir(update, context)
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

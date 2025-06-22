import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from anthropic import Anthropic
from supabase import create_client, Client

# Carrega variables d'entorn
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Inicialitza clients
anthropic = Anthropic(api_key=CLAUDE_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Funció per guardar missatges a Supabase
def guardar_missatge(update: Update, context: CallbackContext):
    if update.message and update.message.text:
        supabase.table("missatges").insert({
            "usuari": update.message.from_user.first_name,
            "text": update.message.text,
            "data": datetime.utcfromtimestamp(update.message.date.timestamp()),
            "grup_id": str(update.message.chat_id)
        }).execute()

# Comanda /missmi per resumir els últims X missatges
def resumir(update: Update, context: CallbackContext):
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

    missatges = resposta.data[::-1]  # invertir per tenir-los en ordre cronològic

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
                {"role": "user", "content": f"Fes un resum clar i coherent de la següent conversa de grup:\n\n{bloc_text}"}
            ]
        )
        update.message.reply_text(resposta_claude.content[0].text.strip())
    except Exception as e:
        update.message.reply_text("Error resumint amb Claude 😢")
        print(e)

# Inicialització del bot
def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & Filters.group, guardar_missatge))
    dp.add_handler(CommandHandler("missmi", resumir))

    updater.start_polling()
    print("Bot en marxa...")
    updater.idle()

if __name__ == "__main__":
    main()

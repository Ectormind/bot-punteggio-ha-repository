# -*- coding: utf-8 -*-
import datetime
import asyncio
import threading
import logging
import sqlite3
import os  # ⬅️ AGGIUNTO: Modulo per leggere le variabili d'ambiente
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from waitress import serve

# ✅ Logging
logging.basicConfig(level=logging.INFO)

# ✅ Configurazione bot
# ⬅️ MODIFICATO: Legge il Token dal campo di configurazione dell'Add-on
TOKEN = os.environ.get('TELEGRAM_TOKEN', 'TOKEN_NON_IMPOSTATO') 
# ⬅️ MODIFICATO: Legge la porta dal campo di configurazione dell'Add-on, usa 8081 come default
WEBHOOK_PORT = int(os.environ.get('PORT', 8081))

DB_PATH = "/data/scores_nuovo.db"
# ⚠️ ATTENZIONE: Se hai più ID autorizzati, aggiorna qui l'elenco come necessario!
ID_UTENTI_AUTORIZZATI = [28292161] 

# ✅ Inizializzazione
app = Flask(__name__)
# Verifica se il token è valido prima di costruire l'applicazione
if TOKEN == 'TOKEN_NON_IMPOSTATO' or TOKEN is None:
    logging.error("❌ ERRORE: TELEGRAM_TOKEN non impostato nella configurazione dell'Add-on.")
    exit(1)

application = Application.builder().token(TOKEN).build()

# ✅ Controllo presenza utente autorizzato nel gruppo
async def chat_autorizzata(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = update.message.chat_id
    for user_id in ID_UTENTI_AUTORIZZATI:
        try:
            membro = await context.bot.get_chat_member(chat_id, user_id)
            if membro.status in ['member', 'administrator', 'creator']:
                return True  # almeno uno degli autorizzati è presente
        except Exception as e:
            logging.warning(f"Controllo presenza fallito per user {user_id}: {e}")
            continue

    # Nessuno degli autorizzati è presente
    try:
        await context.bot.send_message(
            chat_id=ID_UTENTI_AUTORIZZATI[0],  # il tuo ID principale per ricevere gli alert
            text=f"❌ Il bot è stato usato da una chat **non autorizzata**.\nChat ID: `{chat_id}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.warning(f"Errore nell'invio dell'avviso: {e}")
    return False

# ✅ Mappa parole/punti
parole_punteggio = {
    "#bilancia": 10,
    "#colazioneequilibrata": 5,
    "#collagene": 5,
    "#bombetta": 5,
    "#ricostruttore": 5,
    "#idratazionespecifica": 8,
    "#phytocomplete": 5,
    "#pranzobilanciato": 10,
    "#cenabilanciata": 10,
    "#spuntino1": 8,
    "#spuntino2": 8,
    "#integrazione1": 5,
    "#integrazione2": 5,
    "#workout": 15,
    "#pastosostitutivo": 15,
    "#detox": 15,
    "#sensazioni": 5,
    "#fotoiniziale": 10,
    "#fotofinale": 10
}

def connessione_db():
    return sqlite3.connect(DB_PATH)

def crea_tabella_classifica():
    with connessione_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS classifica (
                chat_id INTEGER,
                utente TEXT,
                punti INTEGER NOT NULL,
                PRIMARY KEY (chat_id, utente)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS parole_usate (
                chat_id INTEGER,
                utente TEXT,
                parola TEXT,
                data TEXT,
                PRIMARY KEY (chat_id, utente, parola, data)
            );
        """)
        conn.commit()
        logging.info("📋 Tabelle create/aggiornate.")

def carica_classifica(chat_id):
    with connessione_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT utente, punti FROM classifica WHERE chat_id = ? ORDER BY punti DESC;", (chat_id,))
        return dict(cur.fetchall())

def aggiorna_punteggio(chat_id, utente, punti):
    with connessione_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO classifica (chat_id, utente, punti)
            VALUES (?, ?, COALESCE((SELECT punti FROM classifica WHERE chat_id = ? AND utente = ?) + ?, ?));
        """, (chat_id, utente, chat_id, utente, punti, punti))
        conn.commit()

def ha_gia_usato_parola(chat_id, utente, parola, data_attuale):
    with connessione_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM parole_usate
            WHERE chat_id = ? AND utente = ? AND parola = ? AND data = ?;
        """, (chat_id, utente, parola, data_attuale))
        return cur.fetchone()[0] > 0

def registra_parola_usata(chat_id, utente, parola, data_attuale):
    with connessione_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO parole_usate (chat_id, utente, parola, data)
            VALUES (?, ?, ?, ?);
        """, (chat_id, utente, parola, data_attuale))
        conn.commit()

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await chat_autorizzata(update, context):
        return
    chat_id = update.message.chat_id
    with connessione_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM classifica WHERE chat_id = ?;", (chat_id,))
        cur.execute("DELETE FROM parole_usate WHERE chat_id = ?;", (chat_id,))
        conn.commit()
    await update.message.reply_text("Classifica e parole resettate per questa chat!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await chat_autorizzata(update, context):
        return
    await update.message.reply_text("Invia un hashtag per guadagnare punti!\nOgni hashtag vale solo una volta al giorno!")

async def classifica_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await chat_autorizzata(update, context):
        return

    chat_id = update.message.chat_id
    classifica = carica_classifica(chat_id)

    if not classifica:
        await update.message.reply_text("Classifica vuota!")
        return

    messaggio = "🏆 *Classifica attuale:*\n"
    for i, (utente, punti) in enumerate(classifica.items(), start=1):
        if i == 1:
            messaggio += f"🥇 1. {utente}: {punti} punti\n"
        elif i == 2:
            messaggio += f"🥈 2. {utente}: {punti} punti\n"
        elif i == 3:
            messaggio += f"🥉 3. {utente}: {punti} punti\n"
        else:
            messaggio += f"{i}. {utente}: {punti} punti\n"

    await update.message.reply_text(messaggio, parse_mode="Markdown")

async def gestisci_messaggi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await chat_autorizzata(update, context):
        return

    logging.info("📩 Ricevuto messaggio")

    chat_id = update.message.chat_id
    messaggio = update.message.text or update.message.caption
    if not messaggio:
        return

    utente = update.message.from_user.username or update.message.from_user.first_name
    if not utente:
        return

    data_attuale = datetime.datetime.now().strftime("%Y-%m-%d")
    hashtag_usati = [p for p in parole_punteggio if p in messaggio]

    if not hashtag_usati:
        return

    punti_totali = 0
    parole_assegnate = []
    parole_gia_usate = []

    for parola in hashtag_usati:
        if ha_gia_usato_parola(chat_id, utente, parola, data_attuale):
            parole_gia_usate.append(parola)
        else:
            punti = parole_punteggio[parola]
            punti_totali += punti
            parole_assegnate.append(parola)

    if parole_gia_usate:
        await update.message.reply_text(
            f"⚠️ {utente}, hai già usato oggi: {', '.join(parole_gia_usate)}"
        )

    if punti_totali > 0:
        aggiorna_punteggio(chat_id, utente, punti_totali)
        for parola in parole_assegnate:
            registra_parola_usata(chat_id, utente, parola, data_attuale)
        await update.message.reply_text(f"{utente} ha guadagnato {punti_totali} punti! 🎉")

@app.route("/webhook2", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data:
            logging.error("❌ Nessun JSON ricevuto!")
            return jsonify({"error": "Bad Request"}), 400

        update = Update.de_json(data, application.bot)
        logging.info(f"✅ Webhook update ricevuto: {update}")

        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        return jsonify({"status": "OK"}), 200

    except Exception as e:
        logging.error(f"Errore webhook: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

async def avvia_bot():
    await application.initialize()
    logging.info("✅ Bot Telegram inizializzato.")

def run_async_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == "__main__":
    logging.info("🚀 Avvio del bot...")
    crea_tabella_classifica()

    loop = asyncio.new_event_loop()
    threading.Thread(target=run_async_loop, daemon=True).start()
    asyncio.run_coroutine_threadsafe(avvia_bot(), loop).result()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("classifica", classifica_bot))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, gestisci_messaggi))

    # ⬅️ MODIFICATO: Serve l'applicazione sulla porta dinamica
    serve(app, host="0.0.0.0", port=WEBHOOK_PORT)
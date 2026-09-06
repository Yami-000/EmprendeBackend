import { Telegraf } from 'telegraf';
import axios from 'axios';
import dotenv from 'dotenv';
import { randomUUID } from 'node:crypto';

dotenv.config();

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const RAG_URL = process.env.RAG_URL || 'http://localhost:11400/chat';
const HISTORY_LIMIT = 6;

if (!BOT_TOKEN) {
  throw new Error('TELEGRAM_BOT_TOKEN no está definido en el entorno');
}

// Import diferido: src/models/index.js lee `db` desde config/db.js en el momento
// de su evaluación, por lo que debe cargarse recién después de connectDB().
let modelsPromise;
const getModels = () => {
  if (!modelsPromise) {
    modelsPromise = import('./models/index.js').then((m) => m.default);
  }
  return modelsPromise;
};

const findOrCreateUsuarioByTelegramId = async (Usuario, from) => {
  const telegramId = String(from.id);
  let usuario = await Usuario.findOne({ where: { telegramId } });
  if (!usuario) {
    usuario = await Usuario.create({
      telegramId,
      nombre: (from.first_name || from.username || 'Emprendedor').slice(0, 50),
      correoElectronico: `telegram-${telegramId}@telegram.local`,
      contrasena: randomUUID(),
    });
  }
  return usuario;
};

const findOrCreateChatForUsuario = async (Chat, usuarioID) => {
  let chat = await Chat.findOne({ where: { usuarioID }, order: [['createdAt', 'DESC']] });
  if (!chat) {
    chat = await Chat.create({ usuarioID, nombre: 'Telegram' });
  }
  return chat;
};

export async function startBot() {
  const bot = new Telegraf(BOT_TOKEN);

  bot.start(async (ctx) => {
    const name = ctx.from?.first_name || 'emprendedor';
    await ctx.reply(
      `Hola ${name}. Soy un asistente experto en formalización de PYMEs y trámites del SII. ` +
        'Puedo ayudarte a buscar normativa, pasos y documentación. Envía tu consulta cuando quieras.'
    );
  });

  bot.on('text', async (ctx) => {
    const query = ctx.message.text;
    let statusMessage;
    let chatRecord;
    let Mensaje;
    let history = [];
    try {
      statusMessage = await ctx.reply('⏳ Consultando normativas del SII...');
      const chatId = statusMessage.chat.id;
      const messageId = statusMessage.message_id;

      // La memoria de conversación es "best effort": si la DB falla, seguimos
      // sin historial en vez de abortar la consulta al RAG.
      try {
        const { Usuario, Chat, Mensaje: MensajeModel } = await getModels();
        Mensaje = MensajeModel;

        const usuario = await findOrCreateUsuarioByTelegramId(Usuario, ctx.from);
        chatRecord = await findOrCreateChatForUsuario(Chat, usuario.id);

        const previousMessages = await Mensaje.findAll({
          where: { chatID: chatRecord.id },
          order: [['createdAt', 'DESC']],
          limit: HISTORY_LIMIT,
        });
        history = previousMessages.reverse().map((m) => ({ role: m.role, content: m.content }));

        await Mensaje.create({ chatID: chatRecord.id, usuarioID: usuario.id, role: 'user', content: query });
      } catch (dbErr) {
        console.error('Error de DB al preparar la memoria de conversación:', dbErr?.message || dbErr);
        chatRecord = undefined;
        Mensaje = undefined;
        history = [];
      }

      let resp;
      try {
        resp = await axios.request({
          method: 'POST',
          url: RAG_URL,
          data: { query, history },
          responseType: 'stream',
          timeout: 60000,
        });
      } catch (reqErr) {
        console.error('Error contacting RAG service:', reqErr?.message || reqErr);
        try {
          await ctx.telegram.editMessageText(chatId, messageId, undefined, '❗ El servicio de búsqueda no respondió. Intenta más tarde.');
        } catch (e) {}
        return;
      }

      const stream = resp.data; // Node.js readable stream

      let buffer = '';
      let lastEdit = Date.now();
      const EDIT_INTERVAL_MS = 1500;
      const CHAR_THRESHOLD = 50;

      const doEdit = async () => {
        try {
          const text = buffer || '⏳ Consultando normativas del SII...';
          await ctx.telegram.editMessageText(chatId, messageId, undefined, text);
        } catch (err) {
          // ignore edit errors (rate limits, message deleted, etc.)
        }
      };

      // periodic flush in case small chunks
      const interval = setInterval(async () => {
        if (buffer) await doEdit();
      }, EDIT_INTERVAL_MS);

      stream.on('data', (chunk) => {
        try {
          const str = chunk.toString('utf8');
          // FastAPI puede enviar líneas SSE ("data: ...") o NDJSON crudo de Ollama
          const parts = str.split(/\r?\n/).filter(Boolean);
          for (const p of parts) {
            const payload = p.startsWith('data:') ? p.replace(/^data:\s*/, '') : p;
            if (payload.trim() === '[DONE]') {
              continue;
            }
            try {
              const parsed = JSON.parse(payload);
              if (parsed?.message?.content) {
                buffer += parsed.message.content;
              }
            } catch (e) {
              buffer += payload;
            }
          }

          // immediate edit if buffer large enough
          if (buffer.length >= CHAR_THRESHOLD && Date.now() - lastEdit > 500) {
            lastEdit = Date.now();
            void doEdit();
          }
        } catch (e) {
          // ignore parsing errors
        }
      });

      stream.on('end', async () => {
        clearInterval(interval);
        try {
          if (buffer) {
            await doEdit();
          } else {
            await ctx.telegram.editMessageText(chatId, messageId, undefined, 'No se obtuvo respuesta del servicio.');
          }
        } catch (e) {}

        if (buffer && Mensaje && chatRecord) {
          try {
            await Mensaje.create({ chatID: chatRecord.id, usuarioID: null, role: 'assistant', content: buffer });
          } catch (e) {
            console.error('No se pudo guardar la respuesta del asistente:', e?.message || e);
          }
        }
      });

      stream.on('error', async (err) => {
        clearInterval(interval);
        try {
          await ctx.telegram.editMessageText(chatId, messageId, undefined, '❗ Error consultando el servicio. Intenta más tarde.');
        } catch (e) {}
      });
    } catch (err) {
      console.error('Error en bot text handler:', err?.message || err);
      try {
        if (statusMessage) {
          await ctx.telegram.editMessageText(statusMessage.chat.id, statusMessage.message_id, undefined, '❗ No fue posible consultar el servicio. Intenta más tarde.');
        } else {
          await ctx.reply('❗ No fue posible consultar el servicio. Intenta más tarde.');
        }
      } catch (e) {}
    }
  });

  try {
    await bot.launch();
    console.log('Telegram bot lanzado');
  } catch (err) {
    console.error('No se pudo lanzar el bot de Telegram:', err?.message || err);
    console.warn('Continuando sin bot. Revisa que no haya otra instancia del bot en ejecución.');
    return null;
  }

  process.once('SIGINT', () => bot.stop('SIGINT'));
  process.once('SIGTERM', () => bot.stop('SIGTERM'));

  return bot;
}

export default startBot;

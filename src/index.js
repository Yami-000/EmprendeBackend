import app from './server.js';
import { connectDB } from './config/db.js';
import dotenv from 'dotenv';
import { startBot } from './bot.js';

dotenv.config();

const PORT = process.env.PORT || 4000;

const start = async () => {
  try {
    await connectDB(); // Conexión a la DB

    app.listen(PORT, () => {
      console.log(`Servidor HTTP corriendo en http://localhost:${PORT}/health`);
    });

    // Lanzar bot de Telegram (no bloquear el arranque si falla)
    try {
      await startBot();
    } catch (err) {
      console.error('Error iniciando bot de Telegram:', err?.message || err);
      console.warn('Continuando sin bot.');
    }
  } catch (error) {
    console.error('Error al iniciar el servidor:', error.message);
    process.exit(1);
  }
};

start();


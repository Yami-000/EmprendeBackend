import app from './server.js';
import { connectDB } from './config/db.js';
import dotenv from 'dotenv'

dotenv.config();

const PORT = process.env.PORT || 4000;

const start = async () => {
  try {
    await connectDB(); // Conexión a la DB
    app.listen(PORT, () => {
      console.log(`Servidor corriendo en http://localhost:${PORT}/graphql`);
    });
  } catch (error) {
    console.error('Error al iniciar el servidor:', error.message);
    process.exit(1);
  }
};

start();


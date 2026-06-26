import { Sequelize } from "sequelize";
import dotenv from 'dotenv';

dotenv.config();

export let db = null;

const createPostgres = () => new Sequelize(
  process.env.DB_NAME,
  process.env.DB_USER,
  process.env.DB_PASSWORD,
  {
    host: process.env.DB_HOST,
    port: process.env.DB_PORT ? Number(process.env.DB_PORT) : 5432,
    dialect: 'postgres',
    logging: false,
    dialectOptions: {
      ssl: {
        require: true,
        rejectUnauthorized: false,
      },
    },
  }
);

export const connectDB = async () => {
  try {
    db = createPostgres();
    await db.authenticate();
    console.log('✅ Conexión a Supabase (Postgres) establecida correctamente.');
    await db.sync({ alter: true });
    console.log('Tablas sincronizadas (alter:true)');
    return;
  } catch (error) {
    console.error('Error al conectar a Supabase (Postgres):', error.message);
    console.error('Detalles de conexión:', {
      host: process.env.DB_HOST,
      port: process.env.DB_PORT,
      database: process.env.DB_NAME,
      user: process.env.DB_USER,
    });

    if ((process.env.NODE_ENV || 'development') === 'development') {
      console.warn('Cayendo a SQLite en memoria como último recurso para desarrollo.');
      db = new Sequelize({ dialect: 'sqlite', storage: ':memory:', logging: false });
      try {
        await db.authenticate();
        console.log('Conexión a la base de datos (SQLite in-memory) establecida');
        await db.sync({ alter: true });
        console.log('Tablas sincronizadas en SQLite (alter:true)');
      } catch (e) {
        console.error('Error al inicializar SQLite fallback:', e.message);
      }
      return;
    }

    throw error;
  }
};

import { Sequelize } from "sequelize";
import dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';

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
      console.warn('Cayendo a SQLite en disco como fallback de desarrollo.');
      try {
        const dataDir = path.resolve(process.cwd(), 'data');
        if (!fs.existsSync(dataDir)) {
          fs.mkdirSync(dataDir, { recursive: true });
        }
        const devSqlitePath = path.join(dataDir, 'dev.sqlite');
        db = new Sequelize({ dialect: 'sqlite', storage: devSqlitePath, logging: false });
        await db.authenticate();
        console.log('Conexión a la base de datos (SQLite file) establecida en', devSqlitePath);
        await db.sync({ alter: true });
        console.log('Tablas sincronizadas en SQLite (alter:true)');
      } catch (e) {
        console.error('Error al inicializar SQLite fallback en disco:', e.message);
      }
      return;
    }

    throw error;
  }
};

import { Sequelize } from "sequelize";
import dotenv from 'dotenv';

dotenv.config();

export const db = new Sequelize(
  process.env.PGDATABASE || process.env.DB_NAME,
  process.env.PGUSER || process.env.DB_USER,
  process.env.PGPASSWORD || process.env.DB_PASSWORD,
  {
    host: process.env.PGHOST || process.env.DB_HOST,
    port: process.env.PGPORT || process.env.DB_PORT || 5432,
    dialect: 'postgres',
    logging: false,
    // dialectOptions: {
    //   ssl: process.env.NODE_ENV === 'production' ? {
    //     require: true,
    //     rejectUnauthorized: false,
    //   } : false,
    // },
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
    await db.authenticate();
    console.log('Conexión a la base de datos exitosa');
    await db.sync({ alter: true }); // alter | force
    console.log('Tablas sincronizadas (alter:true)');
  } catch (error) {
    console.error('Error al conectar a la base de datos:', error.message);
    process.exit(1);
  }
};

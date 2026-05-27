import fs from 'fs';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';  // Importar pathToFileURL
import { db } from '../config/db.js';

const models = {};

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const basename = path.basename(__filename);

// Cargar los modelos de forma dinamica
const files = fs.readdirSync(__dirname).filter(
  (file) => file !== basename && file.endsWith('.js')
);

for (const file of files) {
  // Convertir la ruta absoluta a URL file:// para import dinámico ESM
  const modelPath = pathToFileURL(path.join(__dirname, file)).href;
  
  const { default: defineModel } = await import(modelPath);
  const model = defineModel(db);
  models[model.name] = model;
}

// Configurar asociaciones
for (const modelName of Object.keys(models)) {
  if (models[modelName].associate) {
    models[modelName].associate(models);
  }
}

models.db = db;
export default models;

import admin from 'firebase-admin';
import { existsSync, readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, isAbsolute, join, resolve } from 'path';
import dotenv from 'dotenv';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const defaultServiceAccountPath = join(__dirname, '..', '..', 'credentials', 'emprende-73e05-firebase-adminsdk-fbsvc-dc2b367ca8.json');

const serviceAccountJson = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
const serviceAccountPathFromEnv = process.env.FIREBASE_SERVICE_ACCOUNT_PATH;

const buildAdminOptions = () => {
    if (serviceAccountJson) {
        const serviceAccount = JSON.parse(serviceAccountJson);

        return {
            credential: admin.credential.cert(serviceAccount),
            storageBucket: process.env.FIREBASE_STORAGE_BUCKET || `${serviceAccount.project_id}.appspot.com`,
        };
    }

    if (serviceAccountPathFromEnv) {
        const serviceAccountPath = isAbsolute(serviceAccountPathFromEnv)
            ? serviceAccountPathFromEnv
            : resolve(__dirname, serviceAccountPathFromEnv);
        if (!existsSync(serviceAccountPath)) {
            throw new Error(
                `La ruta FIREBASE_SERVICE_ACCOUNT_PATH está configurada, pero el archivo no existe: ${serviceAccountPath}. ` +
                'Coloca el JSON de Firebase Admin correcto en esa ubicación o ajusta la ruta en .env.'
            );
        }

        const serviceAccount = JSON.parse(readFileSync(serviceAccountPath, 'utf8'));
        console.log(`Firebase Admin cargado desde ${serviceAccountPath} (proyecto: ${serviceAccount.project_id})`);

        return {
            credential: admin.credential.cert(serviceAccount),
            storageBucket: process.env.FIREBASE_STORAGE_BUCKET || `${serviceAccount.project_id}.appspot.com`,
        };
    }

    if (existsSync(defaultServiceAccountPath)) {
        const serviceAccount = JSON.parse(readFileSync(defaultServiceAccountPath, 'utf8'));
        console.log(`Firebase Admin cargado desde ${defaultServiceAccountPath} (proyecto: ${serviceAccount.project_id})`);

        return {
            credential: admin.credential.cert(serviceAccount),
            storageBucket: process.env.FIREBASE_STORAGE_BUCKET || `${serviceAccount.project_id}.appspot.com`,
        };
    }

    console.warn('No se encontró ninguna credencial de Firebase Admin. Se usará Application Default Credentials.');

    return {
        credential: admin.credential.applicationDefault(),
        storageBucket: process.env.FIREBASE_STORAGE_BUCKET,
    };
};

if (!admin.apps.length) {
    admin.initializeApp(buildAdminOptions());
}

// Obtener referencia a Firestore
export const db = admin.firestore();

console.log('Firebase Admin inicializado correctamente');

export default admin;

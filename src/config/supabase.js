import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';

dotenv.config();

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseServiceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
const bucketName = process.env.SUPABASE_BUCKET_NAME || 'lookfin-attachments';

if (!supabaseUrl || !supabaseServiceRoleKey) {
    console.warn('Supabase no está configurado. Uploads de archivos no funcionarán.');
}

// Cliente de Supabase con credenciales de servidor (service role key)
// Esta clave es segura solo en el backend
const supabaseClient = supabaseUrl && supabaseServiceRoleKey
    ? createClient(supabaseUrl, supabaseServiceRoleKey)
    : null;

/**
 * Upload a file to Supabase Storage from the server
 * @param {Buffer} fileBuffer - The file buffer to upload
 * @param {string} fileName - The original file name
 * @param {string} chatID - The chat ID for organizing files
 * @returns {Promise<string|null>} The public URL of the uploaded file or null if failed
 */
export const uploadFileToSupabaseServer = async (fileBuffer, fileName, chatID) => {
    if (!supabaseClient) {
        throw new Error('Supabase no está configurado. Configura SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el .env del backend.');
    }

    if (!fileBuffer || !fileName) {
        throw new Error('File buffer and fileName are required');
    }

    // Generate a unique filename
    const timestamp = Date.now();
    const randomSuffix = Math.random().toString(36).substring(7);
    const fileExtension = fileName.split('.').pop();
    const uniqueFileName = `${chatID}/${timestamp}-${randomSuffix}.${fileExtension}`;

    try {
        const { data, error } = await supabaseClient.storage
            .from(bucketName)
            .upload(uniqueFileName, fileBuffer, {
                cacheControl: '3600',
                upsert: false,
            });

        if (error) {
            throw error;
        }

        // Get the public URL for the uploaded file
        const { data: publicUrlData } = supabaseClient.storage
            .from(bucketName)
            .getPublicUrl(data.path);

        return publicUrlData.publicUrl;
    } catch (error) {
        console.error('Error uploading file to Supabase:', error);
        throw new Error(`No se pudo subir el archivo: ${error.message}`);
    }
};

/**
 * Delete a file from Supabase Storage
 * @param {string} fileUrl - The public URL of the file to delete
 */
export const deleteFileFromSupabaseServer = async (fileUrl) => {
    if (!supabaseClient || !fileUrl) return;

    try {
        // Extract the file path from the public URL
        const urlParts = fileUrl.split(`/storage/v1/object/public/${bucketName}/`);
        if (urlParts.length < 2) {
            console.warn('Could not parse Supabase file URL:', fileUrl);
            return;
        }

        const filePath = decodeURIComponent(urlParts[1]);

        const { error } = await supabaseClient.storage
            .from(bucketName)
            .remove([filePath]);

        if (error) {
            console.warn('Error deleting file from Supabase:', error);
        }
    } catch (error) {
        console.warn('Error deleting file from Supabase:', error);
    }
};

export default supabaseClient;

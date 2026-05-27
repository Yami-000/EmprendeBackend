import models from '../models/index.js';
import validationSchemas from '../validations/index.js';
import {
    addMensajeToFirestore,
    updateMensajeFromFirestore,
    getMensajeFromFirestore,
    getMensajesByChatFromFirestore,
    getMensajesByUsuarioFromFirestore,
    deleteMensajeFromFirestore,
    deleteMensajesByChatFromFirestore
} from '../config/firestoreMensajes.js';
import {
    createUserWithEmailPassword,
    verifyIdToken,
    getUserByUID,
    deleteUserByUID
} from '../config/firebaseAuth.js';
import admin from '../config/firebaseAdmin.js';
import { Op } from 'sequelize';
import { uploadFileToSupabaseServer } from '../config/supabase.js';
import { createAgentOrchestrator } from '../agent/orchestrator.js';

const { Chat, Mensaje, Usuario } = models;
const { chatValidationSchema, mensajeValidationSchema, usuarioValidationSchema, updateUsuarioValidationSchema } = validationSchemas;
const MAX_UPLOAD_FILE_SIZE_BYTES = 8 * 1024 * 1024;

const extractStoragePathFromUrl = (url) => {
    if (!url || typeof url !== 'string') return null;
    if (!url.includes('/o/')) return null;
    try {
        const [, afterO] = url.split('/o/');
        const encodedPath = afterO.split('?')[0];
        if (!encodedPath) return null;
        return decodeURIComponent(encodedPath);
    } catch {
        return null;
    }
};

const deleteStorageObjectIfExists = async (mediaURL) => {
    const storagePath = extractStoragePathFromUrl(mediaURL);
    if (!storagePath) return;
    try {
        await admin.storage().bucket().file(storagePath).delete({ ignoreNotFound: true });
    } catch (error) {
        console.warn('No se pudo eliminar archivo de Storage asociado al mensaje:', error?.message || error);
    }
};

const getFirebaseUserSeed = (firebaseUser, fallbackEmail) => {
    const email = firebaseUser?.email ?? fallbackEmail ?? '';

    return {
        nombre: firebaseUser?.displayName?.trim() || email.split('@')[0] || 'Usuario',
        correoElectronico: email,
        firebaseUID: firebaseUser?.uid,
        contrasena: `firebase-auth:${firebaseUser?.uid || email}`,
        fechaNacimiento: null,
    };
};

const ensureUsuarioFromFirebaseUser = async (firebaseUser, fallbackEmail) => {
    if (!firebaseUser?.uid) {
        throw new Error('No se pudo sincronizar el usuario de Firebase con la base de datos');
    }

    const seed = getFirebaseUserSeed(firebaseUser, fallbackEmail);
    const usuario = await Usuario.findOne({
        where: {
            [Op.or]: [
                { firebaseUID: firebaseUser.uid },
                seed.correoElectronico ? { correoElectronico: seed.correoElectronico } : null,
            ].filter(Boolean),
        },
    });

    if (usuario) {
        const updatePayload = {};

        if (!usuario.firebaseUID) {
            updatePayload.firebaseUID = firebaseUser.uid;
        }

        if (seed.correoElectronico && usuario.correoElectronico !== seed.correoElectronico) {
            updatePayload.correoElectronico = seed.correoElectronico;
        }

        if (seed.nombre && usuario.nombre !== seed.nombre) {
            updatePayload.nombre = seed.nombre;
        }

        if (Object.keys(updatePayload).length > 0) {
            await usuario.update(updatePayload);
        }

        return usuario;
    }

    return await Usuario.create(seed);
};

const enrichMensajeWithUser = async (mensaje) => {
    if (!mensaje) return null;
    const usuario = mensaje.usuarioID ? await Usuario.findByPk(mensaje.usuarioID) : null;
    return {
        ...mensaje,
        usuario
    };
};

const createMensajeIAToFirestore = async (chatID, texto, archivoAdjuntoURL = null) => {
    const mensajeData = {
        chatID,
        usuarioID: null, // Mensaje de IA sin usuario
        texto,
        archivoAdjuntoURL,
    };
    
    return await addMensajeToFirestore(mensajeData);
};

const buildSessionHistoryFromMessages = (mensajes = [], limit = 8) => {
    const recentMessages = mensajes
        .filter((mensaje) => typeof mensaje?.texto === 'string' && mensaje.texto.trim().length > 0)
        .slice(-limit);

    return recentMessages.map((mensaje) => ({
        role: mensaje.usuarioID ? 'user' : 'assistant',
        content: mensaje.texto,
    }));
};

const resolvers = {
    Query: {
        // ------------------------------ Usuario ------------------------------
        getUsuarios: async () => {
            try {
                return await Usuario.findAll();
            } catch (error) {
                console.error('query getUsuarios - Error al obtener los usuarios:', error);
                throw new Error('query getUsuarios - Error al obtener los usuarios');
            }
        },

        getUsuarioByID: async (_, { id }) => {
            try {
                const usuario = await Usuario.findByPk(id);
                if (!usuario) {
                    throw new Error('query getUsuarioByID - Usuario no encontrado');
                }
                return usuario;
            } catch (error) {
                console.error('query getUsuarioByID - Error al obtener el usuario:', error);
                throw new Error('query getUsuarioByID - Error al obtener el usuario');
            }
        },

        // ------------------------------ Chat ------------------------------
        getChats: async () => {
            try {
                return await Chat.findAll({
                    include: [{ model: Usuario, as: 'usuario' }]
                });
            } catch (error) {
                console.error('query getChats - Error al obtener los chats:', error);
                throw new Error('query getChats - Error al obtener los chats');
            }
        },

        getChatByID: async (_, { id }) => {
            try {
                const chat = await Chat.findByPk(id, {
                    include: [{ model: Usuario, as: 'usuario' }]
                });
                if (!chat) {
                    throw new Error('query getChatByID - Chat no encontrado');
                }
                return chat;
            } catch (error) {
                console.error('query getChatByID - Error al obtener el chat:', error);
                throw new Error('query getChatByID - Error al obtener el chat');
            }
        },

        getChatsByUsuarioID: async (_, { usuarioID }) => {
            try {
                return await Chat.findAll({
                    where: { usuarioID },
                    include: [{ model: Usuario, as: 'usuario' }]
                });
            } catch (error) {
                console.error('query getChatsByUsuarioID - Error al obtener los chats del usuario:', error);
                throw new Error('query getChatsByUsuarioID - Error al obtener los chats del usuario');
            }
        },

        // ------------------------------ Mensaje ------------------------------
        getMensajes: async (_, { usuarioID }) => {
            try {
                const mensajes = await getMensajesByUsuarioFromFirestore(usuarioID);
                return await Promise.all(mensajes.map((mensaje) => enrichMensajeWithUser(mensaje)));
            } catch (error) {
                console.error('query getMensajes - Error al obtener los mensajes:', error);
                throw new Error('query getMensajes - Error al obtener los mensajes');
            }
        },

        getMensajeByID: async (_, { id, usuarioID }) => {
            try {
                const mensaje = await getMensajeFromFirestore(id);
                if (!mensaje) {
                    throw new Error('query getMensajeByID - Mensaje no encontrado');
                }
                
                // Verificar que el usuario sea propietario del chat
                const chat = await Chat.findByPk(mensaje.chatID);
                if (!chat || chat.usuarioID !== usuarioID) {
                    throw new Error('No autorizado: no tienes acceso a este mensaje');
                }
                
                return await enrichMensajeWithUser(mensaje);
            } catch (error) {
                console.error('query getMensajeByID - Error al obtener el mensaje:', error);
                throw new Error('query getMensajeByID - Error al obtener el mensaje');
            }
        },

        getMensajesByChatID: async (_, { chatID }, { authUser }) => {
            try {
                if (!authUser) {
                    throw new Error('No autenticado. Debes iniciar sesión para consultar mensajes.');
                }

                const usuario = await Usuario.findOne({
                    where: { firebaseUID: authUser.uid }
                });

                if (!usuario) {
                    throw new Error('Usuario no encontrado en la base de datos');
                }

                // Verificar que el usuario sea propietario del chat
                const chat = await Chat.findByPk(chatID);
                if (!chat || chat.usuarioID !== usuario.id) {
                    throw new Error('No autorizado: no tienes acceso a este chat');
                }

                const mensajes = await getMensajesByChatFromFirestore(chatID);
                return await Promise.all(mensajes.map((mensaje) => enrichMensajeWithUser(mensaje)));
            } catch (error) {
                console.error('query getMensajesByChatID - Error al obtener los mensajes del chat:', error);
                throw new Error('query getMensajesByChatID - Error al obtener los mensajes del chat');
            }
        },
    },

    Mutation: {
        // ------------------------------ Usuario ------------------------------
        addUsuario: async (_, { input }) => {
            const { value, error } = usuarioValidationSchema.validate(input, { abortEarly: false, stripUnknown: true });
            if (error) {
                throw new Error(`Mutation addUsuario - Error de validación: ${error.details.map(err => err.message).join(', ')}`);
            }
            try {
                // Crear usuario en Firebase
                const firebaseUser = await createUserWithEmailPassword(value.correoElectronico, value.contrasena);
                
                // Crear usuario en PostgreSQL
                const usuario = await Usuario.create({
                    ...value,
                    firebaseUID: firebaseUser.uid
                });
                
                return usuario;
            } catch (error) {
                console.error('Mutation addUsuario - Error al agregar usuario:', error);
                throw new Error('Mutation addUsuario - Error al agregar usuario: ' + error.message);
            }
        },

        updUsuario: async (_, { id, input }) => {
            const { value, error } = updateUsuarioValidationSchema.validate(input, { abortEarly: false, stripUnknown: true });
            if (error) {
                throw new Error(`Mutation updUsuario - Error de validación: ${error.details.map(err => err.message).join(', ')}`);
            }
            try {
                const usuario = await Usuario.findByPk(id);
                if (!usuario) {
                    throw new Error('Mutation updUsuario - Usuario no encontrado');
                }
                await usuario.update(value);
                return usuario;
            } catch (error) {
                console.error('Mutation updUsuario - Error al actualizar el usuario:', error);
                throw new Error('Mutation updUsuario - Error al actualizar el usuario: ' + error.message);
            }
        },

        delUsuario: async (_, { id }) => {
            try {
                const usuario = await Usuario.findByPk(id);
                if (!usuario) {
                    throw new Error('Mutation delUsuario - Usuario no encontrado');
                }
                
                // Eliminar usuario de Firebase
                if (usuario.firebaseUID) {
                    await deleteUserByUID(usuario.firebaseUID);
                }
                
                // Eliminar chats asociados
                const chats = await Chat.findAll({ where: { usuarioID: id } });
                for (const chat of chats) {
                    await deleteMensajesByChatFromFirestore(chat.id);
                    await chat.destroy();
                }
                
                // Eliminar usuario de PostgreSQL
                await usuario.destroy();
                return { message: 'Usuario eliminado exitosamente' };
            } catch (error) {
                console.error('Mutation delUsuario - Error al eliminar el usuario:', error);
                throw new Error('Mutation delUsuario - Error al eliminar el usuario: ' + error.message);
            }
        },

        // ------------------------------ Chat ------------------------------
        addChat: async (_, { input }, { authUser }) => {
            if (!authUser) {
                throw new Error('No autenticado. Debes iniciar sesión para crear un chat.');
            }

            const usuario = await Usuario.findOne({
                where: { firebaseUID: authUser.uid }
            });

            if (!usuario) {
                throw new Error('Usuario no encontrado en la base de datos');
            }

            const chatInput = {
                ...input,
                usuarioID: usuario.id,
            };

            const { value, error } = chatValidationSchema.validate(chatInput, { abortEarly: false, stripUnknown: true });
            if (error) {
                throw new Error(`Mutation addChat - Error de validación: ${error.details.map(err => err.message).join(', ')}`);
            }
            try {
                const chat = await Chat.create(value);
                return await Chat.findByPk(chat.id, {
                    include: [{ model: Usuario, as: 'usuario' }]
                });
            } catch (error) {
                console.error('Mutation addChat - Error al agregar chat:', error);
                throw new Error('Mutation addChat - Error al agregar chat: ' + error.message);
            }
        },

        updChat: async (_, { id, input }) => {
            const { value, error } = chatValidationSchema.validate(input, { abortEarly: false, stripUnknown: true });
            if (error) {
                throw new Error(`Mutation updChat - Error de validación: ${error.details.map(err => err.message).join(', ')}`);
            }
            try {
                const chat = await Chat.findByPk(id);
                if (!chat) {
                    throw new Error('Mutation updChat - Chat no encontrado');
                }
                await chat.update(value);
                return await Chat.findByPk(id, {
                    include: [{ model: Usuario, as: 'usuario' }]
                });
            } catch (error) {
                console.error('Mutation updChat - Error al actualizar el chat:', error);
                throw new Error('Mutation updChat - Error al actualizar el chat: ' + error.message);
            }
        },

        delChat: async (_, { id }) => {
            try {
                const chat = await Chat.findByPk(id);
                if (!chat) {
                    throw new Error('Mutation delChat - Chat no encontrado');
                }
                
                // Eliminar todos los mensajes del chat
                await deleteMensajesByChatFromFirestore(id);
                
                // Eliminar el chat
                await chat.destroy();
                return { message: 'Chat eliminado exitosamente' };
            } catch (error) {
                console.error('Mutation delChat - Error al eliminar el chat:', error);
                throw new Error('Mutation delChat - Error al eliminar el chat: ' + error.message);
            }
        },

        // ------------------------------ Mensaje ------------------------------
        addMensaje: async (_, { input }, { authUser }) => {
            if (!authUser) {
                throw new Error('No autenticado. Debes iniciar sesión para enviar mensajes.');
            }

            const usuario = await Usuario.findOne({
                where: { firebaseUID: authUser.uid }
            });

            if (!usuario) {
                throw new Error('Usuario no encontrado en la base de datos');
            }

            const normalizedInput = {
                ...input,
                usuarioID: usuario.id,
                texto: typeof input?.texto === 'string' ? input.texto.trim() : '',
            };

            const { value, error } = mensajeValidationSchema.validate(normalizedInput, { abortEarly: false, stripUnknown: true });
            if (error) {
                throw new Error(`Mutation addMensaje - Error de validación: ${error.details.map(err => err.message).join(', ')}`);
            }
            try {
                // Verificar que el chat existe y el usuario tiene acceso
                const chat = await Chat.findByPk(value.chatID);
                if (!chat || chat.usuarioID !== value.usuarioID) {
                    throw new Error('No autorizado: no tienes acceso a este chat');
                }

                const mensaje = await addMensajeToFirestore(value);
                return await enrichMensajeWithUser(mensaje);
            } catch (error) {
                console.error('Mutation addMensaje - Error al agregar mensaje:', error);
                throw new Error('Mutation addMensaje - Error al agregar mensaje: ' + error.message);
            }
        },

        updMensaje: async (_, { id, input }) => {
            const { value, error } = mensajeValidationSchema.validate(input, { abortEarly: false, stripUnknown: true });
            if (error) {
                throw new Error(`Mutation updMensaje - Error de validación: ${error.details.map(err => err.message).join(', ')}`);
            }
            try {
                const mensajeActual = await getMensajeFromFirestore(id);
                if (!mensajeActual) {
                    throw new Error('Mutation updMensaje - Mensaje no encontrado');
                }

                // Verificar que el usuario sea el dueño del mensaje
                if (mensajeActual.usuarioID !== value.usuarioID) {
                    throw new Error('No autorizado: solo el usuario que envió el mensaje puede editarlo');
                }

                const mensaje = await updateMensajeFromFirestore(id, value);
                if (!mensaje) {
                    throw new Error('Mutation updMensaje - Mensaje no encontrado');
                }
                return await enrichMensajeWithUser(mensaje);
            } catch (error) {
                console.error('Mutation updMensaje - Error al actualizar el mensaje:', error);
                throw new Error('Mutation updMensaje - Error al actualizar el mensaje: ' + error.message);
            }
        },

        delMensaje: async (_, { id, usuarioID }) => {
            try {
                const mensaje = await getMensajeFromFirestore(id);
                if (!mensaje) {
                    throw new Error('Mutation delMensaje - Mensaje no encontrado');
                }

                // Verificar que el usuario sea el dueño del mensaje
                if (mensaje.usuarioID !== usuarioID) {
                    throw new Error('No autorizado: solo el usuario que envió el mensaje puede eliminarlo');
                }

                if (mensaje.archivoAdjuntoURL) {
                    await deleteStorageObjectIfExists(mensaje.archivoAdjuntoURL);
                }

                await deleteMensajeFromFirestore(id);
                return { message: 'Mensaje eliminado exitosamente' };
            } catch (error) {
                console.error('Mutation delMensaje - Error al eliminar el mensaje:', error);
                throw new Error('Mutation delMensaje - Error al eliminar el mensaje: ' + error.message);
            }
        },

        procesarMensajeConIA: async (_, { input }, { authUser }) => {
            if (!authUser) {
                throw new Error('No autenticado. Debes iniciar sesión para enviar mensajes.');
            }

            const usuario = await Usuario.findOne({
                where: { firebaseUID: authUser.uid }
            });

            if (!usuario) {
                throw new Error('Usuario no encontrado en la base de datos');
            }

            try {
                // 1. Verificar que el chat existe y el usuario tiene acceso
                const chat = await Chat.findByPk(input.chatID);
                if (!chat || chat.usuarioID !== usuario.id) {
                    throw new Error('No autorizado: no tienes acceso a este chat');
                }

                const mensajesPrevios = await getMensajesByChatFromFirestore(input.chatID);
                const sessionHistory = buildSessionHistoryFromMessages(mensajesPrevios, 8);

                // 2. Guardar el mensaje del usuario
                const mensajeUsuarioData = {
                    chatID: input.chatID,
                    usuarioID: usuario.id,
                    texto: input.texto.trim(),
                    archivoAdjuntoURL: null,
                };

                const mensajeUsuario = await addMensajeToFirestore(mensajeUsuarioData);
                const mensajeUsuarioEnriquecido = await enrichMensajeWithUser(mensajeUsuario);

                // 3. Pasar al orchestrador de IA para procesar
                const host = process.env.OLLAMA_HOST ?? 'http://127.0.0.1:11434';
                const model = process.env.OLLAMA_MODEL ?? 'llama3.1';
                const orchestrator = createAgentOrchestrator(host, model);
                
                const resultadoIA = await orchestrator.processQuery(input.texto, sessionHistory);
                
                // 4. Guardar la respuesta de la IA sin usuarioID
                const mensajeIAData = {
                    chatID: input.chatID,
                    usuarioID: null, // Mensaje de IA sin usuario
                    texto: resultadoIA.response,
                    archivoAdjuntoURL: null,
                };

                const mensajeIA = await createMensajeIAToFirestore(input.chatID, resultadoIA.response, null);
                const mensajeIAEnriquecido = await enrichMensajeWithUser(mensajeIA);

                // 5. Retornar ambos mensajes
                return {
                    mensajeUsuario: mensajeUsuarioEnriquecido,
                    mensajeIA: mensajeIAEnriquecido,
                };
            } catch (error) {
                console.error('Mutation procesarMensajeConIA - Error:', error);
                throw new Error('Mutation procesarMensajeConIA - Error al procesar mensaje con IA: ' + error.message);
            }
        },

        // ------------------------------ Auth Firebase (Sign Up / Login) ------------------------------
        signUpEmailPassword: async (_, { input }) => {
            const { value, error } = validationSchemas.signUpEmailPasswordValidationSchema.validate(input, { abortEarly: false, stripUnknown: true });
            if (error) {
                throw new Error(`Mutation signUpEmailPassword - Error de validación: ${error.details.map(err => err.message).join(', ')}`);
            }
            try {
                // Crear usuario en Firebase
                const firebaseUser = await createUserWithEmailPassword(value.correoElectronico, value.contrasena, value.nombre);

                // Crear o sincronizar usuario en PostgreSQL
                const usuario = await ensureUsuarioFromFirebaseUser(firebaseUser, value.correoElectronico);

                return {
                    success: true,
                    message: 'Usuario registrado exitosamente',
                    usuario,
                    firebaseUID: firebaseUser.uid
                };
            } catch (error) {
                console.error('Mutation signUpEmailPassword - Error al registrar usuario:', error);
                throw new Error('Mutation signUpEmailPassword - Error al registrar usuario: ' + error.message);
            }
        },

        loginEmailPassword: async (_, { input }) => {
            const { value, error } = validationSchemas.loginEmailPasswordValidationSchema.validate(input, { abortEarly: false, stripUnknown: true });
            if (error) {
                throw new Error(`Mutation loginEmailPassword - Error de validación: ${error.details.map(err => err.message).join(', ')}`);
            }
            try {
                // Verificar el token de Firebase
                const decodedToken = await verifyIdToken(value.idToken);

                if (decodedToken.email && decodedToken.email !== value.correoElectronico) {
                    throw new Error('El correo electrónico no coincide con el token de Firebase');
                }

                const firebaseUser = await getUserByUID(decodedToken.uid);
                const usuario = await ensureUsuarioFromFirebaseUser(firebaseUser, value.correoElectronico);

                return {
                    success: true,
                    message: 'Login exitoso',
                    usuario,
                    firebaseUID: decodedToken.uid,
                    idToken: value.idToken
                };
            } catch (error) {
                console.error('Mutation loginEmailPassword - Error al iniciar sesión:', error);
                throw new Error('Mutation loginEmailPassword - Error al iniciar sesión: ' + error.message);
            }
        },

        logout: async (_, { input }) => {
            const { value, error } = validationSchemas.logoutValidationSchema.validate(input, { abortEarly: false, stripUnknown: true });
            if (error) {
                throw new Error(`Mutation logout - Error de validación: ${error.details.map(err => err.message).join(', ')}`);
            }
            try {
                // Verificar que el token es válido antes de desloguear
                await verifyIdToken(value.idToken);

                return {
                    success: true,
                    message: 'Logout exitoso'
                };
            } catch (error) {
                console.error('Mutation logout - Error al cerrar sesión:', error);
                throw new Error('Mutation logout - Error al cerrar sesión: ' + error.message);
            }
        },

        uploadFile: async (_, { input }, { authUser }) => {
            try {
                if (!authUser) {
                    throw new Error('No autenticado. Debes estar logueado para subir archivos.');
                }

                if (!input.file || !input.fileName || !input.chatID) {
                    throw new Error('Se requieren file, fileName y chatID');
                }

                if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(input.chatID)) {
                    throw new Error('chatID inválido. Crea una conversación guardada en la base de datos antes de subir archivos.');
                }

                // Validar que el usuario existe en PostgreSQL
                const usuario = await Usuario.findOne({
                    where: { firebaseUID: authUser.uid }
                });

                if (!usuario) {
                    throw new Error('Usuario no encontrado en la base de datos');
                }

                // Validar que el usuario tiene acceso al chat
                const chat = await Chat.findByPk(input.chatID);
                if (!chat || chat.usuarioID !== usuario.id) {
                    throw new Error('No autorizado: no tienes acceso a este chat');
                }

                // Convertir base64 string a buffer
                const fileBuffer = Buffer.from(input.file, 'base64');

                if (fileBuffer.length > MAX_UPLOAD_FILE_SIZE_BYTES) {
                    throw new Error('El archivo supera el límite de 8 MB. Usa un archivo más pequeño.');
                }

                // Subir a Supabase
                const fileUrl = await uploadFileToSupabaseServer(fileBuffer, input.fileName, input.chatID);

                return {
                    success: true,
                    message: 'Archivo subido exitosamente',
                    fileUrl
                };
            } catch (error) {
                console.error('Mutation uploadFile - Error al subir archivo:', error);
                throw new Error('Mutation uploadFile - Error al subir archivo: ' + error.message);
            }
        }
    }
};

export default resolvers;

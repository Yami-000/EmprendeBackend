import { db } from './firebaseAdmin.js';

const mensajesCollection = db.collection('mensajes');

const toMensajeData = (doc) => {
	if (!doc || !doc.exists) {
		return null;
	}

	const data = doc.data();
	return {
		id: doc.id,
		...data,
	};
};

export const addMensajeToFirestore = async (input) => {
	const now = new Date().toISOString();
	const mensajeRef = mensajesCollection.doc();

	const mensaje = {
		id: mensajeRef.id,
		chatID: input.chatID,
		usuarioID: input.usuarioID,
		texto: input.texto ?? '',
		archivoAdjuntoURL: input.archivoAdjuntoURL ?? null,
		remitente: input.remitente ?? 'usuario',
		createdAt: now,
		updatedAt: now,
	};

	await mensajeRef.set(mensaje);
	return mensaje;
};

export const updateMensajeFromFirestore = async (id, input) => {
	const mensajeRef = mensajesCollection.doc(id);
	const snapshot = await mensajeRef.get();

	if (!snapshot.exists) {
		return null;
	}

	const current = snapshot.data();
	const updated = {
		...current,
		...input,
		updatedAt: new Date().toISOString(),
	};

	await mensajeRef.set(updated, { merge: true });
	return {
		id,
		...updated,
	};
};

export const getMensajeFromFirestore = async (id) => {
	const snapshot = await mensajesCollection.doc(id).get();
	return toMensajeData(snapshot);
};

export const getMensajesByChatFromFirestore = async (chatID) => {
	const snapshot = await mensajesCollection.where('chatID', '==', chatID).orderBy('createdAt', 'asc').get();
	return snapshot.docs.map((doc) => toMensajeData(doc));
};

export const getMensajesByUsuarioFromFirestore = async (usuarioID) => {
	const snapshot = await mensajesCollection.where('usuarioID', '==', usuarioID).orderBy('createdAt', 'asc').get();
	return snapshot.docs.map((doc) => toMensajeData(doc));
};

export const deleteMensajeFromFirestore = async (id) => {
	await mensajesCollection.doc(id).delete();
};

export const deleteMensajesByChatFromFirestore = async (chatID) => {
	const snapshot = await mensajesCollection.where('chatID', '==', chatID).get();

	if (snapshot.empty) {
		return;
	}

	const batch = db.batch();
	snapshot.docs.forEach((doc) => {
		batch.delete(doc.ref);
	});

	await batch.commit();
};

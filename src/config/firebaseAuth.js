import admin from './firebaseAdmin.js';

export const createUserWithEmailPassword = async (email, password, displayName) => {
	return await admin.auth().createUser({
		email,
		password,
		displayName,
	});
};

export const verifyIdToken = async (idToken) => {
	return await admin.auth().verifyIdToken(idToken);
};

export const getUserByUID = async (uid) => {
	return await admin.auth().getUser(uid);
};

export const deleteUserByUID = async (uid) => {
	return await admin.auth().deleteUser(uid);
};

export const extractBearerToken = (authorizationHeader) => {
	if (!authorizationHeader || typeof authorizationHeader !== 'string') {
		return null;
	}

	const [scheme, token] = authorizationHeader.split(' ');
	if (!scheme || scheme.toLowerCase() !== 'bearer' || !token) {
		return null;
	}

	return token.trim();
};

import chatValidationSchema from "./chatValidation.js";
import mensajeValidationSchema from "./mensajeValidation.js";
import usuarioValidationSchema, { updateUsuarioValidationSchema } from "./usuarioValidation.js";

import {
    signUpEmailPasswordValidationSchema,
    loginEmailPasswordValidationSchema,
    logoutValidationSchema
} from "./firebaseAuthValidation.js";

const validationSchemas = {
    chatValidationSchema,
    mensajeValidationSchema,
    usuarioValidationSchema,
    updateUsuarioValidationSchema,
    signUpEmailPasswordValidationSchema,
    loginEmailPasswordValidationSchema,
    logoutValidationSchema
}

export default validationSchemas;
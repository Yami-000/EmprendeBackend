import joi from 'joi';

export const signUpEmailPasswordValidationSchema = joi.object({
    nombre: joi.string().min(1).max(50).required().messages({
        'string.base': 'El nombre debe ser una cadena de texto.',
        'string.min': 'El nombre debe tener al menos 1 carácter.',
        'string.max': 'El nombre no debe exceder los 50 caracteres.',
        'any.required': 'El nombre es obligatorio.'
    }),
    correoElectronico: joi.string().email().min(5).max(100).required().messages({
        'string.base': 'El correo electrónico debe ser una cadena de texto.',
        'string.email': 'El correo electrónico debe ser válido.',
        'string.min': 'El correo electrónico debe tener al menos 5 caracteres.',
        'string.max': 'El correo electrónico no debe exceder los 100 caracteres.',
        'any.required': 'El correo electrónico es obligatorio.'
    }),
    contrasena: joi.string().min(6).max(100).required().messages({
        'string.base': 'La contraseña debe ser una cadena de texto.',
        'string.min': 'La contraseña debe tener al menos 6 caracteres.',
        'string.max': 'La contraseña no debe exceder los 100 caracteres.',
        'any.required': 'La contraseña es obligatoria.'
    })
});

export const loginEmailPasswordValidationSchema = joi.object({
    correoElectronico: joi.string().email().min(5).max(100).required().messages({
        'string.base': 'El correo electrónico debe ser una cadena de texto.',
        'string.email': 'El correo electrónico debe ser válido.',
        'string.min': 'El correo electrónico debe tener al menos 5 caracteres.',
        'string.max': 'El correo electrónico no debe exceder los 100 caracteres.',
        'any.required': 'El correo electrónico es obligatorio.'
    }),
    idToken: joi.string().required().messages({
        'string.base': 'El token debe ser una cadena de texto.',
        'any.required': 'El token es obligatorio.'
    })
});

export const logoutValidationSchema = joi.object({
    idToken: joi.string().required().messages({
        'string.base': 'El token debe ser una cadena de texto.',
        'any.required': 'El token es obligatorio.'
    })
});

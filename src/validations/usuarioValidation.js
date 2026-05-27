import joi from 'joi'

const usuarioValidationSchema = joi.object({
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
    }),
    sueldo: joi.number().min(0).messages({
        'number.base': 'El sueldo debe ser un número.',
        'number.min': 'El sueldo no puede ser negativo.',
    }),
    porcentajeRSH: joi.number().min(0).max(100).messages({
        'number.base': 'El porcentaje RSH debe ser un número.',
        'number.min': 'El porcentaje RSH no puede ser negativo.',
        'number.max': 'El porcentaje RSH no puede exceder el 100%.',
    }),
    profesion: joi.string().max(100).messages({
        'string.base': 'La profesión debe ser una cadena de texto.',
        'string.max': 'La profesión no debe exceder los 100 caracteres.',
    }),
    fechaNacimiento: joi.date().iso().required().messages({
        'date.base': 'La fecha de nacimiento debe ser una fecha válida.',
        'date.format': 'La fecha de nacimiento debe estar en formato ISO (YYYY-MM-DD).',
        'any.required': 'La fecha de nacimiento es obligatoria.'
    }),
    ciudad: joi.string().max(100).messages({
        'string.base': 'La ciudad debe ser una cadena de texto.',
        'string.max': 'La ciudad no debe exceder los 100 caracteres.',
    }),
    region: joi.string().max(100).messages({
        'string.base': 'La región debe ser una cadena de texto.',
        'string.max': 'La región no debe exceder los 100 caracteres.',
    }),

})

// Schema de validación para actualización parcial de usuario
// Todos los campos son opcionales excepto que se validan si se envían
const updateUsuarioValidationSchema = joi.object({
    nombre: joi.string().min(1).max(50).messages({
        'string.base': 'El nombre debe ser una cadena de texto.',
        'string.min': 'El nombre debe tener al menos 1 carácter.',
        'string.max': 'El nombre no debe exceder los 50 caracteres.',
    }),
    correoElectronico: joi.string().email().min(5).max(100).messages({
        'string.base': 'El correo electrónico debe ser una cadena de texto.',
        'string.email': 'El correo electrónico debe ser válido.',
        'string.min': 'El correo electrónico debe tener al menos 5 caracteres.',
        'string.max': 'El correo electrónico no debe exceder los 100 caracteres.',
    }),
    contrasena: joi.string().min(6).max(100).messages({
        'string.base': 'La contraseña debe ser una cadena de texto.',
        'string.min': 'La contraseña debe tener al menos 6 caracteres.',
        'string.max': 'La contraseña no debe exceder los 100 caracteres.',
    }),
    sueldo: joi.number().min(0).messages({
        'number.base': 'El sueldo debe ser un número.',
        'number.min': 'El sueldo no puede ser negativo.',
    }),
    porcentajeRSH: joi.number().min(0).max(100).messages({
        'number.base': 'El porcentaje RSH debe ser un número.',
        'number.min': 'El porcentaje RSH no puede ser negativo.',
        'number.max': 'El porcentaje RSH no puede exceder el 100%.',
    }),
    profesion: joi.string().max(100).messages({
        'string.base': 'La profesión debe ser una cadena de texto.',
        'string.max': 'La profesión no debe exceder los 100 caracteres.',
    }),
    fechaNacimiento: joi.date().iso().messages({
        'date.base': 'La fecha de nacimiento debe ser una fecha válida.',
        'date.format': 'La fecha de nacimiento debe estar en formato ISO (YYYY-MM-DD).',
    }),
    ciudad: joi.string().max(100).messages({
        'string.base': 'La ciudad debe ser una cadena de texto.',
        'string.max': 'La ciudad no debe exceder los 100 caracteres.',
    }),
    region: joi.string().max(100).messages({
        'string.base': 'La región debe ser una cadena de texto.',
        'string.max': 'La región no debe exceder los 100 caracteres.',
    }),
    
}).min(1).messages({
    'object.min': 'Debe proporcionar al menos un campo para actualizar.'
});

export { usuarioValidationSchema, updateUsuarioValidationSchema };
export default usuarioValidationSchema;
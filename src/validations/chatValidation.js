import joi from 'joi'

const chatValidationSchema = joi.object({
    nombre: joi.string().min(1).max(100).required().messages({
        'string.base': 'El nombre del chat debe ser una cadena de texto.',
        'string.min': 'El nombre del chat debe tener al menos 1 carácter.',
        'string.max': 'El nombre del chat no debe exceder los 100 caracteres.',
        'any.required': 'El nombre del chat es obligatorio.'
    }),
    usuarioID: joi.string().uuid().required().messages({
        'string.base': 'El ID del usuario debe ser una cadena de texto.',
        'string.uuid': 'El ID del usuario debe ser un UUID válido.',
        'any.required': 'El ID del usuario es obligatorio.'
    })
})

export default chatValidationSchema;
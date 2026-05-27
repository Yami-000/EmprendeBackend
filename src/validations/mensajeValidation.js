import joi from 'joi'

const mensajeValidationSchema = joi.object({
    chatID: joi.string().uuid().required().messages({
        'string.base': 'El ID del chat debe ser una cadena de texto.',
        'string.uuid': 'El ID del chat debe ser un UUID válido.',
        'any.required': 'El ID del chat es obligatorio.'
    }),
    usuarioID: joi.string().uuid().messages({
        'string.base': 'El ID del usuario debe ser una cadena de texto.',
        'string.uuid': 'El ID del usuario debe ser un UUID válido.',
        'any.required': 'El ID del usuario es obligatorio.'
    }),
    texto: joi.string().trim().allow('').max(500).messages({
        'string.base': 'El texto del mensaje debe ser una cadena de texto.',
        'string.max': 'El texto del mensaje no debe exceder los 500 caracteres.',
    }),
    archivoAdjuntoURL: joi.string().uri().max(255).allow(null).messages({
        'string.base': 'La URL del archivo adjunto debe ser una cadena de texto.',
        'string.uri': 'La URL del archivo adjunto debe ser una URL válida.',
        'string.max': 'La URL del archivo adjunto no debe exceder los 255 caracteres.',
    }),
    remitente: joi.string().valid('usuario', 'ia').default('usuario').messages({
        'string.base': 'El remitente debe ser una cadena de texto.',
        'any.only': 'El remitente debe ser "usuario" o "ia".'
    })
}).custom((value, helpers) => {
    const hasText = typeof value.texto === 'string' && value.texto.trim().length > 0;
    const hasAttachment = typeof value.archivoAdjuntoURL === 'string' && value.archivoAdjuntoURL.trim().length > 0;

    if (!hasText && !hasAttachment) {
        return helpers.error('any.invalid', {
            message: 'Debes enviar texto o un archivo adjunto.'
        });
    }

    return value;
}, 'mensaje content validation').messages({
    'any.invalid': '{{#message}}'
})

export default mensajeValidationSchema;

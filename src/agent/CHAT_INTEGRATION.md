# Integración de Agentes de IA en el Chat

## Descripción General

Los agentes de IA están ahora integrados en el flujo del chat. Cuando un usuario envía un mensaje, el backend:

1. Guarda el mensaje del usuario en la BD (con `usuarioID`)
2. Pasa el mensaje al **orquestador de IA**
3. El orquestador valida, enruta y procesa con agentes especializados
4. Guarda la respuesta de la IA en la BD (sin `usuarioID`)
5. Retorna ambos mensajes (usuario + IA) al cliente

## Nuevas Mutaciones GraphQL

### `procesarMensajeConIA`

**Entrada:**
```graphql
input ProcessMensajeConIAInput {
  chatID: ID!
  texto: String!
}
```

**Respuesta:**
```graphql
type MensajeProcesadoConIAResponse {
  mensajeUsuario: Mensaje!
  mensajeIA: Mensaje!
}
```

**Descripción:**
Procesa un mensaje del usuario a través del sistema de agentes de IA y retorna tanto el mensaje del usuario como la respuesta de la IA.

## Cambios en la Base de Datos

### Modelo `Mensaje`
- El campo `usuarioID` ahora es **nullable** (`allowNull: true`)
  - Mensajes con `usuarioID`: Enviados por el usuario
  - Mensajes sin `usuarioID` (null): Generados por la IA

### Identificación de Mensajes
- **Mensaje del Usuario**: `mensaje.usuarioID !== null`
- **Mensaje de la IA**: `mensaje.usuarioID === null`

## Flujo en el Frontend

### 1. Enviar mensaje a través de IA

```javascript
// Apollo client
const { mutate } = useMutation(gql`
  mutation ProcessMensajeConIA($input: ProcessMensajeConIAInput!) {
    procesarMensajeConIA(input: $input) {
      mensajeUsuario {
        id
        texto
        usuario {
          id
          nombre
        }
        createdAt
      }
      mensajeIA {
        id
        texto
        createdAt
      }
    }
  }
`);

// Llamar la mutación
const handleSendMessage = async (chatID, texto) => {
  const response = await mutate({
    variables: {
      input: {
        chatID,
        texto
      }
    }
  });
  
  const { mensajeUsuario, mensajeIA } = response.data.procesarMensajeConIA;
  
  // Agregar ambos mensajes al historial del chat
  setChatMessages([...chatMessages, mensajeUsuario, mensajeIA]);
};
```

### 2. Mostrar mensajes en el Chat

```javascript
// Diferenciar entre mensajes del usuario y de la IA
{chatMessages.map((msg) => (
  <Message
    key={msg.id}
    texto={msg.texto}
    autor={msg.usuario?.nombre || 'LookFin IA'} // null si es IA
    esUsuario={msg.usuario !== null}
  />
))}
```

## Variables de Entorno

```env
# Ollama (para agentes de IA)
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1
```

## Arquitectura de Agentes

```
Mensaje del Usuario
  ↓
Security Agent (validación)
  ↓
Orchestrator (enrutamiento)
  ├─ Specialized Agent (si aplica)
  │   └─ Response Agent
  └─ Response Agent (directo)
  ↓
Respuesta Final guardada en BD (sin usuarioID)
```

## Consideraciones de Seguridad

1. **Autenticación Requerida**: La mutación `procesarMensajeConIA` requiere que el usuario esté autenticado
2. **Autorización de Chat**: Se verifica que el usuario tenga acceso al chat
3. **Validación de Consulta**: El agente de seguridad rechaza consultas con IDs, números o nombres específicos
4. **Sin información personal**: Los agentes no pueden extraer información personal directa del usuario

## Ejemplo de Flujo Completo

1. **Usuario escribe**: "¿Cuál es mi saldo actual?"
2. **Frontend envía mutación** `procesarMensajeConIA`
3. **Backend guarda** mensaje del usuario con `usuarioID`
4. **Orchestrator valida**: "✓ Consulta válida - sin IDs específicos"
5. **Agent routing**: Detecta como consulta de inversión → `agenteMiPrimeraInversion`
6. **Agente especializado responde** usando contexto documental
7. **Backend guarda** respuesta de IA sin `usuarioID`
8. **Frontend recibe** ambos mensajes y los muestra en el chat

## Mensajes Guardados

- **Usuario**: 
  ```json
  {
    "id": "uuid-1",
    "chatID": "chat-uuid",
    "usuarioID": "user-uuid",
    "texto": "¿Cuál es mi saldo actual?",
    "createdAt": "2026-05-06T10:30:00Z"
  }
  ```

- **IA**:
  ```json
  {
    "id": "uuid-2",
    "chatID": "chat-uuid",
    "usuarioID": null,
    "texto": "Tu saldo es $X.XXX",
    "createdAt": "2026-05-06T10:30:05Z"
  }
  ```

## Troubleshooting

### Error: "Ollama no conecta"
- Verifica que `ollama serve` está ejecutándose
- Revisa `OLLAMA_HOST` en `.env`

### Respuesta de IA vacía
- Revisa logs del backend para errores de validación
- El `securityAgent` podría estar rechazando la consulta

### Mensaje no se guarda en BD
- Verifica que el usuario está autenticado
- Confirma que el `chatID` existe y pertenece al usuario

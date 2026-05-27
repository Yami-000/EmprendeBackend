import { chatWithOllama } from './ollamaClient.js';

const URL_PATTERN = /https?:\/\/[\w.-]+(?:\/[\w\-./?%&=+#]*)?/gi;

const normalizeUrlList = (urls = []) => Array.from(new Set(urls.filter(Boolean).map((url) => url.trim())));

const formatSessionHistory = (sessionHistory = []) => {
  if (!Array.isArray(sessionHistory) || sessionHistory.length === 0) {
    return '';
  }

  return sessionHistory
    .slice(-10)
    .map((message, index) => `${index + 1}. ${message.role === 'user' ? 'Usuario' : 'Asistente'}: ${message.content}`)
    .join('\n');
};

const sanitizeResponseLinks = (response, allowedLinks = [], recommendedLinks = [], userQuery = '') => {
  const allowed = new Set(normalizeUrlList([...allowedLinks, ...recommendedLinks]));
  let sanitized = response;

  const detectedUrls = sanitized.match(URL_PATTERN) ?? [];
  for (const url of detectedUrls) {
    if (!allowed.has(url)) {
      sanitized = sanitized.replace(url, '');
    }
  }

  const asksForLink = /\b(link|enlace|url|simulador|recurso|pagina|p[aá]gina\s+oficial|herramienta|herramientas)\b/i.test(userQuery);
  const preferredLink = recommendedLinks.find((url) => allowed.has(url)) ?? allowedLinks.find((url) => allowed.has(url));

  if (asksForLink && preferredLink && !sanitized.includes(preferredLink)) {
    sanitized = `${sanitized.trim()}\n\nLink oficial: ${preferredLink}`.trim();
  }

  return sanitized.replace(/\n{3,}/g, '\n\n').trim();
};

const RESPONSE_AGENT_SYSTEM_PROMPT = `Eres el agente de respuesta final llamado "agenteDeRespuesta".
Tu trabajo es recibir la información procesada por otros agentes (por ejemplo, agentes especializados)
y generar la respuesta final dirigida al usuario.

Reglas:
- Si recibes contenido generado por un agente especializado, usa ese contenido como la fuente principal y formatea la respuesta para el usuario.
- Si recibes únicamente la consulta del usuario (sin agente especializado), responde la consulta de forma clara y completa.
- Nunca inventes enlaces. Solo puedes incluir URLs que estén explícitamente presentes en la información que recibes.
- Si no hay enlaces autorizados en el contexto, no incluyas ningún link.
- Si el usuario pide un link y no existe en el contexto, di que no está disponible en la documentación.
- Usa la memoria de sesión para responder seguimientos, continuaciones y referencias anafóricas como "pasemos a la siguiente etapa" o "eso".
- Mantén el lenguaje en español, tono empático y práctico.
- Devuelve sólo la respuesta textual pensada para el usuario.
`;

export const createResponseAgent = (host, model) => ({
  async respond(userQuery, specializedAgentResult = null, allowedLinks = [], recommendedLinks = [], sessionHistory = []) {
    const messages = [];
    const memoryBlock = formatSessionHistory(sessionHistory);
    const systemPrompt = memoryBlock
      ? `${RESPONSE_AGENT_SYSTEM_PROMPT}\n\nMEMORIA DE SESIÓN ACTUAL\n${memoryBlock}`
      : RESPONSE_AGENT_SYSTEM_PROMPT;

    // System prompt to instruct the response agent
    messages.push({ role: 'system', content: systemPrompt });

    // If we have a specialized agent result, provide it as context
    if (specializedAgentResult) {
      messages.push({
        role: 'assistant',
        content: JSON.stringify({
          specializedResult: specializedAgentResult,
          allowedLinks,
          recommendedLinks,
          sessionHistory,
        }),
      });
      messages.push({ role: 'user', content: `Por favor, genera la respuesta final para la consulta: ${userQuery}. Si corresponde incluir un enlace, usa solo los de allowedLinks.` });
    } else {
      // Otherwise, respond directly to the user's query
      messages.push({
        role: 'assistant',
        content: JSON.stringify({ allowedLinks, recommendedLinks, sessionHistory }),
      });
      messages.push({ role: 'user', content: userQuery });
    }

    const assistantReply = await chatWithOllama({
      host,
      model,
      messages,
    });

    return sanitizeResponseLinks(assistantReply.trim(), allowedLinks, recommendedLinks, userQuery);
  },
});

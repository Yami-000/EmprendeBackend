const DEFAULT_OLLAMA_HOST = process.env.OLLAMA_HOST ?? 'http://127.0.0.1:11434';
const DEFAULT_OLLAMA_MODEL = process.env.OLLAMA_MODEL ?? 'llama3.1';

const DEFAULT_SYSTEM_PROMPT = `Eres LookFin, un asistente financiero claro, breve y práctico.
Responde en español.
Si faltan datos, pregunta una sola cosa a la vez.
Si el usuario pide pasos técnicos, responde con instrucciones concretas.
No inventes datos.`;

const buildChatPayload = (messages, options = {}) => ({
  model: options.model ?? DEFAULT_OLLAMA_MODEL,
  stream: false,
  messages: [
    { role: 'system', content: options.systemPrompt ?? DEFAULT_SYSTEM_PROMPT },
    ...messages,
  ],
});

export const chatWithOllama = async ({
  messages,
  host = DEFAULT_OLLAMA_HOST,
  model = DEFAULT_OLLAMA_MODEL,
  systemPrompt, // optional override for system prompt
}) => {
  const payload = buildChatPayload(messages, { model, systemPrompt });

  const response = await fetch(`${host.replace(/\/$/, '')}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Ollama respondió ${response.status}: ${errorText}`);
  }

  const data = await response.json();
  return data?.message?.content ?? '';
};

export const testOllamaConnection = async ({ host = DEFAULT_OLLAMA_HOST } = {}) => {
  const response = await fetch(`${host.replace(/\/$/, '')}/api/tags`);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`No se pudo conectar a Ollama (${response.status}): ${errorText}`);
  }

  return await response.json();
};

export const createAssistantTurn = async ({ history, userMessage, host, model }) => {
  const nextMessages = [
    ...history,
    { role: 'user', content: userMessage },
  ];

  const assistantMessage = await chatWithOllama({
    messages: nextMessages,
    host,
    model,
  });

  return {
    history: [
      ...nextMessages,
      { role: 'assistant', content: assistantMessage },
    ],
    assistantMessage,
  };
};

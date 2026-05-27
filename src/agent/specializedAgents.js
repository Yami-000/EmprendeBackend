import { chatWithOllama } from './ollamaClient.js';
import { AGENT_CATALOG, buildAgentSystemPrompt, normalizeText } from './knowledgeBase.js';

const createSpecializedAgent = (agentKey) => {
  const agentConfig = AGENT_CATALOG[agentKey];

  const formatSessionHistory = (sessionHistory = []) => {
    if (!Array.isArray(sessionHistory) || sessionHistory.length === 0) {
      return '';
    }

    return sessionHistory
      .slice(-10)
      .map((message, index) => `${index + 1}. ${message.role === 'user' ? 'Usuario' : 'Asistente'}: ${message.content}`)
      .join('\n');
  };

  return {
    name: agentConfig.name,
    agentKey,
    async respond(query, host, model, sessionHistory = []) {
      const { systemPrompt, sources, allowedLinks, recommendedLinks } = await buildAgentSystemPrompt(agentKey, query, sessionHistory);

      const memoryBlock = formatSessionHistory(sessionHistory);
      const historyContext = memoryBlock ? `\n\n## MEMORIA DE SESIÓN\n${memoryBlock}` : '';

      const response = await chatWithOllama({
        host,
        model,
        systemPrompt: `${systemPrompt}${historyContext}`,
        messages: [{ role: 'user', content: query }],
      });

      return {
        tool: agentConfig.name,
        status: 'completed',
        response: response.trim(),
        sources,
        allowedLinks,
        recommendedLinks,
      };
    },
  };
};

export const agenteMiPrimerAhorro = createSpecializedAgent('mi_primer_ahorro');
export const agenteMiPrimeraInversion = createSpecializedAgent('mi_primera_inversion');
export const agenteMiPrimeraVezPlanificando = createSpecializedAgent('mi_primera_vez_planificando');
export const agenteMiPrimerEndeudamiento = createSpecializedAgent('mi_primer_endeudamiento');
export const agenteMiPrimerSueldo = createSpecializedAgent('mi_primer_sueldo');

export const determineSpecializedAgent = (query = '') => {
  const queryNormalized = normalizeText(query);

  if (/\b(ahorr|ahorro|ahorros|cuenta de ahorro|fondo de emergencia|dep[oó]sito a plazo|dap)\b/i.test(queryNormalized)) {
    return agenteMiPrimerAhorro;
  }

  if (/\b(inver|invertir|inversion|instrumento|instrumentos|acciones|fondos mutuos|fondos de inversion|renta fija|renta variable|portafolio|diversific|rentabilidad|riesgo)\b/i.test(queryNormalized)) {
    return agenteMiPrimeraInversion;
  }

  if (/\b(planific|planificaci[oó]n|presupuesto|gastos hormiga|meta financiera|control de gastos|ingreso neto|saldo mensual)\b/i.test(queryNormalized)) {
    return agenteMiPrimeraVezPlanificando;
  }

  if (/\b(deuda|endeud|tarjeta de credito|tarjeta de cr[eé]dito|pago minimo|estado de cuenta|mora|cupo|inter[eé]s rotativo|avance en efectivo)\b/i.test(queryNormalized)) {
    return agenteMiPrimerEndeudamiento;
  }

  if (/\b(sueldo|salario|primer sueldo|tarjeta de debito|tarjeta de d[eé]bito|cuenta corriente|cuenta a la vista|pin|cajero|fraude|retiro|medio de pago)\b/i.test(queryNormalized)) {
    return agenteMiPrimerSueldo;
  }

  return null;
};

export const allSpecializedAgents = [
  agenteMiPrimerAhorro,
  agenteMiPrimeraInversion,
  agenteMiPrimeraVezPlanificando,
  agenteMiPrimerEndeudamiento,
  agenteMiPrimerSueldo,
];

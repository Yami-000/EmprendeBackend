import { validateQuery } from './securityAgent.js';
import { determineSpecializedAgent } from './specializedAgents.js';
import { createResponseAgent } from './responseAgent.js';

/**
 * Orquestador principal del sistema de agentes
 */
export const createAgentOrchestrator = (host, model) => {
  return {
    host,
    model,

    async processQuery(userQuery, sessionHistory = []) {
      const result = {
        query: userQuery,
        steps: [],
        validation: null,
        response: null,
        agentUsed: null,
      };

      try {
        // PASO 1: Validar consulta con agente de seguridad
        console.log('[Validando consulta...]');
        result.steps.push('security_validation');

        result.validation = await validateQuery(userQuery, this.host, this.model);

        if (!result.validation.valida) {
          result.response = `No puedo procesar tu consulta porque: ${result.validation.razon}`;
          return result;
        }

        // PASO 2: Determinar qué agente usar
        console.log('Consulta validada. Procesando...\n');
        result.steps.push('agent_routing');

        const specializedAgent = determineSpecializedAgent(userQuery);
        const responseAgent = createResponseAgent(this.host, this.model);

        if (specializedAgent) {
          // PASO 3a: Usar agente especializado y luego pasar su resultado al agente de respuesta
          result.agentUsed = specializedAgent.name;
          result.steps.push(specializedAgent.name);

          const agentResponse = await specializedAgent.respond(userQuery, this.host, this.model, sessionHistory);

          // agentResponse.response contiene la salida del agente especializado
          const finalAnswer = await responseAgent.respond(
            userQuery,
            agentResponse.response,
            agentResponse.allowedLinks ?? [],
            agentResponse.recommendedLinks ?? [],
            sessionHistory,
          );
          result.response = finalAnswer;
        } else {
          // PASO 3b: No hay agente especializado — pasar la consulta directamente al agente de respuesta
          result.agentUsed = 'agente_de_respuesta';
          result.steps.push('agente_de_respuesta');

          const finalAnswer = await responseAgent.respond(userQuery, null, [], [], sessionHistory);
          result.response = finalAnswer;
        }
      } catch (error) {
        console.error('Error en el orquestador:', error);
        result.validation = {
          valida: false,
          razon: 'Error interno al procesar la consulta.',
        };
        result.response = 'Ocurrió un error interno al procesar tu consulta. No puedo generar una respuesta confiable en este momento.';
      }

      return result;
    },
  };
};

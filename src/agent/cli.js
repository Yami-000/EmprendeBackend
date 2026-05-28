import dotenv from 'dotenv';
import readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';
import { testOllamaConnection } from './ollamaClient.js';
import { createAgentOrchestrator } from './orchestrator.js';

dotenv.config();

const host = process.env.OLLAMA_HOST;
const model = process.env.OLLAMA_MODEL;

const formatHelp = () => `
Comandos disponibles:
/exit   Salir del sistema
/help   Ver esta ayuda
`;

const main = async () => {
  console.log('\n=== LookFin Multi-Agent System ===');
  console.log(`Host: ${host}`);
  console.log(`Model: ${model}`);
  console.log('Sistema de agentes especializado para finanzas personales.\n');

  try {
    const tags = await testOllamaConnection({ host });
    const availableModels = Array.isArray(tags?.models) ? tags.models.map((entry) => entry.name).filter(Boolean) : [];
    if (availableModels.length > 0) {
      console.log(`Modelos detectados: ${availableModels.join(', ')}`);
    }
  } catch (error) {
    console.error('No se pudo conectar a Ollama. Asegúrate de que el servicio esté activo.');
    console.error(error.message);
    process.exitCode = 1;
    return;
  }

  console.log(formatHelp());

  const rl = readline.createInterface({ input, output });
  const orchestrator = createAgentOrchestrator(host, model);
  const sessionHistory = [];

  try {
    while (true) {
      const userMessage = (await rl.question('Tú> ')).trim();

      if (!userMessage) {
        continue;
      }

      if (userMessage === '/exit') {
        break;
      }

      if (userMessage === '/help') {
        console.log(formatHelp());
        continue;
      }

      try {
        const result = await orchestrator.processQuery(userMessage, sessionHistory);

        if (result.validation && !result.validation.valida) {
          console.log(`\nLookFin> ${result.response}\n`);
        } else {
          const agentInfo = result.agentUsed ? ` [${result.agentUsed}]` : '';
          console.log(`\nLookFin${agentInfo}> ${result.response}\n`);
        }

        sessionHistory.push({ role: 'user', content: userMessage });
        sessionHistory.push({ role: 'assistant', content: result.response });
      } catch (error) {
        console.error(`\nError del agente: ${error.message}\n`);
      }
    }
  } finally {
    rl.close();
  }
};

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

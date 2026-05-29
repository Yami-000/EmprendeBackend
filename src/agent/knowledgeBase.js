import fs from 'node:fs/promises';
import path from 'node:path';
import * as mammoth from 'mammoth';
import { TextLoader } from '@langchain/classic/document_loaders/fs/text';

const BACKEND_ROOT = process.cwd();
const DOCUMENTS_ROOT = path.join(BACKEND_ROOT, 'src', 'agent', 'documents');
const PROMPTS_ROOT = path.join(BACKEND_ROOT, 'markdown');

const AGENT_CATALOG = {
  mi_primer_ahorro: {
    name: 'mi_primer_ahorro',
    folder: 'MiPrimerAhorro',
    promptFile: 'system_prompt_MiPrimerAhorro.md',
    keywords: ['ahorro', 'ahorrar', 'ahorros', 'cuenta de ahorro', 'fondo de emergencia', 'dap'],
  },
  mi_primera_inversion: {
    name: 'mi_primera_inversion',
    folder: 'MiPrimeraInversión',
    promptFile: 'system_prompt_MiPrimeraInversion.md',
    keywords: ['inversión', 'invertir', 'acciones', 'fondos mutuos', 'renta fija', 'renta variable', 'portafolio', 'diversificar'],
  },
  mi_primera_vez_planificando: {
    name: 'mi_primera_vez_planificando',
    folder: 'MiPrimeraVezPlanificando',
    promptFile: 'system_prompt_MiPrimeraVezPlanificando.md',
    keywords: ['planificación', 'planificar', 'presupuesto', 'gastos hormiga', 'meta financiera', 'control de gastos', 'ingreso neto'],
  },
  mi_primer_endeudamiento: {
    name: 'mi_primer_endeudamiento',
    folder: 'MiPrimerEndeudamiento',
    promptFile: 'system_prompt_MiPrimerEndeudamiento.md',
    keywords: ['deuda', 'endeudamiento', 'tarjeta de crédito', 'pago mínimo', 'estado de cuenta', 'mora', 'cupo', 'interés rotativo'],
  },
  mi_primer_sueldo: {
    name: 'mi_primer_sueldo',
    folder: 'MiPrimerSueldo',
    promptFile: 'system_prompt_MiPrimerSueldo.md',
    keywords: ['sueldo', 'salario', 'primer sueldo', 'tarjeta de débito', 'cuenta corriente', 'cuenta a la vista', 'pin', 'cajero', 'fraude'],
  },
  mi_primera_constitucion_emp_simplificada: {
    name: 'mi_primera_constitucion_emp_simplificada',
    folder: 'MiPrimeraConstitucionEmpSimplificada',
    promptFile: 'system_prompt_MiPrimeraConstitucionEmpSimplificada.md',
    keywords: ['constitución', 'empresa', 'constitución simplificada', 'sociedad', 'estatutos', 'documentos'],
  },
  mi_primera_constitucion_emp_tradicional: {
    name: 'mi_primera_constitucion_emp_tradicional',
    folder: 'MiPrimeraConstitucionEmpTradicional',
    promptFile: 'system_prompt_MiPrimeraConstitucionEmpTradicional.md',
    keywords: ['constitución', 'empresa', 'constitución tradicional', 'sociedad', 'estatutos', 'documentos'],
  },
  mi_primera_documentacion_form: {
    name: 'mi_primera_documentacion_form',
    folder: 'MiPrimeraDocumentacionForm',
    promptFile: 'system_prompt_MiPrimeraDocumentacionForm.md',
    keywords: ['documentación', 'formulario', 'requisitos', 'tramites', 'papeles'],
  },
  mi_primera_eleccion_emp: {
    name: 'mi_primera_eleccion_emp',
    folder: 'MiPrimeraEleccionEmp',
    promptFile: 'system_prompt_MiPrimeraEleccionEmp.md',
    keywords: ['elección', 'tipo de empresa', 'forma jurídica', 'persona natural', 'persona jurídica', 'modelo de negocio'],
  },
  mi_primer_inicio_sii: {
    name: 'mi_primer_inicio_sii',
    folder: 'MiPrimerInicioSII',
    promptFile: 'system_prompt_MiPrimerInicioSII.md',
    keywords: ['SII', 'impuestos', 'RUT', 'facturación', 'declaración', 'obligaciones tributarias'],
  },
  mi_primeros_permisos_compl: {
    name: 'mi_primeros_permisos_compl',
    folder: 'MiPrimeroPermisosCompl',
    promptFile: 'system_prompt_MiPrimeroPermisosCompl.md',
    keywords: ['permiso', 'patente municipal', 'licencia', 'compliance', 'regulación'],
  },
  mi_primeros_costos_y_plazos_de_form: {
    name: 'mi_primeros_costos_y_plazos_de_form',
    folder: 'MiPrimerosCostosYPlazosDeForm',
    promptFile: 'system_prompt_MiPrimerosCostosYPlazosDeForm.md',
    keywords: ['costos', 'plazos', 'formación', 'trámites', 'tiempo', 'presupuesto'],
  },
  mi_primer_proceso_form: {
    name: 'mi_primer_proceso_form',
    folder: 'MiPrimerProcesoForm',
    promptFile: 'system_prompt_MiPrimerProcesoForm.md',
    keywords: ['proceso', 'trámites', 'paso a paso', 'formación de empresa', 'documentos', 'inscripción'],
  },
  mi_primera_patente_mun: {
    name: 'mi_primera_patente_mun',
    folder: 'MiPrimeraPatenteMun',
    promptFile: 'systeme_prompt_MiPrimeraPatenteMun.md',
    keywords: ['patente', 'municipal', 'patente municipal', 'licencia comercial'],
  },
};

const TOKEN_PATTERN = /[\p{L}\p{N}]+/gu;
const URL_PATTERN = /https?:\/\/[\w.-]+(?:\/[\w\-./?%&=+#]*)?/gi;
const MAX_CONTEXT_CHARS = 9000;
const CHUNK_SIZE = 1400;
const CHUNK_OVERLAP = 180;

const normalizeText = (text = '') => text
  .toLowerCase()
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .trim();

const tokenize = (text = '') => (normalizeText(text).match(TOKEN_PATTERN) ?? []).filter((token) => token.length > 2);

const isLikelyRealUrl = (url = '') => {
  try {
    const parsed = new URL(url.trim());
    const hostname = parsed.hostname.toLowerCase();

    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return false;
    }

    if (hostname.startsWith('schemas.') || hostname.includes('openxmlformats') || hostname.includes('microsoft.com')) {
      return false;
    }

    return hostname.includes('.');
  } catch {
    return false;
  }
};

const extractUrls = (text = '') => Array.from(new Set((text.match(URL_PATTERN) ?? [])
  .map((url) => url.trim())
  .filter(isLikelyRealUrl)));

const stripHtml = (html = '') => html
  .replace(/<script[\s\S]*?<\/script>/gi, ' ')
  .replace(/<style[\s\S]*?<\/style>/gi, ' ')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;/gi, ' ')
  .replace(/&amp;/gi, '&')
  .replace(/&lt;/gi, '<')
  .replace(/&gt;/gi, '>')
  .replace(/\s+/g, ' ')
  .trim();

const stripRtf = (raw = '') => raw
  .replace(/\r?\n/g, ' ')
  .replace(/\\'[0-9a-fA-F]{2}/g, ' ')
  .replace(/\\[a-zA-Z]+\d* ?/g, ' ')
  .replace(/[{}]/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

const collectFiles = async (directoryPath) => {
  try {
    const entries = await fs.readdir(directoryPath, { withFileTypes: true });
    const files = [];

    for (const entry of entries) {
      const fullPath = path.join(directoryPath, entry.name);
      if (entry.isDirectory()) {
        const nestedFiles = await collectFiles(fullPath);
        files.push(...nestedFiles);
        continue;
      }

      const extension = path.extname(entry.name).toLowerCase();
      if (['.docx', '.md', '.txt', '.rtf'].includes(extension)) {
        files.push(fullPath);
      }
    }

    return files;
  } catch (error) {
    if (error.code === 'ENOENT') {
      return [];
    }
    throw error;
  }
};

const loadFileText = async (filePath) => {
  const extension = path.extname(filePath).toLowerCase();

  try {
    if (extension === '.docx') {
      const htmlResult = await mammoth.convertToHtml({ path: filePath });
      const html = htmlResult.value ?? '';
      const rawResult = await mammoth.extractRawText({ path: filePath });
      const rawText = rawResult.value ?? '';

      return {
        text: `${stripHtml(html)} ${rawText}`.trim(),
        urls: extractUrls(html),
      };
    }

    if (extension === '.md' || extension === '.txt') {
      const loader = new TextLoader(filePath);
      const documents = await loader.load();
      const text = documents.map((document) => document.pageContent ?? '').join('\n\n').trim();
      return {
        text,
        urls: extractUrls(text),
      };
    }

    if (extension === '.rtf') {
      const raw = await fs.readFile(filePath, 'utf8');
      const text = stripRtf(raw);
      return {
        text,
        urls: extractUrls(text),
      };
    }

    return { text: '', urls: [] };
  } catch {
    const raw = await fs.readFile(filePath, 'utf8');
    const text = raw.trim();
    return {
      text,
      urls: extractUrls(text),
    };
  }
};

const chunkText = (text = '') => {
  const normalized = text.replace(/\s+/g, ' ').trim();

  if (!normalized) {
    return [];
  }

  if (normalized.length <= CHUNK_SIZE) {
    return [normalized];
  }

  const chunks = [];
  let start = 0;

  while (start < normalized.length) {
    let end = Math.min(normalized.length, start + CHUNK_SIZE);

    if (end < normalized.length) {
      const window = normalized.slice(start, end);
      const lastSentenceBreak = Math.max(window.lastIndexOf('. '), window.lastIndexOf('\n'), window.lastIndexOf(' '));
      if (lastSentenceBreak > 500) {
        end = start + lastSentenceBreak + 1;
      }
    }

    const chunk = normalized.slice(start, end).trim();
    if (chunk) {
      chunks.push(chunk);
    }

    if (end >= normalized.length) {
      break;
    }

    const nextStart = Math.max(end - CHUNK_OVERLAP, start + 1);
    start = nextStart;
  }

  return chunks;
};

const scoreChunk = (chunkTextValue, queryTokens, agentKeywords) => {
  const chunk = normalizeText(chunkTextValue);
  let score = 0;

  for (const token of queryTokens) {
    const occurrences = chunk.split(token).length - 1;
    score += occurrences * 3;
  }

  for (const keyword of agentKeywords) {
    if (chunk.includes(normalizeText(keyword))) {
      score += 1;
    }
  }

  return score;
};

const selectRecommendedLinks = (agentKey, query, allowedLinks = []) => {
  const normalizedQuery = normalizeText(query);

  if (agentKey === 'mi_primer_ahorro' && /\b(simulador|link|enlace|recurso|planific|ahorr|ahorro)\b/i.test(normalizedQuery)) {
    const preferred = allowedLinks.find((url) => url.includes('simuladorcuantopuedoahorrar'))
      ?? allowedLinks.find((url) => url.includes('simuladorcuantonecesitoahorrar'));

    return preferred ? [preferred] : [];
  }

  return [];
};

const loadPromptText = async (promptFile) => {
  const promptPath = path.join(PROMPTS_ROOT, promptFile);
  return await fs.readFile(promptPath, 'utf8');
};

const loadAgentKnowledge = async (agentKey) => {
  const agent = AGENT_CATALOG[agentKey];

  if (!agent) {
    throw new Error(`No existe configuración para el agente: ${agentKey}`);
  }

  const prompt = await loadPromptText(agent.promptFile);
  const folderPath = path.join(DOCUMENTS_ROOT, agent.folder);
  const documentFiles = await collectFiles(folderPath);
  const chunks = [];
  const urls = new Set();

  for (const filePath of documentFiles) {
    const filePayload = await loadFileText(filePath);
    const fileChunks = chunkText(filePayload.text);

    filePayload.urls.forEach((url) => urls.add(url));

    fileChunks.forEach((chunkTextValue, index) => {
      chunks.push({
        source: filePath,
        fileName: path.basename(filePath),
        chunkIndex: index + 1,
        text: chunkTextValue,
      });
    });
  }

  return {
    ...agent,
    prompt,
    chunks,
    urls: Array.from(urls),
  };
};

const getAllSystemPrompts = async () => {
  const allPrompts = {};

  await Promise.all(Object.entries(AGENT_CATALOG).map(async ([agentKey, agent]) => {
    allPrompts[agentKey] = {
      ...agent,
      prompt: await loadPromptText(agent.promptFile),
    };
  }));

  return allPrompts;
};

const knowledgeCache = new Map();

export const getAgentKnowledge = async (agentKey) => {
  if (!knowledgeCache.has(agentKey)) {
    knowledgeCache.set(agentKey, loadAgentKnowledge(agentKey));
  }

  return await knowledgeCache.get(agentKey);
};

export const buildAgentSystemPrompt = async (agentKey, query) => {
  const knowledge = await getAgentKnowledge(agentKey);
  const queryTokens = Array.from(new Set(tokenize(query)));

  const rankedChunks = knowledge.chunks
    .map((chunk) => ({
      ...chunk,
      score: scoreChunk(chunk.text, queryTokens, knowledge.keywords),
    }))
    .sort((left, right) => right.score - left.score || left.text.length - right.text.length);

  const selectedChunks = rankedChunks.filter((chunk) => chunk.score > 0).slice(0, 4);
  const fallbackChunks = selectedChunks.length > 0 ? selectedChunks : rankedChunks.slice(0, 3);
  const allowedLinks = knowledge.urls.slice(0, 20);
  const recommendedLinks = selectRecommendedLinks(agentKey, query, allowedLinks);

  const contextText = fallbackChunks
    .map((chunk, index) => `[Fuente ${index + 1}: ${chunk.fileName} | bloque ${chunk.chunkIndex}]\n${chunk.text}`)
    .join('\n\n---\n\n');

  const systemSections = [knowledge.prompt.trim()];

  systemSections.push(`## REGLA DE ENLACES\nSolo puedes mencionar enlaces que aparezcan en la lista de ENLACES AUTORIZADOS. Si la lista está vacía, no incluyas ningún link ni inventes URLs. Si el usuario pide un link específico y no está en la lista, dile que no está disponible en la documentación.`);

  if (allowedLinks.length > 0) {
    systemSections.push(`## ENLACES AUTORIZADOS\n${allowedLinks.map((url) => `- ${url}`).join('\n')}`);
  }

  if (contextText) {
    systemSections.push(`## CONTEXTO RECUPERADO DESDE DOCUMENTOS\nUsa este material como referencia principal para responder. No lo cites textualmente; reinterpreta el contenido con lenguaje claro, preciso y respaldado.\n\n${contextText}`);
  }

  const systemPrompt = systemSections.join('\n\n');

  return {
    systemPrompt: systemPrompt.slice(0, MAX_CONTEXT_CHARS),
    allowedLinks,
    recommendedLinks,
    sources: fallbackChunks.map((chunk) => ({
      source: chunk.source,
      fileName: chunk.fileName,
      chunkIndex: chunk.chunkIndex,
      score: chunk.score,
    })),
  };
};

export { AGENT_CATALOG, normalizeText, getAllSystemPrompts };
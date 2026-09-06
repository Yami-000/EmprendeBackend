Resumen de la auditoría y cambios aplicados (Fase 1)

Título sugerido (Conventional Commit):
chore(security): remove exposed credentials, add sqlite dev persistence, standardize rag port, update docs

Descripción extendida (para el PR):

Este PR consolida la Fase 1 de la auditoría técnica y de seguridad llevada a cabo en el repositorio. Contiene limpieza de secretos, endurecimiento operativo mínimo, persistencia local para desarrollo y documentación viva que facilita la continuación de la modernización del pipeline RAG.

Cambios principales aplicados:
- Seguridad y limpieza:
  - Eliminado del árbol de trabajo el archivo de credenciales: `credentials/emprende-73e05-firebase-adminsdk-fbsvc-dc2b367ca8.json` (el archivo debe ser rotado y purgado del historial; ver notas abajo).
  - Añadida entrada `credentials/` y `data/` a `.gitignore`.
  - Eliminadas las dependencias `firebase` y `firebase-admin` de `package.json` (candidatas a remoción tras verificación en staging).

- Persistencia en desarrollo:
  - Reemplazado fallback SQLite in-memory por un archivo persistente en `./data/dev.sqlite`. La carpeta `data/` se crea automáticamente al inicializar la DB en modo `development`.

- Resiliencia y parámetros del pipeline:
  - `ai-service/api.py`: añadido `httpx.AsyncClient(timeout=60)` y `options.num_ctx = 4096` en el body enviado a Ollama.
  - `src/bot.js`: petición al RAG con `timeout: 60000` y manejo de error amigable al usuario cuando el servicio no responde.

- Documentación y artefactos generados:
  - `CONTEXTO.md`: contexto técnico completo (visión, inventario, RAG mapping, seguridad, roadmap).
  - `Bitacora.md`: bitácora viva con registro de la auditoría y checklist actualizado; Fase 1 marcada como validada.
  - `Diagramas.md`: diagramas Mermaid (arquitectura, secuencia y flujo RAG).

Pruebas realizadas:
- Smoke test local ejecutado con éxito:
  - Servicio RAG levantado en `http://0.0.0.0:11400` con `uvicorn ai-service.api:app --port 11400`.
  - Backend Node arrancó con `npm start` (`src/index.js`).
  - Persistencia SQLite en `C:\Visual\EmprendeBackend\data\dev.sqlite` sincronizada correctamente.

Acciones críticas que deben completarse ANTES de mezclar este PR:
1. Rotar la Service Account / credencial de Firebase inmediatamente (se considera comprometida).
2. Purga del historial Git para eliminar cualquier rastro del archivo sensible (usar `git-filter-repo` o BFG). No cerrar PR hasta completar la rotación y purga.

Instrucciones rápidas para purgado (local):
```bash
echo "credentials/" >> .gitignore
git rm --cached -r credentials/
git commit -m "chore(security): remove credentials from tracking"
# Reescribir historial (ejemplo con git-filter-repo)
git filter-repo --invert-paths --path credentials/emprende-73e05-firebase-adminsdk-fbsvc-dc2b367ca8.json
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin --force --all
git push origin --force --tags
```

Backlog prioritario (post-Fase1):
- Sanitización de fragments recuperados antes de su inclusión en el `system` prompt (mitigación de Prompt Injection).
- Modernización del chunking a token-based y evaluación/benchmark de vectorstore local (ChromaDB vs Qdrant/Faiss).

Notas adicionales y recomendaciones:
- No mergear hasta confirmar rotación de claves y purga del historial.
- Revisar en staging que la eliminación de `firebase` no afecta integraciones adicionales (CI, funciones cloud, etc.).
- Considerar añadir tests de integración pequeños que verifiquen endpoints críticos `/health` y `/chat` en pipelines CI.

Contacto: auditoría realizada por el equipo interno/IA (detalles en `CONTEXTO.md` y `Bitacora.md`).

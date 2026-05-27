import express from 'express';
import { ApolloServer } from '@apollo/server';
import { ApolloServerPluginLandingPageDisabled } from '@apollo/server/plugin/disabled';
import { expressMiddleware } from '@as-integrations/express5';
import typeDefs from './graphql/schemas.js';
import resolvers from './graphql/resolvers.js';
import models from './models/index.js';
import { extractBearerToken, verifyIdToken } from './config/firebaseAuth.js';

const app = express();

const allowedOrigins = new Set(
  String(process.env.CORS_ORIGINS ?? process.env.CORS_ORIGIN ?? '*')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean),
);

const isProduction = String(process.env.NODE_ENV ?? '').toLowerCase() === 'production';

app.use('/graphql', (req, res, next) => {
  const origin = req.headers.origin;

  if (isProduction && origin && !allowedOrigins.has('*') && !allowedOrigins.has(origin)) {
    return res.status(403).json({ error: 'Origen no permitido' });
  }

  return next();
});

app.use((req, res, next) => {
  const origin = req.headers.origin;

  if (!origin || allowedOrigins.has('*') || allowedOrigins.has(origin)) {
    res.header('Access-Control-Allow-Origin', allowedOrigins.has('*') ? '*' : origin ?? '*');
    res.header('Vary', 'Origin');
    res.header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
    res.header(
      'Access-Control-Allow-Headers',
      'Content-Type, Authorization, Apollo-Require-Preflight, apollo-require-preflight',
    );
  }

  if (req.method === 'OPTIONS') {
    return res.sendStatus(204);
  }

  return next();
});

const apolloServer = new ApolloServer({
  typeDefs,
  resolvers,
  plugins: isProduction ? [ApolloServerPluginLandingPageDisabled()] : []
});

await apolloServer.start();

app.get('/health', (_, res) => {
  res.status(200).json({ ok: true });
});

app.use(
  '/graphql',
  express.json({ limit: '20mb' }),
  expressMiddleware(apolloServer, {
    context: async ({ req }) => {
      const authorizationHeader = req.headers.authorization;
      const idToken = extractBearerToken(authorizationHeader);

      let authUser = null;
      if (idToken) {
        try {
          authUser = await verifyIdToken(idToken);
        } catch (error) {
          console.warn('No se pudo verificar el token de Firebase enviado en Authorization:', error.message);
        }
      }

      // En producción, exigir token válido para todas las operaciones GraphQL
      // excepto las operaciones de autenticación/registro.
      const publicOperations = new Set(["signUpEmailPassword", "loginEmailPassword", "loginUsuario"]);
      const operationName = req.body && typeof req.body === 'object' ? req.body.operationName : null;

      if (isProduction) {
        const isPublicOp = operationName && publicOperations.has(operationName);
        if (!isPublicOp && !authUser) {
          // Lanzar error para que GraphQL responda con un error de autenticación
          throw new Error('No autenticado. Se requiere un token de Firebase válido.');
        }
      }

      return { models, authUser, idToken };
    }
  })
);

export default app;
import express from 'express';

const app = express();

const allowedOrigins = new Set(
  String(process.env.CORS_ORIGINS ?? process.env.CORS_ORIGIN ?? '*')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean),
);

app.use((req, res, next) => {
  const origin = req.headers.origin;

  if (!origin || allowedOrigins.has('*') || allowedOrigins.has(origin)) {
    res.header('Access-Control-Allow-Origin', allowedOrigins.has('*') ? '*' : origin ?? '*');
    res.header('Vary', 'Origin');
    res.header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
    res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  }

  if (req.method === 'OPTIONS') {
    return res.sendStatus(204);
  }

  return next();
});

app.get('/health', (_, res) => {
  res.status(200).json({ ok: true });
});

export default app;
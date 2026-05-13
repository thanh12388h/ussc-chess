// Vercel Serverless Function - Shared Quiz State Management
// This stores quiz open/closed state shared across all clients

let quizOpenState = false;
let lastUpdateTime = Date.now();

export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method === 'GET') {
    // GET /api/quiz-state -> return current state
    return res.status(200).json({
      quizOpen: quizOpenState,
      timestamp: lastUpdateTime,
    });
  }

  if (req.method === 'POST') {
    // POST /api/quiz-state -> update state
    const { quizOpen } = req.body || {};
    if (typeof quizOpen === 'boolean') {
      quizOpenState = quizOpen;
      lastUpdateTime = Date.now();
      return res.status(200).json({
        success: true,
        quizOpen: quizOpenState,
        timestamp: lastUpdateTime,
      });
    }
    return res.status(400).json({ error: 'Invalid request' });
  }

  return res.status(405).json({ error: 'Method not allowed' });
}

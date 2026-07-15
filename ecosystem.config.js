// PM2 process config for OpenAlgo (multi-tenant fork).
//
// OpenAlgo is a Python app run under Gunicorn with the eventlet worker. It is
// NOT a Node app, so PM2 runs the gunicorn binary directly (interpreter: none).
//
// IMPORTANT:
//   * -w 1 (single worker) is REQUIRED — WebSocket/SocketIO + the in-process
//     WebSocket proxy (port 8765) and ZMQ bus assume one process. Never use
//     PM2 cluster mode or instances > 1.
//   * The app reads its config from .env itself (python-dotenv), so env vars
//     do not need to be duplicated here. cwd MUST be the project root so .env
//     is found and `app:app` resolves.
//
// Prereqs (once):
//   cd /opt/openalgo
//   pip install uv && uv sync
//   uv pip install "gunicorn>=25,<26" eventlet     # not in the default deps
//   # (for an EXISTING db being upgraded) uv run alembic upgrade head
//
// Start:
//   pm2 start ecosystem.config.js
//   pm2 save && pm2 startup      # run the printed command to enable on boot

module.exports = {
  apps: [
    {
      name: 'openalgo',
      // Absolute path to the venv gunicorn. Adjust if your project lives
      // elsewhere or your venv is not `.venv`.
      script: '/opt/openalgo/.venv/bin/gunicorn',
      interpreter: 'none', // gunicorn is an executable, not a JS file
      cwd: '/opt/openalgo',

      // --bind 127.0.0.1:5000 when behind nginx (recommended). Use
      // 0.0.0.0:5000 only if PM2/gunicorn is exposed directly to the internet.
      args: '--worker-class eventlet -w 1 --bind 127.0.0.1:5000 --timeout 300 --graceful-timeout 30 app:app',

      instances: 1,
      exec_mode: 'fork', // NOT cluster — single process only
      autorestart: true,
      max_restarts: 10,
      min_uptime: '20s',
      kill_timeout: 10000, // give eventlet/websocket a moment to shut down
      max_memory_restart: '1500M',

      // PM2's own log files (app also writes to ./log per LOG_TO_FILE in .env).
      out_file: '/opt/openalgo/log/pm2-out.log',
      error_file: '/opt/openalgo/log/pm2-error.log',
      merge_logs: true,
      time: true,
    },
  ],
}

# Windows / PowerShell notes
- Windows PowerShell 5.1 does not support `&&`. Use `;` to chain commands, or run them separately.
- Check tools first: `node -v`, `npm -v`, `python --version` (or `py --version`), `git --version`. If missing, tell me what to install and stop.
- Set environment variables for a session: `$env:NAME="value"`. Prefer `.env` files loaded by the app.
- Use forward slashes in code paths when possible; avoid hardcoding `C:\` paths.
- Activate a Python venv with `.\.venv\Scripts\Activate.ps1`. If blocked, tell me to run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- Long paths and spaces: quote paths (my user folder name contains a space).
- Line endings: set `git config core.autocrlf true` if warnings appear.
- Port in use: `netstat -ano | findstr :<port>` then ask before killing any process.

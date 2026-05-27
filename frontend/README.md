# Pipeline Solar Modernizacao

Frontend React + Vite + TypeScript para operar o backend local em `http://127.0.0.1:8765`.

## Rodar em desenvolvimento

```powershell
cd "C:\Users\User\Documents\New project\Pipeline Solar App - Modernizacao\frontend"
npm install
npm run dev
```

## Rodar com Tauri

```powershell
cd "C:\Users\User\Documents\New project\Pipeline Solar App - Modernizacao\frontend"
npm install
npm run tauri:dev
```

## Build

```powershell
cd "C:\Users\User\Documents\New project\Pipeline Solar App - Modernizacao\frontend"
npm install
npm run build
npm run tauri:build
```

## Contrato de API usado pelo frontend

O frontend opera contra `http://127.0.0.1:8765` e espera estes endpoints:

- `GET /api/settings`: retorna `baseDir`, `downloadsDir`, `outputDir` e `defaultDays`.
- `POST /api/settings`: salva `baseDir`, `downloadsDir`, `outputDir` e `defaultDays`.
- `POST /api/diagnostics/run`: executa diagnostico e retorna `status`, `message` ou `summary`, `items` ou `checks`, e opcionalmente `logs`.
- `GET /api/history`: retorna uma lista ou objeto com `items`/`history` contendo `id`, `job_id`, `client`, `status`, `started_at`, `finished_at`, `output` ou `output_path`.
- `POST /api/history/open-output`: abre a saida de um item historico ou job atual usando `id`, `job_id`, `output` ou `output_path`.
- `POST /api/logs/export`: exporta os logs da execucao atual usando `job_id`, `logs` e dados de diagnostico quando disponiveis.

Os fluxos existentes de operacao continuam usando os endpoints ja previstos no app: `GET /api/health`, `GET /api/clients`, `POST /api/clients/create`, `POST /api/downloads/preview`, `POST /api/pipeline/run`, `GET /api/jobs/:jobId` e `POST /api/open/client`.

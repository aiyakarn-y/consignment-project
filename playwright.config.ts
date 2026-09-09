import { defineConfig } from './frontend/node_modules/@playwright/test';
import path from 'node:path';
const runId=Date.now().toString();
export default defineConfig({
  testDir:'./tests/ui',fullyParallel:false,workers:1,timeout:120_000,
  expect:{timeout:20_000},
  outputDir:'_wrx-output/evidence/playwright',
  reporter:[['list'],['json',{outputFile:'_wrx-output/evidence/playwright-results.json'}]],
  use:{baseURL:'http://127.0.0.1:3118',viewport:{width:1512,height:1100},trace:'retain-on-failure',screenshot:'only-on-failure'},
  webServer:[
    {command:'.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8101',url:'http://127.0.0.1:8101/api/health',reuseExistingServer:false,timeout:30_000,env:{CONSIGN_DATA_DIR:path.resolve('data/test/e2e',runId)}},
    {command:'bash scripts/start-e2e.sh',url:'http://127.0.0.1:3118',reuseExistingServer:false,timeout:120_000,env:{CONSIGN_BACKEND_URL:'http://127.0.0.1:8101',CONSIGN_NEXT_DIR:'.next-e2e-prod',NEXT_TELEMETRY_DISABLED:'1'}}
  ]
});

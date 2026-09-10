import { test, expect } from '../../frontend/node_modules/@playwright/test';
import { createHmac } from 'node:crypto';
import { GET as download } from '../../frontend/app/cloud-download/route';
import { POST as uploadToken } from '../../frontend/app/cloud-storage/route';

test('cloud handlers independently reject missing credentials and invalid download tickets', async () => {
  const names=['CONSIGN_BETA_MODE','CONSIGN_BETA_PASSWORD','CONSIGN_STORAGE_DRIVER','CONSIGN_BLOB_PREFIX','BLOB_READ_WRITE_TOKEN'];
  const previous=Object.fromEntries(names.map(name=>[name,process.env[name]]));
  Object.assign(process.env,{CONSIGN_BETA_MODE:'1',CONSIGN_BETA_PASSWORD:'fixture-password-123',CONSIGN_STORAGE_DRIVER:'vercel_blob',CONSIGN_BLOB_PREFIX:'test',BLOB_READ_WRITE_TOKEN:'vercel_blob_rw_TestStore_fixture'});
  const headers={Authorization:'Basic '+Buffer.from('beta:fixture-password-123').toString('base64')};
  const signed=(body:unknown)=>{const encoded=Buffer.from(JSON.stringify(body)).toString('base64url');return encoded+'.'+createHmac('sha256',process.env.BLOB_READ_WRITE_TOKEN!).update(encoded).digest('hex');};
  try {
    expect((await download(new Request('http://localhost/cloud-download'))).status).toBe(401);
    expect((await uploadToken(new Request('http://localhost/cloud-storage',{method:'POST'}))).status).toBe(401);
    for(const ticket of ['invalid', signed({key:'test/exports/'+'a'.repeat(32)+'.xlsx',expires:1}),signed({key:'test/state/system.json',expires:Math.floor(Date.now()/1000)+100}),signed({key:'production/exports/'+'a'.repeat(32)+'.xlsx',expires:Math.floor(Date.now()/1000)+100})]) {
      expect((await download(new Request('http://localhost/cloud-download?ticket='+ticket,{headers}))).status).toBe(403);
    }
    delete process.env.CONSIGN_BETA_PASSWORD;
    expect((await uploadToken(new Request('http://localhost/cloud-storage',{method:'POST',headers}))).status).toBe(503);
  } finally {
    for(const name of names){if(previous[name]===undefined)delete process.env[name];else process.env[name]=previous[name];}
  }
});

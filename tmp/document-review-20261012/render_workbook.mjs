import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const wb = await SpreadsheetFile.importXlsx(await FileBlob.load('C:/Users/rodri/Downloads/Retaceo (4).xlsx'));
console.log((await wb.inspect({kind:'workbook,sheet,table',maxChars:3500,tableMaxRows:3,tableMaxCols:5})).ndjson);
for (const [name, range] of [['Retaceo','B2:I19'],['Datos','B2:N22']]) {
  const blob = await wb.render({sheetName:name,range,scale:1.5,format:'png'});
  await fs.writeFile(new URL(`${name}.png`,import.meta.url),new Uint8Array(await blob.arrayBuffer()));
  console.log(`Rendered ${name}`);
}

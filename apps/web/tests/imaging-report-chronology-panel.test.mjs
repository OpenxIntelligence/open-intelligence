import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {sourceIndex} from './source-images-fixtures.mjs';
let ImagingReportChronology, SourceReading;
before(async()=>{
 const outDir='.test-dist/imaging-report-chronology-ui';
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/imaging-report-chronology-panel.tsx'),
  outDir,emptyOutDir:true,rollupOptions:{output:{entryFileNames:'chronology.mjs'}}}});
 ({ImagingReportChronology}=await import(pathToFileURL(resolve(outDir,'chronology.mjs')).href));
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/source-reading.tsx'),
  outDir:'.test-dist/imaging-source-reader',emptyOutDir:true,
  rollupOptions:{output:{entryFileNames:'source-reading.mjs'}}}});
 ({SourceReading}=await import(pathToFileURL(resolve('.test-dist/imaging-source-reader/source-reading.mjs')).href));
});
const sources=()=>{
 const original=sourceIndex().sources[0];
 return [original, {...original,source_id:'SRC-'+'B'.repeat(32),document_id:'REPORT-OLD',version:1,
   event_date:'2025-12-01',state:'superseded',sha256:'b'.repeat(64)},
  {...original,source_id:'SRC-'+'C'.repeat(32),document_id:'REPORT-NEW',version:2,
   event_date:'2026-03-17',state:'current',sha256:'c'.repeat(64)}];
};
test('chronology displays latest recorded date first and keeps exact versions and statuses',()=>{
 const html=renderToStaticMarkup(createElement(ImagingReportChronology,{sources:sources(),selectedSourceId:null,onSelect(){}}));
 assert.match(html,/Imaging report chronology/);
 assert.equal((html.match(/data-testid="imaging-chronology-version"/g)||[]).length,3);
 assert.ok(html.indexOf('2026-03-17')<html.indexOf('2025-12-01'));
 assert.match(html,/REPORT-OLD/);assert.match(html,/superseded/);
 assert.match(html,/No clinical image or disease progression comparison/);
 assert.equal((html.match(/data-testid="imaging-select-version"/g)||[]).length,3);
});
test('non-imaging reports do not appear in summary and empty state is explicit',()=>{
 const nonImaging={...sources()[0],kind:'pathology',document_id:'NOT-IMAGING'};
 const html=renderToStaticMarkup(createElement(ImagingReportChronology,{sources:[nonImaging],selectedSourceId:null,onSelect(){}}));
 assert.match(html,/No imaging report versions are in the currently loaded case index/);
 assert.ok(!html.includes('NOT-IMAGING'));
 assert.ok(!html.includes('imaging-select-version'));
});
test('the existing source reader retains source-original actions beneath chronology without auto-loading pixels',()=>{
 const index=sourceIndex();index.sources=sources();
 const html=renderToStaticMarkup(createElement(SourceReading,{index,kind:'imaging',view:'clinical',filters:{query:'',versionState:'all'},
  onFiltersChange(){},busy:false,questionBusy:false,onAskQuestion(){},onOpenOriginal(){},onInspectImages(){},
  onDownloadImage(){},onPreviewImage(){},onDismissImagePreview(){},onDismissImages(){}}));
 assert.equal((html.match(/data-testid="source-version"/g)||[]).length,3);
 assert.equal((html.match(/data-testid="open-original"/g)||[]).length,3);
 assert.equal((html.match(/data-testid="source-images-open"/g)||[]).length,2);
 assert.match(html,/imaging-chronology-version/);
 assert.ok(!html.includes('source-image-preview-open'));
});

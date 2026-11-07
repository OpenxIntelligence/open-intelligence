import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {sourceIndex,sourceId} from './source-images-fixtures.mjs';

let SourceReading;
before(async()=>{
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/source-reading.tsx'),
  outDir:'.test-dist/source-images-ui',emptyOutDir:true,
  rollupOptions:{output:{entryFileNames:'source-reading.mjs'}}}});
 ({SourceReading}=await import(pathToFileURL(resolve('.test-dist/source-images-ui/source-reading.mjs')).href));
});

test('existing source reader exposes image inspection only for a current imaging source and retains original/question actions',()=>{
 const index=sourceIndex();index.sources.push({...index.sources[0],source_id:'SRC-'+'B'.repeat(32),kind:'pathology'},
  {...index.sources[0],source_id:'SRC-'+'D'.repeat(32),state:'superseded',version:2});
 const html=renderToStaticMarkup(createElement(SourceReading,{index,view:'patient',filters:{query:'',versionState:'all'},
  onFiltersChange(){},busy:false,questionBusy:false,onAskQuestion(){},onOpenOriginal(){},onInspectImages(){},
  sourceImages:null,sourceImagesPhase:'idle',sourceImagesMessage:'',sourceImageDownload:null,
  sourceImageDownloadPhase:'idle',sourceImageDownloadMessage:'',sourceImagePreview:null,
  sourceImagePreviewPhase:'idle',sourceImagePreviewMessage:'',onPreviewImage(){},onDismissImagePreview(){},
  onDownloadImage(){},onDismissImages(){}}));
 assert.equal((html.match(/data-testid="source-images-open"/g)||[]).length,1,'one current imaging original has its own governed inspection action');
 assert.equal((html.match(/data-testid="source-image-preview-open"/g)||[]).length,0,'preview appears only after an authorized image list is loaded');
 assert.equal((html.match(/data-testid="open-original"/g)||[]).length,3,'text originals retain their independent action');
 assert.equal((html.match(/data-testid="ask-source-question"/g)||[]).length,1);
 assert.ok(html.includes(sourceId));assert.ok(!html.includes('type="file"'),'image inspection does not introduce automatic image upload');
});


test('loaded image list exposes a non-diagnostic preview action beside exact DICOM download',async()=>{
 const {images}=await import('./source-images-fixtures.mjs');
 const html=renderToStaticMarkup(createElement(SourceReading,{index:sourceIndex(),view:'patient',filters:{query:'',versionState:'all'},
  onFiltersChange(){},busy:false,questionBusy:false,onAskQuestion(){},onOpenOriginal(){},onInspectImages(){},
  sourceImages:images(),sourceImagesSourceId:sourceId,sourceImagesPhase:'ready',sourceImagesMessage:'ready',
  sourceImageDownload:null,sourceImageDownloadPhase:'idle',sourceImageDownloadMessage:'',
  sourceImagePreview:null,sourceImagePreviewPhase:'idle',sourceImagePreviewMessage:'',
  onPreviewImage(){},onDismissImagePreview(){},onDownloadImage(){},onDismissImages(){}}));
 assert.equal((html.match(/data-testid="source-image-preview-open"/g)||[]).length,1);
 assert.equal((html.match(/data-testid="source-image-download"/g)||[]).length,1);
 assert.match(html,/Original custody plus a bounded non-diagnostic preview only\. No diagnostic viewer/);
});

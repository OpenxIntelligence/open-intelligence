import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {sourceIndex,images,image} from './source-images-fixtures.mjs';
let SourceReading;
before(async()=>{
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/source-reading.tsx'),
  outDir:'.test-dist/image-studies-ui',emptyOutDir:true,
  rollupOptions:{output:{entryFileNames:'source-reading.mjs'}}}});
 ({SourceReading}=await import(pathToFileURL(resolve('.test-dist/image-studies-ui/source-reading.mjs')).href));
});
const render=loaded=>renderToStaticMarkup(createElement(SourceReading,{
 index:sourceIndex(),view:'clinical',filters:{query:'',versionState:'all'},onFiltersChange(){},busy:false,
 questionBusy:false,onAskQuestion(){},onOpenOriginal(){},onInspectImages(){},onDownloadImage(){},
 onPreviewImage(){},onDismissImages(){},onDismissImagePreview(){},
 sourceImages:loaded,sourceImagesSourceId:loaded.source_id,sourceImagesPhase:'ready',sourceImagesMessage:'ready',
 sourceImageDownload:null,sourceImageDownloadPhase:'idle',sourceImageDownloadMessage:'',
 sourceImagePreview:null,sourceImagePreviewPhase:'idle',sourceImagePreviewMessage:'',
}));
test('imaging inspection groups multiple exact originals by study then series, retaining all source actions',()=>{
 const loaded=images();const one=loaded.images[0];
 loaded.images.push({...image(),image_id:'IMG-'+'D'.repeat(32),sop_uid:'2.25.104'},
  {...image(),image_id:'IMG-'+'E'.repeat(32),study_uid:'2.25.105',series_uid:'2.25.106',sop_uid:'2.25.107'},
  {...image(),image_id:'IMG-'+'F'.repeat(32),series_uid:'2.25.109',sop_uid:'2.25.110'});
 const html=render(loaded);
 assert.equal((html.match(/data-testid="source-image-study"/g)||[]).length,2);
 assert.equal((html.match(/data-testid="source-image-series"/g)||[]).length,3);
 assert.equal((html.match(/data-testid="source-image-row"/g)||[]).length,4);
 assert.equal((html.match(/data-testid="source-image-preview-open"/g)||[]).length,4);
 assert.equal((html.match(/data-testid="source-image-download"/g)||[]).length,4);
 assert.equal((html.match(/data-testid="source-images-receipt"/g)||[]).length,1);
 assert.ok(html.includes(one.sha256));
 assert.ok(html.indexOf('Study <code>2.25.101')<html.indexOf('Study <code>2.25.105'));
 assert.ok(html.indexOf('Series <code>2.25.102')<html.indexOf('Series <code>2.25.109'));
 assert.ok(!html.includes('diagnostic viewer available'));
});
test('zero originals preserves the honest empty state and does not fabricate a study',()=>{
 const loaded=images();loaded.images=[];
 const html=render(loaded);
 assert.match(html,/No originals are linked to this current report/);
 assert.equal((html.match(/data-testid="source-image-study"/g)||[]).length,0);
});

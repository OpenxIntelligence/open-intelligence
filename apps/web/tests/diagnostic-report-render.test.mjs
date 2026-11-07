import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {sourceIndex} from './source-images-fixtures.mjs';
let SourceReading;
before(async()=>{
  const outDir='.test-dist/diagnostic-source-reader';
  await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/source-reading.tsx'),outDir,
    emptyOutDir:true,rollupOptions:{output:{entryFileNames:'reader.mjs'}}}});
  ({SourceReading}=await import(pathToFileURL(resolve(outDir,'reader.mjs')).href));
});
function render(kind='pathology',filters={query:'',versionState:'all'},count=1) {
  const index=sourceIndex();
  index.sources=Array.from({length:count},(_,i)=>({...index.sources[0],kind,source_id:'SOURCE-'+i,document_id:'REPORT-'+i,specimen_id:null}));
  index.source_reported_assertions=[{...index.source_reported_assertions[0],source_id:'SOURCE-0',source_statement:'Literal <script>alert(1)</script>'},
    {...index.source_reported_assertions[0],source_id:'SOURCE-0',source_line:9,reported_state:'pending',source_statement:'Awaiting fictional report'}];
  return renderToStaticMarkup(createElement(SourceReading,{index,kind,view:'patient',filters,
    onFiltersChange(){},busy:false,questionBusy:false,onAskQuestion(){},onOpenOriginal(){}}));
}
test('pathology and molecular expose labelled controls with raw states and absent specimen',()=>{
  for(const kind of ['pathology','molecular']) {
    const html=render(kind);
    assert.match(html,/for="diagnostic-specimen"/);assert.match(html,/for="diagnostic-reported-state"/);
    assert.match(html,/value="state:not-reported"/);assert.match(html,/value="state:pending"/);
    assert.match(html,/Not recorded \(1 versions\)/);
    assert.match(html,/data-testid="open-original"/);assert.match(html,/data-testid="ask-source-question"/);
    assert.match(html,/&lt;script&gt;alert\(1\)&lt;\/script&gt;/);assert.ok(!html.includes('<script>'));
  }
});
test('filtering states clearly announces partial quotations while retaining exact original action',()=>{
  const html=render('molecular',{query:'',versionState:'all',reportedState:'pending'});
  assert.match(html,/Showing 1 of 2 quoted statements/);assert.match(html,/line 9/);
  assert.ok(!html.includes('alert(1)'));assert.match(html,/data-testid="open-original"/);
});
test('large report collections render a bounded page with a named page navigator',()=>{
  const html=render('pathology',{query:'',versionState:'all'},30);
  assert.equal((html.match(/data-testid="source-version"/g)||[]).length,12);
  assert.match(html,/aria-label="Report pages"/);assert.match(html,/Page 1 of 3/);
  assert.match(html,/1–12 of 30 matching versions/);
});
test('other source domains retain their existing reader without new diagnostic controls',()=>{
  for(const kind of ['imaging','laboratory','clinical'])assert.ok(!render(kind).includes('diagnostic-report-controls'));
});

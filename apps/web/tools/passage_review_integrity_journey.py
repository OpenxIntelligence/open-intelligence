"""Corrupt copies of real fictional review reads, never the stored originals."""


def exercise(cd, click, value, expected_hash):
    panel = "[data-testid=passage-review-preparation]"
    # Keep the real 200, independently authorized API response as the baseline;
    # alter only the response delivered to the browser. No database writes.
    for mutation in ("digest", "page", "original"):
        cd.evaluate(r"""(mutation => {
          const original=window.fetch;
          const probe={original,count:0,mutation};
          window.__passageIntegrityProbe=probe;
          const order=v=>Array.isArray(v)?v.map(order):v&&typeof v==='object'
            ?Object.fromEntries(Object.keys(v).sort().map(k=>[k,order(v[k])])):v;
          window.fetch=async(input,init)=>{
            const path=new URL(typeof input==='string'?input:input.url,location.href).pathname;
            const response=await original(input,init);
            if(!path.endsWith('/review-preparation'))return response;
            if(response.status!==200)throw Error('Integrity probe requires an authorized response');
            probe.count++;
            const body=await response.json();
            if(mutation==='digest')body.packet_sha256='0'.repeat(64);
            else {
              if(mutation==='page')body.selection.page++;
              else body.selection.original_sha256='0'.repeat(64);
              const {packet_sha256,source_access_receipt_id,...content}=body;
              const ascii=JSON.stringify(order(content)).replace(/[\u007f-\uffff]/g,
                ch=>'\\u'+ch.charCodeAt(0).toString(16).padStart(4,'0'));
              body.packet_sha256=Array.from(new Uint8Array(await crypto.subtle.digest(
                'SHA-256',new TextEncoder().encode(ascii))),b=>b.toString(16).padStart(2,'0')).join('');
            }
            return new Response(JSON.stringify(body),{status:200,headers:response.headers});
          };
        })(""" + repr(mutation) + ")")
        try:
            click('Prepare independent verification')
            cd.wait("document.querySelector('[data-testid=saved-passage-questions]')"
                    "?.textContent.includes('Review preparation unavailable.')",
                    'altered '+mutation+' is rejected before review display')
            assert cd.evaluate('window.__passageIntegrityProbe.count') == 1
            assert cd.evaluate("!document.querySelector('"+panel+"')"), (
                'An altered packet must clear previously inspected preparation')
            assert cd.evaluate("Boolean(document.querySelector('[data-testid=source-index]'))"), (
                'Integrity failure must not invent withdrawal of separate source authority')
        finally:
            cd.evaluate('window.fetch=window.__passageIntegrityProbe.original;'
                        'delete window.__passageIntegrityProbe')
        click('Prepare independent verification')
        cd.wait("Boolean(document.querySelector('"+panel+" code'))", 'fresh verified preparation')
        assert cd.evaluate("document.querySelector('"+panel+" code').textContent") == expected_hash

    # A read is not finished when fetch returns: real Web Crypto is asynchronous.
    # Hold its completed result, change local intent, then deliver the old hash.
    cd.evaluate(r"""(() => {
      const original=crypto.subtle.digest;
      const hold={original,waiting:false,seen:false,release:null};
      window.__passageDigestHold=hold;
      crypto.subtle.digest=async function(algorithm,bytes){
        const result=await original.call(this,algorithm,bytes);
        const text=new TextDecoder().decode(bytes);
        if(!hold.seen&&text.includes('"contract":"oi.pg-passage-review-preparation/1"')){
          hold.seen=true;hold.waiting=true;
          return new Promise(resolve=>{hold.release=()=>{
            hold.waiting=false;hold.release=null;resolve(result);
          };});
        }
        return result;
      };
    })()""")
    try:
        click('Prepare independent verification')
        cd.wait('window.__passageDigestHold.waiting', 'actual review digest held')
        value('[data-testid=passage-evidence-query]', 'changed fictional query')
        cd.evaluate('window.__passageDigestHold.release()')
        cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        assert cd.evaluate("!document.querySelector('"+panel+"')"), (
            'Late digest completion cannot restore a preparation after local intent changes')
    finally:
        cd.evaluate('crypto.subtle.digest=window.__passageDigestHold.original;'
                    'window.__passageDigestHold.release?.();delete window.__passageDigestHold')
    click('Prepare independent verification')
    cd.wait("Boolean(document.querySelector('"+panel+" code'))", 'fresh read after digest cancellation')
    assert cd.evaluate("document.querySelector('"+panel+" code').textContent") == expected_hash
    print('PASS PASSAGE REVIEW INTEGRITY: real authorized packet copies with a wrong digest, '
          'rehashed PDF page and rehashed original hash are withheld; fresh reads restore the '
          'unchanged preparation; late actual digest cannot revive display after query edit. '
          'No Review return, clinical approval or source mutation.')

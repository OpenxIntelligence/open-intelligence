import {useLayoutEffect,useRef,useState} from 'react';

type Destination={id:string;label:string};

export function PageContents(){
  const container=useRef<HTMLDivElement>(null);
  const menu=useRef<HTMLDetailsElement>(null);
  const [destinations,setDestinations]=useState<Destination[]>([]);

  useLayoutEffect(()=>{
    const main=container.current?.closest('main');
    if(!main)return;
    function refresh(){
      if(!main)return;
      const result=Array.from(main.querySelectorAll<HTMLElement>('[data-workspace-anchor][id]'))
        .filter(el=>el.checkVisibility())
        .map(el=>({id:el.id,label:el.dataset.workspaceAnchor!}));
      setDestinations(previous=>previous.length===result.length&&
        previous.every((entry,i)=>entry.id===result[i].id&&entry.label===result[i].label)?previous:result);
    }
    refresh();
    const observer=new MutationObserver(refresh);
    observer.observe(main,{childList:true,subtree:true,attributes:true,attributeFilter:['open','hidden','id','data-workspace-anchor']});
    return ()=>observer.disconnect();
  },[]);

  return <div ref={container} className="page-contents">
    {destinations.length>1&&<details ref={menu}>
      <summary>On this page</summary>
      <nav aria-label="On this page">{destinations.map(({id,label})=>
        <a key={id} href={'#'+id} onClick={event=>{
          if(event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
          event.preventDefault();
          const target=document.getElementById(id);
          if(!target?.checkVisibility()||!container.current?.closest('main')?.contains(target))return;
          if(menu.current)menu.current.open=false;
          if(target.tabIndex<0)target.tabIndex=-1;
          target.focus({preventScroll:true});
          target.scrollIntoView({block:'start'});
        }}>{label}</a>
      )}</nav>
    </details>}
  </div>;
}

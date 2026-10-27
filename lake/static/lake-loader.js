const L_PATH='M240 281 C224 280 216 296 215 323 C214 354 214 379 222 392 C232 430 221 480 221 519 M222 392 C204 399 181 406 158 409 M221 519 C219 540 204 561 188 562 C172 562 164 549 168 534 C172 517 188 514 200 520 C215 526 220 542 235 551';
export function lakeLoader({size='md',mode='indeterminate',progress=0,label='Loading',signature=false}={}){
 const px={sm:16,md:32,lg:96}[size]||32, p=Math.max(0,Math.min(1,Number(progress)||0));
 const root=document.createElement('span');root.className=`lake-loader lake-loader-${size}${mode==='determinate'?' is-determinate':''}${signature?' is-signature':''}`;root.setAttribute('role','status');root.setAttribute('aria-live','polite');root.setAttribute('aria-label',label);root.style.setProperty('--loader-size',px+'px');root.style.setProperty('--loader-progress',String(p));
 root.innerHTML=`<svg viewBox="145 270 150 310" width="${px}" height="${px}" aria-hidden="true" focusable="false"><path class="lake-loader-stroke" pathLength="1" d="${L_PATH}"/></svg><span class="lake-loader-label">${label}</span>`;return root;
}
export class LakeLoader extends HTMLElement{
 static observedAttributes=['size','mode','progress','label','signature'];
 connectedCallback(){this.render()}
 attributeChangedCallback(){if(this.isConnected)this.render()}
 render(){const el=lakeLoader({size:this.getAttribute('size')||'md',mode:this.getAttribute('mode')||'indeterminate',progress:this.getAttribute('progress')||0,label:this.getAttribute('label')||'Loading',signature:this.hasAttribute('signature')});this.replaceChildren(...el.childNodes);this.className=el.className;this.setAttribute('role','status');this.setAttribute('aria-live','polite');this.setAttribute('aria-label',el.getAttribute('aria-label'));this.style.cssText=el.style.cssText}
}
if(!customElements.get('lake-loader'))customElements.define('lake-loader',LakeLoader);

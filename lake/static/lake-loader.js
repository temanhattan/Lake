const L_PATH='M159 17 C176 18 194 39 198 65 C203 93 185 113 161 124 C150 130 144 139 159 147 M159 147 L159 297 M159 147 L105 147 M159 297 C159 335 160 366 158 387 C154 419 137 439 112 439 C88 438 77 420 82 399 C87 378 105 367 126 371 C145 373 158 385 169 398';
export function lakeLoader({size='md',mode='indeterminate',progress=0,label='Loading',signature=false}={}){
 const px={sm:16,md:32,lg:96}[size]||32, p=Math.max(0,Math.min(1,Number(progress)||0));
 const root=document.createElement('span');root.className=`lake-loader lake-loader-${size}${mode==='determinate'?' is-determinate':''}${signature?' is-signature':''}`;root.setAttribute('role','status');root.setAttribute('aria-live','polite');root.setAttribute('aria-label',label);root.style.setProperty('--loader-size',px+'px');root.style.setProperty('--loader-progress',String(p));
 root.innerHTML=`<svg viewBox="65 0 155 465" width="${px}" height="${px}" aria-hidden="true" focusable="false"><path class="lake-loader-stroke" pathLength="1" d="${L_PATH}"/></svg><span class="lake-loader-label">${label}</span>`;return root;
}
export class LakeLoader extends HTMLElement{
 static observedAttributes=['size','mode','progress','label','signature'];
 connectedCallback(){this.render()}
 attributeChangedCallback(){if(this.isConnected)this.render()}
 render(){const el=lakeLoader({size:this.getAttribute('size')||'md',mode:this.getAttribute('mode')||'indeterminate',progress:this.getAttribute('progress')||0,label:this.getAttribute('label')||'Loading',signature:this.hasAttribute('signature')});this.replaceChildren(...el.childNodes);this.className=el.className;this.setAttribute('role','status');this.setAttribute('aria-live','polite');this.setAttribute('aria-label',el.getAttribute('aria-label'));this.style.cssText=el.style.cssText}
}
if(!customElements.get('lake-loader'))customElements.define('lake-loader',LakeLoader);

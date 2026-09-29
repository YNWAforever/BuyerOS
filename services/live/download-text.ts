/** Keep export downloads local to the authorized response body. */
export function downloadText(body:string,contentType:string,filename:string):void{
  const url=URL.createObjectURL(new Blob([body],{type:contentType}));
  const link=document.createElement('a');
  link.href=url;link.download=filename;
  document.body.appendChild(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

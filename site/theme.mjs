/** Persistent appearance control; no network calls or prediction-state changes. */
export const THEME_KEY="football-ai-lab-theme";
export const safeTheme=value=>value==="light"?"light":"dark";
export const oppositeTheme=value=>safeTheme(value)==="dark"?"light":"dark";

export function storedTheme(storage){
  try{return safeTheme(storage?.getItem(THEME_KEY));}
  catch{return "dark";}
}
export function applyTheme(theme,{root,button,meta}={}){
  const value=safeTheme(theme);
  if(root){
    root.dataset.theme=value;
    root.style.colorScheme=value;
  }
  if(button){
    const light=value==="light";
    button.setAttribute("aria-pressed",String(light));
    button.setAttribute("aria-label",light?"Activar modo oscuro":"Activar modo claro");
    button.title=light?"Cambiar a modo oscuro":"Cambiar a modo claro";
    const icon=button.querySelector(".theme-toggle-icon");
    const label=button.querySelector(".theme-toggle-label");
    if(icon)icon.textContent=light?"☀":"☾";
    if(label)label.textContent=light?"Claro":"Oscuro";
  }
  if(meta)meta.content=value==="light"?"#f3f6fb":"#061522";
  return value;
}
export function installTheme(documentLike,storage){
  const button=documentLike.getElementById("themeToggle");
  const context={
    root:documentLike.documentElement,
    button,
    meta:documentLike.querySelector('meta[name="theme-color"]')
  };
  let theme=applyTheme(storedTheme(storage),context);
  button?.addEventListener("click",()=>{
    theme=applyTheme(oppositeTheme(theme),context);
    try{storage?.setItem(THEME_KEY,theme);}catch{/* Disabled storage: toggle still works. */}
  });
  return theme;
}

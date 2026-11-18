import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {THEME_KEY,safeTheme,oppositeTheme,storedTheme,applyTheme,installTheme} from "../theme.mjs";

function controls(){
  const events={};
  const icon={textContent:"☾"},label={textContent:"Oscuro"};
  const attrs={};
  const button={
    title:"",
    setAttribute(name,value){attrs[name]=value;},
    querySelector(sel){return sel===".theme-toggle-icon"?icon:sel===".theme-toggle-label"?label:null;},
    addEventListener(name,handler){events[name]=handler;}
  };
  const root={dataset:{},style:{}},meta={content:""};
  const documentLike={
    documentElement:root,
    getElementById(name){return name==="themeToggle"?button:null;},
    querySelector(sel){return sel==='meta[name="theme-color"]'?meta:null;}
  };
  return {events,icon,label,attrs,button,root,meta,documentLike};
}

test("only explicit light preference enables light theme",()=>{
  assert.equal(safeTheme("light"),"light");
  assert.equal(safeTheme("dark"),"dark");
  assert.equal(safeTheme("invalid"),"dark");
  assert.equal(oppositeTheme("dark"),"light");
  assert.equal(oppositeTheme("light"),"dark");
});
test("light mode restores across app startup and switches back to dark",()=>{
  const c=controls();
  const values=new Map([[THEME_KEY,"light"]]);
  const storage={getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value)};
  assert.equal(installTheme(c.documentLike,storage),"light");
  assert.equal(c.root.dataset.theme,"light");
  assert.equal(c.root.style.colorScheme,"light");
  assert.equal(c.attrs["aria-label"],"Activar modo oscuro");
  assert.equal(c.attrs["aria-pressed"],"true");
  assert.equal(c.icon.textContent,"☀");
  assert.equal(c.label.textContent,"Claro");
  assert.equal(c.meta.content,"#f3f6fb");
  c.events.click();
  assert.equal(c.root.dataset.theme,"dark");
  assert.equal(c.attrs["aria-label"],"Activar modo claro");
  assert.equal(c.attrs["aria-pressed"],"false");
  assert.equal(c.label.textContent,"Oscuro");
  assert.equal(c.meta.content,"#061522");
  assert.equal(values.get(THEME_KEY),"dark");
});
test("denied storage cannot break appearance switch",()=>{
  const c=controls();
  const storage={
    getItem(){throw Error("storage blocked");},
    setItem(){throw Error("storage blocked");}
  };
  assert.equal(storedTheme(storage),"dark");
  assert.equal(installTheme(c.documentLike,storage),"dark");
  assert.doesNotThrow(()=>c.events.click());
  assert.equal(c.root.dataset.theme,"light");
});
test("app shell caches both appearance assets and loads light palette after dark",()=>{
  const index=readFileSync(new URL("../index.html",import.meta.url),"utf8");
  const sw=readFileSync(new URL("../sw.js",import.meta.url),"utf8");
  const css=readFileSync(new URL("../theme.css",import.meta.url),"utf8");
  assert.match(index,/id="themeToggle"/);
  assert.ok(index.indexOf('href="./styles.css"')<index.indexOf('href="./theme.css"'));
  assert.match(index,/localStorage\.getItem\("football-ai-lab-theme"\)/);
  assert.match(sw,/"theme\.css"/);
  assert.match(sw,/"theme\.mjs"/);
  assert.match(css,/\.home-teams \.crest-shell\{width:62px;height:62px/);
  assert.match(css,/@media\(max-width:800px\)/);
  assert.match(css,/:root\[data-theme="light"\]/);
  assert.match(css,/\[data-theme="light"\] \.match-dialog/);
  assert.match(css,/\[data-theme="light"\] \.results-v2-score/);
});
test("applying theme works even when optional controls are unavailable",()=>{
  const root={dataset:{},style:{}};
  assert.equal(applyTheme("light",{root}),"light");
  assert.equal(root.dataset.theme,"light");
  assert.equal(applyTheme("invalid",{root}),"dark");
});

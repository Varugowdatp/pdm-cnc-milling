const fs = require('fs');
const src = fs.readFileSync('frontend/js/widgets.js','utf8');
eval(src + '; global.W = W;');

function el(){ return { _h:"", set innerHTML(v){this._h=v;}, get innerHTML(){return this._h;},
                        children: new Proxy({},{get:()=>el()}) }; }
let fails=0;
function check(name, fn){
  try { const out = fn(); 
        if (typeof out === "string" && (out.includes("NaN") || out.includes("undefined") || out.includes("Infinity"))) {
          console.log(`  BAD OUTPUT ${name}: contains NaN/undefined/Infinity`); fails++;
        } else console.log(`  ok  ${name}`);
  } catch(e){ console.log(`  FAIL ${name}: ${e.message}`); fails++; }
}

console.log("gauges:");
check("gauge normal", ()=>{const c=el(); W.gauge(c,{value:1558,min:1000,max:3000,label:"Speed",unit:"rpm"}); return c.innerHTML;});
check("gauge at min", ()=>{const c=el(); W.gauge(c,{value:1000,min:1000,max:3000,label:"x",unit:"y"}); return c.innerHTML;});
check("gauge at max", ()=>{const c=el(); W.gauge(c,{value:3000,min:1000,max:3000,label:"x",unit:"y"}); return c.innerHTML;});
check("gauge below min", ()=>{const c=el(); W.gauge(c,{value:5,min:1000,max:3000,label:"x",unit:"y"}); return c.innerHTML;});
check("gauge above max", ()=>{const c=el(); W.gauge(c,{value:99999,min:1000,max:3000,label:"x",unit:"y"}); return c.innerHTML;});
check("gauge zero range", ()=>{const c=el(); W.gauge(c,{value:5,min:5,max:5,label:"x",unit:"y"}); return c.innerHTML;});

console.log("health ring:");
[0,40,65,85,100].forEach(v=>check(`ring ${v}`, ()=>{const c=el(); W.healthRing(c,v); return c.innerHTML;}));

console.log("charts:");
check("chart normal", ()=>{const c=el(); W.lineChart(c,{series:[{name:"a",color:"#fff",data:[1,2,3,4,5]}],labels:["1","2","3","4","5"]}); return c.innerHTML;});
check("chart single point", ()=>{const c=el(); W.lineChart(c,{series:[{name:"a",color:"#fff",data:[7]}],labels:["1"]}); return c.innerHTML;});
check("chart all nulls", ()=>{const c=el(); W.lineChart(c,{series:[{name:"a",color:"#fff",data:[null,null]}],labels:["1","2"]}); return c.innerHTML;});
check("chart with gaps", ()=>{const c=el(); W.lineChart(c,{series:[{name:"a",color:"#fff",data:[1,null,3,null,5]}],labels:["1","2","3","4","5"]}); return c.innerHTML;});
check("chart flat line", ()=>{const c=el(); W.lineChart(c,{series:[{name:"a",color:"#fff",data:[5,5,5,5]}],labels:["1","2","3","4"]}); return c.innerHTML;});
check("chart empty", ()=>{const c=el(); W.lineChart(c,{series:[],labels:[]}); return c.innerHTML;});
check("chart with bands", ()=>{const c=el(); W.lineChart(c,{series:[{name:"a",color:"#fff",data:[10,50,90]}],labels:["1","2","3"],yMin:0,yMax:100,bands:[{from:0,to:40,color:"#f00"}]}); return c.innerHTML;});

console.log("bars:");
check("stressBars", ()=>{const c=el(); W.stressBars(c,{TWF:0.3,HDF:0,PWF:0.9,OSF:0.5},"PWF"); return c.innerHTML;});
check("probBars", ()=>{const c=el(); W.probBars(c,{Normal:0.9,TWF:0.05,HDF:0.03,PWF:0.01,OSF:0.01},"Normal"); return c.innerHTML;});
check("driverBars", ()=>{const c=el(); W.driverBars(c,[{label:"T",unit:"K",value:8.6,contribution:0.42},{label:"P",unit:"W",value:8769,contribution:-0.25}]); return c.innerHTML;});
check("driverBars empty", ()=>{const c=el(); W.driverBars(c,[]); return c.innerHTML;});
check("driverBars null value", ()=>{const c=el(); W.driverBars(c,[{label:"T",unit:"",value:null,contribution:0.1}]); return c.innerHTML;});
check("driverBars all zero", ()=>{const c=el(); W.driverBars(c,[{label:"T",unit:"",value:1,contribution:0}]); return c.innerHTML;});
check("confusionMatrix", ()=>{const c=el(); W.confusionMatrix(c,{labels:["A","B"],matrix:[[10,2],[1,20]]}); return c.innerHTML;});
check("confusionMatrix zero row", ()=>{const c=el(); W.confusionMatrix(c,{labels:["A","B"],matrix:[[0,0],[1,20]]}); return c.innerHTML;});

console.log("formatting:");
check("fmt null", ()=>{ const r=W.fmt(null); if(r!=="—") throw new Error("expected em dash, got "+r); return r;});
check("fmt NaN", ()=>{ const r=W.fmt(NaN); if(r!=="—") throw new Error("expected em dash, got "+r); return r;});
check("healthColor bounds", ()=>{ [0,39,40,64,65,84,85,100].forEach(v=>{ if(!W.healthColor(v).startsWith("#")) throw new Error("bad at "+v);}); return "ok";});

console.log(fails ? `\n${fails} FAILURES` : "\nALL WIDGET TESTS PASSED");
process.exit(fails?1:0);

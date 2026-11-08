const fs=require('fs'),vm=require('vm'),assert=require('assert');
const text=fs.readFileSync('night-sky.js','utf8');const src=text.split('// ART_DRIFT_GEOMETRY_BEGIN')[1].split('// ART_DRIFT_GEOMETRY_END')[0];const c={};vm.createContext(c);vm.runInContext(src,c);
let cases=0;
for(const [w,h] of [[320,1200],[600,900],[1920,1080],[3440,1440],[7680,2160],[200,4000],[4000,200]])for(const [iw,ih] of [[1920,1080],[1024,1024],[4096,2304]])for(let i=0;i<=100;i++){
 const b=c.artCoverBounds(w,h,iw,ih),n=-1+i/50,x=(w-b.w)/2+n*b.x,y=(h-b.h)/2-n*b.y;
 assert(x<=0&&y<=0&&x+b.w>=w&&y+b.h>=h);assert(b.x<=48&&b.y<=48);cases++;
}
assert.equal(c.artEase(0),0);assert.equal(c.artEase(1),1);
let maxD=0;for(let i=1;i<=10000;i++)maxD=Math.max(maxD,(c.artEase(i/10000)-c.artEase((i-1)/10000))*10000);assert(maxD<=1.875001);
console.log(JSON.stringify({cases,maxDerivative:maxD,maxSpeedPixelsPerSecond:.35,zoom:1.08}));

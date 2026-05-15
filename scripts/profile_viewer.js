#!/usr/bin/env node
/**
 * Generate a standalone HTML viewer for width profile and/or path JSON.
 * Usage:
 *   node scripts/profile_viewer.js <profile.json> [output.html]
 *   node scripts/profile_viewer.js <profile.json> --path <path.json> [output.html]
 *
 * Produces a self-contained HTML file with:
 *   - 2D track map (x vs z) from path data (if provided)
 *   - Width chart comparing raw vs smoothed widths, color-coded by bin status
 * Both panels support scroll zoom and drag pan.
 * Hovering a bin on the width chart highlights it on the track map.
 */

'use strict';

const fs = require('fs');
const path = require('path');

// Parse args
let profilePath = null;
let pathPath = null;
let outPath = null;
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--path') {
    pathPath = args[++i];
  } else if (!profilePath) {
    profilePath = args[i];
  } else {
    outPath = args[i];
  }
}
if (!profilePath) {
  console.error('Usage: node scripts/profile_viewer.js <profile.json> [--path <path.json>] [output.html]');
  process.exit(1);
}
if (!outPath) outPath = profilePath.replace(/\.json$/, '-view.html');

const profile = JSON.parse(fs.readFileSync(profilePath, 'utf8'));
const samples = profile.samples;
const hasSmooth = samples.some(s => s.left_width_smooth_m != null);

const maxLeft = Math.max(...samples.map(s => s.left_width_m || 0), ...samples.map(s => s.left_width_smooth_m || 0));
const maxRight = Math.max(...samples.map(s => s.right_width_m || 0), ...samples.map(s => s.right_width_smooth_m || 0));
const maxW = Math.max(maxLeft, maxRight) || 1;

const statusColors = { complete: '#2d6a4f', 'low-sample': '#e9c46a', 'one-sided': '#f4a261', missing: '#e76f51' };

let pathPoints = null;
if (pathPath && fs.existsSync(pathPath)) {
  const pathData = JSON.parse(fs.readFileSync(pathPath, 'utf8'));
  pathPoints = pathData.points;
}

// Build map canvas HTML and JS only if path data is present
const mapCanvasHtml = pathPoints
  ? '<h2>Track Map (x &#8594; z)</h2><canvas id="map"></canvas>'
  : '';

const mapJs = pathPoints ? `
// ── 2D track map ──
const mapCanvas=document.getElementById('map');
const mapCtx=mapCanvas.getContext('2d');
let mapZoom=1, mapOffX=0, mapOffY=0;

const xs=POINTS.map(function(p){return p.x_m;}), zs=POINTS.map(function(p){return p.z_m;});
const xMin=Math.min.apply(null,xs), xMax=Math.max.apply(null,xs);
const zMin=Math.min.apply(null,zs), zMax=Math.max.apply(null,zs);
const xRange=xMax-xMin||1, zRange=zMax-zMin||1;

function resizeMap(){
  mapCanvas.width=window.innerWidth*dpr;
  mapCanvas.height=280*dpr;
  mapCanvas.style.width=window.innerWidth+'px';
  mapCanvas.style.height='280px';
  drawMap();
}

function drawMap(){
  var w=mapCanvas.width/dpr, h=mapCanvas.height/dpr;
  var pad=20;
  var plotW=w-pad*2, plotH=h-pad*2;
  var scale=Math.min(plotW/(xRange*mapZoom), plotH/(zRange*mapZoom));
  var cx=pad+plotW/2, cy=pad+plotH/2;

  mapCtx.setTransform(dpr,0,0,dpr,0,0);
  mapCtx.clearRect(0,0,w,h);

  // Center path polyline
  mapCtx.strokeStyle='#4cc9f0';
  mapCtx.lineWidth=1.5;
  mapCtx.beginPath();
  for(var i=0;i<POINTS.length;i++){
    var px=cx+((POINTS[i].x_m-(xMin+xMax)/2)*scale)-mapOffX*scale;
    var py=cy+((POINTS[i].z_m-(zMin+zMax)/2)*scale)-mapOffY*scale;
    if(i===0)mapCtx.moveTo(px,py);else mapCtx.lineTo(px,py);
  }
  mapCtx.stroke();

  // Highlight dot for current bin
  if(highlightS!==null){
    var pt=null, bestDist=Infinity;
    for(var j=0;j<POINTS.length;j++){
      var d=Math.abs(POINTS[j].s_m-highlightS);
      if(d<bestDist){bestDist=d;pt=POINTS[j];}
    }
    if(pt){
      var hx=cx+((pt.x_m-(xMin+xMax)/2)*scale)-mapOffX*scale;
      var hy=cy+((pt.z_m-(zMin+zMax)/2)*scale)-mapOffY*scale;
      mapCtx.fillStyle='#ff0';
      mapCtx.beginPath();
      mapCtx.arc(hx,hy,4,0,Math.PI*2);
      mapCtx.fill();
    }
  }

  // Axis labels
  mapCtx.fillStyle='#666';mapCtx.font='10px monospace';mapCtx.textAlign='left';
  mapCtx.fillText('x: '+xMin.toFixed(0)+'..'+xMax.toFixed(0)+'m',pad,h-4);
  mapCtx.textAlign='right';
  mapCtx.fillText('z: '+zMin.toFixed(0)+'..'+zMax.toFixed(0)+'m',w-pad,h-4);
}

// Map zoom/pan
mapCanvas.addEventListener('wheel',function(e){
  e.preventDefault();
  var factor=e.deltaY<0?1.15:1/1.15;
  mapZoom*=factor;mapZoom=Math.max(0.1,Math.min(100,mapZoom));
  drawMap();
},{passive:false});

var mapDrag=null;
mapCanvas.addEventListener('mousedown',function(e){mapDrag={x:e.clientX,y:e.clientY,ox:mapOffX,oy:mapOffY};});
mapCanvas.addEventListener('mousemove',function(e){
  if(!mapDrag)return;
  var scale=Math.min((window.innerWidth-40)/(xRange*mapZoom),(280-40)/(zRange*mapZoom));
  mapOffX=mapDrag.ox+(mapDrag.x-e.clientX)/scale;
  mapOffY=mapDrag.oy-(mapDrag.y-e.clientY)/scale;
  drawMap();
});
mapCanvas.addEventListener('mouseup',function(){mapDrag=null;});
mapCanvas.addEventListener('mouseleave',function(){mapDrag=null;});
` : '';

const legendExtra = pathPoints
  ? '<span><i style="background:#4cc9f0"></i>center path</span>'
  : '';

const html = [
  '<!DOCTYPE html>',
  '<html><head><meta charset="utf-8"><title>Track Viewer &mdash; ' + profile.track_id + '</title>',
  '<style>',
  '*{margin:0;box-sizing:border-box}body{background:#1a1a2e;color:#e0e0e0;font:14px sans-serif}',
  'canvas{display:block;cursor:grab}canvas:active{cursor:grabbing}',
  '.controls{padding:10px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}',
  '.legend{display:flex;gap:10px;align-items:center;font-size:12px}',
  '.legend span{display:flex;align-items:center;gap:4px}',
  '.legend i{width:14px;height:10px;border-radius:2px;display:inline-block}',
  '.info{font-size:12px;color:#888}',
  'h2{font-size:13px;color:#aaa;padding:6px 0 2px 10px}',
  '</style></head><body>',
  '<div class="controls">',
  ' <div class="legend">',
  ...Object.entries(statusColors).map(([k,v]) => `<span><i style="background:${v}"></i>${k}</span>`),
  ...(hasSmooth ? ['<span><i style="background:#4cc9f0"></i>smooth</span><span><i style="background:#888"></i>raw</span>'] : []),
  legendExtra,
  ' </div>',
  ` <div class="info" id="info">scroll to zoom, drag to pan | ${samples.length} bins | ${profile.bin_size_m}m bins${pathPoints ? ' | ' + pathPoints.length + ' path points' : ''}</div>`,
  '</div>',
  mapCanvasHtml,
  '<h2>Width Profile</h2>',
  '<canvas id="c"></canvas>',
  '<script>',
  'const SAMPLES=' + JSON.stringify(samples) + ';',
  'const POINTS=' + JSON.stringify(pathPoints) + ';',
  'const MAX_W=' + maxW + ';',
  'const HAS_SMOOTH=' + hasSmooth + ';',
  'const STATUS_COLORS=' + JSON.stringify(statusColors) + ';',
  'const BIN_SIZE=' + profile.bin_size_m + ';',
  '',
  'var highlightS=null;',
  'function highlightMapBin(s_m){highlightS=s_m;if(typeof drawMap==="function")drawMap();}',
  mapJs,
  '',
  '// ── Width profile chart ──',
  'const canvas=document.getElementById("c");',
  'const ctx=canvas.getContext("2d");',
  'const dpr=window.devicePixelRatio||1;',
  'var offsetX=0, zoom=1;',
  'const PAD_LEFT=60, PAD_RIGHT=20, PAD_TOP=20, PAD_BOT=40;',
  '',
  'function resizeProfile(){',
  '  canvas.width=window.innerWidth*dpr;',
  '  canvas.height=Math.max(400,(window.innerHeight-(POINTS?300:60)))*dpr;',
  '  canvas.style.width=window.innerWidth+"px";',
  '  canvas.style.height=Math.max(400,(window.innerHeight-(POINTS?300:60)))+"px";',
  '  drawProfile();',
  '}',
  '',
  'function drawProfile(){',
  '  var w=canvas.width/dpr, h=canvas.height/dpr;',
  '  var plotW=w-PAD_LEFT-PAD_RIGHT, plotH=h-PAD_TOP-PAD_BOT;',
  '  var sMin=SAMPLES[0].s_m, sMax=SAMPLES[SAMPLES.length-1].s_m;',
  '  var sRange=(sMax-sMin+BIN_SIZE)*zoom;',
  '',
  '  ctx.setTransform(dpr,0,0,dpr,0,0);',
  '  ctx.clearRect(0,0,w,h);',
  '',
  '  // Grid',
  '  ctx.strokeStyle="#333";ctx.lineWidth=0.5;',
  '  for(var v=0;v<=MAX_W;v+=2){',
  '    var y=PAD_TOP+plotH*(1-v/MAX_W);',
  '    ctx.beginPath();ctx.moveTo(PAD_LEFT,y);ctx.lineTo(PAD_LEFT+plotW,y);ctx.stroke();',
  '    ctx.fillStyle="#666";ctx.font="10px monospace";ctx.textAlign="right";',
  '    ctx.fillText(v+"m",PAD_LEFT-6,y+3);',
  '  }',
  '',
  '  // Status bands',
  '  for(var i=0;i<SAMPLES.length;i++){',
  '    var s=SAMPLES[i];',
  '    var x=PAD_LEFT+((s.s_m-sMin-offsetX)/sRange)*plotW;',
  '    if(x<PAD_LEFT||x>PAD_LEFT+plotW)continue;',
  '    var bw=Math.max(1,plotW/sRange*BIN_SIZE);',
  '    ctx.fillStyle=STATUS_COLORS[s.status]||"#555";',
  '    ctx.globalAlpha=0.15;',
  '    ctx.fillRect(x,PAD_TOP,bw,plotH);',
  '  }',
  '  ctx.globalAlpha=1;',
  '',
  '  // Lines',
  '  function line(key,color){',
  '    ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.beginPath();',
  '    var started=false;',
  '    for(var i=0;i<SAMPLES.length;i++){',
  '      var s=SAMPLES[i];',
  '      var px=PAD_LEFT+((s.s_m-sMin-offsetX)/sRange)*plotW;',
  '      var val=s[key];if(val==null||val===0){if(started){ctx.stroke();ctx.beginPath();started=false;}continue;}',
  '      var py=PAD_TOP+plotH*(1-val/MAX_W);',
  '      if(!started){ctx.moveTo(px,py);started=true;}else ctx.lineTo(px,py);',
  '    }',
  '    ctx.stroke();',
  '  }',
  '',
  '  line("left_width_m","#888");',
  '  line("right_width_m","#888");',
  '  if(HAS_SMOOTH){',
  '    line("left_width_smooth_m","#4cc9f0");',
  '    line("right_width_smooth_m","#4cc9f0");',
  '  }',
  '',
  '  // S-axis labels',
  '  ctx.fillStyle="#888";ctx.font="10px monospace";ctx.textAlign="center";',
  '  var step=Math.max(1,Math.round(50/sRange*100)/100)*BIN_SIZE*(zoom<0.5?5:1);',
  '  for(var s=sMin;s<=sMax;s+=step){',
  '    var lx=PAD_LEFT+((s-sMin-offsetX)/sRange)*plotW;',
  '    if(lx<PAD_LEFT||lx>PAD_LEFT+plotW)continue;',
  '    ctx.fillText(s+"m",lx,h-PAD_BOT+14);',
  '  }',
  '',
  '  // Cursor info on hover',
  '  if(profileMouse){',
  '    var mx=profileMouse.x, my=profileMouse.y;',
  '    var sAt=sMin+offsetX+(mx-PAD_LEFT)/plotW*sRange;',
  '    var bin=null,bestD=Infinity;',
  '    for(var i=0;i<SAMPLES.length;i++){',
  '      var d=Math.abs(SAMPLES[i].s_m-sAt);',
  '      if(d<bestD){bestD=d;bin=SAMPLES[i];}',
  '    }',
  '    if(bin&&bestD<BIN_SIZE){',
  '      ctx.fillStyle="rgba(0,0,0,0.7)";ctx.fillRect(mx+10,my-50,240,50);',
  '      ctx.fillStyle="#eee";ctx.font="11px monospace";ctx.textAlign="left";',
  '      ctx.fillText("s="+bin.s_m+"m  "+bin.status+"  conf="+bin.confidence,mx+16,my-34);',
  '      ctx.fillText("L raw="+(bin.left_width_m||0).toFixed(1)+" R raw="+(bin.right_width_m||0).toFixed(1),mx+16,my-20);',
  '      if(HAS_SMOOTH)ctx.fillText("L s="+(bin.left_width_smooth_m||0).toFixed(1)+" R s="+(bin.right_width_smooth_m||0).toFixed(1),mx+16,my-6);',
  '      highlightMapBin(bin.s_m);',
  '    }',
  '  }',
  '}',
  '',
  'var profileMouse=null;',
  'canvas.addEventListener("mousemove",function(e){profileMouse={x:e.offsetX,y:e.offsetY};drawProfile();});',
  'canvas.addEventListener("mouseleave",function(){profileMouse=null;highlightS=null;drawProfile();if(typeof drawMap==="function")drawMap();});',
  'canvas.addEventListener("wheel",function(e){',
  '  e.preventDefault();',
  '  var factor=e.deltaY<0?1.15:1/1.15;',
  '  var w=canvas.width/dpr;',
  '  var plotW=w-PAD_LEFT-PAD_RIGHT;',
  '  var sMin=SAMPLES[0].s_m;',
  '  var sRangeOld=(SAMPLES[SAMPLES.length-1].s_m-sMin+BIN_SIZE)*zoom;',
  '  var mouseS=sMin+offsetX+(e.offsetX-PAD_LEFT)/plotW*sRangeOld;',
  '  zoom*=factor;zoom=Math.max(0.05,Math.min(200,zoom));',
  '  var sRangeNew=(SAMPLES[SAMPLES.length-1].s_m-sMin+BIN_SIZE)*zoom;',
  '  offsetX=mouseS-sMin-(e.offsetX-PAD_LEFT)/plotW*sRangeNew;',
  '  drawProfile();',
  '},{passive:false});',
  '',
  'var dragStart=null;',
  'canvas.addEventListener("mousedown",function(e){dragStart={x:e.clientX,ox:offsetX};});',
  'canvas.addEventListener("mousemove",function(e){if(!dragStart)return;',
  '  var w=canvas.width/dpr,plotW=w-PAD_LEFT-PAD_RIGHT;',
  '  var sRange=(SAMPLES[SAMPLES.length-1].s_m-SAMPLES[0].s_m+BIN_SIZE)*zoom;',
  '  offsetX=dragStart.ox-(e.clientX-dragStart.x)/plotW*sRange;drawProfile();});',
  'canvas.addEventListener("mouseup",function(){dragStart=null;});',
  'canvas.addEventListener("mouseleave",function(){dragStart=null;});',
  '',
  'function onResize(){',
  '  if(POINTS)resizeMap();',
  '  resizeProfile();',
  '}',
  'window.addEventListener("resize",onResize);',
  'onResize();',
  '</script></body></html>'
].join('\n');

fs.writeFileSync(outPath, html);
console.log(`wrote ${outPath} — open in browser to inspect`);
console.log(`  ${samples.length} width bins, ${hasSmooth ? 'smooth+raw' : 'raw only'}, max width ${maxW.toFixed(1)}m${pathPoints ? `, ${pathPoints.length} path points` : ''}`);
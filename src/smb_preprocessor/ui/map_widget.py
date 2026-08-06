from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


MAP_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link rel="stylesheet" href="leaflet.css">
  <link rel="stylesheet" href="leaflet.draw.css">
  <style>
    html,body,#map { height:100%; margin:0; background:#10151c; }
    .leaflet-control-attribution { font-size:10px; }
    .leaflet-draw { margin-top:58px; }
    .leaflet-draw-toolbar { box-shadow:0 2px 9px rgba(0,0,0,.35); }
    .leaflet-draw-toolbar a {
      box-sizing:border-box; width:38px; height:38px; line-height:38px;
      color:#dce6ed; font:600 13px/38px system-ui; text-align:left;
      padding:0; white-space:nowrap; background-color:#111d28;
      background-image:none !important;
      background-repeat:no-repeat !important;
      background-position:center !important;
      background-size:22px 22px !important;
    }
    .leaflet-draw-toolbar .leaflet-draw-draw-polygon {
      background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2356d6d0' stroke-width='1.8' stroke-linejoin='round'%3E%3Cpath d='M4 18 7 5l8-2 5 7-3 10-8 1z'/%3E%3Ccircle cx='7' cy='5' r='1.2' fill='%2356d6d0'/%3E%3Ccircle cx='20' cy='10' r='1.2' fill='%2356d6d0'/%3E%3C/svg%3E") !important;
    }
    .leaflet-draw-toolbar .leaflet-draw-draw-rectangle {
      background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2356d6d0' stroke-width='1.8'%3E%3Crect x='4' y='4' width='16' height='16' rx='1'/%3E%3Cpath d='M4 9h16M9 4v16' stroke-dasharray='2 2'/%3E%3C/svg%3E") !important;
    }
    .leaflet-draw-toolbar .leaflet-draw-edit-edit {
      background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2356d6d0' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m4 20 4-1 11-11-3-3L5 16zM14 7l3 3'/%3E%3C/svg%3E") !important;
    }
    .leaflet-draw-toolbar .leaflet-draw-edit-remove {
      background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff7b86' stroke-width='1.8' stroke-linecap='round'%3E%3Cpath d='M5 7h14M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6'/%3E%3C/svg%3E") !important;
    }
    .leaflet-touch .leaflet-draw-toolbar a {
      width:42px; height:42px; line-height:42px;
    }
    .leaflet-draw-toolbar a:hover,
    .leaflet-draw-toolbar a:focus {
      color:#56d6d0; background-color:#19303b;
    }
    .leaflet-draw-toolbar a.leaflet-disabled {
      color:#607483; background-color:#101820;
    }
    .leaflet-draw-toolbar a span { display:none; }
    .leaflet-bar a, .leaflet-bar a:hover {
      color:#dce6ed; background-color:#111d28; border-bottom-color:#2a3d4e;
    }
    .leaflet-control-layers {
      color:#dce6ed; background:#111d28; border:1px solid #2a3d4e;
      border-radius:6px; box-shadow:0 2px 9px rgba(0,0,0,.35);
    }
    .leaflet-control-layers-toggle {
      background-image:none !important; width:38px !important; height:38px !important;
      position:relative;
    }
    .leaflet-control-layers-toggle::after {
      content:'▱'; position:absolute; inset:0; text-align:center;
      font:22px/38px system-ui; color:#56d6d0;
    }
    .leaflet-editing-icon { cursor:pointer; }
    .leaflet-middle-marker {
      opacity:0 !important; pointer-events:none !important;
    }
    body.vertex-editing.adding-vertices .leaflet-middle-marker {
      opacity:.6 !important; pointer-events:auto !important;
    }
    .leaflet-draw-tooltip { max-width:340px; white-space:normal; }
    body.vertex-editing .leaflet-draw-tooltip { display:none; }
    .status {
      position:absolute; z-index:1000; left:58px; top:12px;
      padding:8px 12px; border-radius:7px; color:#e9f1fa;
      background:rgba(13,23,33,.92); border:1px solid #2a3d4e; font:12px system-ui;
      box-shadow:0 2px 10px rgba(0,0,0,.3);
    }
    .bathy-legend {
      background:rgba(13,23,33,.94); padding:10px 11px; border-radius:7px;
      border:1px solid #2a3d4e; color:#dce6ed; font:12px system-ui;
      box-shadow:0 2px 10px rgba(0,0,0,.4);
    }
    .bathy-title { font-weight:700; margin-bottom:5px; }
    .bathy-scale { display:flex; height:190px; gap:8px; }
    .bathy-gradient {
      width:24px; border:1px solid #444;
      background:linear-gradient(to top,
        #071d49 0%, #0b3c78 18%, #1268a0 38%,
        #1d91b4 58%, #55c5c2 78%, #c8f1df 100%);
    }
    .bathy-ticks {
      display:flex; flex-direction:column; justify-content:space-between;
      white-space:nowrap; min-width:74px;
    }
    .bathy-ticks span {
      position:relative; line-height:12px; color:#aebdca;
    }
    .bathy-ticks span::before {
      content:''; position:absolute; left:-9px; top:6px;
      width:6px; border-top:1px solid #394b59;
    }
    .boundary-help {
      max-width:245px; background:rgba(13,23,33,.94); color:#dce6ed;
      border:1px solid #2a3d4e; border-radius:7px; padding:9px 11px;
      font:12px/1.4 system-ui; box-shadow:0 2px 10px rgba(0,0,0,.4);
    }
    .boundary-help strong { color:#56d6d0; }
    .boundary-tooltip {
      background:#0d1721; color:#eef5f8; border:1px solid #35c9c2;
      border-radius:6px; box-shadow:0 3px 12px rgba(0,0,0,.45);
      font:12px/1.45 system-ui;
    }
    .boundary-tooltip::before { border-top-color:#35c9c2; }
    .result-animation {
      min-width:330px; background:rgba(13,23,33,.95); color:#dce6ed;
      border:1px solid #2a3d4e; border-radius:8px; padding:9px 11px;
      font:12px system-ui; box-shadow:0 3px 14px rgba(0,0,0,.45);
    }
    .result-animation .row { display:flex; align-items:center; gap:9px; }
    .result-animation button {
      width:34px; height:28px; border-radius:5px; border:1px solid #35c9c2;
      color:#061719; background:#22bdb7; cursor:pointer; font-weight:700;
    }
    .result-animation input { flex:1; accent-color:#22bdb7; }
    .result-animation .time { min-width:82px; color:#56d6d0; text-align:right; }
    .result-animation .scale {
      height:6px; margin-top:7px; border-radius:3px;
      background:linear-gradient(to right,#ffffd9,#7fcdbb,#225ea8,#081d58);
    }
  </style>
</head>
<body>
<div id="map"></div>
<div class="status" id="status">Mapa conectado · desenhe um polígono</div>
<script src="leaflet.js"></script>
<script src="leaflet.draw.js"></script>
<script>
L.drawLocal.edit.toolbar.buttons.edit = 'Edit vertices';
L.drawLocal.edit.toolbar.buttons.remove = 'Delete layers';
L.drawLocal.edit.handlers.edit.tooltip.text =
  'Drag a vertex to move it. Click a solid white vertex to delete it.';
L.drawLocal.edit.handlers.edit.tooltip.subtext =
  'The polygon will always keep at least 3 vertices. Click Cancel to undo.';

// Right-click is useful when several vertices occupy the same position.
// Leaflet Draw's own click handler keeps at least three polygon vertices.
L.Edit.PolyVerticesEdit.prototype._onContextMenu = function(event) {
  this._onMarkerClick(event);
  if (event.originalEvent) L.DomEvent.stop(event.originalEvent);
};

// Keep insertion handles hidden and non-interactive by default, because they
// can cover real vertices. Holding Shift reveals and enables them temporarily.
const createMiddleMarker =
  L.Edit.PolyVerticesEdit.prototype._createMiddleMarker;
L.Edit.PolyVerticesEdit.prototype._createMiddleMarker = function(left, right) {
  createMiddleMarker.call(this, left, right);
  const marker = left && left._middleRight;
  const element = marker && marker.getElement();
  if (element) L.DomUtil.addClass(element, 'leaflet-middle-marker');
};

const map = L.map('map', {zoomControl:true}).setView([-2.55,-44.35], 9);
const street = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom:19, attribution:'© OpenStreetMap contributors'
});
street.on('load', () => {
  if (!drawn.getLayers().length)
    document.getElementById('status').textContent = 'OpenStreetMap conectado · desenhe um polígono';
});
street.on('tileerror', () => {
  document.getElementById('status').textContent = 'Sem conexão com o mapa base';
});
const satellite = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  {maxZoom:19, attribution:'Tiles © Esri'}
).addTo(map);
satellite.on('load', () => {
  if (!drawn.getLayers().length)
    document.getElementById('status').textContent = 'Satélite conectado · desenhe um polígono';
});
satellite.on('tileerror', () => {
  document.getElementById('status').textContent = 'Sem conexão com o mapa base';
});
const layerControl = L.control.layers(
  {'Ruas':street,'Satélite':satellite}, null, {position:'topright'}
).addTo(map);
let bathymetry = null;
let bathymetryLegend = null;
let boundaryNodes = null;
let boundaryHelp = null;
const boundaryRenderer = L.canvas({padding:0.5});
let resultOverlay = null;
let resultAnimationControl = null;
let resultTimer = null;
let netcdfOverlay = null;
let netcdfLegend = null;
const drawn = new L.FeatureGroup().addTo(map);
let drawingsDirty = false;
const control = new L.Control.Draw({
  position:'topright',
  draw:{ polygon:{allowIntersection:false,showArea:true}, rectangle:true,
         polyline:false,circle:false,circlemarker:false,marker:false },
  edit:{featureGroup:drawn,remove:true}
});
map.addControl(control);
document.addEventListener('keydown', event => {
  if (event.key === 'Shift' && document.body.classList.contains('vertex-editing')) {
    document.body.classList.add('adding-vertices');
    document.getElementById('status').textContent =
      'Adding vertices: click a semi-transparent point on an edge';
  }
});
document.addEventListener('keyup', event => {
  if (event.key === 'Shift') {
    document.body.classList.remove('adding-vertices');
    if (document.body.classList.contains('vertex-editing')) {
      document.getElementById('status').textContent =
        'Editing: drag to move; click to delete; hold Shift to add';
    }
  }
});
window.addEventListener('blur', () => {
  document.body.classList.remove('adding-vertices');
});
const toolbarLabels = [
  ['.leaflet-draw-draw-polygon', 'Desenhar polígono'],
  ['.leaflet-draw-draw-rectangle', 'Desenhar retângulo'],
  ['.leaflet-draw-edit-edit', 'Editar vértices'],
  ['.leaflet-draw-edit-remove', 'Excluir desenhos']
];
toolbarLabels.forEach(([selector, label]) => {
  const button = document.querySelector(selector);
  if (!button) return;
  const text = document.createElement('span');
  text.textContent = label;
  button.appendChild(text);
  button.setAttribute('aria-label', label);
});
function updateStatus() {
  const count = drawn.getLayers().length;
  document.getElementById('status').textContent =
    count ? count + ' polígono(s) no mapa' : 'Mapa conectado · desenhe um polígono';
}
map.on(L.Draw.Event.CREATED, e => {
  drawn.addLayer(e.layer);
  drawingsDirty = true;
  updateStatus();
});
map.on(L.Draw.Event.EDITED, () => { drawingsDirty = true; updateStatus(); });
map.on(L.Draw.Event.EDITVERTEX, () => { drawingsDirty = true; });
map.on(L.Draw.Event.DELETED, () => { drawingsDirty = true; updateStatus(); });
map.on('draw:editstart', () => {
  document.body.classList.add('vertex-editing');
  document.getElementById('status').textContent =
    'Editing: drag to move; click to delete; hold Shift to add';
});
map.on('draw:deletestart', () => {
  document.getElementById('status').textContent =
    'Deleting: click the polygon or rectangle you want to remove';
});
map.on('draw:editstop', () => {
  document.body.classList.remove('vertex-editing', 'adding-vertices');
  updateStatus();
});
map.on('draw:deletestop', updateStatus);
window.getDrawings = () => JSON.stringify(drawn.toGeoJSON());
window.getDrawingState = () => JSON.stringify({
  dirty: drawingsDirty,
  drawings: drawn.toGeoJSON()
});
window.markDrawingsClean = () => { drawingsDirty = false; };
window.clearDrawings = () => {
  drawn.clearLayers();
  drawingsDirty = true;
  updateStatus();
};
window.clearMapLayers = () => {
  drawn.clearLayers();
  drawingsDirty = true;

  if (bathymetry) {
    layerControl.removeLayer(bathymetry);
    map.removeLayer(bathymetry);
    bathymetry = null;
  }
  if (bathymetryLegend) {
    map.removeControl(bathymetryLegend);
    bathymetryLegend = null;
  }
  if (boundaryNodes) {
    layerControl.removeLayer(boundaryNodes);
    map.removeLayer(boundaryNodes);
    boundaryNodes = null;
  }
  if (boundaryHelp) {
    map.removeControl(boundaryHelp);
    boundaryHelp = null;
  }
  if (resultTimer) {
    clearInterval(resultTimer);
    resultTimer = null;
  }
  if (resultOverlay) {
    layerControl.removeLayer(resultOverlay);
    map.removeLayer(resultOverlay);
    resultOverlay = null;
  }
  if (resultAnimationControl) {
    map.removeControl(resultAnimationControl);
    resultAnimationControl = null;
  }
  if (netcdfOverlay) {
    layerControl.removeLayer(netcdfOverlay);
    map.removeLayer(netcdfOverlay);
    netcdfOverlay = null;
  }
  if (netcdfLegend) {
    map.removeControl(netcdfLegend);
    netcdfLegend = null;
  }

  updateStatus();
  document.getElementById('status').textContent =
    'Camadas removidas · selecione um novo contorno ou uma nova grade';
};
window.loadGeoJSON = text => {
  const data = JSON.parse(text);
  drawn.clearLayers();
  const layer = L.geoJSON(data);
  layer.eachLayer(item => drawn.addLayer(item));
  if (drawn.getLayers().length) map.fitBounds(drawn.getBounds(), {padding:[25,25]});
  drawingsDirty = false;
  updateStatus();
};
window.setMapView = (lat,lon,zoom) => map.setView([lat,lon],zoom);
window.loadBathymetryOverlay = (url, metadata) => {
  if (bathymetry) {
    layerControl.removeLayer(bathymetry);
    map.removeLayer(bathymetry);
  }
  if (bathymetryLegend) map.removeControl(bathymetryLegend);
  bathymetry = L.imageOverlay(url, metadata.bounds, {
    opacity:0.68, interactive:false
  }).addTo(map);
  layerControl.addOverlay(bathymetry, 'Batimetria da grade');
  bathymetryLegend = L.control({position:'bottomright'});
  bathymetryLegend.onAdd = () => {
    const div = L.DomUtil.create('div', 'bathy-legend');
    const count = 7;
    const labels = Array.from({length:count}, (_, index) => {
      const fraction = index / (count - 1);
      const value = metadata.max - fraction * (metadata.max - metadata.min);
      let suffix = '';
      if (index === 0) suffix = ' raso';
      if (index === count - 1) suffix = ' profundo';
      return '<span>' + value.toFixed(1) + ' m' + suffix + '</span>';
    }).join('');
    div.innerHTML =
      '<div class="bathy-title">Batimetria (m)</div>' +
      '<div class="bathy-scale"><div class="bathy-gradient"></div>' +
      '<div class="bathy-ticks">' + labels + '</div></div>';
    return div;
  };
  bathymetryLegend.addTo(map);
  map.fitBounds(metadata.bounds, {padding:[25,25]});
  document.getElementById('status').textContent =
    'Batimetria carregada · azul indica maior profundidade';
};
window.loadBoundaryNodes = records => {
  if (boundaryNodes) {
    layerControl.removeLayer(boundaryNodes);
    map.removeLayer(boundaryNodes);
  }
  if (boundaryHelp) map.removeControl(boundaryHelp);

  boundaryNodes = L.featureGroup();
  const colors = [
    '#56d6d0', '#ffb84d', '#b68cff', '#f06a8a', '#67c587',
    '#5ca8ff', '#e38bd8', '#d4cf5c', '#ff8b5c'
  ];
  const groups = {};
  records.forEach(item => {
    const contour = Number(item.contorno);
    if (!groups[contour]) groups[contour] = [];
    groups[contour].push(item);
  });

  Object.keys(groups).sort((a, b) => Number(a) - Number(b)).forEach(key => {
    const contour = Number(key);
    const color = colors[(contour - 1) % colors.length];
    const items = groups[key].sort((a, b) => Number(a.ordem) - Number(b.ordem));
    const points = items.map(item => [Number(item.latitude), Number(item.longitude)]);
    if (points.length > 1) {
      L.polyline(points.concat([points[0]]), {
        renderer:boundaryRenderer, color:color, weight:2, opacity:0.85
      }).addTo(boundaryNodes);
    }
    items.forEach(item => {
      const point = L.circleMarker(
        [Number(item.latitude), Number(item.longitude)],
        {
          renderer:boundaryRenderer, radius:4, color:'#08131c', weight:1,
          fillColor:color, fillOpacity:0.95, bubblingMouseEvents:false
        }
      );
      const content =
        '<strong>Contorno ' + item.contorno + '</strong> · ' + item.tipo_contorno +
        '<br>Ordem: <strong>' + item.ordem + '</strong>' +
        '<br>Nó TELEMAC: ' + item.no_telemac +
        '<br><span style="color:#8fa3b5">' +
        Number(item.latitude).toFixed(6) + ', ' +
        Number(item.longitude).toFixed(6) + '</span>';
      point.bindTooltip(content, {
        className:'boundary-tooltip', sticky:true, direction:'top', opacity:1
      });
      point.on('mouseover', () => {
        point.setRadius(7); point.setStyle({weight:2, color:'#fff'});
      });
      point.on('mouseout', () => {
        point.setRadius(4); point.setStyle({weight:1, color:'#08131c'});
      });
      point.on('click', () => {
        point.openTooltip();
        document.getElementById('status').textContent =
          'Contorno ' + item.contorno + ' · ordem ' + item.ordem +
          ' · nó TELEMAC ' + item.no_telemac;
      });
      point.addTo(boundaryNodes);
    });
  });

  boundaryNodes.addTo(map);
  layerControl.addOverlay(boundaryNodes, 'Nós e ordens dos contornos');
  boundaryHelp = L.control({position:'bottomleft'});
  boundaryHelp.onAdd = () => {
    const div = L.DomUtil.create('div', 'boundary-help');
    div.innerHTML = '<strong>Encontrar ordem</strong><br>' +
      'Passe o mouse sobre uma bolinha para identificar contorno, ordem e nó TELEMAC.';
    return div;
  };
  boundaryHelp.addTo(map);
  if (boundaryNodes.getLayers().length) {
    map.fitBounds(boundaryNodes.getBounds(), {padding:[35,35]});
  }
  document.getElementById('status').textContent =
    records.length + ' nós de contorno carregados · passe o mouse nas bolinhas';
};
window.loadResultAnimation = (frames, metadata) => {
  if (resultTimer) { clearInterval(resultTimer); resultTimer = null; }
  if (resultOverlay) {
    layerControl.removeLayer(resultOverlay);
    map.removeLayer(resultOverlay);
  }
  if (resultAnimationControl) map.removeControl(resultAnimationControl);
  if (!frames.length) return;

  let current = 0;
  resultOverlay = L.imageOverlay(frames[0], metadata.bounds, {
    opacity:0.82, interactive:false
  }).addTo(map);
  layerControl.addOverlay(resultOverlay, metadata.label || 'Animação NetCDF');
  resultAnimationControl = L.control({position:'bottomleft'});
  resultAnimationControl.onAdd = () => {
    const div = L.DomUtil.create('div', 'result-animation');
    const dataStep = metadata.times.length > 1
      ? (Number(metadata.times[1]) - Number(metadata.times[0])) / 3600 : 0;
    div.innerHTML =
      '<div class="row"><button type="button" class="play">▶</button>' +
      '<input class="timeline" type="range" min="0" max="' +
      (frames.length - 1) + '" value="0"><span class="time"></span></div>' +
      '<div class="scale"></div><div style="display:flex;justify-content:space-between;' +
      'margin-top:3px;color:#8fa3b5"><span>0</span><span>Velocidade (' +
      metadata.unit + '): ' + Number(metadata.max).toFixed(2) +
      ' · Δt ' + dataStep.toFixed(2) + ' h</span></div>';
    L.DomEvent.disableClickPropagation(div);
    const play = div.querySelector('.play');
    const timeline = div.querySelector('.timeline');
    const time = div.querySelector('.time');
    const update = index => {
      current = Number(index);
      resultOverlay.setUrl(frames[current]);
      timeline.value = current;
      const seconds = Number(metadata.times[current] || 0);
      time.textContent = metadata.time_labels && metadata.time_labels[current]
        ? metadata.time_labels[current] : (seconds / 3600).toFixed(2) + ' h';
      document.getElementById('status').textContent =
        (metadata.label || 'NetCDF') + ' · passo ' +
        (current + 1) + '/' + frames.length;
    };
    const stop = () => {
      if (resultTimer) clearInterval(resultTimer);
      resultTimer = null; play.textContent = '▶';
    };
    play.addEventListener('click', () => {
      if (resultTimer) { stop(); return; }
      play.textContent = 'Ⅱ';
      resultTimer = setInterval(() => update((current + 1) % frames.length), 300);
    });
    timeline.addEventListener('input', event => { stop(); update(event.target.value); });
    update(0);
    return div;
  };
  resultAnimationControl.addTo(map);
  const resultBounds = L.latLngBounds(metadata.bounds);
  if (!map.getBounds().intersects(resultBounds)) {
    map.fitBounds(resultBounds, {padding:[30,30]});
  }
};
window.loadResultVideo = (url, metadata) => {
  if (resultTimer) { clearInterval(resultTimer); resultTimer = null; }
  if (resultOverlay) {
    layerControl.removeLayer(resultOverlay);
    map.removeLayer(resultOverlay);
  }
  if (resultAnimationControl) map.removeControl(resultAnimationControl);
  resultOverlay = L.videoOverlay(url, metadata.bounds, {
    opacity:0.84, autoplay:false, loop:true, muted:true, playsInline:true
  }).addTo(map);
  layerControl.addOverlay(resultOverlay, 'Animação de correntes');
  const video = resultOverlay.getElement();
  video.muted = true;
  video.loop = true;
  resultAnimationControl = L.control({position:'bottomleft'});
  resultAnimationControl.onAdd = () => {
    const div = L.DomUtil.create('div', 'result-animation');
    const count = Number(metadata.frame_count);
    const fps = Number(metadata.fps);
    const dataStep = metadata.times.length > 1
      ? (Number(metadata.times[1]) - Number(metadata.times[0])) / 3600 : 0;
    div.innerHTML =
      '<div class="row"><button type="button" class="play">▶</button>' +
      '<input class="timeline" type="range" min="0" max="' + (count - 1) +
      '" value="0"><span class="time">0.00 h</span></div>' +
      '<div class="scale"></div><div style="display:flex;justify-content:space-between;' +
      'margin-top:3px;color:#8fa3b5"><span>0</span><span>Velocidade (' +
      metadata.unit + '): ' + Number(metadata.max).toFixed(2) +
      ' · Δt ' + dataStep.toFixed(2) + ' h</span></div>';
    L.DomEvent.disableClickPropagation(div);
    const play = div.querySelector('.play');
    const timeline = div.querySelector('.timeline');
    const time = div.querySelector('.time');
    const refresh = () => {
      const index = Math.min(count - 1, Math.max(0, Math.round(video.currentTime * fps)));
      timeline.value = index;
      const seconds = Number(metadata.times[index] || 0);
      time.textContent = (seconds / 3600).toFixed(2) + ' h';
      document.getElementById('status').textContent =
        'Correntes · passo ' + (index + 1) + '/' + count +
        ' · t = ' + (seconds / 3600).toFixed(2) + ' h';
    };
    play.addEventListener('click', () => {
      if (video.paused) { video.play(); play.textContent = 'Ⅱ'; }
      else { video.pause(); play.textContent = '▶'; }
    });
    timeline.addEventListener('input', event => {
      video.pause(); play.textContent = '▶';
      video.currentTime = Number(event.target.value) / fps;
      refresh();
    });
    video.addEventListener('timeupdate', refresh);
    video.addEventListener('ended', () => { play.textContent = '▶'; });
    return div;
  };
  resultAnimationControl.addTo(map);
  const resultBounds = L.latLngBounds(metadata.bounds);
  if (!map.getBounds().intersects(resultBounds)) {
    map.fitBounds(resultBounds, {padding:[30,30]});
  }
};
window.loadNetCDFOverlay = (url, metadata) => {
  if (netcdfOverlay) { layerControl.removeLayer(netcdfOverlay); map.removeLayer(netcdfOverlay); }
  if (netcdfLegend) map.removeControl(netcdfLegend);
  netcdfOverlay = L.imageOverlay(url, metadata.bounds, {
    opacity:0.78, interactive:false
  }).addTo(map);
  layerControl.addOverlay(netcdfOverlay, metadata.label || 'Campo NetCDF');
  netcdfLegend = L.control({position:'bottomright'});
  netcdfLegend.onAdd = () => {
    const div = L.DomUtil.create('div', 'bathy-legend');
    div.innerHTML = '<div class="bathy-title">' + (metadata.label || 'NetCDF') +
      (metadata.unit ? ' (' + metadata.unit + ')' : '') + '</div>' +
      '<div class="bathy-scale"><div class="bathy-gradient" style="background:' +
      'linear-gradient(to bottom,#7a0403,#fba238,#a4fc3c,#24a4f2,#30123b)"></div>' +
      '<div class="bathy-ticks"><span>' + Number(metadata.max).toPrecision(4) +
      '</span><span>' + Number(metadata.min).toPrecision(4) + '</span></div></div>';
    return div;
  };
  netcdfLegend.addTo(map);
  map.fitBounds(metadata.bounds, {padding:[25,25]});
  document.getElementById('status').textContent =
    (metadata.label || 'Campo NetCDF') + ' carregado no mapa';
};
</script>
</body>
</html>
"""


class MapWidget(QWebEngineView):
    drawings_received = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings().setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls, True
        )
        assets = Path(__file__).resolve().parents[1] / "assets" / "map"
        self.setHtml(MAP_HTML, QUrl.fromLocalFile(str(assets.resolve()) + "/"))

    def request_drawings(self, callback):
        def parse(value):
            try:
                callback(json.loads(value or '{"type":"FeatureCollection","features":[]}'))
            except Exception as exc:
                callback({"error": str(exc), "type": "FeatureCollection", "features": []})
        self.page().runJavaScript("window.getDrawings()", 0, parse)

    def request_drawing_state(self, callback):
        def parse(value):
            try:
                callback(json.loads(value or '{"dirty":false,"drawings":{}}'))
            except Exception as exc:
                callback({"error": str(exc), "dirty": False, "drawings": {}})
        self.page().runJavaScript("window.getDrawingState()", 0, parse)

    def mark_drawings_clean(self):
        self.page().runJavaScript("window.markDrawingsClean()")

    def clear_drawings(self):
        self.page().runJavaScript("window.clearDrawings()")

    def clear_layers(self):
        self.page().runJavaScript("window.clearMapLayers()")

    def load_geojson(self, data: dict):
        encoded = json.dumps(json.dumps(data, ensure_ascii=False))
        self.page().runJavaScript(f"window.loadGeoJSON({encoded})")

    def load_bathymetry_overlay(self, image: Path, metadata: dict):
        url = QUrl.fromLocalFile(str(image.resolve())).toString()
        encoded_url = json.dumps(url)
        encoded_metadata = json.dumps(metadata, ensure_ascii=False)
        self.page().runJavaScript(
            f"window.loadBathymetryOverlay({encoded_url}, {encoded_metadata})"
        )

    def load_boundary_nodes(self, records: list[dict]):
        """Display TELEMAC boundary nodes over the current map workspace."""
        encoded = json.dumps(records, ensure_ascii=False)
        self.page().runJavaScript(f"window.loadBoundaryNodes({encoded})")

    def load_result_animation(self, frames: list[Path], metadata: dict):
        urls = [QUrl.fromLocalFile(str(path.resolve())).toString() for path in frames]
        self.page().runJavaScript(
            "window.loadResultAnimation("
            + json.dumps(urls)
            + ","
            + json.dumps(metadata, ensure_ascii=False)
            + ")"
        )

    def load_result_video(self, video: Path, metadata: dict):
        url = QUrl.fromLocalFile(str(video.resolve())).toString()
        self.page().runJavaScript(
            "window.loadResultVideo("
            + json.dumps(url)
            + ","
            + json.dumps(metadata, ensure_ascii=False)
            + ")"
        )

    def load_netcdf_overlay(self, image: Path, metadata: dict):
        url = QUrl.fromLocalFile(str(image.resolve())).toString()
        self.page().runJavaScript(
            "window.loadNetCDFOverlay(" + json.dumps(url) + "," +
            json.dumps(metadata, ensure_ascii=False) + ")"
        )

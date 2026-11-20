"use strict";
(() => {
  const form = document.querySelector('#query'), back = document.querySelector('#return');
  const locate = document.querySelector('#locate'), notice = document.querySelector('#location-status');
  let geoGeneration = 0, locating = false;
  const fields = Object.fromEntries(['origin', 'destination'].map(key => [key, {
    input: document.querySelector('#' + key + '-place'), button: document.querySelector('#' + key + '-search'),
    status: document.querySelector('#' + key + '-place-status'), results: document.querySelector('#' + key + '-place-results'),
    lat: form.elements[key + '_lat'], lon: form.elements[key + '_lon'], generation: 0, controller: null
  }]));
  function cancel(field) {
    field.generation++; field.controller?.abort(); field.results.replaceChildren();
    field.button.disabled = false;
  }
  function cancelGeo() { geoGeneration++; locating = false; locate.textContent = 'Usar mi ubicación'; }
  function mirror() {
    const origin = fields.origin, target = fields.destination;
    target.input.readOnly = back.checked; target.button.disabled = back.checked;
    target.lat.readOnly = target.lon.readOnly = back.checked;
    if (back.checked) {
      target.input.value = origin.input.value; target.lat.value = origin.lat.value; target.lon.value = origin.lon.value;
      target.status.textContent = 'El destino es el origen.';
    }
  }
  for (const [key, field] of Object.entries(fields)) {
    field.input.addEventListener('input', () => {
      cancel(field); field.lat.value = field.lon.value = ''; field.status.textContent = 'Buscá y elegí un resultado para confirmar la ubicación.';
      if (key === 'origin') { cancelGeo(); notice.textContent = ''; }
      mirror();
    });
    for (const coordinate of [field.lat, field.lon]) coordinate.addEventListener('input', () => {
      cancel(field); field.input.value = ''; field.status.textContent = 'Coordenadas ingresadas manualmente.';
      if (key === 'origin') cancelGeo(); mirror();
    });
    field.input.addEventListener('keydown', event => {
      if (event.key === 'Enter') { event.preventDefault(); field.button.click(); }
    });
    field.button.addEventListener('click', async () => {
      cancel(field);
      if (key === 'origin') cancelGeo();
      mirror();
      if (key === 'destination' && back.checked) return;
      const text = field.input.value.trim(), access = document.querySelector('#access').value.trim();
      if (text.length < 3) { field.status.textContent = 'Escribí al menos tres caracteres.'; field.input.focus(); return; }
      if (!access) { field.status.textContent = 'Ingresá primero el código de acceso a la demo.'; document.querySelector('#access').focus(); return; }
      const generation = field.generation, controller = new AbortController(); field.controller = controller;
      const timer = setTimeout(() => controller.abort(), 15000);
      field.button.disabled = true; field.status.textContent = 'Buscando lugares en CABA…';
      try {
        const response = await fetch('/api/v1/places', {method: 'POST', credentials: 'omit', cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer', signal: controller.signal,
          headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + access}, body: JSON.stringify({text})});
        if (generation !== field.generation) return;
        if (!response.ok) {
          field.status.textContent = response.status === 401 ? 'Revisá el código de acceso.' : response.status === 429 ? 'Hay otra búsqueda en curso. Esperá un momento y volvé a buscar.' : 'El buscador no está disponible. Podés reintentar o ingresar coordenadas.';
          return;
        }
        const data = await response.json();
        if (generation !== field.generation) return;
        if (!Array.isArray(data.items)) throw new Error();
        const choices = data.items.slice(0, 3).filter(item => typeof item.label === 'string' && Number.isFinite(item.lat) && Number.isFinite(item.lon) && item.lat >= -34.71 && item.lat <= -34.52 && item.lon >= -58.54 && item.lon <= -58.33);
        field.status.textContent = choices.length ? 'Elegí el lugar correcto para confirmar.' : 'No encontramos coincidencias en CABA. Probá con calle y altura, o con un nombre más específico.';
        for (const item of choices) {
          const li = document.createElement('li'), button = document.createElement('button');
          button.type = 'button'; button.className = 'secondary'; button.textContent = item.label;
          button.addEventListener('click', () => {
            if (generation !== field.generation) return;
            field.lat.value = item.lat; field.lon.value = item.lon; field.input.value = item.label;
            field.status.textContent = 'Ubicación elegida: ' + item.label; cancel(field); mirror(); field.input.focus();
          });
          li.append(button); field.results.append(li);
        }
      } catch (failure) {
        if (generation === field.generation) field.status.textContent = failure.name === 'AbortError' ? 'La búsqueda demoró demasiado. Podés reintentar o ingresar coordenadas.' : 'No pudimos buscar ese lugar. Revisá la conexión y volvé a intentar.';
      } finally {
        clearTimeout(timer);
        if (generation === field.generation) { field.controller = null; field.button.disabled = key === 'destination' && back.checked; }
      }
    });
  }
  back.addEventListener('change', () => {
    cancel(fields.destination);
    if (!back.checked) { fields.destination.input.value = fields.destination.lat.value = fields.destination.lon.value = ''; fields.destination.status.textContent = ''; }
    mirror();
  });
  locate.addEventListener('click', () => {
    if (locating) { cancelGeo(); notice.textContent = 'Ubicación cancelada. Podés buscar tu dirección.'; fields.origin.input.focus(); return; }
    if (!navigator.geolocation) { notice.textContent = 'Este navegador no ofrece ubicación. Buscá una dirección o ingresá coordenadas.'; fields.origin.input.focus(); return; }
    cancel(fields.origin); cancelGeo();
    fields.origin.input.value = fields.origin.lat.value = fields.origin.lon.value = ''; fields.origin.status.textContent = ''; mirror();
    const generation = geoGeneration; locating = true; locate.textContent = 'Cancelar ubicación'; notice.textContent = 'Buscando tu ubicación… También podés cancelarla y escribir una dirección.';
    function find(retry) {
      navigator.geolocation.getCurrentPosition(position => {
        if (generation !== geoGeneration) return;
        cancelGeo();
        const {latitude: lat, longitude: lon, accuracy} = position.coords;
        if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -34.71 || lat > -34.52 || lon < -58.54 || lon > -58.33) {
          notice.textContent = 'La ubicación recibida no está dentro de CABA. Buscá tu dirección para confirmarla.'; fields.origin.input.focus(); return;
        }
        fields.origin.lat.value = lat; fields.origin.lon.value = lon; fields.origin.input.value = 'Mi ubicación';
        fields.origin.status.textContent = 'Ubicación del navegador seleccionada.'; mirror();
        notice.textContent = 'Ubicación completada' + (Number.isFinite(accuracy) ? ' (aproximadamente ±' + Math.ceil(accuracy) + ' m)' : '') + '. Confirmá que sea correcta; podés reemplazarla por una dirección.';
      }, failure => {
        if (generation !== geoGeneration) return;
        if (failure.code === 3 && !retry) { notice.textContent = 'La primera búsqueda demoró. Reintentando una vez; podés cancelar y buscar una dirección.'; find(true); return; }
        cancelGeo();
        const reason = {1: 'El navegador o el sistema no dieron permiso de ubicación.', 2: 'El equipo no pudo determinar dónde estás.', 3: 'El equipo no respondió con una ubicación.'}[failure.code] || 'No pudimos obtener tu ubicación.';
        notice.textContent = reason + ' Buscá tu dirección o ingresá las coordenadas manualmente.'; fields.origin.input.focus();
      }, {timeout: retry ? 20000 : 12000, maximumAge: 60000, enableHighAccuracy: retry});
    }
    find(false);
  });
  form.addEventListener('submit', event => {
    for (const field of Object.values(fields)) if (!field.lat.value || !field.lon.value) {
      event.preventDefault(); event.stopImmediatePropagation(); field.status.textContent = 'Elegí un resultado de búsqueda o ingresá las coordenadas.'; field.input.focus(); return;
    }
    cancelGeo(); for (const field of Object.values(fields)) cancel(field); mirror();
  });
  window.addEventListener('pagehide', () => {
    cancelGeo(); notice.textContent = '';
    for (const field of Object.values(fields)) { cancel(field); field.input.value = field.lat.value = field.lon.value = ''; field.status.textContent = ''; }
    mirror();
  });
  mirror();
})();

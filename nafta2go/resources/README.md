# Comunas públicas de las estaciones

Fuente: [GCBA, Comunas](https://data.buenosaires.gob.ar/dataset/comunas).
Licencia: CC-BY-2.5-AR. Extracción: 2026-11-22.
SHA-256 del GeoJSON original: `a4a7be8222a6a5c4a5a28c5e6e1b5ff5b0f6ba25f2788250f0ab3f9d6d59959f`.

`communes.json` conserva IDs de comuna y todos los polígonos/anillos del GeoJSON,
redondeando a seis decimales y descartando propiedades ajenas al cálculo.
No contiene estaciones ni ubicaciones de conductores. Reproducción:
`python scripts/prepare_communes.py`. Si cambia la fuente se debe revisar su hash.
Un punto sin clasificación se publica como `unknown`, nunca se infiere del usuario.

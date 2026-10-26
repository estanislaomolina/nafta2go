# Cierre de la Entrega 2

La POC se demuestra con [POC-05](POC-05.md); el diseño está en el [SRD](SRD.md).
El video de esta entrega todavía debe grabarse. El enlace del README corresponde
a la Entrega 1 y no reemplaza esa demostración.

## Guion sugerido: 8 a 10 minutos

| Tiempo | Responsable sugerido | Qué mostrar |
|---|---|---|
| 0:00–1:00 | Estanislao | Problema, caso Obelisco → Cabildo y alcance de la POC |
| 1:00–2:30 | Felipe | Fuente, normalización, fechas, cobertura cerca del recorrido y respaldo histórico rotulado |
| 2:30–4:00 | Santiago | Adaptador ORS, evidencia autenticada, esquema SQLite, migraciones y CI |
| 4:00–7:00 | Estanislao | Consulta completa, explicación de la estación elegida y variantes sin presupuesto y sin cobertura |
| 7:00–8:30 | Equipo | SRD y diagramas, ADRs, simplificaciones y próximos pasos del MVP |
| 8:30–9:00 | Equipo | PRs y contribuciones, evidencia de pruebas, commit de entrega |

Todos deben poder explicar el código que presentan. Los tiempos y responsables
son una propuesta; no implican resultados de una grabación ya realizada.

## Preparar la demo

Instalar dependencias y usar una base nueva para que el escenario sea reproducible:

```bash
export DATABASE_URL=sqlite:////tmp/nafta2go-video-entrega2.db
python -m nafta2go.query \
  --origin=-34.6037,-58.3816 --destination=-34.5627,-58.4565 \
  --matrix-file docs/evidencia/poc-05-flujo-2026-10-26/matrix.json
```

Explicar que los precios son del escenario del 24/10 y las rutas se consultaron
el 26/10. El rótulo aparece en pantalla. La estación 3765 gana las tres
prioridades en este caso, por eso se muestra una vez. Después ejecutar:

```bash
# Misma consulta anterior con --presupuesto=0: no hay ganadora factible.
python -m nafta2go.query \
  --origin=-34.6037,-58.3816 --destination=-34.5627,-58.4565 \
  --matrix-file docs/evidencia/poc-05-flujo-2026-10-26/matrix.json --presupuesto=0

# Dentro del rectángulo de CABA, sin cobertura suficiente: no consulta rutas.
python -m nafta2go.query --origin=-34.71,-58.33
```

No mostrar `.env` ni credenciales durante la grabación. La reproducción anterior
no necesita clave ni conexión. Para demostrar la ingesta y las rutas en vivo,
seguir [POC-05](POC-05.md); conservar los rótulos y las fechas reales.

## Antes de entregar

- Integrar el PR de cierre de POC-05 con aprobación de Felipe o Santiago y CI verde.
- Revisar los ADRs propuestos y confirmar sus estados.
- Actualizar los issues y el Project contra los criterios, sin cerrar requisitos
  que sigan pendientes. POC-03 declara que el límite por minuto no fue medido;
  el valor publicado y la cuota diaria observada son cosas diferentes.
- Grabar el video de 5 a 12 minutos y enlazarlo explícitamente como Entrega 2
  desde el README.
- Abrir el PR `dev` → `main`, revisar y usar merge commit para la entrega.
- Esperar el CI verde sobre `main` y crear el tag anotado `entrega-2-poc` sobre
  ese commit. No etiquetar una entrega que todavía no incluye el video o la POC.
- Entregar el enlace al repositorio, al video y al commit/tag solicitado.

El bug numérico de baja gravedad [#34](https://github.com/estanislaomolina/nafta2go/issues/34)
está declarado; no debe presentarse como corregido en el video.

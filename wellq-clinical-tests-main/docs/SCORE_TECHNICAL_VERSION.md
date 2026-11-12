# Score técnico v1.1 (propuesta no aprobada clínicamente)

El catálogo `cat-2026.08` es una selección inicial: pesos definidos bone 0.45,
muscle 0.55, joint 0.55 y cardio 0.90. No equivale al catálogo completo de la
Tabla 21 proporcionada por el usuario. No se añadieron marcadores, pesos o rangos.

`score-v1.1` corrige cobertura como suma de pesos válidos/suma de pesos definidos
en ese catálogo. Los umbrales se aplican antes de redondear. La suma decimal de
pesos evita promover 0.349 o 0.599 por redondeo. Pesos inválidos o denominador
cero no generan un pilar publicable. El índice utiliza subscores/pilares sin
redondeo intermedio; el redondeo de presentación no alimenta la agregación.
Las banderas direccionales solo penalizan el lado correspondiente de la regla.
Las mediciones con unidad canónica incompatible quedan excluidas explícitamente.

La cobertura puede ser 1 respecto de esta selección, **no** de la propuesta
completa. Cada snapshot nuevo conserva en `parameters` la base de cobertura,
`catalog_definition_complete=false` y `technical_only=true`. La publicación
clínica requiere tanto aprobación como completitud; un flag solo no basta.
ENVIRONMENT=test permite resultados técnicos sintéticos, no aprobación médica.

Se conserva el histórico append-only y su versión original. El motor no admite
etiquetar un cálculo nuevo como una implementación histórica desconocida.
Los snapshots v1.0 se conservan como evidencia; no se republican como cálculos
v1.1 actuales. No hubo recálculo ni migración de la base histórica.

Fronteras: 0.349 → insuficiente; 0.350 → media; 0.599 → media; 0.600 → alta.
Ejemplo documental agregado: base 78.5, penalización high 5, índice 73.5.
La ventana usa meses calendario, ambos días límite incluidos, y la última
medición válida confirmada por marcador; las pruebas existentes cubren empates,
invalidaciones y conservación de snapshots.

Validación aislada: checks de Score, reproducción de fórmulas, exportación PDF
atómica y presentación PDF. Mongo en memoria y dobles de almacenamiento; no
certifica transacciones Mongo reales ni proveedores productivos.

El contenedor histórico se conserva con su imagen anterior. La nueva versión
se prueba en memoria y debe desplegarse únicamente en la demostración aislada;
no se sustituyó la imagen histórica ni se eludió el control de coincidencia de
código del puente. Después de estos cambios, una nueva recuperación bridge-only
puede rechazar correctamente la imagen histórica por desfase de fuente.

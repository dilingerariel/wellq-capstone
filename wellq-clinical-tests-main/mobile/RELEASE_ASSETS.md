# Preparación de fuentes Flutter sin PDF de demostración

El `pubspec.yaml` habitual y `assets/synthetic.pdf` se conservan para desarrollo
y pruebas. **Un release construido directamente desde esa carpeta todavía
incluiría el ejemplo.** No se añadieron flavors ni se cambiaron identidad,
selección de PDF, hashes, Drift, paquete Android, firma o sincronización.

Para preparar futuras compilaciones productivas, desde la raíz del repositorio
con Git limpio y los cambios guardados:

```powershell
.venv/Scripts/python.exe -B wellq-clinical-tests-main/mobile/tool/prepare_release_source.py
```

La herramienta usa `git archive HEAD` y crea una carpeta nueva e ignorada por Git
en `.venv/wellq-mobile-release-source/run-*/mobile`. Copia únicamente fuentes y
configuración de plataformas versionadas, sin el directorio de assets, tests,
herramientas, cachés ni `.runtime`. En **esa copia** elimina exclusivamente el
bloque actual del único asset de ejemplo. Rechaza cambios inesperados del
manifiesto en vez de omitir silenciosamente otros assets futuros.

No lee configuración local de SDK, claves de firma ni datos del dispositivo.
No sobrescribe carpetas, modifica el checkout ni compila. Registra el commit y
los hashes de las fuentes preparadas en `release-source.json`, con estado
`SOURCES_PREPARED_NOT_BUILT`. Si se añaden otros assets necesarios al proyecto,
debe revisarse explícitamente la preparación antes de usarla.

Una futura compilación release autorizada deberá partir de **esa carpeta** y
provisionar SDK/firma aprobados por separado. La app sigue bloqueada para uso
productivo: esta preparación no integra identidad real ni habilita pacientes.
No se debe ejecutar el modo demo desde la copia, porque no contiene su PDF.

## Verificación pequeña

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s wellq-clinical-tests-main/mobile/tool -p test_prepare_release_source.py
```

Las pruebas usan archivos sintéticos temporales y no llaman a Flutter. Quedan
pendientes compilar el candidato con autorización e inspeccionar el APK/AAB
final, su manifiesto de assets y dependencias para acreditar que no contiene el
PDF ni otros recursos indebidos. La inspección de fuentes preparadas **no**
equivale a una verificación de un APK limpio. No se eliminan fixtures originales.

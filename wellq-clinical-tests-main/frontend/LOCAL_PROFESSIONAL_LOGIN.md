# Acceso profesional sintético desde React

Este recorrido usa el gestor de sesión y el emisor RS256 **local existente**.
No es un proveedor productivo, no crea usuarios ni incorpora contraseñas/OTP.
El navegador recibe tokens solo en RAM; no se escriben en comandos ni consola.

## Condición previa

Debe estar disponible el entorno de integración sintética existente, con su
identidad y aislamiento verificados. No se inicia Docker/WSL ni se crean datos
para demostrar este acceso. Si el puente ya funciona, se conserva tal cual.
Si el entorno autorizado ya está saludable y solo falta el puente, el modo
existente `bridge-only` comprueba pertenencia y salud antes de iniciarlo:

```powershell
cd C:\Dev\wellq-capstone
.venv/Scripts/python.exe -B wellq-clinical-tests-main/frontend/scripts/local_web.py bridge-only
```

Ese modo no inicia contenedores ni ejecuta `host.seed()`. Si rechaza el entorno,
detenerse y conservar el error: no sustituirlo por el arranque habitual, no
desactivar aislamiento y no ejecutar semillas. Sin el puente/API disponibles,
se puede revisar la interfaz, pero no acreditar sesión ni permisos HTTP reales.
No ejecutar `WellQ.ps1 Start` ni el modo `Live` para este procedimiento.

## Abrir y demostrar el acceso

Abrir `C:\Dev\wellq-capstone` en VS Code. En otra terminal PowerShell:

```powershell
cd C:\Dev\wellq-capstone\wellq-clinical-tests-main\frontend
$env:VITE_DATA_MODE='api'
$env:WELLQ_LOCAL_INTEGRATION='1'
$env:WELLQ_LOCAL_PROFESSIONAL_LOGIN='1'
$env:WELLQ_DEV_API_TARGET='http://127.0.0.1:8765'
npm run dev -- --port 5178 --strictPort
```

Abrir `http://127.0.0.1:5178/clinical`. El puerto 5178 es el origen admitido por
el puente existente; no sustituir procesos si está ocupado. Debe aparecer el
aviso de entorno sintético y la tarjeta **Acceso profesional**, sin sesión.

1. Pulsar **Iniciar sesión**. El adaptador solicita al host existente el perfil
   sintético `clinician`; no permite elegir otro rol en esta entrada profesional.
2. El portal muestra navegación profesional. Seleccionar un paciente sigue
   requiriendo autorización del backend; escribir un ID no concede acceso.
   No consultar pacientes reales ni crear documentos para esta demostración.
3. La acción de renovación usa el método ya existente del adaptador. El gestor
   conserva los controles de expiración y limpia el estado privado al salir.
4. Pulsar **Cerrar sesión**: vuelve la tarjeta de acceso. **Comprobar sesión**
   no vuelve a iniciar sesión; hace falta pulsar **Iniciar sesión** otra vez.

Sin `WELLQ_LOCAL_PROFESSIONAL_LOGIN=1`, el adaptador anterior conserva su
comportamiento para las herramientas aisladas de paciente/integración. Las
variables de esta guía pertenecen solo a la terminal de desarrollo.

El plugin solo se aplica a `serve` y rechaza servidor con configuración
productiva. La entrada profesional exige el destino exacto de loopback
`http://127.0.0.1:8765`; rechaza destinos externos o alternativos.
No se integra en el build de producción. Permanecen las barreras de
modo React y de autoridad sintética FastAPI. No se cambiaron roles, JWT ni API.

## Evidencia y límites de esta entrega

Las pruebas focalizadas usan el adaptador JS, `SessionManager`, `RuntimeProvider`
y la interfaz React reales, con **dobles HTTP explícitos** en JSDOM. Cubren
entrada desde el botón, rol/navegación profesional, renovación, logout sin
reentrada, sesión expirada, compatibilidad del adaptador anterior y guardia de
producción. No firman JWT ni llaman a MongoDB o FastAPI.

Quedan pendientes la demostración en navegador contra el host real, validación
RS256 efectiva y pruebas negativas de paciente/tenant ajeno en el entorno
aislado autorizado. No se acredita aquí el recorrido E2E ni uso productivo.
La integración productiva requiere un contrato autorizado del proveedor y su
configuración de emisor, audiencia, claves, renovación y revocación.

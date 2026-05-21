# Guion para AWS: Ajolotes en la Nube

## Enfoque

Esta version debe sentirse como una conferencia centrada en AWS. El caso real es Zoolandingpage y `zoolanding-data-dropper-lambda`, pero cada diapositiva debe sostener una idea completa por si sola: tesis, evidencia tecnica y conclusion practica.

Tesis para repetir: una arquitectura serverless buena no es acumular servicios; es que cada servicio tenga una responsabilidad clara.

## Ritmo sugerido por bloques

### Apertura y objetivo

Tiempo sugerido: 6 minutos.

Abre con el problema completo: capturar eventos de una app real sin exponer credenciales AWS ni construir una plataforma de analitica desde cero.

Menciona brevemente que AWS Ajolotes en la Nube es la comunidad AWS de Ciudad de Mexico que invito la charla; no lo presentes como metafora tecnica del diseno.

Mensajes clave:

- Browser no habla directo con S3.
- API Gateway y Lambda forman un punto de entrada publico y controlado.
- S3 recibe eventos originales para analitica posterior.
- Cada slide debe poder compartirse aislada sin depender de "la anterior".

### Vocabulario y mapa AWS

Tiempo sugerido: 10 minutos.

Usa el glosario para nivelar a la audiencia. No leas todo: detente en Edge, Origin, Lambda, S3 prefix, IAM role y SAM.

En el mapa serverless, recorre de izquierda a derecha:

Browser -> Angular -> CloudFront -> API Gateway -> Lambda -> S3 -> ETL futuro.

Mensaje clave: cada servicio tiene una responsabilidad pequena, por eso el sistema es explicable.

### Punto de entrada y API

Tiempo sugerido: 10 minutos.

Contrasta dos opciones:

- Directo a S3 desde frontend: mas permisos expuestos y mas acoplamiento.
- HTTP hacia API Gateway/Lambda: entrada controlada y rol IAM limitado.

Cuando muestres CloudFront y API Gateway, usa visuales redaccionados por defecto. Si abres consola real, evita revelar IDs de cuenta, IDs de API, distribution IDs, cookies o URLs internas que no sean necesarias.

### Lambda como codigo bajo demanda

Tiempo sugerido: 14 minutos.

Esta es la parte mas tecnica. Recorre el handler en el orden del flujo:

1. `_decode_body`
2. parse JSON
3. validar `appName` y `timestamp`
4. normalizar segundos/milisegundos
5. derivar particion UTC
6. calcular hora local solo con IANA timezone valida
7. `put_object`

Mensaje clave: la Lambda no hace BI ni ETL; protege la ingesta y conserva el evento original.

### S3, tiempo y eventos originales

Tiempo sugerido: 10 minutos.

Enfatiza que la key es una decision de arquitectura, no un detalle de formato de texto.

Puntos importantes:

- UTC para particiones.
- Viewer-local time solo como metadata y respuesta cuando el cliente manda timezone valida.
- El JSON original no se reescribe.

### Seguridad, IAM, SAM y operacion

Tiempo sugerido: 14 minutos.

Este bloque es el corazon AWS para la audiencia cloud.

Resalta:

- IAM con `s3:PutObject` solamente.
- CORS declarado en API Gateway.
- Runtime, timeout, memoria y env vars versionados con SAM.
- Logs JSON utiles para rastrear `requestId`, `appName`, `key` y `size`.
- CloudWatch puede ser muy util, pero los logs tambien cuestan si crecen sin control.

### Costos, escala, futuro y demo

Tiempo sugerido: 12 minutos.

No prometas numeros si no hay calculo actual. Explica motores de costo:

- Lambda por invocacion y duracion.
- API Gateway por peticiones.
- S3 por objetos, almacenamiento y peticiones.
- CloudWatch por volumen de logs.
- Athena futura por datos escaneados.

El futuro recomendado es una primera tabla normalizada desde S3, sin romper el almacenamiento original.

## Demo recomendada

1. Abrir `template.yaml` y mostrar API, Lambda, CORS e IAM.
2. Abrir `lambda_function.py` y mostrar el flujo del handler.
3. Abrir `tests/test_lambda_function.py` y mostrar el test de key + metadata.
4. Si hay entorno disponible, mostrar DevTools con `POST /analytics`.
5. Si se muestra consola AWS, limitarse a API Gateway, Lambda env vars y S3 prefix sin revelar identificadores sensibles.

## Respuestas preparadas

### Por que no DynamoDB

Porque el caso actual solo agrega eventos sin transformar. DynamoDB puede servir para otros patrones, pero aqui el valor principal es conservar eventos reprocesables con costo bajo y analizarlos despues.

### Por que no Kinesis

Kinesis tiene sentido si hay necesidad explicita de streaming, multiples consumidores en tiempo casi real o volumen que justifique ese costo operativo. El repo actual no necesita eso para el primer patron.

### Por que no inferir timezone desde IP o region AWS

Porque seria impreciso y puede introducir problemas de privacidad. El repo conserva UTC siempre y solo calcula viewer-local time si el cliente manda una timezone IANA valida.

### Que sigue despues

El siguiente paso esta descrito en `docs/etl-starting-point.md`: leer S3 por app/rango UTC, parsear JSON original, agrupar por `sessionId`, resolver timezone por sesion y producir una tabla normalizada para reportes.

## Checklist previo

- Renderizar `slides-aws-ajolotes.md` con Marp.
- Validar que `images/aws-ajolotes-stack.svg` se vea completo.
- Revisar que cada diapositiva tenga claim propio y no dependa de otra para entenderse.
- Confirmar que las capturas reales sigan reemplazadas por SVGs redaccionados en CloudFront, API Gateway, Lambda y DevTools.
- Confirmar que no se agregaron IDs de cuenta, API IDs, distribution IDs, secretos, cookies o datos personales.
- Ejecutar `python -m unittest discover -s tests`.
- Preparar archivos a abrir en vivo: `template.yaml`, `lambda_function.py`, `tests/test_lambda_function.py`, `docs/etl-starting-point.md`.

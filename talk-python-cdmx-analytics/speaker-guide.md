# Guion general de exposicion

## Enfoque general

Este guion esta pensado para una charla de **60 a 70 minutos** con espacio para preguntas al final. No es una transcripcion literal; es una guia de ritmo, mensajes clave y recortes posibles.

## Estructura y tiempos sugeridos

### Slides 1-6 — Apertura, agenda, glosario e indice

**Tiempo sugerido:** 7 minutos

Abre explicando que la charla no es una introduccion abstracta a AWS, sino un recorrido tecnico sobre un caso real: como Zoolandingpage captura eventos y como una Lambda Python los guarda de forma barata y util para analitica posterior.

Mensajes clave:

- La parte central de la charla es `zoolanding-data-dropper-lambda`.
- Zoolandingpage se usa como contexto para entender de donde salen los eventos.
- El objetivo no es hacer BI en tiempo real, sino construir una base solida para analisis posterior.

Si vas justo de tiempo, resume la agenda en menos de un minuto.

Ahora el glosario ya vive al inicio. Usalo para nivelar a la audiencia antes de entrar en arquitectura. No leas cada definicion completa; alcanza con presentar los terminos que vas a repetir durante toda la charla: SAM, DNS, CloudFront, API Gateway, Lambda, S3, CORS, IAM y UTC.

Despues del glosario ahora hay un indice navegable. Sirve para volver rapido al bloque correcto si en algun momento saltas desde una slide tecnica hacia una definicion.

### Slides 7-8 — Que problema estamos resolviendo

**Tiempo sugerido:** 6 minutos

Explica que una landing genera preguntas de producto y negocio muy concretas: que CTA funciona, cuanto scroll hay, que seccion ve el usuario, si hay diferencias por idioma o ruta. Enfatiza que el problema no es solo recolectar eventos, sino hacerlo sin meter demasiada complejidad ni costo en el frontend.

Mensajes clave:

- separar captura de eventos y persistencia cruda simplifica el sistema
- no todos los proyectos necesitan una plataforma de analytics compleja desde el dia uno
- S3 puede ser suficiente y muy conveniente para la primera etapa

### Slide 9 — Vista general del sistema

**Tiempo sugerido:** 5 minutos

Usa el diagrama para recorrer el pipeline completo. Menciona que el usuario interactua con una landing Angular, el frontend genera o detecta eventos, los envia a un endpoint estable, y el backend serverless se limita a validarlos y guardarlos.

Mensaje que conviene repetir:

Cada bloque hace poco, pero lo hace muy claro.

### Slides 10-11 — Generacion de eventos en Angular

**Tiempo sugerido:** 8 minutos

Explica que el frontend ya tiene un catalogo de eventos y un servicio centralizado. Esto evita que cada componente hable directo con la API de analytics. Menciona ejemplos del catalogo y resalta que tambien se trackean patrones automaticos como `scroll_depth`, `section_view` y navegacion por anchors.

Mensajes clave:

- el frontend centraliza envio, mapeo y buffering
- eso permite dejar la Lambda muy pequena
- la disciplina del lado cliente reduce mucho el caos del lado servidor

Recorte posible:

- si falta tiempo, menciona solo dos eventos manuales y dos automaticos

### Slides 12-13 — Contrato minimo y razon de ser de la Lambda

**Tiempo sugerido:** 6 minutos

Muestra que el contrato minimo es deliberadamente pequeno: `appName` y `timestamp`. Todo lo adicional se conserva. Enfatiza que esto desacopla mucho el backend del tipo exacto de eventos que vaya emitiendo el frontend.

Luego conecta eso con la existencia de la Lambda dedicada: no exponer credenciales, no hablar directo a S3 desde el navegador, y centralizar convenciones de persistencia.

### Slides 14-18 — Deep dive de la Lambda

**Tiempo sugerido:** 16 minutos

Esta es la parte mas importante de la charla. Recorrela con calma.

Orden recomendado:

1. `decode_body`: compatibilidad con API Gateway y base64.
2. parseo JSON y validacion minima.
3. normalizacion de timestamp a milisegundos.
4. derivacion de fecha en UTC.
5. construccion de la key.
6. `put_object` guardando el body original.

Mensajes clave:

- la Lambda no “entiende” todos los eventos, solo garantiza un raw sink confiable
- usar UTC para particiones evita dolores posteriores
- preservar el body original es una decision de producto y de arquitectura, no un detalle accidental

Recorte posible:

- si el tiempo aprieta, omite la lectura textual del codigo y resume el flujo con el diagrama

### Slide 19 — Ejemplo completo de payload a key

**Tiempo sugerido:** 4 minutos

Aqui conviene detenerte un poco para que la audiencia conecte todo. Toma el JSON del lado izquierdo y explica como se transforma unicamente en naming y ubicacion, no en estructura nueva. Remarca que el contenido interno del evento no se reescribe.

### Slides 20-33 — S3, AWS y lectura de capturas

**Tiempo sugerido:** 18 minutos

Explica los beneficios de S3 para eventos raw y despues abre el panorama AWS.

Puntos a mencionar:

- CloudFront da un dominio estable para la API
- API Gateway expone la ruta `POST /analytics`
- Lambda ejecuta la logica minima
- S3 almacena los objetos
- Route 53 es la capa DNS que normalmente apunta dominios propios hacia CloudFront

No sobreexplique Route 53: en esta charla es contexto, no el centro del caso.

Ahora ya tienes capturas reales y el tramo fue dividido en piezas mas pequenas. Aprovechalas en este orden:

1. CloudFront para explicar alias y routing.
2. API Gateway para mostrar la entrada `POST /analytics`.
3. Lambda para mostrar handler y variables de entorno.
4. S3 para enseñar el resultado real.
5. DevTools para cerrar el ciclo desde el navegador.

Tambien ya hay una slide separada para SAM y otra para sus parametros operativos; eso te da margen para explicar IaC sin saturar una sola diapositiva.

### Slides 26-30 — SAM, seguridad y demo de codigo

**Tiempo sugerido:** 8 minutos

Explica por que el template SAM importa: infraestructura declarada, menos drift, permisos mas claros. Menciona que el rol IAM solo necesita `s3:PutObject` y que la Lambda tiene `DRY_RUN` para pruebas locales.

Si decides abrir el repo en vivo, esta es la mejor parte para hacerlo.

### Slides 34-36 — Costos, lecciones y evoluciones

**Tiempo sugerido:** 7 minutos

En esta parte conviene sonar practico. Habla de costo, mantenibilidad y escalado gradual.

Mensajes clave:

- este patron tiene una relacion costo/beneficio muy buena
- no todos los proyectos necesitan tiempo real desde el primer dia
- guardar crudo primero permite construir agregados despues

### Slide final — Cierre y preguntas

**Tiempo sugerido:** 4 minutos

Resume en una sola frase fuerte:

Una Lambda pequena, con una convencion clara de keys y S3 como raw store, puede ser una muy buena base de analytics para un producto real.

Despues abre preguntas.

## Preguntas que probablemente te haran

### Por que no mandar directo a S3 desde frontend

Porque perderias un punto central de validacion, controlarias peor CORS y expondrias mas superficie de seguridad. La Lambda cuesta poco y te deja una frontera clara.

### Por que no usar DynamoDB o RDS para cada evento

Porque para eventos append-only S3 suele ser mas barato y suficiente. Si despues se necesitan consultas o agregados, puedes procesar el raw data.

### Por que guardar el JSON original

Porque evita perder campos nuevos y te deja rehacer transformaciones despues. Es una decision muy buena cuando aun estas aprendiendo que preguntas analiticas importan de verdad.

### Que sigue despues de esta arquitectura

Athena, Glue, agregados diarios, dashboards o pipelines batch. La clave es que ya tienes una fuente raw confiable.

## Material que conviene tener abierto durante la conferencia

- [zoolandingpage/src/app/shared/services/analytics.service.ts](../../zoolandingpage/src/app/shared/services/analytics.service.ts)
- [zoolandingpage/src/app/shared/services/analytics.events.ts](../../zoolandingpage/src/app/shared/services/analytics.events.ts)
- [zoolanding-data-dropper-lambda/local_test.py](../local_test.py)
- [zoolanding-data-dropper-lambda/lambda_function.py](../lambda_function.py)
- [zoolanding-data-dropper-lambda/template.yaml](../template.yaml)
- [zoolandingpage/docs/06-deployment.md](../../zoolandingpage/docs/06-deployment.md)

## Checklist previo a exponer

- confirmar que el deck renderiza bien en Marp
- validar que las capturas nuevas se vean con buena resolucion en pantalla completa
- probar que los enlaces internos al glosario y al indice funcionen al hacer click en el preview o export final
- abrir de antemano los archivos de codigo que vas a mostrar
- preparar un ejemplo real de key de S3 si ya existe en produccion
- decidir si mostraras CloudWatch o solo el flujo de escritura a S3

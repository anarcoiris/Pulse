# Rediseño del Circuito Teórico: Enfoque en el Control y la Seguridad
El nuevo diseño se centra en tres pilares:

- **Conmutación Controlada:** Reemplazar el spark gap caótico por un sistema de conmutación de estado sólido, controlado y repetible.
- **Gestión de la Energía:** Asegurar que la descarga sea rápida y potente, pero contenida y dirigida.
- **Aislamiento y Seguridad:** Proteger tanto al operador como a la electrónica circundante.

## 1. Solución a la Conmutación (Problemas Spark Gap, Interruptores)
El spark gap es la mayor fuente de caos. Lo reemplazamos por un tiristor (SCR) de pulso o un IGBT de alta velocidad, que son los componentes estándar en la industria para esta aplicación.

**Componente Clave:** Un SCR de pulso (como un dispositivo de la familia "Pulse Rated Thyristor") o un IGBT de alta velocidad y alta tensión.

**Ventajas:**
- **Disparo Preciso:** Se activan con una señal de baja tensión (5-15V) en su puerta (gate), permitiendo un control por microcontrolador o circuito de temporización.
- **Jitter Casi Nulo:** El momento de la conmutación es altamente predecible y repetible.
- **Baja Resistencia en Conducción:** Una vez que se encienden, se comportan como un cortocircuito, ideal para una descarga de alta corriente.
- **Sin EMI de Conmutación:** A diferencia del arco, no hay una explosión de plasma que genere interferencias caóticas.

## 2. Solución a la Fuente de Alimentación (Problema Flyback)
La fuente flyback es inadecuada para cargar un banco de condensadores de forma precisa. La reemplazamos por una fuente de alta tensión con control de corriente.

**Componente Clave:** Módulo fuente HV DC-DC con control de corriente y voltaje (disponibles comercialmente para aplicaciones de láser N2, tubos de Geissler, etc.).

**Ventajas:**
- **Salida DC Limpia:** Proporciona un voltaje estable y sin ruido.
- **Control Preciso:** Permite definir la tensión de carga exacta (ej. 4.5 kV) y limitar la corriente para una carga segura y controlada de los condensadores.
- **Seguridad:** Suelen incluir protecciones internas de sobrecorriente y sobrevoltaje.

## 3. Solución al Inductor y la Antena (Problema de Layout y Desadaptación)
El problema es que el circuito no es un resonador LC limpio, sino una línea de transmisión de pulso. Debemos diseñarlo como tal.

**Componente Clave:** Una Red Formadora de Pulso (PFN - Pulse Forming Network). Esta es la solución estándar de ingeniería para generar pulsos rectangulares de alta potencia.

**Diseño de la PFN:**
- En lugar de un único LC, usamos una cadena de secciones LC (el documento original lo mencionaba: PFN tipo Guillemin).
- Esto crea una línea de transmisión artificial con una impedancia característica $Z_0$ bien definida.
- El diseño se basa en la impedancia de la antena (ej. 50 Ω) y la duración del pulso deseada ($\tau$).

$$
Z_0 = \sqrt{L_{\text{sección}} / C_{\text{sección}}} = 50\,\Omega
$$
$$
\tau = 2N \sqrt{L_{\text{sección}} \cdot C_{\text{sección}}}
$$
(donde $N$ es el número de secciones)

- **Inductores:** Se deben usar inductores de aire o toroides de ferrita específicos para alta potencia de pico, calculados para no saturar con la corriente de pico esperada.
- **Antena:** La antena TEM Horn sigue siendo una buena opción, pero ahora está perfectamente adaptada a la impedancia de la PFN, maximizando la transferencia de energía y minimizando reflexiones.

## Esquema del Circuito Mejorado
Aquí tienes un nuevo esquema que incorpora estas mejoras:

```text
+---------------------+
          |  Fuente HV DC-DC    |
          |  (Controlada)       |
          |  0-5 kV, 10 mA      |
          +----------+----------+
                     |
                 [R_limite]
                 100 kΩ
                     |
                     +----+----+----[V_medición HV]----+
                     |    |    |                        |
         +-----------+    |    |                        |
         |                |                             |
       +---+            +---+                         |
       | S1|            | S2|                         |
       |   |            |   |                         |
         +---+            +---+                         |
         | ON/OFF         | Medición                   |
         |                |                             |
         +----------------+-----------------------------+
                     |
                     +----+----+----+----+----+----+----+
                     |    |    |    |    |    |    |    |
                   +---+ +---+ +---+ +---+ +---+ +---+ +---+
                   | C1 | | C2 | | C3 | | C4 | | C5 | | C6 |
                   | 0.1| | 0.1| | 0.1| | 0.1| | 0.1| | 0.1|
                   | µF | | µF | | µF | | µF | | µF | | µF |
                   @5kV @5kV @5kV @5kV @5kV @5kV
                   +---+ +---+ +---+ +---+ +---+ +---+
                     |    |    |    |    |    |    |
                     +----+----+----+----+----+----+
                                 |
                                 |  (Banco de Condensadores)
                                 |
                           +-----+------+
                           |  PFN       |
                           | (N=6 sec.) |
                           | Lk=125nH   |
                           | Ck=0.1µF   |
                           +-----+------+
                                 |
                                 +----+----+----[V_salida PFN]----+
                                 |    |    |                        |
                               +---+  +---+                        |
                               | S3   | S4                         |
                               |      |                            |
                     +---------+----+ +----+-----------------------+
                     |               |    |
                     |           [SCR/IGBT]    <-- Disparador de Puerta (Gate)
                     |           (Conmutador)     (Controlado por MCU)
                     |               |    |
                     +-------+-------+----+
                             |
                           [Inductor de Aislamiento]
                           (Pico de tensión)
                             |
                             +----+----+----[V_antena]----+
                             |    |    |                    |
                           +---+  +---+                    |
                           | S5   | S6                     |
                           |      |                        |
                 +---------+----+ +----+-------------------+
                 |               |    |
                 |             [Antena]
                 |             (TEM Horn)
                 |             Z=50Ω
                 |               |
                 +---------------+
```

**Descripción de los Componentes Mejorados:**
- **Fuente HV DC-DC Controlada:** Proporciona un DC limpio. S1 es un interruptor de seguridad principal. S2 permite aislar el banco para medir su voltaje de forma segura.
- **Banco de Condensadores (PFN):** En lugar de un simple LC, tenemos un banco de condensadores que forma parte de la PFN. Los valores de C y L están calculados para crear una impedancia de 50 Ω y un pulso de, por ejemplo, $\tau = 100\,$ns.
- **Conmutador de Estado Sólido (SCR/IGBT):** Este es el corazón del nuevo diseño. S3 y S4 son la conexión a la carga (la PFN). El dispositivo se activa mediante una señal de control en su puerta (Gate), que puede venir de un circuito temporizador simple (555) o un microcontrolador (Arduino, PIC) para una precisión total.
- **Inductor de Aislamiento:** Un pequeño inductor en serie con el conmutador ayuda...

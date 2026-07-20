# Lista de Materiales (BOM)

El sistema robótico de ajedrez se compone de cinco subsistemas principales: procesamiento central, percepción visual, manipulación mecánica, electrónica de control y el entorno físico operativo. A continuación se detallan las especificaciones de hardware y software correspondientes a cada módulo.

## 1. Unidad de Procesamiento Central (Host)

Encargada de la ejecución del algoritmo de visión artificial, el motor de ajedrez y el cálculo de la cinemática para el sistema de actuación.

| Componente                   | Especificación Técnica                                     |
| ---------------------------- | ---------------------------------------------------------- |
| **Sistema Operativo**        | Windows 11                                                 |
| **Procesador (CPU)**         | Intel Core i7                                              |
| **Memoria RAM**              | 16 GB                                                      |
| **Almacenamiento**           | 1 TB Unidad de Estado Sólido (SSD)                         |
| **Procesador Gráfico (GPU)** | NVIDIA GeForce RTX 4070 (Aceleración de inferencia visual) |

## 2. Sistema de Percepción Visual

Responsable de la captura cenital del estado del tablero y su transmisión inalámbrica hacia la unidad de procesamiento central.

| Componente                   | Especificación Técnica                                    |
| ---------------------------- | --------------------------------------------------------- |
| **Módulo de Procesamiento**  | Placa de desarrollo ESP32-CAM                             |
| **Sensor de Imagen**         | Omnivision OV3660 (3 Megapíxeles)                         |
| **Interfaz de Comunicación** | Wi-Fi 802.11 b/g/n (Protocolo de streaming sobre HTTP)    |
| **Interfaz de Programación** | Módulo adaptador serie FTDI / Base shield Micro-USB a TTL |

## 3. Sistema Mecánico y de Actuación

Mecanismo articulado responsable de la interacción física con las piezas de ajedrez en el espacio de trabajo.

| Componente                     | Especificación Técnica                                                         |
| ------------------------------ | ------------------------------------------------------------------------------ |
| **Estructura del Manipulador** | Chasis de aluminio ROT3U (Soportes en U, rodamientos y tornillería M3)         |
| **Grados de Libertad (DOF)**   | 5+1 (5 ejes de posicionamiento espacial + 1 actuador de efector final)         |
| **Actuadores Principales**     | 6x Servomotores de alto torque (Ej. estándar MG996R, con engranajes metálicos) |
| **Efector Final**              | Pinza robótica de aluminio                                                     |
| **Apertura Máxima de Pinza**   | 55 mm                                                                          |
| **Radio de Alcance Máximo**    | ~355 mm                                                                        |

## 4. Electrónica de Control y Potencia

Subsistema intermedio que traduce los comandos lógicos provenientes del Host en señales eléctricas moduladas (PWM) y gestiona la demanda energética de los actuadores.

| Componente                    | Especificación Técnica                                                             |
| ----------------------------- | ---------------------------------------------------------------------------------- |
| **Unidad de Control Local**   | Microcontrolador Arduino UNO (o placa compatible)                                  |
| **Controlador de Actuadores** | Módulo PCA9685 (Driver de 16 canales PWM, interfaz I2C, resolución de 12 bits)     |
| **Fuente de Alimentación**    | Fuente conmutada (SMPS) externa de 5V DC o 6V DC con capacidad mínima de 10A - 15A |
| **Protocolo de Comunicación** | Serial (UART) vía bus USB entre Host y Unidad de Control Local                     |

## 5. Entorno Físico y Accesorios

Elementos pasivos que conforman la zona de interacción del robot y la infraestructura de montaje.

| Componente                            | Especificación Técnica                                                                                                      |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Superficie de Juego**               | Tablero de ajedrez estándar clásico                                                                                         |
| **Piezas de Juego**                   | Set de ajedrez estándar (Geometría y dimensiones compatibles con la apertura del efector final)                             |
| **Soporte de Percepción**             | Estructura rígida tipo pórtico o trípode para anclaje cenital del módulo ESP32-CAM                                          |
| **Conductores Eléctricos**            | Set de cables Dupont (Jumpers macho-macho, macho-hembra) y cable de datos USB de longitud extendida                         |
| **Zonas de Descarte**                 | 2x bandeja/contenedor rígido (una por color) — la pieza se libera por caída, sin necesidad de posicionamiento fino ni slots |
| **Piezas de Repuesto para Promoción** | 2x Dama adicional (una por color)                                                                                           |

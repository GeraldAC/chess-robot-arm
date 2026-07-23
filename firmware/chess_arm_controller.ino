/*
 * chess_arm_controller.ino
 *
 * Firmware de referencia para Arduino UNO + PCA9685 (M8, M8_SPEC.md §3).
 * Implementa el protocolo Serial ASCII descrito en M8_SPEC.md §3:
 *
 *   PING                         -> PONG
 *   SET ch:pulso,ch:pulso,...    -> ACK | ERR 1 | ERR 2 | ERR 3
 *
 * Deliberadamente "tonto": no conoce waypoints, trayectorias, ni
 * temporización -- toda esa lógica vive en el Host (chess_actuators,
 * ver M8_SPEC.md §2.2). Este firmware solo traduce comandos de línea a
 * escrituras de registro del PCA9685 vía Adafruit_PWMServoDriver.
 *
 * Dependencias (Arduino Library Manager): "Adafruit PWM Servo Driver
 * Library".
 *
 * ADVERTENCIA DE HARDWARE (ver M8_SPEC.md §3, §9): el Arduino UNO se
 * reinicia por defecto al abrirse una conexión Serial (toggle de DTR),
 * lo que apaga los canales PWM hasta el primer SET. Si el brazo está
 * sosteniendo una pieza al reconectar, puede perder sujeción. La
 * mitigación (capacitor en RESET / deshabilitar auto-reset) es un
 * cambio de hardware, fuera del alcance de este firmware.
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

const long BAUD_RATE = 115200;
const uint8_t MAX_CHANNEL = 15;         // PCA9685: 16 canales (0-15)
const uint8_t MAX_PAIRS_PER_COMMAND = 16;

// Límites de seguridad genéricos del firmware, INDEPENDIENTES de la
// calibración por servo que vive en el Host (ActuatorCalibration,
// M8_SPEC.md §6). Son un piso/techo de cordura para detectar comandos
// claramente corruptos o mal calculados antes de escribirlos al
// PCA9685 -- no reemplazan la calibración fina por canal.
const uint16_t PULSE_MIN_US = 400;
const uint16_t PULSE_MAX_US = 2600;

const uint8_t PWM_FREQUENCY_HZ = 50;    // servos estándar (MG996R, BOM.md §3)

String inputLine;

void setup() {
  Serial.begin(BAUD_RATE);
  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(PWM_FREQUENCY_HZ);
  inputLine.reserve(160);
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      handleLine(inputLine);
      inputLine = "";
    } else if (c != '\r') {
      inputLine += c;
    }
  }
}

void handleLine(const String &line) {
  if (line == "PING") {
    Serial.println("PONG");
    return;
  }
  if (line.startsWith("SET ")) {
    handleSet(line.substring(4));
    return;
  }
  Serial.println("ERR 4");  // comando desconocido, no listado en M8_SPEC.md §3 v1
}

void handleSet(const String &payload) {
  // payload: "ch:pulso,ch:pulso,..."
  // Se valida TODO el comando antes de aplicar ningún canal (falla
  // atómica: o se mueven los 6 canales del waypoint, o ninguno).
  int channels[MAX_PAIRS_PER_COMMAND];
  int pulses[MAX_PAIRS_PER_COMMAND];
  int count = 0;
  int start = 0;

  while (start < (int)payload.length()) {
    int comma = payload.indexOf(',', start);
    String pair = (comma == -1) ? payload.substring(start) : payload.substring(start, comma);

    int colon = pair.indexOf(':');
    if (colon == -1 || count >= MAX_PAIRS_PER_COMMAND) {
      Serial.println("ERR 1");
      return;
    }

    int channel = pair.substring(0, colon).toInt();
    int pulse = pair.substring(colon + 1).toInt();

    if (channel < 0 || channel > MAX_CHANNEL) {
      Serial.println("ERR 1");
      return;
    }
    if (pulse < PULSE_MIN_US || pulse > PULSE_MAX_US) {
      Serial.println("ERR 2");
      return;
    }

    channels[count] = channel;
    pulses[count] = pulse;
    count++;

    if (comma == -1) {
      break;
    }
    start = comma + 1;
  }

  if (count == 0) {
    Serial.println("ERR 1");
    return;
  }

  // Nota: Adafruit_PWMServoDriver::writeMicroseconds no retorna un
  // código de estado I2C, así que ERR 3 (fallo de escritura I2C) queda
  // reservado para una futura revisión que use Wire directamente y
  // chequee Wire.endTransmission() -- ver M8_SPEC.md §9. En v1, un
  // fallo de bus I2C no se distingue de un éxito desde este firmware.
  for (int i = 0; i < count; i++) {
    pwm.writeMicroseconds(channels[i], pulses[i]);
  }
  Serial.println("ACK");
}

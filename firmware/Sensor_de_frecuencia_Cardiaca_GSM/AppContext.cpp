#include "AppContext.h"

int Lectura = 0;
float Voltaje = 0;
byte Porcent = 0;

const byte MaxNumeros = 5;
String Numeros[MaxNumeros] = {"", "", "", "", ""};
byte CantidadDeNumeros = 0;
byte Var = 0;
String Temporal = "";
String EnvioMen = "SUB";
byte Milis = 0;
String AdminNumero = "";
bool AdminConfigurado = false;
unsigned long UltimaRevisionSMS = 0;
const unsigned long IntervaloRevisionSMS = 5000;
const int TamanoMaxTelefono = 20;
const int EEPROMSize = 256;
const uint32_t ConfigMagic = 0x49544753;
const String CodigoReset = "2468";

const uint8_t i2c_Address = 0x3c;
const int SCREEN_WIDTH = 128;
const int SCREEN_HEIGHT = 64;
const int OLED_RESET = -1;
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

MAX30105 particleSensor;

const byte RATE_SIZE = 4;
byte rates[RATE_SIZE];
byte rateSpot = 0;
long lastBeat = 0;
float beatsPerMinute = 0;
int beatAvg = 0;

double avered = 0;
double aveir = 0;
double sumirrms = 0;
double sumredrms = 0;
double SpO2 = 0;
double ESpO2 = 95.0;
double FSpO2 = 0.7;
double frate = 0.95;
int i = 0;
int Num = 15;
const long FINGER_ON = 12000;
const double MINIMUM_SPO2 = 60.0;

long irValue = 0;
const byte LimitLectIncorr = 50;
byte LectIncorr = 0;
const byte LimitLectCorrec = 3;
byte LectCorrec = 0;
const byte Buzzer = 4;
bool Mensaje = false;
bool ConteoActivo = false;
byte ConteoRegresivo = 5;
unsigned long UltimoTickConteo = 0;
bool InicioOperativoNotificado = false;
unsigned long UltimoLatidoVisual = 0;
int CSQActual = -1;
byte BarrasGSM = 0;
unsigned long UltimaRevisionGSM = 0;
const unsigned long IntervaloRevisionGSM = 15000;
bool DisplayDisponible = false;
unsigned long UltimaActualizacionPantalla = 0;
const unsigned long IntervaloPantalla = 200;
unsigned long InicioBootMillis = 0;
const unsigned long RetardoNotificacionInicio = 30000;
byte IntentosNotificacionInicio = 0;
const byte MaxIntentosNotificacionInicio = 3;
long IrBase = 0;
long UmbralDedoActual = FINGER_ON;
unsigned long InicioLecturaDedo = 0;
const unsigned long TimeoutLecturaDedo = 12000;
bool SensorEnCalibracion = true;
bool EnvioBiometricoArmado = true;
unsigned long UltimoEnvioBiometrico = 0;
const unsigned long EnfriamientoEnvioBiometrico = 30000;
bool ModoPresentacion = true;
const byte ConteoRegresivoNormal = 5;
const byte ConteoRegresivoPresentacion = 2;
const byte LecturasEstablesNormal = 3;
const byte LecturasEstablesPresentacion = 1;
const unsigned long TimeoutLecturaNormal = 12000;
const unsigned long TimeoutLecturaPresentacion = 7000;
const int SpO2MuestrasNormal = 15;
const int SpO2MuestrasPresentacion = 8;

const char *TextoMotivoReset(esp_reset_reason_t motivo)
{
  switch (motivo)
  {
    case ESP_RST_POWERON: return "POWERON";
    case ESP_RST_EXT: return "EXTERNAL";
    case ESP_RST_SW: return "SOFTWARE";
    case ESP_RST_PANIC: return "PANIC";
    case ESP_RST_INT_WDT: return "INT_WDT";
    case ESP_RST_TASK_WDT: return "TASK_WDT";
    case ESP_RST_WDT: return "WDT";
    case ESP_RST_DEEPSLEEP: return "DEEPSLEEP";
    case ESP_RST_BROWNOUT: return "BROWNOUT";
    case ESP_RST_SDIO: return "SDIO";
    default: return "UNKNOWN";
  }
}

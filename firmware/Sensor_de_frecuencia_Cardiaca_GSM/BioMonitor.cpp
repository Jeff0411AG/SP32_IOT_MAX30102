#include "BioMonitor.h"
#include "ConfigStore.h"
#include "DisplayUi.h"
#include "GsmService.h"

static byte LecturasEstablesRequeridas()
{
  return ModoPresentacion ? LecturasEstablesPresentacion : LecturasEstablesNormal;
}

static unsigned long TimeoutLecturaActual()
{
  return ModoPresentacion ? TimeoutLecturaPresentacion : TimeoutLecturaNormal;
}

void ActualizaConteoRegresivo(bool lecturaValida)
{
  if (!lecturaValida)
  {
    ReiniciaConteoMedicion();
    return;
  }

  if (!PuedeArmarNuevoEnvioBiometrico())
  {
    ReiniciaConteoMedicion();
    return;
  }

  if (!ConteoActivo)
  {
    byte lecturasRequeridas = LecturasEstablesRequeridas();

    if (LectCorrec < lecturasRequeridas)
      LectCorrec++;

    if (LectCorrec >= lecturasRequeridas)
    {
      ConteoActivo = true;
      ConteoRegresivo = ModoPresentacion ? ConteoRegresivoPresentacion : ConteoRegresivoNormal;
      UltimoTickConteo = millis();
      Serial.print("Conteo iniciado en ");
      Serial.println(ConteoRegresivo);
    }

    return;
  }

  if (millis() - UltimoTickConteo >= 1000)
  {
    UltimoTickConteo = millis();

    if (ConteoRegresivo > 1)
    {
      ConteoRegresivo--;
      Serial.print("Conteo: ");
      Serial.println(ConteoRegresivo);
    }
    else
    {
      Mensaje = true;
      ReiniciaConteoMedicion();
      Serial.println("Conteo finalizado. Enviando SMS.");
    }
  }
}

void InicializaPantalla()
{
  delay(50);
  DisplayDisponible = display.begin(i2c_Address, true);
  if (DisplayDisponible)
  {
    display.clearDisplay();
    display.display();
    delay(500);
  }
  else
  {
    Serial.println("OLED no disponible en I2C.");
  }
}

void InicializaGSM()
{
  Serial2.println("AT");
  delay(500);
  Serial2.println("AT");
  delay(500);
  EnviaYEscucha("AT");
  delay(100);
  EnviaYEscucha("AT+CMGF=1");
  delay(100);
  EnviaYEscucha("AT+CSCS=\"GSM\"");
  delay(100);
  EnviaYEscucha("AT+CPMS=\"MT\",\"MT\",\"MT\"");
  delay(100);
  EnviaYEscucha("AT+CPMS?");
  delay(100);
  EnviaYEscucha("AT+CREG?");
  delay(100);
  EnviaYEscucha("AT+COPS?");
  delay(100);
  EnviaYEscucha("AT+CNMI=0,0,0,0,0");
  delay(100);
  ActualizaEstadoGSM(true);
}

void InicializaSensorBiometrico()
{
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST))
  {
    Serial.println("No se encontro MAX30102");
    while (1) {}
  }

  byte ledBrightness = 0x1F;
  byte sampleAverage = ModoPresentacion ? 4 : 8;
  byte ledMode = 2;
  int sampleRate = ModoPresentacion ? 400 : 200;
  int pulseWidth = 118;
  int adcRange = 4096;

  particleSensor.setup(ledBrightness, sampleAverage, ledMode, sampleRate, pulseWidth, adcRange);
  particleSensor.disableDIETEMPRDY();
  particleSensor.setPulseAmplitudeIR(0x24);
  particleSensor.setPulseAmplitudeRed(0x14);
  particleSensor.setPulseAmplitudeGreen(0);

  IrBase = 0;
  UmbralDedoActual = FINGER_ON;
  SensorEnCalibracion = true;
  InicioLecturaDedo = 0;
  Num = ModoPresentacion ? SpO2MuestrasPresentacion : SpO2MuestrasNormal;
}

void InicializaSistema()
{
  Serial.begin(9600);
  delay(10);
  Serial2.begin(9600, SERIAL_8N1, 16, 17);
  delay(10);
  Serial.flush();
  Serial2.flush();

  InicioBootMillis = millis();
  ReportaMotivoReset();
  EEPROM.begin(EEPROMSize);
  CargaConfiguracion();

  pinMode(Buzzer, OUTPUT);
  digitalWrite(Buzzer, LOW);

  InicializaPantalla();
  InicializaGSM();
  InicializaSensorBiometrico();

  ActualizaBateria();
  Serial.print("Lectura:");
  Serial.println(Lectura);
  Serial.print("Porcent:");
  Serial.print(Porcent);
  Serial.println("%");

  for (byte rx = 0; rx < RATE_SIZE; rx++)
    rates[rx] = 68;

  ReiniciaConteoMedicion();
  RenderPantallaPrincipal(false, true);
  Serial.println("loop");
}

static void ProcesaSinDedo()
{
  CalibraSensorSinDedo(irValue);
  InicioLecturaDedo = 0;
  EnvioBiometricoArmado = true;
  RevisaSMSRecibidos();

  if (!Mensaje && !ConteoActivo)
    ActualizaEstadoGSM(false);

  NotificaInicioOperativo();

  for (byte rx = 0; rx < RATE_SIZE; rx++)
    rates[rx] = 68;

  beatAvg = 0;
  rateSpot = 0;
  lastBeat = 0;
  ReiniciaConteoMedicion();
  avered = 0;
  aveir = 0;
  sumirrms = 0;
  sumredrms = 0;
  SpO2 = 0;
  ESpO2 = 95.0;
  RenderPantallaPrincipal(false);
}

static void ProcesaConDedo()
{
  if (InicioLecturaDedo == 0)
    InicioLecturaDedo = millis();

  Serial.print("LectIncorr:");
  Serial.println(LectIncorr);

  if ((LectIncorr++) >= LimitLectIncorr)
  {
    LectIncorr = 0;
    ReiniciaConteoMedicion();
    Serial.println();
    Serial.print("LectCorrec:");
    Serial.println(LectCorrec);
    Serial.println();
  }

  if (checkForBeat(irValue))
  {
    UltimoLatidoVisual = millis();
    digitalWrite(Buzzer, HIGH);

    Serial.println();
    Serial.print("LectIncorr:");
    Serial.println(LectIncorr);
    Serial.println();
    LectIncorr = 0;

    long delta = millis() - lastBeat;
    lastBeat = millis();
    beatsPerMinute = 60 / (delta / 1000.0);
    if (beatsPerMinute < 255 && beatsPerMinute > 20)
    {
      rates[rateSpot++] = (byte)beatsPerMinute;
      rateSpot %= RATE_SIZE;
      beatAvg = 0;
      for (byte x = 0; x < RATE_SIZE; x++)
        beatAvg += rates[x];
      beatAvg /= RATE_SIZE;
    }

    int bpmMinimo = ModoPresentacion ? 45 : 30;
    double spo2Minima = ModoPresentacion ? 85.0 : MINIMUM_SPO2;
    bool lecturaEstable = beatAvg > bpmMinimo && ESpO2 >= spo2Minima;
    ActualizaConteoRegresivo(lecturaEstable);
  }

  uint32_t ir = 0;
  uint32_t red = 0;
  double fred = 0;
  double fir = 0;
  particleSensor.check();
  if (particleSensor.available())
  {
    i++;
    ir = particleSensor.getFIFOIR();
    red = particleSensor.getFIFORed();
    fir = (double)ir;
    fred = (double)red;
    aveir = aveir * frate + (double)ir * (1.0 - frate);
    avered = avered * frate + (double)red * (1.0 - frate);
    sumirrms += (fir - aveir) * (fir - aveir);
    sumredrms += (fred - avered) * (fred - avered);

    if ((i % Num) == 0)
    {
      double R = (sqrt(sumirrms) / aveir) / (sqrt(sumredrms) / avered);
      SpO2 = -23.3 * (R - 0.4) + 121.5;
      ESpO2 = FSpO2 * ESpO2 + (1.0 - FSpO2) * SpO2;
      if (ESpO2 <= MINIMUM_SPO2)
        ESpO2 = MINIMUM_SPO2;
      if (ESpO2 > 100)
        ESpO2 = 98;
      sumredrms = 0.0;
      sumirrms = 0.0;
      SpO2 = 0;
      i = 0;
    }

    particleSensor.nextSample();
  }

  if (millis() - InicioLecturaDedo > TimeoutLecturaActual() && beatAvg == 0)
  {
    Serial.println("Timeout de lectura. Recalibrando sensor.");
    InicioLecturaDedo = 0;
    ReiniciaConteoMedicion();
    LectIncorr = 0;
    avered = 0;
    aveir = 0;
    sumirrms = 0;
    sumredrms = 0;
    SpO2 = 0;
    ESpO2 = 95.0;
    SensorEnCalibracion = true;
  }

  RenderPantallaPrincipal(true);
  digitalWrite(Buzzer, LOW);

  if (Mensaje)
  {
    EnviaMensaje();
    Mensaje = false;
  }
}

void ProcesaLoopPrincipal()
{
  irValue = particleSensor.getIR();
  bool dedoPresente = DedoDetectado(irValue);

  if (dedoPresente)
    ProcesaConDedo();
  else
    ProcesaSinDedo();
}

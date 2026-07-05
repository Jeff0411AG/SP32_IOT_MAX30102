#include "DisplayUi.h"

int ExtraeCSQ(String respuesta)
{
  int inicio = respuesta.indexOf(':');
  int coma = respuesta.indexOf(',');

  if (inicio < 0 || coma < 0 || coma <= inicio)
    return -1;

  String valor = respuesta.substring(inicio + 1, coma);
  valor.trim();
  return valor.toInt();
}

byte ConvierteCSQABarras(int csq)
{
  if (csq == 99 || csq < 2)
    return 0;
  if (csq < 10)
    return 1;
  if (csq < 16)
    return 2;
  if (csq < 22)
    return 3;
  return 4;
}

void DibujaBarrasGSM(int x, int y)
{
  const byte alturas[4] = {3, 6, 9, 12};

  for (byte idx = 0; idx < 4; idx++)
  {
    int barraX = x + (idx * 4);
    int barraY = y + 12 - alturas[idx];
    display.drawRect(barraX, barraY, 3, alturas[idx], SH110X_WHITE);

    if (idx < BarrasGSM)
      display.fillRect(barraX, barraY, 3, alturas[idx], SH110X_WHITE);
  }

  if (BarrasGSM == 0)
  {
    display.drawLine(x, y, x + 14, y + 12, SH110X_WHITE);
    display.drawLine(x, y + 12, x + 14, y, SH110X_WHITE);
  }
}

void DibujaCabeceraEstado()
{
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(0, 2);
  display.print("BAT ");
  display.print(Porcent);
  display.print("%");
  DibujaBarrasGSM(110, 1);
  display.drawLine(0, 13, 127, 13, SH110X_WHITE);
}

void DibujaPanelDato(int x, int y, int w, int h, const char *titulo, String valor, bool resaltar)
{
  display.drawRoundRect(x, y, w, h, 6, SH110X_WHITE);
  display.setTextSize(1);
  display.setCursor(x + 5, y + 4);
  display.print(titulo);

  if (resaltar)
    display.fillCircle(x + w - 8, y + 8, 3, SH110X_WHITE);

  display.setTextSize(2);
  int cursorX = x + 6;

  if (valor.length() <= 2)
    cursorX = x + 14;
  else if (valor.length() == 3)
    cursorX = x + 8;

  display.setCursor(cursorX, y + 16);
  display.print(valor);
}

String TextoEstadoMedicion(bool dedoPresente)
{
  if (SensorEnCalibracion)
    return "CALIBRANDO SENSOR";
  if (!dedoPresente)
    return "PONGA DEDO EN SENSOR";
  if (!EnvioBiometricoArmado)
    return "RETIRE EL DEDO PARA REARMAR";
  if (millis() - UltimoEnvioBiometrico < EnfriamientoEnvioBiometrico)
    return "ESPERE NUEVA MEDICION";
  if (Mensaje)
    return "ENVIANDO SMS...";
  if (ConteoActivo)
    return "ENVIO EN " + String(ConteoRegresivo) + " s";
  if (LectCorrec > 0)
    return "ESTABILIZANDO LECTURA";
  return "LEYENDO SENAL...";
}

bool PuedeArmarNuevoEnvioBiometrico()
{
  if (!EnvioBiometricoArmado)
    return false;

  return millis() - UltimoEnvioBiometrico >= EnfriamientoEnvioBiometrico;
}

void RenderPantallaPrincipal(bool dedoPresente, bool forzar)
{
  if (!DisplayDisponible)
    return;

  if (!forzar && (millis() - UltimaActualizacionPantalla) < IntervaloPantalla)
    return;

  UltimaActualizacionPantalla = millis();
  display.clearDisplay();
  display.setTextColor(SH110X_WHITE);
  DibujaCabeceraEstado();

  String bpmTexto = dedoPresente && beatAvg > 0 ? String(beatAvg) : "--";
  String spo2Texto = dedoPresente && beatAvg > 30 ? String((int)ESpO2) : "--";
  bool latidoReciente = (millis() - UltimoLatidoVisual) < 180;

  DibujaPanelDato(2, 18, 60, 32, "BPM", bpmTexto, latidoReciente);
  DibujaPanelDato(66, 18, 60, 32, "SpO2", spo2Texto, false);

  display.setTextSize(1);
  display.setCursor(108, 39);
  display.print("%");

  display.drawRoundRect(2, 53, 124, 10, 4, SH110X_WHITE);
  display.setCursor(6, 55);
  display.print(TextoEstadoMedicion(dedoPresente));
  display.display();
}

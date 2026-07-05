#include "ConfigStore.h"

void ReportaMotivoReset()
{
  esp_reset_reason_t motivo = esp_reset_reason();
  Serial.print("Motivo de reset: ");
  Serial.println(TextoMotivoReset(motivo));
}

void ReiniciaConteoMedicion()
{
  LectCorrec = 0;
  ConteoActivo = false;
  ConteoRegresivo = ModoPresentacion ? ConteoRegresivoPresentacion : ConteoRegresivoNormal;
  UltimoTickConteo = 0;
}

void ActualizaUmbralDedo()
{
  long umbralCalculado = IrBase + 4000;

  if (umbralCalculado < FINGER_ON)
    umbralCalculado = FINGER_ON;

  if (umbralCalculado > 30000)
    umbralCalculado = 30000;

  UmbralDedoActual = umbralCalculado;
}

void CalibraSensorSinDedo(long lecturaIR)
{
  if (lecturaIR < 0)
    return;

  if (IrBase == 0)
    IrBase = lecturaIR;
  else
    IrBase = (IrBase * 9 + lecturaIR) / 10;

  ActualizaUmbralDedo();
  SensorEnCalibracion = false;
}

bool DedoDetectado(long lecturaIR)
{
  return lecturaIR > UmbralDedoActual;
}

void LimpiaContactos()
{
  for (byte idx = 0; idx < MaxNumeros; idx++)
    Numeros[idx] = "";

  ActualizaCantidadDeNumeros();
}

void ReiniciaEstadoFabrica(bool guardarEnEEPROM)
{
  AdminNumero = "";
  AdminConfigurado = false;
  LimpiaContactos();
  InicioOperativoNotificado = false;
  IntentosNotificacionInicio = 0;

  if (guardarEnEEPROM)
    GuardaConfiguracion();
}

void ActualizaCantidadDeNumeros()
{
  CantidadDeNumeros = 0;

  for (byte idx = 0; idx < MaxNumeros; idx++)
  {
    if (Numeros[idx].length() > 0)
      CantidadDeNumeros++;
  }
}

void EscribeCadenaEEPROM(int direccion, String valor, int longitudMaxima)
{
  for (int idx = 0; idx < longitudMaxima; idx++)
  {
    byte dato = 0;

    if (idx < valor.length())
      dato = valor.charAt(idx);

    EEPROM.write(direccion + idx, dato);
  }
}

String LeeCadenaEEPROM(int direccion, int longitudMaxima)
{
  String valor = "";

  for (int idx = 0; idx < longitudMaxima; idx++)
  {
    byte dato = EEPROM.read(direccion + idx);

    if (dato == 0 || dato == 255)
      break;

    valor += (char)dato;
  }

  valor.trim();
  return valor;
}

void GuardaConfiguracion()
{
  int direccion = 0;

  EEPROM.put(direccion, ConfigMagic);
  direccion += sizeof(uint32_t);
  EEPROM.write(direccion, AdminConfigurado ? 1 : 0);
  direccion += 1;
  EscribeCadenaEEPROM(direccion, AdminNumero, TamanoMaxTelefono);
  direccion += TamanoMaxTelefono;

  for (byte idx = 0; idx < MaxNumeros; idx++)
  {
    EscribeCadenaEEPROM(direccion, Numeros[idx], TamanoMaxTelefono);
    direccion += TamanoMaxTelefono;
  }

  EEPROM.commit();
}

void CargaConfiguracion()
{
  int direccion = 0;
  uint32_t magicLeido = 0;
  EEPROM.get(direccion, magicLeido);

  if (magicLeido != ConfigMagic)
  {
    ReiniciaEstadoFabrica(true);
    Serial.println("EEPROM inicializada con configuracion actual.");
    return;
  }

  direccion += sizeof(uint32_t);
  AdminConfigurado = EEPROM.read(direccion) == 1;
  direccion += 1;
  AdminNumero = NormalizaTelefonoGuardado(LeeCadenaEEPROM(direccion, TamanoMaxTelefono));
  direccion += TamanoMaxTelefono;

  for (byte idx = 0; idx < MaxNumeros; idx++)
  {
    Numeros[idx] = NormalizaTelefonoGuardado(LeeCadenaEEPROM(direccion, TamanoMaxTelefono));
    direccion += TamanoMaxTelefono;
  }

  if (AdminConfigurado && !EsTelefonoValido(AdminNumero))
  {
    ReiniciaEstadoFabrica(true);
    Serial.println("Configuracion invalida detectada. Restaurando estado de fabrica.");
    return;
  }

  if (!AdminConfigurado)
    AdminNumero = "";

  InicioOperativoNotificado = false;
  ActualizaCantidadDeNumeros();
  Serial.println("Configuracion cargada desde EEPROM.");
}

void ActualizaBateria()
{
  Lectura = analogRead(36);
  Voltaje = (Lectura * 3.3) / 4095;
  long porcentajeCalculado = map(Lectura, 3100, 4095, 0, 100);
  porcentajeCalculado = constrain(porcentajeCalculado, 0, 100);
  Porcent = (byte)porcentajeCalculado;
}

String LimpiaTelefono(String numero)
{
  String limpio = "";

  for (int idx = 0; idx < numero.length(); idx++)
  {
    char caracter = numero.charAt(idx);

    if ((caracter >= '0' && caracter <= '9') || (caracter == '+' && limpio.length() == 0))
      limpio += caracter;
  }

  return limpio;
}

String ExtraeCampoEntreComillas(String texto, byte indiceCampo)
{
  byte campoActual = 0;
  int inicio = -1;

  for (int idx = 0; idx < texto.length(); idx++)
  {
    if (texto.charAt(idx) == '"')
    {
      if (inicio < 0)
      {
        inicio = idx + 1;
      }
      else
      {
        if (campoActual == indiceCampo)
          return texto.substring(inicio, idx);

        campoActual++;
        inicio = -1;
      }
    }
  }

  return "";
}

int ExtraeIndiceSMS(String cabecera)
{
  int inicio = cabecera.indexOf(':');
  int coma = cabecera.indexOf(',');

  if (inicio < 0 || coma < 0 || coma <= inicio)
    return -1;

  String valor = cabecera.substring(inicio + 1, coma);
  valor.trim();
  return valor.toInt();
}

String NormalizaComando(String comando)
{
  comando.trim();
  comando.toUpperCase();
  return comando;
}

String NormalizaTelefonoGuardado(String numero)
{
  String limpio = LimpiaTelefono(numero);

  if (limpio.startsWith("+51") && limpio.length() >= 12)
    return limpio.substring(limpio.length() - 9);

  if (limpio.startsWith("51") && limpio.length() >= 11)
    return limpio.substring(limpio.length() - 9);

  if (limpio.length() > 9)
    return limpio.substring(limpio.length() - 9);

  return limpio;
}

bool EsTelefonoValido(String numero)
{
  String telefono = NormalizaTelefonoGuardado(numero);

  if (telefono.length() != 9)
    return false;

  for (int idx = 0; idx < telefono.length(); idx++)
  {
    char caracter = telefono.charAt(idx);

    if (caracter < '0' || caracter > '9')
      return false;
  }

  return true;
}

int BuscaContacto(String numero)
{
  String telefono = NormalizaTelefonoGuardado(numero);

  for (byte idx = 0; idx < MaxNumeros; idx++)
  {
    if (Numeros[idx].length() == 0)
      continue;

    if (NormalizaTelefonoGuardado(Numeros[idx]) == telefono)
      return idx;
  }

  return -1;
}

int BuscaEspacioLibreContacto()
{
  for (byte idx = 0; idx < MaxNumeros; idx++)
  {
    if (Numeros[idx].length() == 0)
      return idx;
  }

  return -1;
}

String ResumenContactos()
{
  String lista = "";

  for (byte idx = 0; idx < MaxNumeros; idx++)
  {
    if (Numeros[idx].length() == 0)
      continue;

    if (lista.length() > 0)
      lista += ",";

    lista += Numeros[idx];
  }

  if (lista.length() == 0)
    lista = "Sin contactos";

  return lista;
}

bool EsAdministrador(String numero)
{
  return AdminConfigurado && numero == AdminNumero;
}

bool EsNumeroAutorizado(String numero)
{
  if (EsAdministrador(numero))
    return true;

  return BuscaContacto(numero) >= 0;
}

bool EsComandoValido(String comando)
{
  String comandoNormalizado = NormalizaComando(comando);

  return comandoNormalizado == "STATUS"
         || comandoNormalizado == "STATUS?"
         || comandoNormalizado.startsWith("STATUS ")
         || comandoNormalizado.startsWith("ADD ")
         || comandoNormalizado.startsWith("DEL ")
         || comandoNormalizado.startsWith("CAMBIAR ")
         || comandoNormalizado.startsWith("RESET ");
}

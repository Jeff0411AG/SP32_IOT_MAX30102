#include "GsmService.h"
#include "ConfigStore.h"
#include "DisplayUi.h"

static String ExtraeEstadoSMSCabecera(const String &cabecera)
{
  return ExtraeCampoEntreComillas(cabecera, 0);
}

static bool EstadoSMSProcesable(const String &estado)
{
  return estado == "REC UNREAD";
}

static String ExtraeNombreComando(const String &comandoNormalizado)
{
  int separador = comandoNormalizado.indexOf(' ');
  if (separador < 0)
    return comandoNormalizado;

  return comandoNormalizado.substring(0, separador);
}

static String ExtraeArgumentosComando(const String &comandoNormalizado)
{
  int separador = comandoNormalizado.indexOf(' ');
  if (separador < 0)
    return "";

  String argumentos = comandoNormalizado.substring(separador + 1);
  argumentos.trim();
  return argumentos;
}

static void RespondeComandoSMS(const String &numeroDestino, const String &mensaje)
{
  Serial.print("Respuesta comando hacia ");
  Serial.print(numeroDestino);
  Serial.print(": ");
  Serial.println(mensaje);
  EnviarSMSA(numeroDestino, mensaje);
}

static bool EnviaComandoConReintento(const String &comando, unsigned long timeoutMs = 1500, byte intentos = 3)
{
  for (byte intento = 1; intento <= intentos; intento++)
  {
    Serial.print("Intento ");
    Serial.print(intento);
    Serial.print(" para comando: ");
    Serial.println(comando);

    if (EnviaYEscucha(comando, timeoutMs))
      return true;

    delay(250);
  }

  return false;
}

static bool EsperaConfirmacionEnvioSMS(unsigned long timeoutMs)
{
  Temporal = "";
  unsigned long inicio = millis();

  while (millis() - inicio < timeoutMs)
  {
    while (Serial2.available() > 0)
    {
      char caracter = (char)Serial2.read();
      Temporal += caracter;
    }

    bool tieneCMGS = Temporal.indexOf("+CMGS:") >= 0;
    bool tieneOK = Temporal.indexOf("\r\nOK\r\n") >= 0;
    bool tieneERROR = Temporal.indexOf("\r\nERROR\r\n") >= 0;

    if ((tieneCMGS && tieneOK) || tieneERROR)
      break;

    delay(20);
  }

  Temporal.trim();
  if (Temporal.length() > 0)
  {
    Serial.print("Confirmacion SMS:");
    Serial.println(Temporal);
  }
  else
  {
    Serial.println("Sin confirmacion SMS dentro del tiempo.");
  }

  return Temporal.indexOf("+CMGS:") >= 0 && Temporal.indexOf("ERROR") < 0;
}

String ClasificaSpO2(int spo2)
{
  if (spo2 >= 95)
    return "Normal";
  if (spo2 >= 90)
    return "Bajo";
  return "Critico";
}

String ClasificaBPM(int bpm)
{
  if (bpm < 60)
    return "Bajo";
  if (bpm <= 100)
    return "Normal";
  return "Alto";
}

String NivelGeneral(int spo2, int bpm)
{
  if (spo2 >= 95 && bpm >= 60 && bpm <= 100)
    return "NORMAL";
  return "ALERTA";
}

String RecomendacionClinica(int spo2, int bpm)
{
  if (spo2 < 90 || bpm < 50 || bpm > 120)
    return "Acudir a revision medica";

  if (spo2 < 95 || bpm < 60 || bpm > 100)
    return "Monitoreo y seguimiento";

  return "Continuar control regular";
}

String ConstruyeMensajeBiometrico()
{
  int spo2 = (int)ESpO2;
  int bpm = beatAvg;
  String mensaje = "[";
  mensaje += NivelGeneral(spo2, bpm);
  mensaje += "] Oxigeno: ";
  mensaje += spo2;
  mensaje += "% (";
  mensaje += ClasificaSpO2(spo2);
  mensaje += ") | Pulso: ";
  mensaje += bpm;
  mensaje += " lpm (";
  mensaje += ClasificaBPM(bpm);
  mensaje += ") | Recomendacion: ";
  mensaje += RecomendacionClinica(spo2, bpm);
  mensaje += " | Bat: ";
  mensaje += Porcent;
  mensaje += "%";
  return mensaje;
}

String ConstruyeMensajeInicio()
{
  ActualizaBateria();
  String mensaje = "Sistema Activo | Bateria: ";
  mensaje += Porcent;
  mensaje += "% | Contactos: ";
  mensaje += CantidadDeNumeros;
  mensaje += " | Sensores: OK | GSM: ";
  mensaje += BarrasGSM;
  mensaje += "/4";
  return mensaje;
}

bool SistemaListoParaNotificacionInicio()
{
  if (!AdminConfigurado || InicioOperativoNotificado || IntentosNotificacionInicio >= MaxIntentosNotificacionInicio)
    return false;

  if (millis() - InicioBootMillis < RetardoNotificacionInicio)
    return false;

  if (Mensaje || ConteoActivo)
    return false;

  return CSQActual >= 0;
}

void NotificaInicioOperativo()
{
  if (!SistemaListoParaNotificacionInicio())
    return;

  IntentosNotificacionInicio++;
  EnviarSMSA(AdminNumero, ConstruyeMensajeInicio());
  InicioOperativoNotificado = true;
}

void ActualizaEstadoGSM(bool forzar)
{
  if (!forzar && (millis() - UltimaRevisionGSM < IntervaloRevisionGSM))
    return;

  UltimaRevisionGSM = millis();

  if (EnviaYEscucha("AT+CSQ") && RespuestaGSMContiene("+CSQ:"))
  {
    int csqLeido = ExtraeCSQ(Temporal);

    if (csqLeido >= 0)
    {
      CSQActual = csqLeido;
      BarrasGSM = ConvierteCSQABarras(CSQActual);
      Serial.print("CSQ: ");
      Serial.print(CSQActual);
      Serial.print(" Barras: ");
      Serial.println(BarrasGSM);
    }
  }
}

bool RespuestaGSMContiene(const String &texto)
{
  return Temporal.indexOf(texto) >= 0;
}

bool LeeRespuestaGSM(unsigned long timeoutMs, bool detenerEnPrompt)
{
  Temporal = "";
  unsigned long inicio = millis();
  unsigned long ultimaLectura = millis();

  while (millis() - inicio < timeoutMs)
  {
    while (Serial2.available() > 0)
    {
      char caracter = (char)Serial2.read();
      Temporal += caracter;
      ultimaLectura = millis();

      if (detenerEnPrompt && caracter == '>')
      {
        Serial.print("Respuesta GSM:");
        Serial.println(Temporal);
        return true;
      }
    }

    if (Temporal.length() > 0)
    {
      bool respuestaFinal = Temporal.indexOf("\r\nOK\r\n") >= 0
                            || Temporal.indexOf("\r\nERROR\r\n") >= 0
                            || Temporal.indexOf("+CMGS:") >= 0;

      if (respuestaFinal)
        break;

      if (millis() - ultimaLectura > 500)
        break;
    }

    delay(2);
  }

  Temporal.trim();

  if (Temporal.length() > 0)
  {
    Serial.print("Respuesta GSM:");
    Serial.println(Temporal);
    return Temporal.indexOf("ERROR") < 0;
  }

  Serial.println("Nada");
  return false;
}

String ExtraeLinea(String texto, int &cursor)
{
  if (cursor >= texto.length())
    return "";

  int siguienteSalto = texto.indexOf('\n', cursor);

  if (siguienteSalto < 0)
    siguienteSalto = texto.length();

  String linea = texto.substring(cursor, siguienteSalto);
  cursor = siguienteSalto + 1;
  linea.trim();
  return linea;
}

void EnviarSMSA(String numeroDestino, String mensaje)
{
  if (numeroDestino.length() == 0)
    return;

  String numeroParaEnviar = numeroDestino;
  if (numeroParaEnviar.length() == 9 && numeroParaEnviar.charAt(0) == '9')
    numeroParaEnviar = "+51" + numeroParaEnviar;

  if (!EnviaComandoConReintento("AT", 1200))
  {
    Serial.println("SIM800L no respondio al comando AT.");
    return;
  }

  EnviaComandoConReintento("AT+CMGF=1", 1200);
  VaciarBufferGSM();

  Serial2.print("AT+CMGS=\"");
  Serial2.print(numeroParaEnviar);
  Serial2.println("\"");

  bool promptRecibido = LeeRespuestaGSM(4000, true) && RespuestaGSMContiene(">");

  if (promptRecibido)
  {
    Serial.println("Prompt '>' recibido. Enviando cuerpo del mensaje...");
    Serial2.print(mensaje);
    Serial2.write(26);

    if (!EsperaConfirmacionEnvioSMS(45000))
      Serial.println("No hubo confirmacion del envio SMS.");
  }
  else
  {
    Serial.println("Error: No se recibio el prompt '>' del SIM800L.");
  }
}

void BorraSMS(int indiceSMS)
{
  if (indiceSMS < 0)
    return;

  EnviaYEscucha("AT+CMGD=" + String(indiceSMS));
}

void ProcesaComandoSMS(String numeroRemitente, String comandoSMS)
{
  String numeroNormalizado = NormalizaTelefonoGuardado(numeroRemitente);
  String comandoNormalizado = NormalizaComando(comandoSMS);
  String nombreComando = ExtraeNombreComando(comandoNormalizado);
  String argumentosComando = ExtraeArgumentosComando(comandoNormalizado);
  bool esAdmin = false;

  Serial.print("Procesando SMS de: ");
  Serial.println(numeroNormalizado);
  Serial.print("Comando normalizado: ");
  Serial.println(comandoNormalizado);
  Serial.print("Nombre comando: ");
  Serial.println(nombreComando);
  Serial.print("Argumentos comando: ");
  Serial.println(argumentosComando);

  if (comandoNormalizado == "RESET 2468")
  {
    ReiniciaEstadoFabrica(true);
    RespondeComandoSMS(numeroNormalizado, "RESET OK - Estado de fabrica");
    Serial.println("Sistema reiniciado a estado de fabrica por RESET global.");
    return;
  }

  if (!EsComandoValido(comandoNormalizado))
  {
    Serial.println("SMS ignorado: comando no valido");
    RespondeComandoSMS(numeroNormalizado, "Comando no valido. Use STATUS, ADD, DEL, CAMBIAR o RESET.");
    return;
  }

  if (!AdminConfigurado)
  {
    AdminNumero = numeroNormalizado;
    AdminConfigurado = true;
    GuardaConfiguracion();
    Serial.print("Nuevo admin autoconfigurado: ");
    Serial.println(AdminNumero);
    RespondeComandoSMS(AdminNumero, "ADMIN REGISTRADO. Equipo listo para recibir comandos.");
    return;
  }

  if (!EsNumeroAutorizado(numeroNormalizado))
  {
    Serial.print("SMS descartado por whitelist: ");
    Serial.println(numeroNormalizado);
    RespondeComandoSMS(numeroNormalizado, "Numero no autorizado para este equipo.");
    return;
  }

  esAdmin = EsAdministrador(numeroNormalizado);

  if (nombreComando == "STATUS" || comandoNormalizado == "STATUS?")
  {
    ActualizaBateria();
    String estado = "[ONLINE] GSM: OK | Bateria: ";
    estado += Porcent;
    estado += "% | Contactos: ";
    estado += CantidadDeNumeros;
    estado += " | Lista: ";
    estado += ResumenContactos();
    estado += " | Sensores: OK | Admin: ";
    estado += esAdmin ? "SI" : "NO";
    RespondeComandoSMS(numeroNormalizado, estado);
    return;
  }

  if (nombreComando == "ADD")
  {
    if (!esAdmin)
    {
      RespondeComandoSMS(numeroNormalizado, "Comando solo para administrador");
      return;
    }

    String nuevoNumero = NormalizaTelefonoGuardado(argumentosComando);

    if (!EsTelefonoValido(nuevoNumero))
    {
      RespondeComandoSMS(numeroNormalizado, "Comando invalido. Use: ADD +51XXXXXXXXX");
      return;
    }

    if (nuevoNumero == AdminNumero || BuscaContacto(nuevoNumero) >= 0)
    {
      RespondeComandoSMS(numeroNormalizado, "Numero ya registrado: " + nuevoNumero);
      return;
    }

    int espacioLibre = BuscaEspacioLibreContacto();

    if (espacioLibre < 0)
    {
      RespondeComandoSMS(numeroNormalizado, "Error, maximo de contactos alcanzado");
      return;
    }

    Numeros[espacioLibre] = nuevoNumero;
    ActualizaCantidadDeNumeros();
    GuardaConfiguracion();
    RespondeComandoSMS(numeroNormalizado, "Numero agregado: " + nuevoNumero);
    return;
  }

  if (nombreComando == "DEL")
  {
    if (!esAdmin)
    {
      RespondeComandoSMS(numeroNormalizado, "Comando solo para administrador");
      return;
    }

    String numeroEliminar = NormalizaTelefonoGuardado(argumentosComando);

    if (!EsTelefonoValido(numeroEliminar))
    {
      RespondeComandoSMS(numeroNormalizado, "Comando invalido. Use: DEL +51XXXXXXXXX");
      return;
    }

    if (numeroEliminar == AdminNumero)
    {
      RespondeComandoSMS(numeroNormalizado, "No se puede eliminar el numero administrador");
      return;
    }

    int indiceEliminar = BuscaContacto(numeroEliminar);

    if (indiceEliminar < 0)
    {
      RespondeComandoSMS(numeroNormalizado, "Numero no encontrado: " + numeroEliminar);
      return;
    }

    Numeros[indiceEliminar] = "";
    ActualizaCantidadDeNumeros();
    GuardaConfiguracion();
    RespondeComandoSMS(numeroNormalizado, "Eliminado: " + numeroEliminar);
    return;
  }

  if (nombreComando == "CAMBIAR")
  {
    if (!esAdmin)
    {
      RespondeComandoSMS(numeroNormalizado, "Comando solo para administrador");
      return;
    }

    String parametros = argumentosComando;
    parametros.trim();
    int separador = parametros.indexOf(' ');

    if (separador < 0)
    {
      RespondeComandoSMS(numeroNormalizado, "Comando invalido. Use: CAMBIAR +51OLD +51NEW");
      return;
    }

    String numeroAnterior = NormalizaTelefonoGuardado(parametros.substring(0, separador));
    String numeroNuevo = NormalizaTelefonoGuardado(parametros.substring(separador + 1));

    if (!EsTelefonoValido(numeroAnterior) || !EsTelefonoValido(numeroNuevo))
    {
      RespondeComandoSMS(numeroNormalizado, "Comando invalido. Use: CAMBIAR +51OLD +51NEW");
      return;
    }

    if (numeroNuevo == AdminNumero || BuscaContacto(numeroNuevo) >= 0)
    {
      RespondeComandoSMS(numeroNormalizado, "Numero nuevo ya registrado: " + numeroNuevo);
      return;
    }

    int indiceCambiar = BuscaContacto(numeroAnterior);

    if (indiceCambiar < 0)
    {
      RespondeComandoSMS(numeroNormalizado, "Numero no encontrado: " + numeroAnterior);
      return;
    }

    Numeros[indiceCambiar] = numeroNuevo;
    ActualizaCantidadDeNumeros();
    GuardaConfiguracion();
    RespondeComandoSMS(numeroNormalizado, "Numero actualizado: " + numeroAnterior + " -> " + numeroNuevo);
    return;
  }

  if (nombreComando == "RESET")
  {
    if (!esAdmin)
    {
      RespondeComandoSMS(numeroNormalizado, "Comando solo para administrador");
      return;
    }

    String codigo = argumentosComando;
    codigo.trim();

    if (codigo != CodigoReset)
    {
      RespondeComandoSMS(numeroNormalizado, "Codigo RESET incorrecto");
      return;
    }

    ReiniciaEstadoFabrica(true);
    RespondeComandoSMS(numeroNormalizado, "RESET OK - Estado de fabrica");
    Serial.println("Sistema reiniciado a estado de fabrica.");
    return;
  }

  RespondeComandoSMS(numeroNormalizado, "Comando reconocido. Se implementara en la siguiente iteracion.");
}

void RevisaSMSRecibidos()
{
  if (millis() - UltimaRevisionSMS < IntervaloRevisionSMS)
    return;

  UltimaRevisionSMS = millis();
  Serial.println("Revisando SMS no leidos...");

  if (!EnviaComandoConReintento("AT", 1200))
  {
    Serial.println("Modulo GSM sin respuesta antes de revisar SMS.");
    return;
  }

  EnviaComandoConReintento("AT+CMGF=1", 1200);

  if (!EnviaComandoConReintento("AT+CMGL=\"REC UNREAD\"", 8000))
    return;

  if (Temporal.indexOf("+CMGL:") < 0)
  {
    Serial.println("Sin SMS no leidos.");
    return;
  }

  int cursor = 0;
  int indiceSMS = -1;
  String numeroRemitente = "";
  String estadoSMS = "";
  bool esperandoCuerpo = false;

  while (cursor < Temporal.length())
  {
    String linea = ExtraeLinea(Temporal, cursor);

    if (linea.length() == 0 || linea == "OK" || linea == "ERROR")
      continue;

    Serial.print("SMS RX: ");
    Serial.println(linea);

    if (linea.startsWith("+CMGL:"))
    {
      indiceSMS = ExtraeIndiceSMS(linea);
      numeroRemitente = LimpiaTelefono(ExtraeCampoEntreComillas(linea, 1));
      estadoSMS = ExtraeEstadoSMSCabecera(linea);
      Serial.print("Indice SMS: ");
      Serial.println(indiceSMS);
      Serial.print("Estado SMS: ");
      Serial.println(estadoSMS);
      Serial.print("Remitente SMS: ");
      Serial.println(numeroRemitente);
      esperandoCuerpo = true;
      continue;
    }

    if (esperandoCuerpo)
    {
      if (EstadoSMSProcesable(estadoSMS) && numeroRemitente.length() > 0)
      {
        ProcesaComandoSMS(numeroRemitente, linea);
        BorraSMS(indiceSMS);
      }
      else
      {
        Serial.println("SMS omitido por estado no procesable o remitente vacio.");
      }

      indiceSMS = -1;
      numeroRemitente = "";
      estadoSMS = "";
      esperandoCuerpo = false;
    }
  }
}

void EnviaMensaje()
{
  if (!PuedeArmarNuevoEnvioBiometrico())
  {
    Serial.println("Envio biometrico bloqueado por rearmado/enfriamiento.");
    return;
  }

  ActualizaBateria();
  String mensaje = ConstruyeMensajeBiometrico();
  bool enviado = false;

  if (AdminConfigurado && AdminNumero.length() > 0)
  {
    digitalWrite(Buzzer, HIGH);
    delay(500);
    digitalWrite(Buzzer, LOW);
    Serial.println("Enviando Mensaje a admin");
    EnviarSMSA(AdminNumero, mensaje);
    enviado = true;
  }

  for (Var = 0; Var < MaxNumeros; Var++)
  {
    if (Numeros[Var].length() == 0)
      continue;

    if (NormalizaTelefonoGuardado(Numeros[Var]) == AdminNumero)
      continue;

    digitalWrite(Buzzer, HIGH);
    delay(500);
    digitalWrite(Buzzer, LOW);
    Serial.println("Enviando Mensaje");
    EnviarSMSA(Numeros[Var], mensaje);
    Serial.println("Mensaje Enviado");
    enviado = true;
  }

  if (enviado)
  {
    UltimoEnvioBiometrico = millis();
    EnvioBiometricoArmado = false;
  }
}

void VaciarBufferGSM()
{
  while (Serial2.available() > 0)
    Serial2.read();
}

boolean EnviaYEscucha(String Estring)
{
  return EnviaYEscucha(Estring, 1500);
}

boolean EnviaYEscucha(String Estring, unsigned long timeoutMs)
{
  if (Estring.startsWith("AT"))
    VaciarBufferGSM();

  Serial.print("Enviando:");
  if (EnvioMen.indexOf(Estring) == 0)
  {
    Serial.println("SUB (Ctrl+Z)");
    Serial2.write(26);
  }
  else
  {
    Serial.println(Estring);
    Serial2.println(Estring);
  }

  delay(80);
  return LeeRespuestaGSM(timeoutMs);
}

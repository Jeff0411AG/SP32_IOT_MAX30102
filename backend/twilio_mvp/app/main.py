from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from twilio.twiml.messaging_response import MessagingResponse

from .config_store import (
    append_audit_event,
    is_admin,
    is_authorized,
    load_config,
    load_state,
    normalize_phone,
    recipients,
    save_config,
    save_state,
)


app = FastAPI(title="ESP32 Assisted SMS Backend")


class StartupPayload(BaseModel):
    device_id: str
    message: str
    battery: int
    wifi_rssi: int | None = None


class AlertPayload(BaseModel):
    device_id: str
    status: str
    bpm: int
    spo2: int
    battery: int
    message: str


class DebugCommandPayload(BaseModel):
    from_number: str
    body: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def twiml_message(body: str) -> str:
    response = MessagingResponse()
    response.message(body)
    return str(response)


def audit_event(kind: str, payload: dict[str, Any]) -> None:
    append_audit_event(
        {
            "kind": kind,
            "at": now_iso(),
            **payload,
        }
    )


def validate_device(device_id: str, token: str | None) -> dict[str, Any]:
    config = load_config()
    if device_id != config.get("device_id"):
        raise HTTPException(status_code=403, detail="device_id no autorizado")
    if token != config.get("device_token"):
        raise HTTPException(status_code=403, detail="token no autorizado")
    return config


def format_status(config: dict[str, Any], state: dict[str, Any]) -> str:
    last_alert = state.get("last_alert")
    contacts = recipients(config)
    if last_alert:
        resumen = (
            f"Ultimo estado: {last_alert['status']} | BPM: {last_alert['bpm']} | "
            f"SpO2: {last_alert['spo2']}% | Bat: {last_alert['battery']}%"
        )
    else:
        resumen = "Sin alertas previas registradas"
    return f"[ONLINE] Contactos: {len(contacts)} | {resumen}"


def build_sms_link(number: str, body: str) -> str:
    return f"sms:{normalize_phone(number)}?body={quote(body)}"


def render_dashboard(config: dict[str, Any], state: dict[str, Any], console_result: str = "") -> str:
    last_alert = state.get("last_alert")
    last_startup = state.get("last_startup")
    target_number = normalize_phone(config.get("admin_phone", ""))
    contacts = recipients(config)
    audit_count = len(state.get("audit_log", []))

    if last_alert:
        status = last_alert.get("status", "SIN ALERTAS")
        message = last_alert.get("message", "Sin mensaje")
        bpm = last_alert.get("bpm", "--")
        spo2 = last_alert.get("spo2", "--")
        battery = last_alert.get("battery", "--")
        received_at = last_alert.get("received_at", "--")
    else:
        status = "SIN ALERTAS"
        message = "Aun no hay alertas registradas."
        bpm = "--"
        spo2 = "--"
        battery = "--"
        received_at = "--"

    startup_message = last_startup.get("message", "Sin arranque registrado") if last_startup else "Sin arranque registrado"
    startup_time = last_startup.get("received_at", "--") if last_startup else "--"
    sms_link = build_sms_link(target_number, message)
    badge_color = "#b91c1c" if status == "ALERTA" else "#166534"
    contacts_html = "".join(
        f'<li style="margin-bottom:6px;">{contact}</li>' for contact in contacts
    ) or '<li>Sin destinatarios configurados</li>'
    console_block = (
        f"""
      <article class="card">
        <p class="eyebrow">Respuesta de consola</p>
        <div class="message">{console_result}</div>
      </article>
"""
        if console_result
        else ""
    )

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Panel ESP32</title>
  <meta http-equiv="refresh" content="15">
  <style>
    :root {{
      --bg: #efe7d8;
      --card: #fffdf8;
      --ink: #1f2937;
      --muted: #6b7280;
      --line: #d8d1c2;
      --accent: #0f766e;
      --warn: #c2410c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, #fff8e8 0, transparent 30%),
        linear-gradient(135deg, #f6f0e2 0%, #eadfcb 100%);
      min-height: 100vh;
    }}
    .wrap {{
      max-width: 1024px;
      margin: 0 auto;
      padding: 28px 18px 48px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2.2rem, 4vw, 3.6rem);
      line-height: 0.95;
      letter-spacing: -0.04em;
    }}
    .sub {{
      color: var(--muted);
      max-width: 760px;
      margin: 10px 0 26px;
      line-height: 1.5;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 16px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
      box-shadow: 0 12px 28px rgba(68, 48, 18, 0.08);
    }}
    .eyebrow {{
      margin: 0 0 8px;
      font-size: 0.82rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .value {{
      margin: 0;
      font-size: clamp(1.8rem, 4vw, 2.8rem);
      line-height: 1;
    }}
    .badge {{
      display: inline-block;
      padding: 8px 12px;
      border-radius: 999px;
      background: {badge_color};
      color: white;
      font-weight: 700;
    }}
    .message {{
      background: #fcfaf5;
      border: 1px dashed var(--line);
      border-radius: 16px;
      padding: 16px;
      white-space: pre-wrap;
      line-height: 1.45;
    }}
    .stack {{
      display: grid;
      gap: 16px;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 14px;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 48px;
      padding: 0 18px;
      border-radius: 14px;
      text-decoration: none;
      font-weight: 700;
      border: 1px solid transparent;
    }}
    .btn-primary {{
      background: var(--accent);
      color: white;
    }}
    .btn-secondary {{
      background: transparent;
      border-color: var(--warn);
      color: var(--warn);
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.92rem;
      margin-top: 10px;
    }}
    .tiny {{
      color: var(--muted);
      font-size: 0.84rem;
      margin-top: 8px;
    }}
    .form-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }}
    label {{
      display: grid;
      gap: 6px;
      font-size: 0.92rem;
      color: var(--muted);
    }}
    input {{
      width: 100%;
      min-height: 46px;
      border-radius: 12px;
      border: 1px solid var(--line);
      padding: 0 12px;
      font: inherit;
      color: var(--ink);
      background: white;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <p class="eyebrow">Panel de Alerta Biometrica</p>
    <h1>ESP32 + MAX30102<br>Centro de Alerta</h1>
    <p class="sub">El ESP32 reporta al backend por detrás. Desde esta interfaz se visualiza la última alerta y se abre la app de mensajes con el número y el texto listos para envío manual.</p>

    <section class="grid">
      <article class="card">
        <p class="eyebrow">Estado</p>
        <span class="badge">{status}</span>
      </article>
      <article class="card">
        <p class="eyebrow">BPM</p>
        <p class="value">{bpm}</p>
      </article>
      <article class="card">
        <p class="eyebrow">SpO2</p>
        <p class="value">{spo2}%</p>
      </article>
      <article class="card">
        <p class="eyebrow">Bateria</p>
        <p class="value">{battery}%</p>
      </article>
    </section>

    <section class="stack">
      <article class="card">
        <p class="eyebrow">Destino actual</p>
        <p class="value" style="font-size:1.5rem;">{target_number or 'Sin numero configurado'}</p>
        <p class="meta">Ultima alerta registrada en: {received_at}</p>
      </article>

      <article class="card">
        <p class="eyebrow">Destinatarios activos</p>
        <ul>{contacts_html}</ul>
        <p class="tiny">Esta lista se actualiza desde la consola web usando los comandos operativos del backend.</p>
      </article>

      <article class="card">
        <p class="eyebrow">Mensaje listo para despacho</p>
        <div class="message">{message}</div>
        <div class="actions">
          <a class="btn btn-primary" href="{sms_link}">Abrir SMS</a>
          <a class="btn btn-secondary" href="/debug/audit" target="_blank" rel="noreferrer">Ver auditoria</a>
        </div>
        <p class="tiny">El enlace usa exactamente el ultimo mensaje generado por el ESP32 y deja el numero precargado. No se envia automaticamente por Twilio.</p>
      </article>

      <article class="card">
        <p class="eyebrow">Ultimo arranque del equipo</p>
        <div class="message">{startup_message}</div>
        <p class="meta">Registrado en: {startup_time}</p>
      </article>

{console_block}

      <article class="card">
        <p class="eyebrow">Consola de comandos</p>
        <p class="meta">Aqui otra persona puede simular el flujo SMS completo desde la web usando los mismos comandos del backend.</p>
        <form method="post" action="/console/command">
          <div class="form-grid">
            <label>
              Numero origen
              <input type="text" name="from_number" value="{target_number or '+51910521259'}" placeholder="+51910521259">
            </label>
            <label>
              Comando
              <input type="text" name="body" placeholder="STATUS | ADD +519... | DEL +519... | CAMBIAR ... | RESET 2468">
            </label>
          </div>
          <div class="actions">
            <button class="btn btn-primary" type="submit">Procesar comando</button>
          </div>
        </form>
        <p class="tiny">Ejemplos: STATUS, ADD +51911111111, DEL +51911111111, CAMBIAR +51911111111 +51922222222, RESET 2468.</p>
      </article>

      <article class="card">
        <p class="eyebrow">Resumen operativo</p>
        <div class="message">1. El ESP32 toma datos y envia al backend.\n2. El backend guarda la ultima alerta y actualiza el panel.\n3. Otra persona abre el SMS manualmente con el texto listo.\n4. Esa misma persona administra la lista con STATUS, ADD, DEL, CAMBIAR y RESET desde esta web.\n5. El backend ya no despacha Twilio automaticamente.</div>
        <p class="meta">Eventos auditados actualmente: {audit_count}</p>
      </article>
    </section>
  </main>
</body>
</html>"""


def process_incoming_command(number: str, raw_body: str) -> str:
    config = load_config()
    state = load_state()

    body = raw_body.strip().upper()
    parts = body.split()
    command = parts[0] if parts else ""
    args = parts[1:]

    audit_event(
        "sms_inbound",
        {
            "from": normalize_phone(number),
            "body": raw_body,
            "normalized_body": body,
        },
    )

    if command == "":
        reply = "Comando no valido."
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if not config.get("admin_phone"):
        config["admin_phone"] = normalize_phone(number)
        save_config(config)
        reply = "ADMIN REGISTRADO. Backend listo para recibir comandos."
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if command == "STATUS" or body == "STATUS?":
        if not is_authorized(config, number):
            reply = "Numero no autorizado para este equipo."
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        reply = format_status(config, state)
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if not is_admin(config, number):
        reply = "Comando solo para administrador"
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if command == "ADD":
        if len(args) != 1:
            reply = "Comando invalido. Use: ADD +51XXXXXXXXX"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        new_number = normalize_phone(args[0])
        if new_number in recipients(config):
            reply = f"Numero ya registrado: {new_number}"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        config["contacts"].append(new_number)
        save_config(config)
        reply = f"Numero agregado: {new_number}"
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if command == "DEL":
        if len(args) != 1:
            reply = "Comando invalido. Use: DEL +51XXXXXXXXX"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        target = normalize_phone(args[0])
        if target == normalize_phone(config["admin_phone"]):
            reply = "No se puede eliminar el numero administrador"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        if target not in [normalize_phone(item) for item in config.get("contacts", [])]:
            reply = f"Numero no encontrado: {target}"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        config["contacts"] = [item for item in config["contacts"] if normalize_phone(item) != target]
        save_config(config)
        reply = f"Eliminado: {target}"
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if command == "CAMBIAR":
        if len(args) != 2:
            reply = "Comando invalido. Use: CAMBIAR +51OLD +51NEW"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        old_number = normalize_phone(args[0])
        new_number = normalize_phone(args[1])
        contacts = [normalize_phone(item) for item in config.get("contacts", [])]
        if old_number not in contacts:
            reply = f"Numero no encontrado: {old_number}"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        if new_number in recipients(config):
            reply = f"Numero nuevo ya registrado: {new_number}"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        config["contacts"] = [new_number if normalize_phone(item) == old_number else item for item in config["contacts"]]
        save_config(config)
        reply = f"Numero actualizado: {old_number} -> {new_number}"
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    if command == "RESET":
        if len(args) != 1:
            reply = "Comando invalido. Use: RESET 2468"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        if args[0] != config.get("reset_code", "2468"):
            reply = "Codigo RESET incorrecto"
            audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
            return reply
        config["admin_phone"] = ""
        config["contacts"] = []
        save_config(config)
        reply = "RESET OK - Estado de fabrica"
        audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
        return reply

    reply = "Comando no valido. Use STATUS, ADD, DEL, CAMBIAR o RESET."
    audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
    return reply


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true"}


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return render_dashboard(load_config(), load_state())


@app.post("/console/command", response_class=HTMLResponse)
def console_command(
    from_number: str = Form(...),
    body: str = Form(...),
) -> str:
    reply = process_incoming_command(from_number, body)
    console_result = (
        f"Origen: {normalize_phone(from_number)}\n"
        f"Comando: {body.strip().upper()}\n"
        f"Respuesta: {reply}"
    )
    return render_dashboard(load_config(), load_state(), console_result=console_result)


@app.post("/api/startup")
def startup(
    payload: StartupPayload,
    x_device_token: str | None = Header(default=None),
) -> dict[str, Any]:
    config = validate_device(payload.device_id, x_device_token)
    state = load_state()
    state["last_startup"] = payload.model_dump() | {"received_at": now_iso()}
    save_state(state)
    audit_event(
        "startup_received",
        {
            "device_id": payload.device_id,
            "message": payload.message,
            "battery": payload.battery,
            "wifi_rssi": payload.wifi_rssi,
        },
    )
    return {"ok": True, "mode": "assisted", "recipients": recipients(config)}


@app.post("/api/alert")
def alert(
    payload: AlertPayload,
    x_device_token: str | None = Header(default=None),
) -> dict[str, Any]:
    config = validate_device(payload.device_id, x_device_token)
    state = load_state()
    state["last_alert"] = payload.model_dump() | {"received_at": now_iso()}
    save_state(state)
    audit_event(
        "alert_received",
        {
            "device_id": payload.device_id,
            "status": payload.status,
            "bpm": payload.bpm,
            "spo2": payload.spo2,
            "battery": payload.battery,
            "message": payload.message,
        },
    )
    return {"ok": True, "mode": "assisted", "recipients": recipients(config), "message_ready": True}


@app.post("/twilio/webhook", response_class=PlainTextResponse)
def twilio_webhook(
    From: str = Form(...),
    Body: str = Form(...),
) -> str:
    return twiml_message(process_incoming_command(From, Body))


@app.post("/debug/command")
def debug_command(payload: DebugCommandPayload) -> dict[str, Any]:
    reply = process_incoming_command(payload.from_number, payload.body)
    state = load_state()
    config = load_config()
    return {
        "ok": True,
        "reply": reply,
        "config": config,
        "audit_tail": state.get("audit_log", [])[-10:],
    }


@app.get("/debug/audit")
def debug_audit() -> dict[str, Any]:
    state = load_state()
    return {
        "ok": True,
        "audit_log": state.get("audit_log", []),
    }

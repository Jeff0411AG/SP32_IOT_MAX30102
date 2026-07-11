from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
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
MAX_RECIPIENTS = 5


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
    append_audit_event({"kind": kind, "at": now_iso(), **payload})


def validate_device(device_id: str, token: str | None) -> dict[str, Any]:
    config = load_config()
    if device_id != config.get("device_id"):
        raise HTTPException(status_code=403, detail="device_id no autorizado")
    if token != config.get("device_token"):
        raise HTTPException(status_code=403, detail="token no autorizado")
    return config


def format_status(config: dict[str, Any], state: dict[str, Any]) -> str:
    last_alert = state.get("last_alert")
    contact_count = len(recipients(config))
    if last_alert:
        summary = (
            f"Ultimo estado: {last_alert['status']} | BPM: {last_alert['bpm']} | "
            f"SpO2: {last_alert['spo2']}% | Bat: {last_alert['battery']}%"
        )
    else:
        summary = "Sin alertas previas registradas"
    return f"[ONLINE] Contactos: {contact_count} | {summary}"


def build_sms_link(number: str, body: str) -> str:
    return f"sms:{normalize_phone(number)}?body={quote(body)}"


def enqueue_messages(state: dict[str, Any], numbers: list[str], body: str, source: str) -> dict[str, Any]:
    outbox = list(state.get("outbox", []))
    created_at = now_iso()
    for number in numbers:
        normalized = normalize_phone(number)
        if not normalized:
            continue
        outbox.append(
            {
                "id": uuid4().hex[:10],
                "to": normalized,
                "body": body,
                "source": source,
                "created_at": created_at,
                "sent_at": None,
            }
        )
    state["outbox"] = outbox[-60:]
    return state


def mark_outbox_item(item_id: str) -> bool:
    state = load_state()
    for item in state.get("outbox", []):
        if item.get("id") == item_id and not item.get("sent_at"):
            item["sent_at"] = now_iso()
            save_state(state)
            return True
    return False


def clear_outbox() -> None:
    state = load_state()
    state["outbox"] = []
    save_state(state)


def pending_outbox(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in reversed(state.get("outbox", [])) if not item.get("sent_at")]


def sent_outbox(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in reversed(state.get("outbox", [])) if item.get("sent_at")]


def render_queue_item(item: dict[str, Any], sent: bool) -> str:
    chip = "Enviado" if sent else "Pendiente"
    chip_class = "chip chip-sent" if sent else "chip"
    date_label = "Enviado" if sent else "Creado"
    date_value = item.get("sent_at") if sent else item.get("created_at")
    actions = ""
    if not sent:
        actions = f"""
          <div class="actions">
            <a class="btn btn-primary" href="{build_sms_link(item['to'], item['body'])}">Abrir SMS</a>
            <form method="post" action="/queue/{item['id']}/sent">
              <button class="btn btn-secondary" type="submit">Marcar enviado</button>
            </form>
          </div>
        """
    return f"""
      <article class="queue-item {'queue-item-sent' if sent else ''}">
        <div class="queue-head">
          <div>
            <p class="queue-title">{item['source']}</p>
            <p class="queue-meta">Para {item['to']} | {date_label}: {date_value}</p>
          </div>
          <span class="{chip_class}">{chip}</span>
        </div>
        <div class="message">{item['body']}</div>
        {actions}
      </article>
    """


def render_dashboard(config: dict[str, Any], state: dict[str, Any], console_result: str = "") -> str:
    last_alert = state.get("last_alert")
    last_startup = state.get("last_startup")
    admin_number = normalize_phone(config.get("admin_phone", ""))
    active_recipients = recipients(config)
    pending_items = pending_outbox(state)
    sent_items = sent_outbox(state)
    latest_item = pending_items[0] if pending_items else None
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
    badge_color = "#b91c1c" if status == "ALERTA" else "#166534"
    contacts_html = "".join(f"<li>{contact}</li>" for contact in active_recipients) or "<li>Sin destinatarios configurados</li>"
    pending_html = "".join(render_queue_item(item, sent=False) for item in pending_items) or (
        '<div class="message">No hay mensajes pendientes.</div>'
    )
    sent_html = "".join(render_queue_item(item, sent=True) for item in sent_items[:10]) or (
        '<div class="message">Todavia no hay mensajes marcados como enviados.</div>'
    )
    console_block = (
        f"""
      <article class="card">
        <p class="eyebrow">Resultado</p>
        <div class="message">{console_result}</div>
      </article>
"""
        if console_result
        else ""
    )
    primary_sms_link = build_sms_link(latest_item["to"], latest_item["body"]) if latest_item else "#"
    primary_sms_class = "btn btn-primary" if latest_item else "btn btn-secondary"

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Panel ESP32</title>
  <meta http-equiv="refresh" content="10">
  <style>
    :root {{
      --card: #fffdfa;
      --ink: #1f2937;
      --muted: #6b7280;
      --line: #d9cfbc;
      --accent: #0f766e;
      --accent-strong: #115e59;
      --warn: #9a3412;
      --bg: #f5efe4;
      --soft: #f8f2e8;
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
      max-width: 920px;
      margin: 0 auto;
      padding: 18px 14px 28px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(1.6rem, 3vw, 2.3rem);
      line-height: 1;
      letter-spacing: -0.04em;
    }}
    .sub {{
      color: var(--muted);
      max-width: 760px;
      margin: 6px 0 14px;
      line-height: 1.35;
      font-size: 0.92rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 10px;
      margin-bottom: 10px;
    }}
    .stack {{
      display: grid;
      gap: 10px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      box-shadow: 0 8px 18px rgba(68, 48, 18, 0.06);
    }}
    .eyebrow {{
      margin: 0 0 4px;
      font-size: 0.72rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .value {{
      margin: 0;
      font-size: clamp(1.2rem, 3vw, 1.8rem);
      line-height: 1;
    }}
    .badge {{
      display: inline-block;
      padding: 5px 9px;
      border-radius: 999px;
      background: {badge_color};
      color: white;
      font-weight: 700;
      font-size: 0.84rem;
    }}
    .message {{
      background: #fcfaf5;
      border: 1px dashed var(--line);
      border-radius: 10px;
      padding: 10px;
      white-space: pre-wrap;
      line-height: 1.3;
      font-size: 0.9rem;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }}
    form {{ margin: 0; }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 34px;
      padding: 0 12px;
      border-radius: 10px;
      text-decoration: none;
      font-weight: 700;
      border: 1px solid transparent;
      cursor: pointer;
      font: inherit;
      font-size: 0.88rem;
    }}
    .btn-primary {{
      background: var(--accent);
      color: white;
    }}
    .btn-primary:hover {{
      background: var(--accent-strong);
    }}
    .btn-secondary {{
      background: white;
      border-color: var(--warn);
      color: var(--warn);
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.84rem;
      margin-top: 6px;
    }}
    .tiny {{
      color: var(--muted);
      font-size: 0.78rem;
      margin-top: 6px;
    }}
    .form-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 8px;
    }}
    label {{
      display: grid;
      gap: 4px;
      font-size: 0.82rem;
      color: var(--muted);
    }}
    input {{
      width: 100%;
      min-height: 36px;
      border-radius: 10px;
      border: 1px solid var(--line);
      padding: 0 10px;
      font: inherit;
      color: var(--ink);
      background: white;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    .queue {{
      display: grid;
      gap: 8px;
    }}
    .queue-item {{
      background: var(--soft);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
    }}
    .queue-item-sent {{
      background: #f4f8f4;
    }}
    .queue-head {{
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
    }}
    .queue-title {{
      margin: 0 0 2px;
      font-size: 0.92rem;
      font-weight: 700;
    }}
    .queue-meta {{
      margin: 0;
      color: var(--muted);
      font-size: 0.78rem;
    }}
    .chip {{
      background: #fff;
      color: var(--warn);
      border: 1px solid #f5c2a8;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 0.72rem;
      font-weight: 700;
      white-space: nowrap;
    }}
    .chip-sent {{
      color: #166534;
      border-color: #bbf7d0;
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <p class="eyebrow">Panel de Comunicacion Asistida</p>
    <h1>ESP32 + MAX30102</h1>
    <p class="sub">Vista compacta de pendientes, enviados y destinos activos.</p>

    <section class="grid">
      <article class="card"><p class="eyebrow">Estado</p><span class="badge">{status}</span></article>
      <article class="card"><p class="eyebrow">BPM</p><p class="value">{bpm}</p></article>
      <article class="card"><p class="eyebrow">SpO2</p><p class="value">{spo2}%</p></article>
      <article class="card"><p class="eyebrow">Bateria</p><p class="value">{battery}%</p></article>
      <article class="card"><p class="eyebrow">Pendientes</p><p class="value">{len(pending_items)}</p></article>
      <article class="card"><p class="eyebrow">Enviados</p><p class="value">{len(sent_items)}</p></article>
    </section>

    <section class="stack">
      <article class="card">
        <p class="eyebrow">Siguiente</p>
        <p class="value" style="font-size:1.2rem;">{latest_item['to'] if latest_item else 'Sin pendientes'}</p>
        <p class="meta">{latest_item['source'] if latest_item else 'Esperando siguiente evento.'}</p>
        <div class="message">{latest_item['body'] if latest_item else 'No hay ningun mensaje pendiente por enviar.'}</div>
        <div class="actions">
          <a class="{primary_sms_class}" href="{primary_sms_link}">Abrir siguiente SMS</a>
          <form method="post" action="/queue/clear">
            <button class="btn btn-secondary" type="submit">Vaciar cola</button>
          </form>
          <a class="btn btn-secondary" href="/debug/audit" target="_blank" rel="noreferrer">Ver auditoria</a>
        </div>
      </article>

      <article class="card">
        <p class="eyebrow">Pendientes</p>
        <div class="queue">{pending_html}</div>
      </article>

      <article class="card">
        <p class="eyebrow">Enviados</p>
        <div class="queue">{sent_html}</div>
      </article>

      <article class="card">
        <p class="eyebrow">Comandos</p>
        <form method="post" action="/console/command">
          <div class="form-grid">
            <label>
              Numero origen
              <input type="text" name="from_number" value="{admin_number or '+51910521259'}" placeholder="+51910521259">
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
        <p class="tiny">Limite actual: {MAX_RECIPIENTS} destinatarios activos contando al administrador.</p>
      </article>

      <article class="card">
        <p class="eyebrow">Destinos</p>
        <ul>{contacts_html}</ul>
        <p class="tiny">Administrador actual: {admin_number or 'Sin numero configurado'} | Total: {len(active_recipients)} de {MAX_RECIPIENTS}</p>
      </article>

      <article class="card">
        <p class="eyebrow">Ultimos datos</p>
        <div class="message">Alerta: {message}\nRecibida: {received_at}\n\nArranque: {startup_message}\nRegistrado: {startup_time}</div>
      </article>

{console_block}

      <article class="card">
        <p class="eyebrow">Resumen</p>
        <div class="message">El backend crea un mensaje por destinatario. Lo envias manualmente y luego lo marcas como enviado.</div>
        <p class="meta">Eventos auditados: {audit_count}</p>
      </article>
    </section>
  </main>
</body>
</html>"""


def queue_command_reply(state: dict[str, Any], number: str, reply: str) -> str:
    enqueue_messages(state, [number], reply, "Respuesta comando")
    save_state(state)
    audit_event("sms_reply", {"to": normalize_phone(number), "body": reply})
    return reply


def process_incoming_command(number: str, raw_body: str) -> str:
    config = load_config()
    state = load_state()

    body = raw_body.strip().upper()
    parts = body.split()
    command = parts[0] if parts else ""
    args = parts[1:]

    audit_event(
        "sms_inbound",
        {"from": normalize_phone(number), "body": raw_body, "normalized_body": body},
    )

    if command == "":
        return queue_command_reply(state, number, "Comando no valido.")

    if not config.get("admin_phone"):
        config["admin_phone"] = normalize_phone(number)
        save_config(config)
        return queue_command_reply(state, number, "ADMIN REGISTRADO. Backend listo para recibir comandos.")

    if command == "STATUS" or body == "STATUS?":
        if not is_authorized(config, number):
            return queue_command_reply(state, number, "Numero no autorizado para este equipo.")
        return queue_command_reply(state, number, format_status(config, state))

    if not is_admin(config, number):
        return queue_command_reply(state, number, "Comando solo para administrador")

    if command == "ADD":
        if len(args) != 1:
            return queue_command_reply(state, number, "Comando invalido. Use: ADD +51XXXXXXXXX")
        new_number = normalize_phone(args[0])
        if new_number in recipients(config):
            return queue_command_reply(state, number, f"Numero ya registrado: {new_number}")
        if len(recipients(config)) >= MAX_RECIPIENTS:
            return queue_command_reply(state, number, f"Limite alcanzado. Solo se permiten {MAX_RECIPIENTS} destinatarios.")
        config["contacts"].append(new_number)
        save_config(config)
        return queue_command_reply(state, number, f"Numero agregado: {new_number}")

    if command == "DEL":
        if len(args) != 1:
            return queue_command_reply(state, number, "Comando invalido. Use: DEL +51XXXXXXXXX")
        target = normalize_phone(args[0])
        if target == normalize_phone(config["admin_phone"]):
            return queue_command_reply(state, number, "No se puede eliminar el numero administrador")
        if target not in [normalize_phone(item) for item in config.get("contacts", [])]:
            return queue_command_reply(state, number, f"Numero no encontrado: {target}")
        config["contacts"] = [item for item in config["contacts"] if normalize_phone(item) != target]
        save_config(config)
        return queue_command_reply(state, number, f"Eliminado: {target}")

    if command == "CAMBIAR":
        if len(args) != 2:
            return queue_command_reply(state, number, "Comando invalido. Use: CAMBIAR +51OLD +51NEW")
        old_number = normalize_phone(args[0])
        new_number = normalize_phone(args[1])
        contacts = [normalize_phone(item) for item in config.get("contacts", [])]
        if old_number not in contacts:
            return queue_command_reply(state, number, f"Numero no encontrado: {old_number}")
        if new_number in recipients(config):
            return queue_command_reply(state, number, f"Numero nuevo ya registrado: {new_number}")
        config["contacts"] = [new_number if normalize_phone(item) == old_number else item for item in config["contacts"]]
        save_config(config)
        return queue_command_reply(state, number, f"Numero actualizado: {old_number} -> {new_number}")

    if command == "RESET":
        if len(args) != 1:
            return queue_command_reply(state, number, "Comando invalido. Use: RESET 2468")
        if args[0] != config.get("reset_code", "2468"):
            return queue_command_reply(state, number, "Codigo RESET incorrecto")
        config["admin_phone"] = ""
        config["contacts"] = []
        save_config(config)
        return queue_command_reply(state, number, "RESET OK - Estado de fabrica")

    return queue_command_reply(state, number, "Comando no valido. Use STATUS, ADD, DEL, CAMBIAR o RESET.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true"}


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return render_dashboard(load_config(), load_state())


@app.post("/console/command", response_class=HTMLResponse)
def console_command(from_number: str = Form(...), body: str = Form(...)) -> RedirectResponse:
    process_incoming_command(from_number, body)
    return RedirectResponse(url="/", status_code=303)


@app.post("/queue/{item_id}/sent", response_class=HTMLResponse)
def queue_mark_sent(item_id: str) -> RedirectResponse:
    mark_outbox_item(item_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/queue/clear", response_class=HTMLResponse)
def queue_clear() -> RedirectResponse:
    clear_outbox()
    return RedirectResponse(url="/", status_code=303)


@app.post("/api/startup")
def startup(payload: StartupPayload, x_device_token: str | None = Header(default=None)) -> dict[str, Any]:
    config = validate_device(payload.device_id, x_device_token)
    state = load_state()
    state["last_startup"] = payload.model_dump() | {"received_at": now_iso()}
    enqueue_messages(state, recipients(config), payload.message, "Encendido")
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
    return {"ok": True, "mode": "assisted", "recipients": recipients(config), "message_ready": True}


@app.post("/api/alert")
def alert(payload: AlertPayload, x_device_token: str | None = Header(default=None)) -> dict[str, Any]:
    config = validate_device(payload.device_id, x_device_token)
    state = load_state()
    state["last_alert"] = payload.model_dump() | {"received_at": now_iso()}
    enqueue_messages(state, recipients(config), payload.message, "Alerta biometrica")
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
def twilio_webhook(From: str = Form(...), Body: str = Form(...)) -> str:
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
        "outbox_tail": state.get("outbox", [])[-10:],
    }


@app.get("/debug/audit")
def debug_audit() -> dict[str, Any]:
    state = load_state()
    return {"ok": True, "audit_log": state.get("audit_log", []), "outbox": state.get("outbox", [])}

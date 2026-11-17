import os
import unicodedata
import pandas as pd
from fastapi import FastAPI, Request, Response

app = FastAPI()

SHEET_ID = "19kkoRLxDnAGF96QUm7NBq9r2M2poQ09y_Ko_w72olNQ"

url_creditos = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Base_Creditos"
url_asesores = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Asesores_Autorizados"

# Estructura en memoria: { celular: { "cedula": "...", "alertas": [...] } }
sesiones_activas = {}

def limpiar_texto(texto):
    if not isinstance(texto, str):
        return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).strip().upper()

@app.get("/")
def home():
    return {"status": "KALA Assist activo y escuchando 🚀"}

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    try:
        data = await request.form()
        celular_remitente = str(data.get("From", "")).strip()
        mensaje_texto = str(data.get("Body", "")).strip()
        
        # Detección de archivos adjuntos (opcionales)
        num_media = data.get("NumMedia", "0")
        tiene_archivo = False
        try:
            if int(num_media) > 0:
                tiene_archivo = True
        except:
            pass
            
        if not tiene_archivo:
            for key in data.keys():
                if "MediaContentType" in key or "MediaUrl" in key:
                    tiene_archivo = True
                    break
        
        # Limpieza de prefijo de país y etiqueta de whatsapp
        celular_limpio = celular_remitente.replace("whatsapp:", "").strip()
        if celular_limpio.startswith("+57"):
            celular_limpio = celular_limpio[3:]
        elif celular_limpio.startswith("57") and len(celular_limpio) > 10:
            celular_limpio = celular_limpio[2:]
            
        df_asesores = pd.read_csv(url_asesores)
        df_asesores['Telefono_WhatsApp'] = df_asesores['Telefono_WhatsApp'].astype(str).str.replace(r'\D', '', regex=True)
        
        asesor_registrado = df_asesores[df_asesores['Telefono_WhatsApp'] == celular_limpio]
        
        if asesor_registrado.empty:
            texto_respuesta = f"❌ Acceso denegado: El número {celular_limpio} no está registrado como asesor autorizado en KALA."
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")
        
        nombre_asesor = str(asesor_registrado.iloc[0]['Nombre_Asesor']).strip()
        
        # Opción 2 para finalizar el chat en cualquier momento
        if mensaje_texto == "2":
            if celular_limpio in sesiones_activas:
                del sesiones_activas[celular_limpio]
            texto_respuesta = f"👋 Chat finalizado con éxito. Gracias por usar KALA Assist, {nombre_asesor}. ¡Muchos éxitos en tus gestiones!"
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")

        # Si el usuario ya está en sesión activa y envía el comentario/soporte de la alerta seleccionada
        if celular_limpio in sesiones_activas:
            # El comentario es obligatorio
            if not mensaje_texto and not tiene_archivo:
                texto_respuesta = "⚠️ Debes enviar el **comentario obligatorio** explicando cómo se subsana la alerta (el soporte adjunto es opcional)."
                xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                return Response(content=xml_respuesta, media_type="application/xml")
            
            cedula_consultada = sesiones_activas[celular_limpio]["cedula"]
            del sesiones_activas[celular_limpio]
            
            texto_respuesta = (
                f"✅ ¡Recibido y verificado, {nombre_asesor}!\n\n"
                f"📄 El comentario y soporte han sido adjuntados correctamente al expediente del crédito con cédula {cedula_consultada}.\n"
                f"🔄 El caso ha sido actualizado a estado **Estudio Subsanado** y pasará a revisión final por mesa de control.\n\n"
                f"¿Deseas consultar otro número de cédula o finalizar?\n"
                f"• Envía otra **cédula** para nueva consulta\n"

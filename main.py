import os
import unicodedata
import pandas as pd
from fastapi import FastAPI, Request, Response

app = FastAPI()

SHEET_ID = "19kkoRLxDnAGF96QUm7NBq9r2M2poQ09y_Ko_w72olNQ"

url_creditos = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Base_Creditos"
url_asesores = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Asesores_Autorizados"

# Diccionario temporal en memoria para rastrear en qué alerta va cada asesor mientras chatea
# Estructura: { celular: { "cedula": "...", "alertas": [...], "indice_actual": 0 } }
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

        # Verificamos si el asesor está en un proceso activo de subsanación de alertas
        if celular_limpio in sesiones_activas:
            sesion = sesiones_activas[celular_limpio]
            
            # El comentario es obligatorio (si manda texto o si manda archivo acompañado de texto explicativo)
            if not mensaje_texto and not tiene_archivo:
                texto_respuesta = "⚠️ Por favor, escribe un comentario obligatorio explicando cómo se subsana esta alerta (el soporte adjunto es opcional)."
                xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                return Response(content=xml_respuesta, media_type="application/xml")
            
            # Avanzamos a la siguiente alerta pendiente
            sesion["indice_actual"] += 1
            
            # Si aún quedan alertas por resolver
            if sesion["indice_actual"] < len(sesion["alertas"]):
                alerta_siguiente = sesion["alertas"][sesion["indice_actual"]]
                texto_respuesta = (
                    f"✅ ¡Comentario registrado correctamente!\n\n"
                    f"⚠️ *Siguiente alerta pendiente ({sesion['indice_actual'] + 1} de {len(sesion['alertas'])}):*\n"
                    f"{alerta_siguiente}\n\n"
                    f"💡 *Recomendación KALA:* Escribe tu comentario obligatorio explicando la solución y opcionalmente adjunta el soporte.\n"
                    f"*(O marca **2** para finalizar)*"
                )
                xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                return Response(content=xml_respuesta, media_type="application/xml")
            else:
                # Ya se resolvieron todas las alertas
                cedula_consultada = sesion["cedula"]
                del sesiones_activas[celular_limpio]
                
                texto_respuesta = (
                    f"🎉 ¡Excelente, {nombre_asesor}! Has subsanado todas las alertas del crédito con cédula {cedula_consultada}.\n\n"
                    f"🔄 El expediente ha sido actualizado a estado **Estudio Subsanado** y enviado a revisión final por mesa de control.\n\n"
                    f"¿Deseas consultar otro número de cédula o finalizar?\n"
                    f"• Envía otra **cédula** para nueva consulta\n"
                    f"• Marca **2** para finalizar"
                )
                xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                return Response(content=xml_respuesta, media_type="application/xml")

        # Manejo si presiona 1 para iniciar el proceso de subsanación de un crédito previamente consultado
        if mensaje_texto == "1":
            texto_respuesta = (
                f"📂 ¡Perfecto, {nombre_asesor}!\n\n"
                f"💡 *Instrucción KALA:* Vamos a resolver las alertas una por una. Por favor, escribe tu **comentario obligatorio** explicando la solución (el soporte adjunto es opcional)."
            )
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")

        # Si el usuario manda un saludo o texto que no es cédula ni opción
        if not mensaje_texto.isdigit():
            texto_respuesta = (
                f"¡Hola, {nombre_asesor}! 🌟 Te doy la bienvenida a **KALA Assist**.\n\n"
                f"Por favor, envíame el **número de cédula** del cliente a consultar o escribe una opción:\n"
                f"• Envía la **cédula** para consultar estado\n"
                f"• Marca **2** para finalizar el chat"
            )
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")
        
        # Si es una cédula, consultamos los créditos
        df_creditos = pd.read_csv(url_creditos)
        
        columnas_map = {limpiar_texto(c): c for c in df_creditos.columns}
        
        col_cedula = next((columnas_map[c] for c in columnas_map if 'CEDULA' in c), None)
        col_cliente = next((columnas_map[c] for c in columnas_map if 'CLIENTE' in c or 'NOMBRE' in c), None)
        col_pagaduria = next((columnas_map[c] for c in columnas_map if 'PAGADUR' in c), None)
        col_etapa = next((columnas_map[c] for c in columnas_map if 'ETAPA' in c), None)
        col_alertas = next((columnas_map[c] for c in columnas_map if 'ALERTA' in c), None)
        col_asesor = next((columnas_map[c] for c in columnas_map if 'ASESOR' in c), None)
        
        df_creditos['Cedula_Clean'] = pd.to_numeric(df_creditos[col_cedula], errors='coerce').fillna(0).astype(int)
        cedula_int = int(mensaje_texto)
        
        df_creditos['Asesor_Clean'] = df_creditos[col_asesor].astype(str).str.strip().str.upper()
        nombre_asesor_clean = nombre_asesor.upper()
        
        resultado = df_creditos[
            (df_creditos['Asesor_Clean'] == nombre_asesor_clean) & 
            (df_creditos['Cedula_Clean'] == cedula_int)
        ]
        
        if resultado.empty:
            texto_respuesta = f"⚠️ Hola {nombre_asesor}, no se encontraron créditos asignados a tu nombre con la cédula {mensaje_texto}. Escribe otra cédula o marca 2 para finalizar."
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")
        
        fila_datos = resultado.iloc[0]
        
        nombre_cliente = str(fila_datos.get(col_cliente, 'No registrado')).strip()
        pagaduria_val = str(fila_datos.get(col_pagaduria, 'No registrada')).strip()
        etapa_val = str(fila_datos.get(col_etapa, 'N/A')).strip()
        alertas_val = str(fila_datos.get(col_alertas, 'Ninguna')).strip()
        
        # Separar las alertas para manejarlas de forma individual
        lista_alertas = [a.strip() for a in alertas_val.replace("\\n", "\n").split("\n") if a.strip()]
        
        # Guardamos la sesión activa para este asesor
        sesiones_activas[celular_limpio] = {
            "cedula": mensaje_texto,
            "alertas": lista_alertas,
            "indice_actual": 0
        }
        
        primera_alerta = lista_alertas[0] if lista_alertas else "Ninguna"
        
        texto_resumen = (
            f"📋 *Estado del Crédito - KALA*\n\n"
            f"👤 *Cliente:* {nombre_cliente}\n"
            f"🆔 *Cédula:* {mensaje_texto}\n"
            f"🏢 *Pagaduría:* {pagaduria_val}\n"
            f"📌 *Etapa Actual:* {etapa_val}\n"
            f"⚡ *Total Alertas Pendientes:* {len(lista_alertas)}\n\n"
            f"🔍 *Comenzamos con la Alerta 1 de {len(lista_alertas)}:*\n"
            f"   • {primera_alerta}\n\n"
            f"👉 *Acción requerida:*\n"
            f"Presiona **1** para redactar tu comentario obligatorio y adjuntar soporte para esta alerta.\n"
            f"*(O marca **2** para finalizar chat)*"
        )
        
        xml_respuesta = f"<Response><Message>{texto_resumen}</Message></Response>"
        return Response(content=xml_respuesta, media_type="application/xml")

    except Exception as e:
        texto_respuesta = f"Ocurrió un evento en el servidor: {str(e)}"
        xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
        return Response(content=xml_respuesta, media_type="application/xml")

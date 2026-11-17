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

        # Si el asesor ya consultó una cédula y selecciona el número de la alerta (ej. "1" o "2")
        if celular_limpio in sesiones_activas and sesiones_activas[celular_limpio].get("esperando_seleccion"):
            sesion = sesiones_activas[celular_limpio]
            if mensaje_texto.isdigit():
                opcion_num = int(mensaje_texto)
                if 1 <= opcion_num <= len(sesion["alertas"]):
                    alerta_seleccionada = sesion["alertas"][opcion_num - 1]
                    sesion["esperando_seleccion"] = False
                    sesion["alerta_en_proceso"] = alerta_seleccionada
                    
                    texto_respuesta = (
                        f"📂 ¡Perfecto, {nombre_asesor}!\n\n"
                        f"🎯 *Alerta seleccionada:*\n{alerta_seleccionada}\n\n"
                        f"💡 *Recomendación KALA:* Recuerda dejar tu **comentario obligatorio** explicando la solución y, en caso de que aplique, adjuntar soporte **completamente legible, sin tachones y sin enmedaduras** para que el crédito pase a estudio.\n\n"
                        f"📎 Por favor, escribe tu comentario y opcionalmente adjunta el soporte correspondiente."
                    )
                    xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                    return Response(content=xml_respuesta, media_type="application/xml")

        # Si el asesor está enviando el comentario y/o soporte para la alerta elegida
        if celular_limpio in sesiones_activas and sesiones_activas[celular_limpio].get("alerta_en_proceso"):
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
                f"• Marca **2** para finalizar el chat"
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
        
        # Separar las alertas para listarlas con números individuales
        lista_alertas = [a.strip() for a in alertas_val.replace("\\n", "\n").split("\n") if a.strip()]
        
        alertas_formateadas = "\n".join([f"   • #{i+1} {alt.replace(f'#{i+1}', '').strip()}" for i, alt in enumerate(lista_alertas)])
        
        # Guardamos la sesión activa esperando que el asesor elija el número de la alerta
        sesiones_activas[celular_limpio] = {
            "cedula": mensaje_texto,
            "alertas": lista_alertas,
            "esperando_seleccion": True
        }
        
        texto_resumen = (
            f"📋 *Estado del Crédito - KALA*\n\n"
            f"👤 *Cliente:* {nombre_cliente}\n"
            f"🆔 *Cédula:* {mensaje_texto}\n"
            f"🏢 *Pagaduría:* {pagaduria_val}\n"
            f"📌 *Etapa Actual:* {etapa_val}\n"
            f"⚡ *Total Alertas Pendientes:* {len(lista_alertas)}\n\n"
            f"🔍 *Alertas pendientes:*\n{alertas_formateadas}\n\n"
            f"👉 *Acción requerida:*\n"
            f"Presiona **el número de la alerta** que deseas subsanar\n"
            f"*(O marca **2** para finalizar chat)*"
        )
        
        xml_respuesta = f"<Response><Message>{texto_resumen}</Message></Response>"
        return Response(content=xml_respuesta, media_type="application/xml")

    except Exception as e:
        texto_respuesta = f"Ocurrió un evento en el servidor: {str(e)}"
        xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
        return Response(content=xml_respuesta, media_type="application/xml")

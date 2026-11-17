import os
import unicodedata
import pandas as pd
from fastapi import FastAPI, Request, Response

app = FastAPI()

SHEET_ID = "19kkoRLxDnAGF96QUm7NBq9r2M2poQ09y_Ko_w72olNQ"

url_creditos = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Base_Creditos"
url_asesores = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Asesores_Autorizados"

# Estructura de sesiones robusta en memoria:
# { celular: { "cedula": "...", "alertas_pendientes": [...], "etapa": "menu_alertas" / "esperando_comentario" / "preguntar_continuar" } }
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
        
        # Manejo de sesiones activas según la etapa en la que vaya el asesor
        if celular_limpio in sesiones_activas:
            sesion = sesiones_activas[celular_limpio]
            etapa = sesion.get("etapa")
            
            # ETAPA 1: El asesor seleccionó el número de la alerta a subsanar
            if etapa == "menu_alertas":
                if mensaje_texto.isdigit():
                    opcion_num = int(mensaje_texto)
                    alertas_actuales = sesion["alertas_pendientes"]
                    
                    if 1 <= opcion_num <= len(alertas_actuales):
                        alerta_elegida = alertas_actuales[opcion_num - 1]
                        sesion["alerta_en_proceso"] = alerta_elegida
                        sesion["etapa"] = "esperando_comentario"
                        
                        texto_respuesta = (
                            f"📂 ¡Perfecto, {nombre_asesor}!\n\n"
                            f"🎯 *Alerta seleccionada:*\n{alerta_elegida}\n\n"
                            f"💡 *Recomendación KALA:* Deja el comentario para subsanar la alerta de forma clara y precisa y, de ser necesario, adjunta el documento soporte legible (sin tachones ni enmedaduras).\n\n"
                            f"📎 Por favor, envía tu comentario obligatorio y opcionalmente el soporte."
                        )
                        xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                        return Response(content=xml_respuesta, media_type="application/xml")
            
            # ETAPA 2: El asesor está enviando el comentario y/o soporte para la alerta elegida
            elif etapa == "esperando_comentario":
                if not mensaje_texto and not tiene_archivo:
                    texto_respuesta = "⚠️ Debes enviar el **comentario obligatorio** explicando cómo se subsana la alerta (el soporte adjunto es opcional)."
                    xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                    return Response(content=xml_respuesta, media_type="application/xml")
                
                # Eliminamos la alerta que acaba de ser subsanada de la lista pendiente
                alerta_resuelta = sesion["alerta_en_proceso"]
                if alerta_resuelta in sesion["alertas_pendientes"]:
                    sesion["alertas_pendientes"].remove(alerta_resuelta)
                
                sesion["alerta_en_proceso"] = None
                
                # Verificamos si aún quedan alertas pendientes
                if len(sesion["alertas_pendientes"]) > 0:
                    sesion["etapa"] = "preguntar_continuar"
                    texto_respuesta = (
                        f"✅ ¡Subsanado con éxito, {nombre_asesor}!\n\n"
                        f"¿Deseas subsanar otra alerta?\n"
                        f"1️⃣ - Sí\n"
                        f"2️⃣ - Finalizar chat"
                    )
                    xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                    return Response(content=xml_respuesta, media_type="application/xml")
                else:
                    # ¡Cero alertas pendientes! El crédito viaja a estudio con éxito
                    cedula_fin = sesion["cedula"]
                    del sesiones_activas[celular_limpio]
                    texto_respuesta = (
                        f"🎉 ¡Completaste todas las alertas pendientes, {nombre_asesor}!\n\n"
                        f"🚀 El crédito con cédula {cedula_fin} viaja a estudio y ha sido actualizado a **Estudio Subsanado**.\n\n"
                        f"Envía otra **cédula** cuando desees realizar una nueva consulta."
                    )
                    xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                    return Response(content=xml_respuesta, media_type="application/xml")

            # ETAPA 3: El asesor respondió "1 - Sí" o "2 - Finalizar" tras subsanar una alerta
            elif etapa == "preguntar_continuar":
                if mensaje_texto == "1":
                    # Vuelve a mostrar el listado de las alertas que aún siguen pendientes
                    sesion["etapa"] = "menu_alertas"
                    alertas_pendientes = sesion["alertas_pendientes"]
                    
                    alertas_formateadas = "\n".join([f"   • #{i+1} {alt}" for i, alt in enumerate(alertas_pendientes)])
                    
                    texto_respuesta = (
                        f"🔍 *Alertas pendientes por subsanar:*\n{alertas_formateadas}\n\n"
                        f"👉 *Acción requerida:*\n"
                        f"Presiona **el número de la alerta** que deseas subsanar"
                    )
                    xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                    return Response(content=xml_respuesta, media_type="application/xml")
                
                elif mensaje_texto == "2":
                    # Alerta si el asesor decide finalizar sin completar todas las alertas
                    alertas_restantes = len(sesion.get("alertas_pendientes", []))
                    del sesiones_activas[celular_limpio]
                    
                    texto_respuesta = (
                        f"⚠️ *Alarma KALA:* Recuerda que para que el crédito viaje a estudio debes subsanar todas las alertas pendientes ({alertas_restantes} aún sin resolver).\n\n"
                        f"👋 Chat finalizado. ¡Muchos éxitos en tus gestiones comerciales, {nombre_asesor}!"
                    )
                    xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
                    return Response(content=xml_respuesta, media_type="application/xml")

        # Si el usuario manda un saludo o texto que no es cédula
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
            texto_respuesta = f"⚠️ Hola {nombre_asesor}, no se encontraron créditos asignados a tu nombre con la cédula {mensaje_texto}. Escribe otra cédula."
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")
        
        fila_datos = resultado.iloc[0]
        
        nombre_cliente = str(fila_datos.get(col_cliente, 'No registrado')).strip()
        pagaduria_val = str(fila_datos.get(col_pagaduria, 'No registrada')).strip()
        etapa_val = str(fila_datos.get(col_etapa, 'N/A')).strip()
        alertas_val = str(fila_datos.get(col_alertas, 'Ninguna')).strip()
        
        # Separar las alertas y numerarlas
        lista_alertas = [a.strip() for a in alertas_val.replace("\\n", "\n").split("\n") if a.strip()]
        
        alertas_formateadas = "\n".join([f"   • #{i+1} {alt.replace(f'#{i+1}', '').strip()}" for i, alt in enumerate(lista_alertas)])
        
        # Iniciamos la sesión activa en el menú de selección de alertas
        sesiones_activas[celular_limpio] = {
            "cedula": mensaje_texto,
            "alertas_pendientes": lista_alertas,
            "etapa": "menu_alertas",
            "alerta_en_proceso": None
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
            f"Presiona **el número de la alerta** que deseas subsanar"
        )
        
        xml_respuesta = f"<Response><Message>{texto_resumen}</Message></Response>"
        return Response(content=xml_respuesta, media_type="application/xml")

    except Exception as e:
        texto_respuesta = f"Ocurrió un evento en el servidor: {str(e)}"
        xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
        return Response(content=xml_respuesta, media_type="application/xml")

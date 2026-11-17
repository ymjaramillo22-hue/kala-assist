import os
import pandas as pd
from fastapi import FastAPI, Request, Response

app = FastAPI()

SHEET_ID = "19kkoRLxDnAGF96QUm7NBq9r2M2poQ09y_Ko_w72olNQ"

url_creditos = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Base_Creditos"
url_asesores = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Asesores_Autorizados"

@app.get("/")
def home():
    return {"status": "KALA Assist activo y escuchando 🚀"}

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    try:
        data = await request.form()
        celular_remitente = str(data.get("From", "")).strip()
        mensaje_texto = str(data.get("Body", "")).strip()
        
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
        
        # Manejo de opciones de menú si el usuario presiona 1 o 2
        if mensaje_texto == "1":
            texto_respuesta = f"📂 ¡Perfecto, {nombre_asesor}! Por favor, adjunta o envía por este medio el soporte necesario para subsanar el crédito."
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")
            
        if mensaje_texto == "2":
            texto_respuesta = f"👋 Chat finalizado con éxito. Gracias por usar KALA Assist, {nombre_asesor}. ¡Muchos éxitos en tus gestiones!"
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")

        # Si el usuario manda un saludo o texto que no es cédula ni opción de menú
        if not mensaje_texto.isdigit():
            texto_respuesta = (
                f"¡Hola, {nombre_asesor}! 🌟 Te doy la bienvenida a **KALA Assist**.\n\n"
                f"Por favor, envíame el **número de cédula** del cliente a consultar o escribe un número de opción:\n"
                f"• Envía la **cédula** para consultar estado\n"
                f"• Marca **2** para finalizar el chat"
            )
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")
        
        # Si es una cédula, consultamos los créditos
        df_creditos = pd.read_csv(url_creditos)
        
        # Búsqueda flexible de columnas para evitar N/A
        col_cedula = next((c for c in df_creditos.columns if 'CEDULA' in c.upper() or 'CÉDULA' in c.upper()), None)
        col_cliente = next((c for c in df_creditos.columns if 'CLIENTE' in c.upper() or 'NOMBRE' in c.upper()), None)
        col_pagaduria = next((c for c in df_creditos.columns if 'PAGADURIA' in c.upper() or 'PAGADURÍA' in c.upper()), None)
        col_etapa = next((c for c in df_creditos.columns if 'ETAPA' in c.upper()), None)
        col_alertas = next((c for c in df_creditos.columns if 'ALERTA' in c.upper()), None)
        col_asesor = next((c for c in df_creditos.columns if 'ASESOR' in c.upper()), None)
        
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
        
        # Extracción segura de valores
        nombre_cliente = str(fila_datos.get(col_cliente, 'No registrado')).strip()
        pagaduria_val = str(fila_datos.get(col_pagaduria, 'No registrada')).strip()
        etapa_val = str(fila_datos.get(col_etapa, 'N/A')).strip()
        alertas_val = str(fila_datos.get(col_alertas, 'Ninguna')).strip()
        
        # Respuesta estructurada con guía de opciones
        texto_resumen = (
            f"📋 *Estado del Crédito - KALA*\n\n"
            f"👤 *Cliente:* {nombre_cliente}\n"
            f"🆔 *Cédula:* {mensaje_texto}\n"
            f"🏢 *Pagaduría:* {pagaduria_val}\n"
            f"📌 *Etapa Actual:* {etapa_val}\n"
            f"⚡ *Alertas:* {alertas_val}\n\n"
            f"👉 *Acciones disponibles:*\n"
            f"1️⃣ Presiona **1** para subsanar\n"
            f"2️⃣ Presiona **2** para finalizar chat\n\n"
            f"*(Asesor a cargo: {nombre_asesor})*"
        )
        
        xml_respuesta = f"<Response><Message>{texto_resumen}</Message></Response>"
        return Response(content=xml_respuesta, media_type="application/xml")

    except Exception as e:
        texto_respuesta = f"Ocurrió un evento en el servidor: {str(e)}"
        xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
        return Response(content=xml_respuesta, media_type="application/xml")

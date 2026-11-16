import os
import pandas as pd
from fastapi import FastAPI, Request, Response
from google import genai
from google.genai import types

app = FastAPI()

API_KEY = os.environ.get("GEMINI_API_KEY")
SHEET_ID = "19kkoRLxDnAGF96QUm7NBq9r2M2poQ09y_Ko_w72olNQ"

client = genai.Client(api_key=API_KEY)

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
        
        nombre_asesor = asesor_registrado.iloc[0]['Nombre_Asesor']
        
        # Si el usuario manda un saludo o texto que no es cédula, KALA saluda y guía
        if not mensaje_texto.isdigit():
            texto_respuesta = f"¡Hola, {nombre_asesor}! 🌟 Te doy la bienvenida a **KALA Assist**. Por favor, escríbeme el **número de cédula** del cliente que deseas consultar para verificar su estado y las alertas pendientes."
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")
        
        # Si es una cédula, consultamos los créditos
        df_creditos = pd.read_csv(url_creditos)
        col_cedula = [c for c in df_creditos.columns if 'CEDULA' in c.upper() or 'CÉDULA' in c.upper()][0]
        
        df_creditos['Cedula_Clean'] = pd.to_numeric(df_creditos[col_cedula], errors='coerce').fillna(0).astype(int)
        cedula_int = int(mensaje_texto)
        
        df_creditos['Asesor_Clean'] = df_creditos['Asesor'].astype(str).str.strip().str.upper()
        nombre_asesor_clean = str(nombre_asesor).strip().upper()
        
        resultado = df_creditos[
            (df_creditos['Asesor_Clean'] == nombre_asesor_clean) & 
            (df_creditos['Cedula_Clean'] == cedula_int)
        ]
        
        if resultado.empty:
            texto_respuesta = f"⚠️ Hola {nombre_asesor}, no se encontraron créditos asignados a tu nombre con la cédula {mensaje_texto}."
            xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
            return Response(content=xml_respuesta, media_type="application/xml")
        
        fila_datos = resultado.iloc[0]
        
        prompt_contexto = f"""
        El asesor {nombre_asesor} consultó el crédito con la cédula {mensaje_texto}.
        Datos del crédito:
        - Cliente: {fila_datos.get('Nombre_Cliente', 'N/A')}
        - Pagaduría: {fila_datos.get('Pagaduria', 'N/A')}
        - Etapa Actual: {fila_datos.get('Etapa', 'N/A')}
        - Alertas: {fila_datos.get('Alertas_Pendientes', 'Ninguna')}
        
        Genera una respuesta muy bien formateada para WhatsApp confirmando estos datos y dándole la opción de adjuntar soporte para subsanar.
        """
        
        system_instruction = "Eres KALA Assist, asistente de postventa para asesores KALA. Usa emojis y viñetas de WhatsApp."
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_contexto,
            config=types.GenerateContentConfig(system_instruction=system_instruction)
        )
        
        texto_respuesta = response.text
        xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
        return Response(content=xml_respuesta, media_type="application/xml")

    except Exception as e:
        texto_respuesta = f"Ocurrió un evento en el servidor: {str(e)}"
        xml_respuesta = f"<Response><Message>{texto_respuesta}</Message></Response>"
        return Response(content=xml_respuesta, media_type="application/xml")

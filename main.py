import os
import pandas as pd
from fastapi import FastAPI, Request
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
    data = await request.json()
    
    try:
        celular_remitente = data.get("sender", "")
        mensaje_texto = data.get("text", "").strip()
        
        df_creditos = pd.read_csv(url_creditos)
        df_asesores = pd.read_csv(url_asesores)
        
        col_cedula = [c for c in df_creditos.columns if 'CEDULA' in c.upper() or 'CÉDULA' in c.upper()][0]
        df_asesores['Telefono_WhatsApp'] = pd.to_numeric(df_asesores['Telefono_WhatsApp'], errors='coerce')
        
        asesor_registrado = df_asesores[df_asesores['Telefono_WhatsApp'] == pd.to_numeric(celular_remitente, errors='coerce')]
        
        if asesor_registrado.empty:
            return {"reply": "❌ Acceso denegado: Este número no está registrado como asesor autorizado en KALA."}
        
        nombre_asesor = asesor_registrado.iloc[0]['Nombre_Asesor']
        
        df_creditos['Cedula_Clean'] = pd.to_numeric(df_creditos[col_cedula], errors='coerce').fillna(0).astype(int)
        cedula_int = int(mensaje_texto) if mensaje_texto.isdigit() else 0
        
        df_creditos['Asesor_Clean'] = df_creditos['Asesor'].astype(str).str.strip().str.upper()
        nombre_asesor_clean = str(nombre_asesor).strip().upper()
        
        resultado = df_creditos[
            (df_creditos['Asesor_Clean'] == nombre_asesor_clean) & 
            (df_creditos['Cedula_Clean'] == cedula_int)
        ]
        
        if resultado.empty:
            return {"reply": f"⚠️ Hola {nombre_asesor}, no se encontraron créditos asignados a tu nombre con la cédula {mensaje_texto}."}
        
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
            model='gemini-3.8-flash',
            contents=prompt_contexto,
            config=types.GenerateContentConfig(system_instruction=system_instruction)
        )
        
        return {"reply": response.text}

    except Exception as e:
        return {"reply": f"Ocurrió un evento en el servidor: {str(e)}"}

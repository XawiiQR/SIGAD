from agente import MotorAnalisis


def ejecutar_prueba_outliers():
    """Fase 3 — Outliers: muestra los valores concretos detectados."""
    print("🚀 Inicializando Motor de Análisis para Fase 3 — Outliers...")
    motor = MotorAnalisis()
    columnas_a_evaluar = ["PM2.5", "PM10", "SO2"]

    try:
        resultado = motor.obtener_analisis_outliers_batch_fase3(columnas_a_evaluar)
        for columna, datos in resultado.items():
            if "error" in datos:
                print(f"\n⚠️ {columna}: {datos['error']}")
                continue
            print(f"\n📌 {columna}: {datos['outliers_count']} outliers")
            print(f"   Límites IQR: {datos['limites_iqr']}")
            for registro in datos["registros_outliers"]:
                print(f"   - Fila {registro['indice_fila']}: {registro['valor']}")

        print("\n" + "=" * 70)
        print("🤖 RECOMENDACIÓN DEL LLM:")
        print("=" * 70)
        print(motor.analizar_batch_outliers_fase3(columnas_a_evaluar))
    except Exception as error:
        print(f"❌ Ocurrió un error al ejecutar el análisis: {error}")
        print("Verifica que Flask esté activo en http://127.0.0.1:5000.")


if __name__ == "__main__":
    ejecutar_prueba_outliers()

import sweetviz as sv
import pandas as pd

df = pd.read_csv("Data/Data.csv")

# Genera el reporte automático
analisis = sv.analyze(df)

# Lo guarda en un HTML interactivo
analisis.show_html("reporte_sweetviz.html")
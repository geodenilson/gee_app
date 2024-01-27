import ee
import geemap
import streamlit as st
import streamlit_folium
from streamlit_folium import st_folium
import plotly.express as px 
import folium
import pandas as pd
import geopandas as gpd
from datetime import datetime
import shutil
import tempfile
from pathlib import Path
import fiona
import json


def main():
    st.title("Aplicativo Streamlit para Plotar GeoJSON")

    # Upload do arquivo GeoJSON
    uploaded_file = st.file_uploader("Escolha um arquivo GeoJSON", type=["geojson"])

    if uploaded_file is not None:
        # Carrega o GeoDataFrame a partir do arquivo GeoJSON
        gdf = gpd.read_file(uploaded_file)
        # ##convertendo de shp para to json
        shp_json = gdf.to_json()
        ##Carregando o arquivo json
        f_json = json.loads(shp_json)
        ##selecionando as features
        f_json = f_json['features']
        
        roi = ee.FeatureCollection(f_json)
                  
        m = geemap.Map(width=800)
        m.add_basemap('Esri.WorldImagery')
        m.addLayer(roi)
        m.centerObject(roi,10)
        m.to_streamlit()
    else:
        m=geemap.Map()
        d= m.user_rois.getInfo()
        roi = ee.FeatureCollection(d)
        m.addLayer(roi)
        m.centerObject(roi,10)
        st.write(roi)
        

if __name__ == "__main__":
    main()
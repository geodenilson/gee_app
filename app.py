import ee
import geemap
import geemap.foliumap as geemap
import streamlit as st
import streamlit_folium
from streamlit_folium import st_folium
import plotly.express as px 
import folium
import pandas as pd
import geopandas as gpd
from datetime import datetime
from pathlib import Path
import json


@st.cache_data
def ee_authenticate(token_name="EARTHENGINE_TOKEN"):
    geemap.ee_initialize(token_name=token_name)

# Configuração da página
st.set_page_config(layout="wide")
st.title('Aplicativo para seleção de imagens, cálculo de índices e download das imagens')
st.markdown(""" #### O APP foi desenvolvido para que o usuário possa carregar a região de interesse, definir o período e visualizar o NDVI, EVI e NDRE. A aplicação processa Datasets disponíveis no Google Earth Engine.
               
#### Para criar o arquivo **GeoJSON** use o site [geojson.io](https://geojson.io/#new&map=2/0/20).""")

# Inicializar o mapa com ROI como None
roi = None

# Upload do arquivo GeoJSON
st.sidebar.subheader("Carregue o Arquivo Geojson:")
uploaded_file = st.sidebar.file_uploader("Escolha um arquivo GeoJSON", type=["geojson"])

if uploaded_file is not None:
    # Carrega o GeoDataFrame a partir do arquivo GeoJSON
    gdf = gpd.read_file(uploaded_file)
    # ##convertendo de shp para to json
    shp_json = gdf.to_json()
    ##Carregando o arquivo json
    f_json = json.loads(shp_json)
    ##selecionando as features
    f_json = f_json['features']
    # Converte de GeoDataFrame para JSON
    # Necessário para autenticação do código via GEE
    st.sidebar.write("Arquivo GeoJSON carregado com sucesso!")
    # Carrega a FeatureCollection no Earth Engine
    roi = ee.FeatureCollection(f_json)

# Cria o mapa
m = geemap.Map(heigth=800)
point = ee.Geometry.Point(-45.259679, -17.871838)
m.centerObject(point,8)
m.setOptions("HYBRID")

 # Adicionar campos de datas iniciais e finais na barra lateral
start_date = st.sidebar.date_input("Selecione a data inicial", datetime(2024, 1, 1))
end_date = st.sidebar.date_input("Selecione a data final", datetime.now())
# Adicionar slider para definir o limite de nuvens
cloud_percentage_limit = st.sidebar.slider("Limite de percentual de nuvens", 0, 100, 15)

# Adiciona a ROI se ela existir
if roi is not None:
    
       
     # Função de nuvens, fator de escala e clip
    def maskCloudAndShadowsSR(image):
        cloudProb = image.select('MSK_CLDPRB');
        snowProb = image.select('MSK_SNWPRB');
        cloud = cloudProb.lt(5)
        snow = snowProb.lt(5)
        scl = image.select('SCL')
        shadow = scl.eq(3)  # 3 = cloud shadow
        cirrus = scl.eq(10)  # 10 = cirrus
        # Probabilidade de nuvem inferior a 5% ou classificação de sombra de nuvem
        mask = (cloud.And(snow)).And(cirrus.neq(1)).And(shadow.neq(1));
        return image.updateMask(mask).divide(10000)\
            .select("B.*")\
            .clip(roi)\
            .copyProperties(image, image.propertyNames())

    # Cálculo do índice
    def indice(image):
        ndvi = image.normalizedDifference(['B8','B4']).rename('ndvi')
        ndre = image.normalizedDifference(['B8','B5']).rename('ndre') 
        evi = image.expression('2.5 * ((N - R) / (N + (6 * R) - (7.5 * B) + 1))',
         { #//Huete 2002
        'N': image.select('B8'), 
        'R': image.select('B4'), 
        'B': image.select('B2')}).rename('evi'); 
        return image.addBands([ndvi, ndre,evi]).set({'data': image.date().format('yyyy-MM-dd')})

       
    # Coleção de imagens 
    collection = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")\
                    .filterBounds(roi)\
                    .filter(ee.Filter.date(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))\
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_percentage_limit))\
                    .map(maskCloudAndShadowsSR)\
                    .map(indice)
    
    # Criar a tabela usando os dados da coleção filtrada
    data_table = pd.DataFrame({
        "Data": collection.aggregate_array("data").getInfo(),
        "Percentual de Nuvens": collection.aggregate_array("CLOUDY_PIXEL_PERCENTAGE").getInfo(),
        "ID": collection.aggregate_array("system:id").getInfo()
    })
    
    # Exibir informações no Streamlit
    expander = st.expander('Clique para saber mais')
    expander.write(
        f"""As imagens disponíveis que atendem os filtros estão no quadro abaixo.
        """
    )
    ##Data Frame
    expander.write(data_table)
    
    # Criar lista de botões para cada data
    selected_dates = st.multiselect("Selecione as datas", data_table["Data"].tolist())
    
    # Filtrar a coleção com base nas datas selecionadas
    selected_collection = collection.filter(ee.Filter.inList('data', selected_dates))
    
   # Criar checkboxes para escolher os índices
    st.sidebar.subheader("Escolha os índices para visualização:")
    show_ndvi = st.sidebar.checkbox("NDVI", value=False)
    show_ndre = st.sidebar.checkbox("NDRE", value=False)
    show_evi = st.sidebar.checkbox("EVI", value=False)

    # Adicionar a ROI e a imagem ao mapa
    m = geemap.Map(heigth=800)
    m.centerObject(roi, 13)
    m.setOptions("HYBRID")
    m.addLayer(roi, {}, 'Região de Interesse')
    m.addLayer(selected_collection, {'bands':['B12', 'B8', 'B4'], 'min':0.1, 'max':0.4},str(f'Img {selected_dates}'))
    
    # Adicionar camadas de acordo com as escolhas
    if show_ndvi:
        m.addLayer(selected_collection.select('ndvi'), {'min': -1, 'max': 1, 'palette': ['red', 'yellow', 'green']}, 'NDVI')
    if show_ndre:
        m.addLayer(selected_collection.select('ndre'), {'min': -1, 'max': 1, 'palette': ['red', 'yellow', 'green']}, 'NDRE')
    if show_evi:
        m.addLayer(selected_collection.select('evi'), {'min': -1, 'max': 1, 'palette': ['red', 'yellow', 'green']}, 'EVI')
        
    st.divider()
    # Função para aplicar a redução por regiões para toda a coleção usando map
    def reduce_region_for_collection(img):
        # Obtém a data da imagem
        date = img.date().format('yyyy-MM-dd')

        # Aplica a redução por regiões para a imagem
        stats = img.reduceRegions(
            collection=roi,
            reducer=ee.Reducer.mean(),
            scale=10  # Defina a escala apropriada para sua aplicação
        )

        # Adiciona a data à propriedade 'data'
        stats = stats.map(lambda f: f.set('data', date))

        return stats

    # Aplica a redução por regiões para toda a coleção usando map
    stats_collection = collection.select(['ndre', 'ndvi', 'evi']).map(reduce_region_for_collection)

    # Converte para df
    df = geemap.ee_to_df(stats_collection.flatten())

    # Adiciona a data como coluna no formato datetime
    df['datetime'] = pd.to_datetime(df['data'], format='%Y-%m-%d')

    # Plotar gráfico usando Plotly Express
    fig = px.line(df, x='datetime', y=['ndre', 'ndvi', 'evi'], title='Série Temporal de Índices', 
                labels={'value': 'Índice', 'variable': 'Tipo de Índice'},
                line_dash='variable', line_group='variable')

    ##criando coluna 1 e 2 
    col1, col2 = st.columns([0.6,0.4])

    # Exibir o gráfico no Streamlit
    with col1:
        st.plotly_chart(fig)

    with col2:
        # Exibir a tabela
        st.dataframe(df.style.set_table_styles([{'selector': 'table', 'props': [('width', '400px')]}]))

    # Adicionar botão de download
    if st.button("Download da Imagem"):
        # Adicionar aqui a lógica para o download da imagem
        # Você pode usar a biblioteca geemap para exportar a imagem

     # Por exemplo:
        import os
        # Por exemplo:
        out_dir = os.path.join(os.path.expanduser('~'), 'Downloads')

        # Exportar a imagem B1-B8
        filename_b1_b8 = os.path.join(out_dir, 'image_b1_b8.tif')
        geemap.ee_export_image(selected_collection.select('B.*').first(), filename_b1_b8, scale=10, crs='EPSG:4674', region=roi.geometry())

        # Exportar a imagem NDVI, NDRE, EVI
        filename_ndvi_ndre_evi = os.path.join(out_dir, 'image_ndvi_ndre_evi.tif')
        geemap.ee_export_image(selected_collection.select(['ndvi', 'ndre', 'evi']).first(), filename_ndvi_ndre_evi, scale=10, crs='EPSG:4674', region=roi.geometry())

        # Verificar se os arquivos existem antes de verificar os tamanhos
        if os.path.exists(filename_b1_b8) and os.path.exists(filename_ndvi_ndre_evi):
            # Tamanhos dos arquivos em MB
            file_size_b1_b8 = os.path.getsize(filename_b1_b8) / (1024 * 1024)
            file_size_ndvi_ndre_evi = os.path.getsize(filename_ndvi_ndre_evi) / (1024 * 1024)

            # Limite de tamanho (40 MB)
            size_limit = 40

            if file_size_b1_b8 > size_limit or file_size_ndvi_ndre_evi > size_limit:
                # Remover os arquivos grandes
                if file_size_b1_b8 > size_limit:
                    os.remove(filename_b1_b8)
                if file_size_ndvi_ndre_evi > size_limit:
                    os.remove(filename_ndvi_ndre_evi)

                # Exibir mensagem de erro
                st.sidebar.error('Imagens não foram exportadas, tamanho maior que 40 MB.')
            else:
                # Exibir mensagem de sucesso e adicionar os hyperlinks para os arquivos exportados
                st.sidebar.success("As imagens foram exportadas com sucesso para o seu sistema de arquivos local.")
        else:
            # Exibir mensagem de erro se os arquivos não existirem
            st.sidebar.error('Erro durante a exportação. Os arquivos não foram criados.')

# Exibe o mapa no Streamlit
m.to_streamlit()
st.sidebar.markdown('Desenvolvido por [Christhian Cunha](https://www.linkedin.com/in/christhian-santana-cunha/)')




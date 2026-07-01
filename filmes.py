import time
import json
import queue
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

# Configurações de Concorrência
NUM_THREADS = 4

def create_driver():
    """Cria e retorna uma instância do Chrome WebDriver em modo headless otimizada."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false") # Desabilita imagens
    chrome_options.add_argument("--lang=pt-BR")
    
    # Define a estratégia de carregamento rápido (eager = DOM carregado, ignora imagens/CSS externos)
    chrome_options.page_load_strategy = 'eager'
    
    # Define preferências experimentais de idioma e desativa imagens
    prefs = {
        "intl.accept_languages": "pt-BR,pt",
        "profile.managed_default_content_settings.images": 2
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    # Define o timeout de carregamento da página para 8 segundos para evitar travamentos
    driver.set_page_load_timeout(8)
    return driver

def get_top_250_list():
    """Obtém a lista dos 250 melhores filmes do IMDb."""
    print("Iniciando o navegador para buscar a lista do Top 250...")
    driver = create_driver()
    try:
        url = "https://www.imdb.com/chart/top/"
        driver.get(url)
        time.sleep(3)  # Aguarda o carregamento dos elementos
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        json_data = soup.find('script', type='application/ld+json')
        
        if not json_data:
            raise Exception("Não foi possível encontrar a tag JSON-LD no Top 250.")
            
        data = json.loads(json_data.string)
        movies = []
        for rank, item in enumerate(data.get('itemListElement', []), 1):
            movie_info = item.get('item', {})
            movies.append({
                'rank': rank,
                'nome': movie_info.get('alternateName') or movie_info.get('name'),
                'url': movie_info.get('url')
            })
        return movies
    finally:
        driver.quit()

# Fila para compartilhar os WebDrivers entre as threads de forma segura
driver_queue = queue.Queue()

def worker_scrape_details(movie):
    """Função executada por thread para raspar os detalhes de um filme."""
    url = movie['url']
    driver = driver_queue.get()
    
    release_date = "N/A"
    country_of_origin = "N/A"
    
    try:
        # Tenta carregar a página (até 2 tentativas)
        for attempt in range(2):
            try:
                try:
                    driver.get(url)
                except TimeoutException:
                    # Timeout ocorreu, mas o HTML parcial/DOM costuma já estar carregado.
                    # Prosseguimos para tentar ler as tags.
                    pass
                
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Extrai Data de Lançamento
                release_date_el = soup.find(attrs={"data-testid": "title-details-releasedate"})
                if release_date_el:
                    parts = [p.strip() for p in release_date_el.get_text(separator='|').split('|') if p.strip()]
                    if len(parts) > 1:
                        release_date = parts[1]
                        
                # Extrai País de Origem
                country_el = soup.find(attrs={"data-testid": "title-details-origin"})
                if country_el:
                    parts = [p.strip() for p in country_el.get_text(separator='|').split('|') if p.strip()]
                    if len(parts) > 1:
                        country_of_origin = ", ".join(parts[1:])
                        
                # Só consideramos sucesso se conseguimos extrair as informações básicas
                # ou se for a segunda tentativa.
                if release_date != "N/A" or country_of_origin != "N/A" or attempt == 1:
                    break
            except Exception as e:
                if attempt == 1:
                    print(f"\n[Erro] Falha ao obter dados de {movie['nome']}: {e}")
                time.sleep(1)
    finally:
        driver_queue.put(driver)
        
    return {
        'Rank': movie['rank'],
        'Nome do Filme': movie['nome'],
        'Data de Lançamento': release_date,
        'País de Origem': country_of_origin,
        'Link': url
    }

def main():
    start_time = time.time()
    
    # 1. Obter lista inicial
    try:
        movies = get_top_250_list()
        print(f"Sucesso: {len(movies)} filmes encontrados no Top 250.")
    except Exception as e:
        print(f"Erro ao obter a lista inicial: {e}")
        sys.exit(1)
        
    # 2. Inicializar Pool de WebDrivers
    print(f"Inicializando {NUM_THREADS} navegadores em segundo plano para raspagem rápida...")
    drivers = []
    for i in range(NUM_THREADS):
        drivers.append(create_driver())
        driver_queue.put(drivers[-1])
        
    # 3. Raspagem concorrente
    results = []
    print("Buscando detalhes de cada filme (data de lançamento e país de origem)...")
    
    try:
        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            future_to_movie = {executor.submit(worker_scrape_details, m): m for m in movies}
            
            completed = 0
            for future in as_completed(future_to_movie):
                completed += 1
                result = future.result()
                results.append(result)
                
                # Exibe o progresso
                percent = (completed / len(movies)) * 100
                sys.stdout.write(f"\rProgresso: {completed}/{len(movies)} ({percent:.1f}%) concluído...")
                sys.stdout.flush()
    finally:
        # Fechar todos os WebDrivers
        print("\nFechando navegadores...")
        for driver in drivers:
            try:
                driver.quit()
            except:
                pass

    # Ordenar os resultados pelo Rank original (posição no Top 250)
    results = sorted(results, key=lambda x: x['Rank'])

    # 4. Criar planilha Excel e CSV
    print("Salvando resultados nas planilhas...")
    df = pd.DataFrame(results)
    
    # Salvar XLSX (Excel)
    excel_file = "melhores_250_filmes.xlsx"
    df.to_excel(excel_file, index=False)
    print(f"Planilha Excel criada com sucesso: {excel_file}")
    
    # Salvar CSV como alternativa
    csv_file = "melhores_250_filmes.csv"
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"Planilha CSV criada com sucesso: {csv_file}")
    
    duration = time.time() - start_time
    print(f"Concluído em {duration:.1f} segundos!")

if __name__ == "__main__":
    main()

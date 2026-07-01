import os
import re
import json
import webbrowser
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox

# --- CONFIGURAÇÃO DE CORES (Estilo Netflix Red / Rose Cream) ---
COLOR_BG = "#8b0906"          # Fundo Vermelho Escuro
COLOR_CARD = "#fcebeb"        # Fundo dos Cards (Rosa Claro / Creme)
COLOR_TEXT = "#4a0202"        # Texto Principal (Burgundy Escuro)
COLOR_TEXT_MUTED = "#802020"  # Texto Secundário
COLOR_ACCENT = "#e50914"      # Vermelho Netflix para detalhes/botões
COLOR_WHITE = "#ffffff"       # Branco

class ScrollableFrame(tk.Frame):
    """Container rolável para abrigar a lista de filmes com checkboxes."""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, bg=COLOR_CARD)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=COLOR_CARD)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Ajusta a largura interna conforme o canvas muda de tamanho
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Eventos para ativar scroll com o scroll do mouse
        self.scrollable_frame.bind('<Enter>', self._bind_mousewheel)
        self.scrollable_frame.bind('<Leave>', self._unbind_mousewheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class DashboardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IMDb Top 250 - Dashboard Interativo de Filmes")
        self.geometry("1200x750")
        self.configure(bg=COLOR_BG)
        
        self.csv_path = "melhores_250_filmes.csv"
        self.vistos_path = "filmes_vistos.json"
        
        self.load_data()
        self.load_vistos()
        
        self.selected_movie = None
        self.movie_widgets = []
        self.checkbox_vars = {}
        
        self.init_ui()
        self.update_statistics()

    def load_data(self):
        """Carrega os dados do CSV de filmes."""
        if not os.path.exists(self.csv_path):
            messagebox.showerror(
                "Arquivo Não Encontrado", 
                f"Não foi possível localizar o arquivo '{self.csv_path}'. Por favor, execute o script 'filmes.py' primeiro para raspar os dados."
            )
            self.df = pd.DataFrame(columns=['Rank', 'Nome do Filme', 'Data de Lançamento', 'País de Origem', 'Link'])
        else:
            self.df = pd.read_csv(self.csv_path)
            # Tratar possíveis nulos
            self.df['Nome do Filme'] = self.df['Nome do Filme'].fillna("Sem Título")
            self.df['Data de Lançamento'] = self.df['Data de Lançamento'].fillna("N/A")
            self.df['País de Origem'] = self.df['País de Origem'].fillna("N/A")
            self.df['Link'] = self.df['Link'].fillna("")

    def load_vistos(self):
        """Carrega o arquivo JSON com os filmes já assistidos."""
        if os.path.exists(self.vistos_path):
            try:
                with open(self.vistos_path, 'r', encoding='utf-8') as f:
                    self.vistos = json.load(f)
            except Exception:
                self.vistos = {}
        else:
            self.vistos = {}

    def save_vistos(self):
        """Salva o progresso dos filmes assistidos no JSON."""
        try:
            with open(self.vistos_path, 'w', encoding='utf-8') as f:
                json.dump(self.vistos, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print("Erro ao salvar vistos:", e)

    def init_ui(self):
        # Estilo para os componentes ttk
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TScrollbar", gripcount=0, background=COLOR_CARD, troughcolor=COLOR_CARD, bordercolor=COLOR_CARD)
        
        # Grid layout principal
        self.columnconfigure(0, weight=1) # Coluna da Esquerda (Lista & Busca)
        self.columnconfigure(1, weight=2) # Coluna da Direita (Métricas e Gráficos)
        self.rowconfigure(0, weight=1)

        # =========================================================================
        # PAINEL DA ESQUERDA: Busca & Lista de Filmes
        # =========================================================================
        left_panel = tk.Frame(self, bg=COLOR_BG, padx=15, pady=15)
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1) # Permite a lista expandir verticalmente

        # CARD DE BUSCA & TÍTULO DO APP
        search_card = tk.Frame(left_panel, bg=COLOR_CARD, padx=15, pady=15, bd=0)
        search_card.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        # Logo tipo Netflix
        app_title_lbl = tk.Label(
            search_card, 
            text="NETFLIX STYLE\nIMDb Top 250", 
            font=("Helvetica", 18, "bold"), 
            fg=COLOR_ACCENT, 
            bg=COLOR_CARD,
            justify="center"
        )
        app_title_lbl.pack(pady=(0, 10))

        search_label = tk.Label(
            search_card, 
            text="Buscar Filme por Nome:", 
            font=("Helvetica", 10, "bold"), 
            fg=COLOR_TEXT, 
            bg=COLOR_CARD
        )
        search_label.pack(anchor="w")

        # Campo de Busca
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filter_movies)
        search_entry = tk.Entry(
            search_card, 
            textvariable=self.search_var, 
            font=("Helvetica", 12), 
            bg=COLOR_WHITE, 
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT,
            bd=1,
            relief="solid"
        )
        search_entry.pack(fill="x", pady=(5, 5))
        
        # Dica rápida
        tip_lbl = tk.Label(
            search_card, 
            text="Clique em um filme para ver detalhes e o link.", 
            font=("Helvetica", 8, "italic"), 
            fg=COLOR_TEXT_MUTED, 
            bg=COLOR_CARD
        )
        tip_lbl.pack(anchor="w")

        # LISTA DE FILMES COM CHECKBOXES
        list_card = tk.Frame(left_panel, bg=COLOR_CARD, padx=10, pady=10)
        list_card.grid(row=1, column=0, sticky="nsew")
        list_card.rowconfigure(1, weight=1)
        list_card.columnconfigure(0, weight=1)

        list_header_lbl = tk.Label(
            list_card, 
            text="Lista de Filmes", 
            font=("Helvetica", 12, "bold"), 
            fg=COLOR_TEXT, 
            bg=COLOR_CARD
        )
        list_header_lbl.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.scroll_frame = ScrollableFrame(list_card)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")

        # =========================================================================
        # PAINEL DA DIREITA: Métricas (KPIs), Gráficos e Detalhes
        # =========================================================================
        right_panel = tk.Frame(self, bg=COLOR_BG, padx=15, pady=15)
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1) # Linha dos gráficos expande
        right_panel.rowconfigure(2, weight=1) # Linha dos detalhes expande

        # 1. LINHA SUPERIOR: METRICAS (KPI CARDS)
        kpis_frame = tk.Frame(right_panel, bg=COLOR_BG)
        kpis_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        kpis_frame.columnconfigure(0, weight=1)
        kpis_frame.columnconfigure(1, weight=1)
        kpis_frame.columnconfigure(2, weight=1)

        # Card KPI 1: Total Filmes
        kpi1_card = tk.Frame(kpis_frame, bg=COLOR_CARD, padx=10, pady=10)
        kpi1_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        tk.Label(kpi1_card, text="Total de Filmes", font=("Helvetica", 10, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")
        self.kpi_total_val = tk.Label(kpi1_card, text="250", font=("Helvetica", 20, "bold"), fg=COLOR_TEXT, bg=COLOR_CARD)
        self.kpi_total_val.pack(anchor="w", pady=(5, 0))

        # Card KPI 2: Assistidos
        kpi2_card = tk.Frame(kpis_frame, bg=COLOR_CARD, padx=10, pady=10)
        kpi2_card.grid(row=0, column=1, padx=(0, 10), sticky="nsew")
        tk.Label(kpi2_card, text="Filmes Assistidos", font=("Helvetica", 10, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")
        self.kpi_seen_val = tk.Label(kpi2_card, text="0", font=("Helvetica", 20, "bold"), fg=COLOR_ACCENT, bg=COLOR_CARD)
        self.kpi_seen_val.pack(anchor="w", pady=(5, 0))

        # Card KPI 3: Porcentagem
        kpi3_card = tk.Frame(kpis_frame, bg=COLOR_CARD, padx=10, pady=10)
        kpi3_card.grid(row=0, column=2, sticky="nsew")
        tk.Label(kpi3_card, text="Progresso Concluído", font=("Helvetica", 10, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")
        self.kpi_percent_val = tk.Label(kpi3_card, text="0.0%", font=("Helvetica", 20, "bold"), fg=COLOR_TEXT, bg=COLOR_CARD)
        self.kpi_percent_val.pack(anchor="w", pady=(5, 0))

        # 2. LINHA DO MEIO: GRÁFICOS (Décadas & Países)
        charts_frame = tk.Frame(right_panel, bg=COLOR_BG)
        charts_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        charts_frame.columnconfigure(0, weight=1)
        charts_frame.columnconfigure(1, weight=1)
        charts_frame.rowconfigure(0, weight=1)

        # Card do Gráfico de Rosca (Décadas)
        self.donut_card = tk.Frame(charts_frame, bg=COLOR_CARD, padx=15, pady=15)
        self.donut_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        tk.Label(self.donut_card, text="Distribuição por Décadas", font=("Helvetica", 11, "bold"), fg=COLOR_TEXT, bg=COLOR_CARD).pack(anchor="w")
        
        self.donut_canvas = tk.Canvas(self.donut_card, width=280, height=220, bg=COLOR_CARD, bd=0, highlightthickness=0)
        self.donut_canvas.pack(fill="both", expand=True, pady=(5, 0))

        # Card do Gráfico de Barras (Países)
        self.bar_card = tk.Frame(charts_frame, bg=COLOR_CARD, padx=15, pady=15)
        self.bar_card.grid(row=0, column=1, sticky="nsew")
        tk.Label(self.bar_card, text="Top 5 Países de Origem", font=("Helvetica", 11, "bold"), fg=COLOR_TEXT, bg=COLOR_CARD).pack(anchor="w")
        
        self.bar_canvas = tk.Canvas(self.bar_card, width=280, height=220, bg=COLOR_CARD, bd=0, highlightthickness=0)
        self.bar_canvas.pack(fill="both", expand=True, pady=(5, 0))

        # 3. LINHA INFERIOR: DETALHES DO FILME SELECIONADO
        detail_card = tk.Frame(right_panel, bg=COLOR_CARD, padx=20, pady=20)
        detail_card.grid(row=2, column=0, sticky="nsew")
        detail_card.columnconfigure(0, weight=1)

        tk.Label(detail_card, text="Ficha Técnica & Detalhes", font=("Helvetica", 12, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")
        
        # Widgets de informações do filme
        self.detail_title_lbl = tk.Label(detail_card, text="Selecione um filme na lista para ver os detalhes", font=("Helvetica", 14, "bold"), fg=COLOR_TEXT, bg=COLOR_CARD, wraplength=550, justify="left")
        self.detail_title_lbl.pack(anchor="w", pady=(10, 5))

        self.detail_rank_lbl = tk.Label(detail_card, text="Posição no Rank: -", font=("Helvetica", 10), fg=COLOR_TEXT, bg=COLOR_CARD)
        self.detail_rank_lbl.pack(anchor="w", pady=2)

        self.detail_date_lbl = tk.Label(detail_card, text="Data de Lançamento: -", font=("Helvetica", 10), fg=COLOR_TEXT, bg=COLOR_CARD)
        self.detail_date_lbl.pack(anchor="w", pady=2)

        self.detail_country_lbl = tk.Label(detail_card, text="País de Origem: -", font=("Helvetica", 10), fg=COLOR_TEXT, bg=COLOR_CARD)
        self.detail_country_lbl.pack(anchor="w", pady=2)

        # Botão para abrir no IMDb
        self.imdb_btn = tk.Button(
            detail_card, 
            text="Ver no IMDb (Navegador) ➔", 
            font=("Helvetica", 10, "bold"), 
            bg=COLOR_ACCENT, 
            fg=COLOR_WHITE, 
            activebackground="#b20710", 
            activeforeground=COLOR_WHITE,
            bd=0, 
            padx=15, 
            pady=8,
            cursor="hand2",
            state="disabled",
            command=self.open_imdb_link
        )
        self.imdb_btn.pack(anchor="w", pady=(15, 0))

        # Renderiza a lista de filmes inicial
        self.populate_movie_list(self.df)
        self.draw_charts()

    def populate_movie_list(self, df_to_show):
        """Popula o frame rolável com a lista de filmes."""
        # Limpar widgets antigos
        for widget in self.movie_widgets:
            widget.destroy()
        self.movie_widgets.clear()

        # Cria linha por linha para os filmes
        for _, row in df_to_show.iterrows():
            rank = row['Rank']
            name = row['Nome do Filme']
            
            # Container do item do filme
            item_frame = tk.Frame(self.scroll_frame.scrollable_frame, bg=COLOR_CARD, cursor="hand2")
            item_frame.pack(fill="x", ipady=2, pady=1)
            self.movie_widgets.append(item_frame)

            # Checkbox para marcar como visto
            var = tk.BooleanVar(value=(str(rank) in self.vistos or name in self.vistos))
            self.checkbox_vars[rank] = var
            
            # Função para atualizar o status ao clicar no checkbox
            cb = tk.Checkbutton(
                item_frame, 
                variable=var, 
                bg=COLOR_CARD, 
                activebackground=COLOR_CARD,
                selectcolor=COLOR_WHITE,
                command=lambda r=rank, n=name, v=var: self.toggle_seen(r, n, v.get())
            )
            cb.pack(side="left", padx=(5, 5))

            # Texto do Filme (Rank - Nome)
            lbl_text = f"{rank}. {name}"
            lbl = tk.Label(
                item_frame, 
                text=lbl_text, 
                font=("Helvetica", 9, "bold" if self.selected_movie is not None and self.selected_movie['Rank'] == rank else "normal"), 
                fg=COLOR_TEXT, 
                bg=COLOR_CARD, 
                anchor="w",
                justify="left",
                wraplength=280
            )
            lbl.pack(side="left", fill="x", expand=True)

            # Eventos de clique para selecionar o filme e mudar o background no hover
            for widget in (item_frame, lbl):
                widget.bind("<Button-1>", lambda event, r=row: self.select_movie(r))
                widget.bind("<Enter>", lambda event, f=item_frame: f.configure(bg="#f2dada"))
                widget.bind("<Leave>", lambda event, f=item_frame: f.configure(bg=COLOR_CARD))

    def filter_movies(self, *args):
        """Filtra a lista de filmes com base no texto do campo de busca."""
        query = self.search_var.get().lower().strip()
        if not query:
            self.populate_movie_list(self.df)
        else:
            filtered_df = self.df[self.df['Nome do Filme'].str.lower().str.contains(query, na=False)]
            self.populate_movie_list(filtered_df)

    def select_movie(self, row):
        """Seleciona um filme e carrega suas informações na ficha técnica."""
        self.selected_movie = row
        
        # Atualizar a Ficha Técnica
        self.detail_title_lbl.configure(text=row['Nome do Filme'])
        self.detail_rank_lbl.configure(text=f"Posição no Rank: {row['Rank']}º Lugar")
        self.detail_date_lbl.configure(text=f"Data de Lançamento: {row['Data de Lançamento']}")
        self.detail_country_lbl.configure(text=f"País de Origem: {row['País de Origem']}")
        
        if row['Link']:
            self.imdb_btn.configure(state="normal")
        else:
            self.imdb_btn.configure(state="disabled")

        # Refresca o estilo da lista para destacar o selecionado
        query = self.search_var.get().lower().strip()
        df_to_use = self.df if not query else self.df[self.df['Nome do Filme'].str.lower().str.contains(query, na=False)]
        self.populate_movie_list(df_to_use)

    def open_imdb_link(self):
        """Abre o link do IMDb do filme selecionado no navegador."""
        if self.selected_movie and self.selected_movie['Link']:
            webbrowser.open(self.selected_movie['Link'])

    def toggle_seen(self, rank, name, is_checked):
        """Alterna o estado de assistido do filme e atualiza os dados/estatísticas."""
        if is_checked:
            self.vistos[str(rank)] = name
        else:
            self.vistos.pop(str(rank), None)
            self.vistos.pop(name, None) # Backup por nome
            
        self.save_vistos()
        self.update_statistics()

    def update_statistics(self):
        """Atualiza os indicadores estatísticos KPI."""
        total = len(self.df)
        seen = len(self.vistos)
        percent = (seen / total * 100) if total > 0 else 0
        
        self.kpi_total_val.configure(text=str(total))
        self.kpi_seen_val.configure(text=f"{seen} / {total}")
        self.kpi_percent_val.configure(text=f"{percent:.1f}%")

    def draw_charts(self):
        """Desenha os gráficos estatísticos de rosca e barras usando Tkinter Canvas."""
        # --- 1. GRÁFICO DE ROSCA (DÉCADAS) ---
        self.donut_canvas.delete("all")
        
        # Extrair anos dos lançamentos
        years = []
        for d in self.df['Data de Lançamento']:
            match = re.search(r'\b(19\d{2}|20\d{2})\b', str(d))
            if match:
                years.append(int(match.group(0)))
        
        decades = {}
        for y in years:
            dec = f"{(y // 10) * 10}s"
            decades[dec] = decades.get(dec, 0) + 1
            
        # Ordenar e agrupar antigas se necessário
        sorted_decades = sorted(decades.items())
        
        if sorted_decades:
            # Desenha o Donut Chart
            total_elements = sum(decades.values())
            start_ang = 0
            
            # Paleta de tons vermelhos e rosas
            colors = ["#e50914", "#ff5c5c", "#b20710", "#ff9e9e", "#8b0906", "#ffc2c2", "#4a0202", "#f78383"]
            
            cx, cy, r = 100, 110, 80
            legend_y = 30
            
            for idx, (decade, count) in enumerate(sorted_decades):
                extent_ang = (count / total_elements) * 360
                color = colors[idx % len(colors)]
                
                # Fila
                self.donut_canvas.create_arc(
                    cx - r, cy - r, cx + r, cy + r,
                    start=start_ang, extent=extent_ang,
                    fill=color, outline=COLOR_CARD, width=1
                )
                
                # Legenda
                pct = (count / total_elements) * 100
                self.donut_canvas.create_rectangle(200, legend_y, 212, legend_y + 12, fill=color, outline="")
                self.donut_canvas.create_text(220, legend_y + 6, text=f"{decade}: {pct:.1f}%", anchor="w", font=("Helvetica", 8, "bold"), fill=COLOR_TEXT)
                legend_y += 20
                
                start_ang += extent_ang
                
            # Circulo central (cria o efeito de rosca/donut)
            r_inner = 45
            self.donut_canvas.create_oval(
                cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner,
                fill=COLOR_CARD, outline=COLOR_CARD
            )
            # Texto no meio
            self.donut_canvas.create_text(cx, cy, text=f"{total_elements}\nFilmes", font=("Helvetica", 10, "bold"), fill=COLOR_TEXT, justify="center")

        # --- 2. GRÁFICO DE BARRAS (PAÍSES) ---
        self.bar_canvas.delete("all")
        
        # Extrair e contar países
        countries = {}
        for c_str in self.df['País de Origem']:
            if pd.isna(c_str) or c_str == "N/A":
                continue
            # Separar por vírgula no caso de múltiplos
            parts = [p.strip() for p in c_str.split(',')]
            for p in parts:
                countries[p] = countries.get(p, 0) + 1
                
        # Top 5 países
        top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:5]
        
        if top_countries:
            max_val = max(c[1] for c in top_countries)
            canvas_h = 160
            x_start = 40
            x_width = 38
            x_gap = 14
            
            for idx, (country, val) in enumerate(top_countries):
                # Altura da barra proporcional
                bar_h = (val / max_val) * canvas_h if max_val > 0 else 0
                x1 = x_start + idx * (x_width + x_gap)
                y1 = 180 - bar_h
                x2 = x1 + x_width
                y2 = 180
                
                # Desenha a barra
                self.bar_canvas.create_rectangle(x1, y1, x2, y2, fill=COLOR_ACCENT, outline="")
                
                # Valor acima da barra
                self.bar_canvas.create_text(x1 + x_width/2, y1 - 8, text=str(val), font=("Helvetica", 8, "bold"), fill=COLOR_TEXT)
                
                # Nome do país rotacionado ou cortado
                short_name = country
                if len(short_name) > 8:
                    short_name = short_name[:7] + "."
                    
                self.bar_canvas.create_text(
                    x1 + x_width/2, 195, 
                    text=short_name, 
                    font=("Helvetica", 8, "bold"), 
                    fill=COLOR_TEXT,
                    justify="center"
                )

if __name__ == "__main__":
    app = DashboardApp()
    app.mainloop()

import tkinter as tk
from tkinter import ttk, Menu, messagebox
import time
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import matplotlib.pyplot as plt
from collections import deque

# Definição das classes de elementos estruturais
class TipoApoio(Enum):
    PINO = "Pino"
    ROLETE = "Rolete"
    ENGASTE = "Engaste"

class PosicaoApoio(Enum):
    BASE = "Base"
    TOPO = "Topo"

@dataclass
class ElementoEstrutural:
    id: int
    posicao_x: float
    descricao: str
    
@dataclass
class Apoio(ElementoEstrutural):
    tipo: TipoApoio
    posicao_vertical: PosicaoApoio = PosicaoApoio.BASE
    
@dataclass
class CargaConcentrada(ElementoEstrutural):
    valor: float
    direcao: str
    
@dataclass
class CargaDistribuida(ElementoEstrutural):
    valor_inicial: float
    valor_final: float
    posicao_final_x: float
    
@dataclass
class Momento(ElementoEstrutural):
    valor: float
    sentido: str

class Historico:
    """Gerencia o histórico de ações para desfazer/refazer"""
    def __init__(self, max_historico=50):
        self.undo_stack = deque(maxlen=max_historico)
        self.redo_stack = deque(maxlen=max_historico)
    
    def adicionar_acao(self, acao):
        self.undo_stack.append(acao)
        self.redo_stack.clear()
    
    def desfazer(self):
        if self.undo_stack:
            acao = self.undo_stack.pop()
            self.redo_stack.append(acao)
            return acao
        return None
    
    def refazer(self):
        if self.redo_stack:
            acao = self.redo_stack.pop()
            self.undo_stack.append(acao)
            return acao
        return None
    
    def pode_desfazer(self):
        return len(self.undo_stack) > 0
    
    def pode_refazer(self):
        return len(self.redo_stack) > 0
    
    def limpar(self):
        self.undo_stack.clear()
        self.redo_stack.clear()

class Viga:
    def __init__(self, comprimento=10.0):
        self.comprimento = comprimento
        self.elementos: List[ElementoEstrutural] = []
        self.proximo_id = 1
        self.criada = False
        
    def criar_viga(self, comprimento):
        self.comprimento = comprimento
        self.criada = True
        
    def adicionar_elemento(self, elemento: ElementoEstrutural):
        elemento.id = self.proximo_id
        self.elementos.append(elemento)
        self.proximo_id += 1
        
    def remover_elemento(self, id: int):
        self.elementos = [e for e in self.elementos if e.id != id]
        
    def editar_elemento(self, id: int, **kwargs):
        for elemento in self.elementos:
            if elemento.id == id:
                for key, value in kwargs.items():
                    if hasattr(elemento, key):
                        setattr(elemento, key, value)
                return True
        return False
    
    def obter_elementos_por_tipo(self, tipo_classe):
        return [e for e in self.elementos if isinstance(e, tipo_classe)]
    
    def limpar_tudo(self):
        self.elementos.clear()
        self.proximo_id = 1
    
    def obter_estado(self):
        return {
            'comprimento': self.comprimento,
            'elementos': [elem.__class__(**{k: v for k, v in elem.__dict__.items()}) 
                         for elem in self.elementos],
            'proximo_id': self.proximo_id,
            'criada': self.criada
        }
    
    def restaurar_estado(self, estado):
        self.comprimento = estado['comprimento']
        self.elementos = estado['elementos']
        self.proximo_id = estado['proximo_id']
        self.criada = estado['criada']

class Aplicacao:
    def __init__(self, root):
        self.root = root
        self.root.title("Calculadora de Momento Fletor e Esforço Cortante")
        self.root.geometry("1200x750")
        
        self.viga = Viga()
        self.historico = Historico()
        
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        
        self.animacao_em_andamento = False
        self.layout_modificado = False
        self.frame_atual = None
        
        self.editando_elemento = None
        self.valores_originais = {}
        self.frame_edicao_atual = None
        
        self.root.update_idletasks()
        self.ultimo_tempo_frame = time.time()
        self.fps_alvo = 60
        self.frame_interval = 1000 / self.fps_alvo
        
        self.largura_frame = 0
        self.altura_frame = 0
        self.pos_y_frame = 0
        self.largura_total = 0
        
        self.container_principal = tk.Frame(self.root, bg="#2c3e50", highlightthickness=0, bd=0)
        self.container_principal.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.container_principal.grid_rowconfigure(0, weight=1)
        self.container_principal.grid_columnconfigure(0, weight=1)
        self.container_principal.grid_columnconfigure(1, weight=1)
        
        self.canvas_fundo = tk.Canvas(self.container_principal, bg="#2c3e50", highlightthickness=0, bd=0)
        self.canvas_fundo.grid(row=0, column=0, columnspan=2, sticky="nsew")
        
        self.criar_frame_superior()
        self.criar_frames_laterais()
        self.criar_planos_cartesianos()
        
        self.frames_operacoes = {}
        
        self.redimensionamento_timer = None
        self.root.bind("<Configure>", self.ao_redimensionar)
        
        self.root.after(200, self.atualizar_dimensoes)
        self.root.update()
        
        self.atualizar_botoes_historico()
        
    def criar_frame_superior(self):
        self.frame_superior = tk.Frame(self.root, bg="#2c3e50", height=50)
        self.frame_superior.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.frame_superior.grid_propagate(False)
        
        frame_botoes = tk.Frame(self.frame_superior, bg="#2c3e50")
        frame_botoes.pack(side="left", padx=10, pady=10)
        
        # Botão Adicionar
        self.menubutton_adicionar = tk.Menubutton(frame_botoes, text="Adicionar", bg="#27ae60", fg="white",
            font=("Arial", 10, "bold"), relief="raised", padx=20, pady=5, cursor="hand2")
        self.menubutton_adicionar.pack(side="left", padx=5)
        
        self.menu_adicionar = Menu(self.menubutton_adicionar, tearoff=False, bg="#ecf0f1", fg="#2c3e50", font=("Arial", 10))
        for opcao in ["Carga Concentrada", "Carga Distribuída", "Momento", "Apoio"]:
            self.menu_adicionar.add_command(label=opcao, command=lambda o=opcao: self.ao_adicionar_elemento(o))
        self.menubutton_adicionar.config(menu=self.menu_adicionar)
        
        # Botão Editar
        self.menubutton_editar = tk.Menubutton(frame_botoes, text="Editar", bg="#f39c12", fg="white",
            font=("Arial", 10, "bold"), relief="raised", padx=20, pady=5, cursor="hand2")
        self.menubutton_editar.pack(side="left", padx=5)
        
        self.menu_editar = Menu(self.menubutton_editar, tearoff=False, bg="#ecf0f1", fg="#2c3e50", font=("Arial", 10))
        for opcao in ["Editar Carga", "Editar Apoio", "Editar Comprimento"]:
            self.menu_editar.add_command(label=opcao, command=lambda o=opcao: self.ao_editar_elemento(o))
        self.menubutton_editar.config(menu=self.menu_editar)
        
        # Botão Remover
        self.menubutton_remover = tk.Menubutton(frame_botoes, text="Remover", bg="#e74c3c", fg="white",
            font=("Arial", 10, "bold"), relief="raised", padx=20, pady=5, cursor="hand2")
        self.menubutton_remover.pack(side="left", padx=5)
        
        self.menu_remover = Menu(self.menubutton_remover, tearoff=False, bg="#ecf0f1", fg="#2c3e50", font=("Arial", 10))
        for opcao in ["Remover Carga", "Remover Apoio", "Remover Momento", "Limpar Tudo"]:
            self.menu_remover.add_command(label=opcao, command=lambda o=opcao: self.ao_remover_elemento(o))
        self.menubutton_remover.config(menu=self.menu_remover)
        
        separator = tk.Frame(self.frame_superior, bg="#7f8c8d", width=2, height=30)
        separator.pack(side="left", padx=10)
        
        # Botão Desfazer
        self.botao_desfazer = tk.Button(self.frame_superior, text="↩ Desfazer", command=self.desfazer_acao,
            bg="#95a5a6", fg="white", font=("Arial", 9, "bold"), padx=10, pady=5, relief="flat", cursor="hand2",
            state="disabled")
        self.botao_desfazer.pack(side="left", padx=2)
        
        # Botão Refazer
        self.botao_refazer = tk.Button(self.frame_superior, text="↪ Refazer", command=self.refazer_acao,
            bg="#95a5a6", fg="white", font=("Arial", 9, "bold"), padx=10, pady=5, relief="flat", cursor="hand2",
            state="disabled")
        self.botao_refazer.pack(side="left", padx=2)
        
        # Botão Criar Viga
        self.botao_criar_viga = tk.Button(self.frame_superior, text="🔧 Criar Viga", command=self.abrir_criar_viga,
            bg="#9b59b6", fg="white", font=("Arial", 9, "bold"), padx=15, pady=5, relief="flat", cursor="hand2")
        self.botao_criar_viga.pack(side="left", padx=5)
        
        # Botão Mostrar Diagramas
        self.botao_mostrar_diagramas = tk.Button(self.frame_superior, text="📊 Mostrar Diagramas", command=self.mostrar_diagramas,
            bg="#3498db", fg="white", font=("Arial", 9, "bold"), padx=15, pady=5, relief="flat", cursor="hand2")
        self.botao_mostrar_diagramas.pack(side="left", padx=5)
        
        self.label_info = tk.Label(self.frame_superior, text="Calculadora de Diagramas - Momento Fletor e Esforço Cortante",
            bg="#2c3e50", fg="white", font=("Arial", 9))
        self.label_info.pack(side="right", padx=20, pady=10)
        
        self.label_selecao = tk.Label(self.frame_superior, text="", bg="#2c3e50", fg="#f39c12", font=("Arial", 8, "italic"))
        self.label_selecao.pack(side="right", padx=10, pady=10)
        
    def criar_frames_laterais(self):
        self.frame_esquerdo = tk.Frame(self.container_principal, bg="white", bd=1, relief="solid", highlightthickness=0)
        self.frame_esquerdo.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        
        self.frame_direito = tk.Frame(self.container_principal, bg="#2c3e50", bd=0, relief="flat", highlightthickness=0)
        self.frame_direito.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        
        self.frame_direito.grid_rowconfigure(0, weight=1)
        self.frame_direito.grid_rowconfigure(1, weight=1)
        self.frame_direito.grid_columnconfigure(0, weight=1)
        
        self.frame_direito_superior = tk.Frame(self.frame_direito, bg="white", bd=1, relief="solid", highlightthickness=0)
        self.frame_direito_superior.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 5))
        
        self.frame_direito_inferior = tk.Frame(self.frame_direito, bg="white", bd=1, relief="solid", highlightthickness=0)
        self.frame_direito_inferior.grid(row=1, column=0, sticky="nsew", padx=0, pady=(5, 0))
    
    def criar_plano_cartesiano_branco(self, frame, titulo="Plano Cartesiano"):
        fig = Figure(figsize=(5, 4), dpi=100, facecolor='white')
        ax = fig.add_subplot(111)
        
        ax.set_title(titulo, fontsize=12, fontweight='bold', pad=10, color='#2c3e50')
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
        ax.set_facecolor('#fafafa')
        ax.axhline(y=0, color='black', linewidth=0.8, alpha=0.5)
        ax.axvline(x=0, color='black', linewidth=0.8, alpha=0.5)
        ax.set_xlim(-1, 11)
        ax.set_ylim(-5, 5)
        ax.spines['left'].set_position('zero')
        ax.spines['bottom'].set_position('zero')
        ax.spines['right'].set_color('none')
        ax.spines['top'].set_color('none')
        ax.set_xticks(range(0, 11, 2))
        ax.set_yticks(range(-4, 5, 2))
        ax.tick_params(axis='both', which='major', labelsize=8, colors='#555555')
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        return fig, ax, canvas
    
    def criar_planos_cartesianos(self):
        self.fig_esquerdo, self.ax_esquerdo, self.canvas_esquerdo = self.criar_plano_cartesiano_branco(
            self.frame_esquerdo, "Diagrama de Corpo Livre")
        self.fig_direito_sup, self.ax_direito_sup, self.canvas_direito_sup = self.criar_plano_cartesiano_branco(
            self.frame_direito_superior, "Diagrama de Esforço Cortante (DEC)")
        self.fig_direito_inf, self.ax_direito_inf, self.canvas_direito_inf = self.criar_plano_cartesiano_branco(
            self.frame_direito_inferior, "Diagrama de Momento Fletor (DMF)")
    
    def salvar_estado(self):
        self.historico.adicionar_acao(self.viga.obter_estado())
        self.atualizar_botoes_historico()
    
    def desfazer_acao(self):
        estado_anterior = self.historico.desfazer()
        if estado_anterior:
            estado_atual = self.viga.obter_estado()
            self.historico.redo_stack[-1] = estado_atual
            self.viga.restaurar_estado(estado_anterior)
            self.desenhar_diagrama_corpo_livre()
            self.label_info.config(text="Ação desfeita")
            self.atualizar_botoes_historico()
            self.atualizar_frames_abertos()
    
    def refazer_acao(self):
        estado_refazer = self.historico.refazer()
        if estado_refazer:
            estado_atual = self.viga.obter_estado()
            self.historico.undo_stack[-1] = estado_atual
            self.viga.restaurar_estado(estado_refazer)
            self.desenhar_diagrama_corpo_livre()
            self.label_info.config(text="Ação refeita")
            self.atualizar_botoes_historico()
            self.atualizar_frames_abertos()
    
    def atualizar_botoes_historico(self):
        if self.historico.pode_desfazer():
            self.botao_desfazer.configure(state="normal", bg="#e67e22")
        else:
            self.botao_desfazer.configure(state="disabled", bg="#95a5a6")
        
        if self.historico.pode_refazer():
            self.botao_refazer.configure(state="normal", bg="#2ecc71")
        else:
            self.botao_refazer.configure(state="disabled", bg="#95a5a6")
    
    def atualizar_frames_abertos(self):
        if self.layout_modificado and self.frame_atual:
            for key, frame in self.frames_operacoes.items():
                if frame == self.frame_atual:
                    if key.startswith("Editar"):
                        if key == "Editar Carga":
                            novo_frame = self.criar_frame_editar_cargas()
                        elif key == "Editar Apoio":
                            novo_frame = self.criar_frame_editar_apoios()
                        elif key == "Editar Comprimento":
                            novo_frame = self.criar_frame_editar_comprimento()
                        else:
                            continue
                    elif key.startswith("Remover"):
                        if key == "Remover Carga":
                            novo_frame = self.criar_frame_remover_cargas()
                        elif key == "Remover Apoio":
                            novo_frame = self.criar_frame_remover_apoios()
                        elif key == "Remover Momento":
                            novo_frame = self.criar_frame_remover_momentos()
                        else:
                            continue
                    else:
                        continue
                    
                    self.frames_operacoes[key] = novo_frame
                    self.trocar_frame_operacao(novo_frame)
                    break
    
    def desenhar_diagrama_corpo_livre(self):
        if not self.viga.criada:
            return
            
        self.ax_esquerdo.clear()
        
        self.ax_esquerdo.set_title("Diagrama de Corpo Livre", fontsize=12, fontweight='bold', pad=10, color='#2c3e50')
        self.ax_esquerdo.set_xlabel('')
        self.ax_esquerdo.set_ylabel('')
        self.ax_esquerdo.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
        self.ax_esquerdo.set_facecolor('#fafafa')
        
        margem = self.viga.comprimento * 0.1
        
        max_forca = 1
        for carga in self.viga.obter_elementos_por_tipo(CargaConcentrada):
            if abs(carga.valor) > max_forca:
                max_forca = abs(carga.valor)
        for carga in self.viga.obter_elementos_por_tipo(CargaDistribuida):
            if abs(carga.valor_inicial) > max_forca:
                max_forca = abs(carga.valor_inicial)
            if abs(carga.valor_final) > max_forca:
                max_forca = abs(carga.valor_final)
        
        limite_y = max_forca * 1.3
        if limite_y < 5:
            limite_y = 5
        limite_y = int(np.ceil(limite_y))
        if limite_y < 1:
            limite_y = 1
        if limite_y > 50:
            limite_y = 50
        
        self.ax_esquerdo.set_xlim(-margem, self.viga.comprimento + margem)
        self.ax_esquerdo.set_ylim(-limite_y, limite_y)
        self.ax_esquerdo.axhline(y=0, color='black', linewidth=0.8, alpha=0.5)
        self.ax_esquerdo.axvline(x=0, color='black', linewidth=0.8, alpha=0.5)
        self.ax_esquerdo.spines['left'].set_position('zero')
        self.ax_esquerdo.spines['bottom'].set_position('zero')
        self.ax_esquerdo.spines['right'].set_color('none')
        self.ax_esquerdo.spines['top'].set_color('none')
        
        if limite_y <= 10:
            passo_y = 1
        elif limite_y <= 20:
            passo_y = 2
        elif limite_y <= 50:
            passo_y = 5
        else:
            passo_y = 10
        
        ticks_positivos = np.arange(0, limite_y + passo_y, passo_y)
        ticks_negativos = np.arange(-passo_y, -limite_y - passo_y, -passo_y)[::-1]
        ticks_y = np.concatenate([ticks_negativos, ticks_positivos])
        self.ax_esquerdo.set_yticks(ticks_y)
        
        passo_x = max(1, int(self.viga.comprimento / 5))
        ticks_x = np.arange(0, self.viga.comprimento + passo_x, passo_x)
        self.ax_esquerdo.set_xticks(ticks_x)
        
        self.ax_esquerdo.plot([0, self.viga.comprimento], [0, 0], 'k-', linewidth=3, label='Viga')
        
        # Desenhar apoios
        for apoio in self.viga.obter_elementos_por_tipo(Apoio):
            if apoio.tipo == TipoApoio.ENGASTE:
                altura_engaste = limite_y * 0.2
                largura_engaste = self.viga.comprimento * 0.02
                if apoio.posicao_x == 0:
                    self.ax_esquerdo.fill_between([-largura_engaste, 0], [-altura_engaste, -altura_engaste], 
                                                 [altura_engaste, altura_engaste], color='gray', alpha=0.5, hatch='////')
                    self.ax_esquerdo.plot([0, 0], [-altura_engaste, altura_engaste], 'k-', linewidth=2)
                elif apoio.posicao_x == self.viga.comprimento:
                    self.ax_esquerdo.fill_between([self.viga.comprimento, self.viga.comprimento + largura_engaste], 
                                                 [-altura_engaste, -altura_engaste], [altura_engaste, altura_engaste], 
                                                 color='gray', alpha=0.5, hatch='////')
                    self.ax_esquerdo.plot([self.viga.comprimento, self.viga.comprimento], 
                                         [-altura_engaste, altura_engaste], 'k-', linewidth=2)
                self.ax_esquerdo.text(apoio.posicao_x, -altura_engaste - limite_y * 0.08, 'Engaste', ha='center', fontsize=8, color='gray')
                
            elif apoio.tipo == TipoApoio.PINO:
                y_offset = -0.1 if apoio.posicao_vertical == PosicaoApoio.BASE else 0.1
                altura_pino = limite_y * 0.1
                largura_pino = self.viga.comprimento * 0.03
                y_base = y_offset - altura_pino if apoio.posicao_vertical == PosicaoApoio.BASE else y_offset + altura_pino
                self.ax_esquerdo.plot([apoio.posicao_x, apoio.posicao_x - largura_pino, apoio.posicao_x + largura_pino],
                        [y_offset, y_base, y_base], 'b-', linewidth=2)
                self.ax_esquerdo.fill([apoio.posicao_x, apoio.posicao_x - largura_pino, apoio.posicao_x + largura_pino],
                        [y_offset, y_base, y_base], 'lightblue', alpha=0.5)
                label_y = -limite_y * 0.15 if apoio.posicao_vertical == PosicaoApoio.BASE else limite_y * 0.15
                self.ax_esquerdo.text(apoio.posicao_x, label_y, f'Pino\n({apoio.posicao_vertical.value})', ha='center', fontsize=7, color='blue')
                
            elif apoio.tipo == TipoApoio.ROLETE:
                if apoio.posicao_vertical == PosicaoApoio.BASE:
                    y_centro = -0.3
                    y_base = -0.6
                else:
                    y_centro = 0.3
                    y_base = 0.6
                raio = 0.15
                circle = plt.Circle((apoio.posicao_x, y_centro), raio, color='green', fill=True, alpha=0.7, zorder=5)
                self.ax_esquerdo.add_patch(circle)
                largura_base = 0.3
                self.ax_esquerdo.plot([apoio.posicao_x - largura_base, apoio.posicao_x + largura_base], 
                                     [y_base, y_base], 'g-', linewidth=2.5, solid_capstyle='round')
                self.ax_esquerdo.plot([apoio.posicao_x - largura_base, apoio.posicao_x - largura_base], 
                                     [y_centro - raio, y_base], 'g-', linewidth=1.5)
                self.ax_esquerdo.plot([apoio.posicao_x + largura_base, apoio.posicao_x + largura_base], 
                                     [y_centro - raio, y_base], 'g-', linewidth=1.5)
                label_y = -0.9 if apoio.posicao_vertical == PosicaoApoio.BASE else 0.9
                self.ax_esquerdo.text(apoio.posicao_x, label_y, f'Rolete\n({apoio.posicao_vertical.value})', ha='center', fontsize=7, color='green')
        
        # Desenhar cargas concentradas
        for carga in self.viga.obter_elementos_por_tipo(CargaConcentrada):
            valor = abs(carga.valor)
            if carga.direcao == "Para baixo":
                y_inicio = valor
                y_fim = 0
                text_y = valor + limite_y * 0.05
            else:
                y_inicio = -valor
                y_fim = 0
                text_y = -valor - limite_y * 0.05
            
            self.ax_esquerdo.annotate('', xy=(carga.posicao_x, y_fim), xytext=(carga.posicao_x, y_inicio),
                arrowprops=dict(arrowstyle='->', color='red', lw=2, mutation_scale=15, shrinkA=0, shrinkB=0))
            self.ax_esquerdo.text(carga.posicao_x, text_y, f'{carga.valor} kN', ha='center', fontsize=9, color='red', fontweight='bold')
        
        # Desenhar cargas distribuídas
        for carga in self.viga.obter_elementos_por_tipo(CargaDistribuida):
            y_fim_valor_inicial = carga.valor_inicial
            y_fim_valor_final = carga.valor_final
            vertices_x = [carga.posicao_x, carga.posicao_x, carga.posicao_final_x, carga.posicao_final_x]
            vertices_y = [0, y_fim_valor_inicial, y_fim_valor_final, 0]
            self.ax_esquerdo.fill(vertices_x, vertices_y, alpha=0.3, color='orange')
            self.ax_esquerdo.plot([carga.posicao_x, carga.posicao_final_x], [y_fim_valor_inicial, y_fim_valor_final], 'orange', linewidth=2)
            self.ax_esquerdo.plot([carga.posicao_x, carga.posicao_x], [0, y_fim_valor_inicial], 'orange', linewidth=1.5)
            self.ax_esquerdo.plot([carga.posicao_final_x, carga.posicao_final_x], [0, y_fim_valor_final], 'orange', linewidth=1.5)
            
            num_setas = max(3, min(8, int((carga.posicao_final_x - carga.posicao_x) * 2)))
            for i in range(num_setas):
                xi = carga.posicao_x + (carga.posicao_final_x - carga.posicao_x) * i / (num_setas - 1)
                yi_carga = y_fim_valor_inicial + (y_fim_valor_final - y_fim_valor_inicial) * i / (num_setas - 1)
                if abs(yi_carga) > 0.05:
                    self.ax_esquerdo.annotate('', xy=(xi, 0), xytext=(xi, yi_carga),
                        arrowprops=dict(arrowstyle='->', color='orange', lw=1, alpha=0.7, mutation_scale=10, shrinkA=0, shrinkB=0))
            
            offset_y = limite_y * 0.05
            offset_y_inicial = offset_y if y_fim_valor_inicial >= 0 else -offset_y
            offset_y_final = offset_y if y_fim_valor_final >= 0 else -offset_y
            self.ax_esquerdo.text(carga.posicao_x, y_fim_valor_inicial + offset_y_inicial, 
                    f'{carga.valor_inicial} kN/m', ha='center', fontsize=8, color='orange', fontweight='bold')
            self.ax_esquerdo.text(carga.posicao_final_x, y_fim_valor_final + offset_y_final, 
                    f'{carga.valor_final} kN/m', ha='center', fontsize=8, color='orange', fontweight='bold')
        
            # Desenhar momentos - NOVA VERSÃO (estilo engenharia)
        # Desenhar momentos - CÍRCULO COM 1/4 FALTANDO E SETA CURVA
        for momento in self.viga.obter_elementos_por_tipo(Momento):
            raio = 0.4  # Tamanho fixo
            
            if momento.sentido == "Horário":
                # REGRA: Seta do ponto mais ALTO para o ponto mais BAIXO seguindo curvatura
                # Círculo acima da viga, sentido horário, falta 1/4 no canto inferior direito
                theta = np.linspace(np.pi/2, 5*np.pi/2 - np.pi/4, 50)
                y_arco = raio * np.sin(theta)
                x_arco = momento.posicao_x + raio * np.cos(theta)
                
                # SETA NO PONTO MAIS ALTO (INÍCIO) APONTANDO PARA BAIXO
                x_ponta = x_arco[0]
                y_ponta = y_arco[0]


                # Direção da seta: seguir a curvatura do círculo (para direita e para baixo)
                dx = 0.15   # Para direita
                dy = -0.15  # Para baixo
                
            else:  # Anti-horário
                # REGRA: Seta do ponto mais BAIXO para o ponto mais ALTO seguindo curvatura
                # Círculo abaixo da viga, sentido anti-horário, falta 1/4 no canto inferior esquerdo
                theta = np.linspace(np.pi/2, np.pi/2 - 2*np.pi + np.pi/4, 50)
                y_arco = -raio * np.sin(theta)
                x_arco = momento.posicao_x + raio * np.cos(theta)
                
                # SETA NO PONTO MAIS BAIXO (FINAL) APONTANDO PARA CIMA
                x_ponta = x_arco[-1]
                y_ponta = y_arco[-1]

                
                # Direção da seta: seguir a curvatura do círculo (para esquerda e para cima)
                dx = -0.15  # Para esquerda
                dy = 0.15   # Para cima
            
            # Desenhar linha curva do círculo
            self.ax_esquerdo.plot(x_arco, y_arco, 'm-', linewidth=2.5, solid_capstyle='round')
            
            # Adicionar ponta de seta
            self.ax_esquerdo.annotate('',
                xy=(x_ponta + dx, y_ponta + dy),
                xytext=(x_ponta, y_ponta),
                arrowprops=dict(arrowstyle='->', color='magenta', lw=2.5, 
                              mutation_scale=20, shrinkA=0, shrinkB=0,
                              fc='magenta', ec='magenta'))
            
            # Valor do momento em caixa
            text_y = 0.8 if momento.sentido == "Horário" else -0.8
            self.ax_esquerdo.text(momento.posicao_x, text_y, 
                    f'{momento.valor} kN·m',
                    ha='center', va='center', fontsize=9, color='magenta', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                            edgecolor='magenta', linewidth=1.5, alpha=0.9))
            
        self.fig_esquerdo.tight_layout()
        self.canvas_esquerdo.draw()
    
    def abrir_criar_viga(self):
        self.frames_operacoes["Criar Viga"] = self.criar_formulario_viga()
        if self.layout_modificado:
            self.trocar_frame_operacao(self.frames_operacoes["Criar Viga"])
        else:
            self.iniciar_animacao_frame_operacao(self.frames_operacoes["Criar Viga"])
    
    def criar_formulario_viga(self):
        frame, conteudo = self.criar_frame_operacao("Criar Viga", "#9b59b6")
        
        tk.Label(conteudo, text="Defina o comprimento da viga:", bg="white", font=("Arial", 12, "bold")).pack(pady=20)
        tk.Label(conteudo, text="Comprimento (m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_comprimento = tk.Entry(conteudo, font=("Arial", 12), width=20)
        entry_comprimento.pack(pady=10)
        entry_comprimento.insert(0, str(self.viga.comprimento))
        
        def criar_viga():
            try:
                comprimento = float(entry_comprimento.get())
                if comprimento <= 0:
                    messagebox.showerror("Erro", "O comprimento deve ser maior que zero")
                    return
                self.salvar_estado()
                self.viga.criar_viga(comprimento)
                self.ax_esquerdo.set_xlim(-1, comprimento + 1)
                self.ax_esquerdo.set_xticks(range(0, int(comprimento) + 1, max(1, int(comprimento)//5)))
                self.desenhar_diagrama_corpo_livre()
                self.label_info.config(text=f"Viga criada com comprimento de {comprimento} m")
                for key in list(self.frames_operacoes.keys()):
                    if key != "Criar Viga":
                        del self.frames_operacoes[key]
                self.mostrar_diagramas()
            except ValueError:
                messagebox.showerror("Erro", "Por favor, insira um valor numérico válido")
        
        tk.Button(conteudo, text="✓ Criar Viga", command=criar_viga, bg="#9b59b6", fg="white",
            font=("Arial", 12, "bold"), padx=30, pady=12, relief="flat", cursor="hand2").pack(pady=20)
        tk.Label(conteudo, text="Após criar a viga, você pode adicionar\ncargas, apoios e momentos.",
            bg="white", fg="#7f8c8d", font=("Arial", 9, "italic"), justify=tk.CENTER).pack(pady=10)
        return frame
    
    def criar_formulario_apoio(self):
        frame, conteudo = self.criar_frame_operacao("Adicionar Apoio", "#27ae60")
        
        if not self.viga.criada:
            tk.Label(conteudo, text="⚠️ Crie a viga primeiro!", bg="white", fg="#e74c3c", font=("Arial", 12, "bold")).pack(pady=20)
            return frame
        
        tk.Label(conteudo, text="Tipo de Apoio:", bg="white", font=("Arial", 10, "bold")).pack(pady=(10, 5))
        tipo_var = tk.StringVar(value="Pino")
        tipo_menu = ttk.Combobox(conteudo, textvariable=tipo_var, values=["Pino", "Rolete", "Engaste"],
            state="readonly", font=("Arial", 10), width=28)
        tipo_menu.pack(pady=5)
        
        info_frame = tk.Frame(conteudo, bg="#f8f9fa", bd=1, relief="solid")
        info_frame.pack(pady=10, padx=20, fill=tk.X)
        info_label = tk.Label(info_frame, text="", bg="#f8f9fa", font=("Arial", 9), justify=tk.LEFT, wraplength=350)
        info_label.pack(padx=10, pady=10)
        
        tk.Label(conteudo, text="Posição na viga (m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_posicao = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_posicao.pack(pady=5)
        
        posicao_frame = tk.Frame(conteudo, bg="white")
        posicao_frame.pack(pady=10)
        tk.Label(posicao_frame, text="Posição vertical:", bg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        posicao_var = tk.StringVar(value="Base")
        posicao_menu = ttk.Combobox(posicao_frame, textvariable=posicao_var, values=["Base", "Topo"],
            state="readonly", font=("Arial", 10), width=10)
        posicao_menu.pack(side=tk.LEFT, padx=5)
        
        tk.Label(conteudo, text="Descrição (opcional):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_descricao = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_descricao.pack(pady=5)
        
        def atualizar_info(*args):
            tipo = tipo_var.get()
            if tipo == "Engaste":
                info_label.config(text="• O engaste só pode ser colocado nas extremidades da viga (x=0 ou x=final)\n• Restringe movimento vertical e horizontal\n• Restringe rotação", fg="#e74c3c")
                posicao_menu.configure(state="disabled")
            elif tipo == "Pino":
                info_label.config(text="• Pode ser colocado em qualquer posição da viga\n• Restringe movimento vertical e horizontal\n• Permite rotação\n• Pode ser na base ou no topo da viga", fg="#3498db")
                posicao_menu.configure(state="readonly")
            elif tipo == "Rolete":
                info_label.config(text="• Pode ser colocado em qualquer posição da viga\n• Restringe apenas movimento vertical\n• Permite movimento horizontal e rotação\n• Pode ser na base ou no topo da viga", fg="#27ae60")
                posicao_menu.configure(state="readonly")
        
        tipo_var.trace('w', atualizar_info)
        atualizar_info()
        
        def inserir_apoio():
            try:
                if not self.viga.criada:
                    messagebox.showerror("Erro", "Crie a viga primeiro!")
                    return
                posicao = float(entry_posicao.get())
                tipo_str = tipo_var.get()
                descricao = entry_descricao.get() or f"Apoio {tipo_str}"
                if posicao < 0 or posicao > self.viga.comprimento:
                    messagebox.showerror("Erro", f"Posição deve estar entre 0 e {self.viga.comprimento} m")
                    return
                if tipo_str == "Engaste" and posicao != 0 and posicao != self.viga.comprimento:
                    messagebox.showerror("Erro", "Engaste só pode ser colocado nas extremidades da viga (x=0 ou x=final)")
                    return
                
                self.salvar_estado()
                tipo_map = {"Pino": TipoApoio.PINO, "Rolete": TipoApoio.ROLETE, "Engaste": TipoApoio.ENGASTE}
                apoio = Apoio(id=0, posicao_x=posicao, descricao=descricao, tipo=tipo_map[tipo_str],
                    posicao_vertical=PosicaoApoio.BASE if posicao_var.get() == "Base" else PosicaoApoio.TOPO)
                self.viga.adicionar_elemento(apoio)
                self.desenhar_diagrama_corpo_livre()
                self.label_info.config(text=f"Apoio {tipo_str} adicionado em x={posicao} m")
                entry_posicao.delete(0, tk.END)
                entry_descricao.delete(0, tk.END)
            except ValueError:
                messagebox.showerror("Erro", "Por favor, insira valores numéricos válidos")
        
        tk.Button(conteudo, text="✓ Inserir Apoio", command=inserir_apoio, bg="#27ae60", fg="white",
            font=("Arial", 11, "bold"), padx=20, pady=10, relief="flat", cursor="hand2").pack(pady=20)
        return frame
    
    def criar_formulario_carga_concentrada(self):
        frame, conteudo = self.criar_frame_operacao("Adicionar Carga Concentrada", "#27ae60")
        
        if not self.viga.criada:
            tk.Label(conteudo, text="⚠️ Crie a viga primeiro!", bg="white", fg="#e74c3c", font=("Arial", 12, "bold")).pack(pady=20)
            return frame
        
        tk.Label(conteudo, text="Posição na viga (m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_posicao = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_posicao.pack(pady=5)
        
        tk.Label(conteudo, text="Valor da carga (kN):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_valor = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_valor.pack(pady=5)
        
        tk.Label(conteudo, text="Direção:", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        direcao_var = tk.StringVar(value="Para baixo")
        ttk.Combobox(conteudo, textvariable=direcao_var, values=["Para baixo", "Para cima"],
            state="readonly", font=("Arial", 10), width=28).pack(pady=5)
        
        tk.Label(conteudo, text="Descrição (opcional):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_descricao = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_descricao.pack(pady=5)
        
        def inserir_carga():
            try:
                if not self.viga.criada:
                    messagebox.showerror("Erro", "Crie a viga primeiro!")
                    return
                posicao = float(entry_posicao.get())
                valor = float(entry_valor.get())
                direcao = direcao_var.get()
                descricao = entry_descricao.get() or "Carga Concentrada"
                if posicao < 0 or posicao > self.viga.comprimento:
                    messagebox.showerror("Erro", f"Posição deve estar entre 0 e {self.viga.comprimento} m")
                    return
                self.salvar_estado()
                carga = CargaConcentrada(id=0, posicao_x=posicao, descricao=descricao, valor=valor, direcao=direcao)
                self.viga.adicionar_elemento(carga)
                self.desenhar_diagrama_corpo_livre()
                self.label_info.config(text=f"Carga concentrada de {valor} kN adicionada em x={posicao} m")
                entry_posicao.delete(0, tk.END)
                entry_valor.delete(0, tk.END)
                entry_descricao.delete(0, tk.END)
            except ValueError:
                messagebox.showerror("Erro", "Por favor, insira valores numéricos válidos")
        
        tk.Button(conteudo, text="✓ Inserir Carga", command=inserir_carga, bg="#27ae60", fg="white",
            font=("Arial", 11, "bold"), padx=20, pady=10, relief="flat", cursor="hand2").pack(pady=20)
        return frame
    
    def criar_formulario_carga_distribuida(self):
        frame, conteudo = self.criar_frame_operacao("Adicionar Carga Distribuída", "#27ae60")
        
        if not self.viga.criada:
            tk.Label(conteudo, text="⚠️ Crie a viga primeiro!", bg="white", fg="#e74c3c", font=("Arial", 12, "bold")).pack(pady=20)
            return frame
        
        tk.Label(conteudo, text="Posição inicial (m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_pos_inicial = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_pos_inicial.pack(pady=5)
        
        tk.Label(conteudo, text="Posição final (m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_pos_final = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_pos_final.pack(pady=5)
        
        tk.Label(conteudo, text="Valor inicial (kN/m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_valor_inicial = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_valor_inicial.pack(pady=5)
        
        tk.Label(conteudo, text="Valor final (kN/m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_valor_final = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_valor_final.pack(pady=5)
        
        tk.Label(conteudo, text="Descrição (opcional):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_descricao = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_descricao.pack(pady=5)
        
        info_frame = tk.Frame(conteudo, bg="#f8f9fa", bd=1, relief="solid")
        info_frame.pack(pady=10, padx=20, fill=tk.X)
        tk.Label(info_frame, text="• Valores positivos: carga para baixo\n• Valores negativos: carga para cima\n• Valores diferentes: carga triangular/trapezoidal",
            bg="#f8f9fa", font=("Arial", 9), justify=tk.LEFT).pack(padx=10, pady=10)
        
        def inserir_carga_distribuida():
            try:
                if not self.viga.criada:
                    messagebox.showerror("Erro", "Crie a viga primeiro!")
                    return
                pos_inicial = float(entry_pos_inicial.get())
                pos_final = float(entry_pos_final.get())
                valor_inicial = float(entry_valor_inicial.get())
                valor_final = float(entry_valor_final.get())
                descricao = entry_descricao.get() or "Carga Distribuída"
                if pos_inicial < 0 or pos_inicial > self.viga.comprimento:
                    messagebox.showerror("Erro", f"Posição inicial deve estar entre 0 e {self.viga.comprimento} m")
                    return
                if pos_final < 0 or pos_final > self.viga.comprimento:
                    messagebox.showerror("Erro", f"Posição final deve estar entre 0 e {self.viga.comprimento} m")
                    return
                if pos_final <= pos_inicial:
                    messagebox.showerror("Erro", "Posição final deve ser maior que a inicial")
                    return
                self.salvar_estado()
                carga = CargaDistribuida(id=0, posicao_x=pos_inicial, descricao=descricao,
                    valor_inicial=valor_inicial, valor_final=valor_final, posicao_final_x=pos_final)
                self.viga.adicionar_elemento(carga)
                self.desenhar_diagrama_corpo_livre()
                self.label_info.config(text=f"Carga distribuída adicionada de x={pos_inicial} a x={pos_final} m")
                entry_pos_inicial.delete(0, tk.END)
                entry_pos_final.delete(0, tk.END)
                entry_valor_inicial.delete(0, tk.END)
                entry_valor_final.delete(0, tk.END)
                entry_descricao.delete(0, tk.END)
            except ValueError:
                messagebox.showerror("Erro", "Por favor, insira valores numéricos válidos")
        
        tk.Button(conteudo, text="✓ Inserir Carga Distribuída", command=inserir_carga_distribuida, bg="#27ae60", fg="white",
            font=("Arial", 11, "bold"), padx=20, pady=10, relief="flat", cursor="hand2").pack(pady=20)
        return frame
    
    def criar_formulario_momento(self):
        frame, conteudo = self.criar_frame_operacao("Adicionar Momento", "#27ae60")
        
        if not self.viga.criada:
            tk.Label(conteudo, text="⚠️ Crie a viga primeiro!", bg="white", fg="#e74c3c", font=("Arial", 12, "bold")).pack(pady=20)
            return frame
        
        tk.Label(conteudo, text="Posição na viga (m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_posicao = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_posicao.pack(pady=5)
        
        tk.Label(conteudo, text="Valor do momento (kN·m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_valor = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_valor.pack(pady=5)
        
        tk.Label(conteudo, text="Sentido:", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        sentido_var = tk.StringVar(value="Horário")
        ttk.Combobox(conteudo, textvariable=sentido_var, values=["Horário", "Anti-horário"],
            state="readonly", font=("Arial", 10), width=28).pack(pady=5)
        
        tk.Label(conteudo, text="Descrição (opcional):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        entry_descricao = tk.Entry(conteudo, font=("Arial", 10), width=30)
        entry_descricao.pack(pady=5)
        
        def inserir_momento():
            try:
                if not self.viga.criada:
                    messagebox.showerror("Erro", "Crie a viga primeiro!")
                    return
                posicao = float(entry_posicao.get())
                valor = float(entry_valor.get())
                sentido = sentido_var.get()
                descricao = entry_descricao.get() or "Momento"
                if posicao < 0 or posicao > self.viga.comprimento:
                    messagebox.showerror("Erro", f"Posição deve estar entre 0 e {self.viga.comprimento} m")
                    return
                self.salvar_estado()
                momento = Momento(id=0, posicao_x=posicao, descricao=descricao, valor=valor, sentido=sentido)
                self.viga.adicionar_elemento(momento)
                self.desenhar_diagrama_corpo_livre()
                self.label_info.config(text=f"Momento de {valor} kN·m adicionado em x={posicao} m")
                entry_posicao.delete(0, tk.END)
                entry_valor.delete(0, tk.END)
                entry_descricao.delete(0, tk.END)
            except ValueError:
                messagebox.showerror("Erro", "Por favor, insira valores numéricos válidos")
        
        tk.Button(conteudo, text="✓ Inserir Momento", command=inserir_momento, bg="#27ae60", fg="white",
            font=("Arial", 11, "bold"), padx=20, pady=10, relief="flat", cursor="hand2").pack(pady=20)
        return frame
    
    def criar_frame_operacao(self, titulo, cor_titulo="#2c3e50"):
        frame = tk.Frame(self.container_principal, bg="white", bd=1, relief="solid", highlightthickness=0)
        tk.Label(frame, text=titulo, bg="white", fg=cor_titulo, font=("Arial", 14, "bold")).pack(pady=20)
        frame_conteudo = tk.Frame(frame, bg="white")
        frame_conteudo.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        frame_botao = tk.Frame(frame, bg="#f0f0f0", height=60)
        frame_botao.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=20)
        tk.Button(frame_botao, text="← Voltar aos Diagramas", command=self.mostrar_diagramas, bg="#3498db", fg="white",
            font=("Arial", 11, "bold"), padx=30, pady=12, relief="flat", highlightthickness=0, cursor="hand2").pack(pady=5)
        return frame, frame_conteudo
    
    def criar_tabela_elementos(self, parent, elementos, tipo_elemento):
        frame_tabela = tk.Frame(parent, bg="white")
        frame_tabela.pack(fill=tk.BOTH, expand=True, pady=10)
        
        if tipo_elemento == "carga":
            colunas = ("ID", "Tipo", "Posição", "Valor", "Direção/Sentido", "Descrição")
        elif tipo_elemento == "apoio":
            colunas = ("ID", "Tipo", "Posição", "Pos. Vertical", "Descrição")
        elif tipo_elemento == "momento":
            colunas = ("ID", "Posição", "Valor", "Sentido", "Descrição")
        else:
            colunas = ("ID", "Descrição")
        
        tree = ttk.Treeview(frame_tabela, columns=colunas, show="headings", height=8)
        for col in colunas:
            tree.heading(col, text=col)
            tree.column(col, width=100, anchor="center")
        
        scrollbar = ttk.Scrollbar(frame_tabela, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        for elem in elementos:
            if tipo_elemento == "carga":
                if isinstance(elem, CargaConcentrada):
                    valores = (elem.id, "Concentrada", f"{elem.posicao_x}m", f"{elem.valor}kN", elem.direcao, elem.descricao)
                elif isinstance(elem, CargaDistribuida):
                    valores = (elem.id, "Distribuída", f"{elem.posicao_x}-{elem.posicao_final_x}m",
                             f"{elem.valor_inicial}-{elem.valor_final}kN/m", "-", elem.descricao)
                else:
                    valores = (elem.id, "Outra", "-", "-", "-", elem.descricao)
            elif tipo_elemento == "apoio":
                valores = (elem.id, elem.tipo.value, f"{elem.posicao_x}m", elem.posicao_vertical.value, elem.descricao)
            elif tipo_elemento == "momento":
                valores = (elem.id, f"{elem.posicao_x}m", f"{elem.valor}kN·m", elem.sentido, elem.descricao)
            else:
                valores = (elem.id, elem.descricao)
            tree.insert("", tk.END, values=valores)
        
        return tree, elementos
    
    def obter_valores_elemento(self, elemento):
        valores = {}
        if isinstance(elemento, CargaConcentrada):
            valores = {'posicao_x': elemento.posicao_x, 'valor': elemento.valor,
                      'direcao': elemento.direcao, 'descricao': elemento.descricao}
        elif isinstance(elemento, CargaDistribuida):
            valores = {'posicao_x': elemento.posicao_x, 'posicao_final_x': elemento.posicao_final_x,
                      'valor_inicial': elemento.valor_inicial, 'valor_final': elemento.valor_final,
                      'descricao': elemento.descricao}
        return valores
    
    def houve_alteracao(self, elemento):
        if not self.editando_elemento:
            return False
        try:
            return self.obter_valores_campos(elemento) != self.valores_originais
        except:
            return True
    
    def obter_valores_campos(self, elemento):
        valores = {}
        try:
            if isinstance(elemento, CargaConcentrada):
                valores = {'posicao_x': float(self.entry_posicao.get()), 'valor': float(self.entry_valor.get()),
                          'direcao': self.direcao_var.get(), 'descricao': self.entry_descricao.get()}
            elif isinstance(elemento, CargaDistribuida):
                valores = {'posicao_x': float(self.entry_pos_inicial.get()), 'posicao_final_x': float(self.entry_pos_final.get()),
                          'valor_inicial': float(self.entry_valor_inicial.get()), 'valor_final': float(self.entry_valor_final.get()),
                          'descricao': self.entry_descricao.get()}
        except ValueError:
            raise ValueError("Valores inválidos nos campos")
        return valores
    
    def criar_campos_carga_concentrada(self, parent, elemento):
        tk.Label(parent, text="Posição na viga (m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        self.entry_posicao = tk.Entry(parent, font=("Arial", 10), width=30)
        self.entry_posicao.pack(pady=5)
        self.entry_posicao.insert(0, str(elemento.posicao_x))
        
        tk.Label(parent, text="Valor da carga (kN):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        self.entry_valor = tk.Entry(parent, font=("Arial", 10), width=30)
        self.entry_valor.pack(pady=5)
        self.entry_valor.insert(0, str(elemento.valor))
        
        tk.Label(parent, text="Direção:", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        self.direcao_var = tk.StringVar(value=elemento.direcao)
        ttk.Combobox(parent, textvariable=self.direcao_var, values=["Para baixo", "Para cima"],
            state="readonly", font=("Arial", 10), width=28).pack(pady=5)
        
        tk.Label(parent, text="Descrição:", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        self.entry_descricao = tk.Entry(parent, font=("Arial", 10), width=30)
        self.entry_descricao.pack(pady=5)
        self.entry_descricao.insert(0, elemento.descricao)
    
    def criar_campos_carga_distribuida(self, parent, elemento):
        tk.Label(parent, text="Posição inicial (m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        self.entry_pos_inicial = tk.Entry(parent, font=("Arial", 10), width=30)
        self.entry_pos_inicial.pack(pady=5)
        self.entry_pos_inicial.insert(0, str(elemento.posicao_x))
        
        tk.Label(parent, text="Posição final (m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        self.entry_pos_final = tk.Entry(parent, font=("Arial", 10), width=30)
        self.entry_pos_final.pack(pady=5)
        self.entry_pos_final.insert(0, str(elemento.posicao_final_x))
        
        tk.Label(parent, text="Valor inicial (kN/m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        self.entry_valor_inicial = tk.Entry(parent, font=("Arial", 10), width=30)
        self.entry_valor_inicial.pack(pady=5)
        self.entry_valor_inicial.insert(0, str(elemento.valor_inicial))
        
        tk.Label(parent, text="Valor final (kN/m):", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        self.entry_valor_final = tk.Entry(parent, font=("Arial", 10), width=30)
        self.entry_valor_final.pack(pady=5)
        self.entry_valor_final.insert(0, str(elemento.valor_final))
        
        tk.Label(parent, text="Descrição:", bg="white", font=("Arial", 10)).pack(pady=(10, 5))
        self.entry_descricao = tk.Entry(parent, font=("Arial", 10), width=30)
        self.entry_descricao.pack(pady=5)
        self.entry_descricao.insert(0, elemento.descricao)
    
    def salvar_edicao(self, elemento):
        if messagebox.askyesno("Confirmar", "Deseja salvar as alterações?"):
            try:
                self.salvar_estado()
                novos_valores = self.obter_valores_campos(elemento)
                self.viga.editar_elemento(elemento.id, **novos_valores)
                self.desenhar_diagrama_corpo_livre()
                self.label_info.config(text="Alterações salvas com sucesso!")
                novo_frame = self.criar_frame_editar_cargas()
                self.frames_operacoes["Editar Carga"] = novo_frame
                self.trocar_frame_operacao(novo_frame)
            except ValueError as e:
                messagebox.showerror("Erro", f"Valores inválidos: {str(e)}")
    
    def descartar_edicao(self):
        if messagebox.askyesno("Confirmar", "Tem certeza que deseja descartar as alterações?"):
            novo_frame = self.criar_frame_editar_cargas()
            self.frames_operacoes["Editar Carga"] = novo_frame
            self.trocar_frame_operacao(novo_frame)
    
    def voltar_selecao_cargas(self):
        if self.houve_alteracao(self.editando_elemento):
            resposta = messagebox.askyesnocancel("Alterações não salvas",
                "Existem alterações não salvas.\n\nSim = Descartar alterações\nNão = Continuar editando\nCancelar = Cancelar")
            if resposta is True:
                novo_frame = self.criar_frame_editar_cargas()
                self.frames_operacoes["Editar Carga"] = novo_frame
                self.trocar_frame_operacao(novo_frame)
            elif resposta is False:
                return
        else:
            novo_frame = self.criar_frame_editar_cargas()
            self.frames_operacoes["Editar Carga"] = novo_frame
            self.trocar_frame_operacao(novo_frame)
    
    def criar_frame_editar_cargas(self):
        frame, conteudo = self.criar_frame_operacao("Editar Cargas", "#f39c12")
        
        cargas = []
        cargas.extend(self.viga.obter_elementos_por_tipo(CargaConcentrada))
        cargas.extend(self.viga.obter_elementos_por_tipo(CargaDistribuida))
        
        if not cargas:
            tk.Label(conteudo, text="Nenhuma carga cadastrada.", bg="white", fg="#7f8c8d", font=("Arial", 10, "italic")).pack(pady=20)
            return frame
        
        self.editando_elemento = None
        self.valores_originais = {}
        self.frame_edicao_atual = None
        
        frame_selecao = tk.Frame(conteudo, bg="white")
        frame_selecao.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame_selecao, text="Selecione a carga para editar:", bg="white", font=("Arial", 10, "bold")).pack(pady=5)
        tree, cargas_lista = self.criar_tabela_elementos(frame_selecao, cargas, "carga")
        
        def abrir_edicao():
            selecao = tree.selection()
            if not selecao:
                messagebox.showwarning("Aviso", "Selecione um elemento para editar.")
                return
            
            item = tree.item(selecao[0])
            id_elemento = item['values'][0]
            elemento = next((e for e in cargas_lista if e.id == id_elemento), None)
            if elemento is None:
                return
            
            self.editando_elemento = elemento
            self.valores_originais = self.obter_valores_elemento(elemento)
            
            for widget in conteudo.winfo_children():
                widget.pack_forget()
            
            self.frame_edicao_atual = tk.Frame(conteudo, bg="white")
            self.frame_edicao_atual.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            if isinstance(elemento, CargaConcentrada):
                self.criar_campos_carga_concentrada(self.frame_edicao_atual, elemento)
            elif isinstance(elemento, CargaDistribuida):
                self.criar_campos_carga_distribuida(self.frame_edicao_atual, elemento)
            
            frame_botoes_edicao = tk.Frame(self.frame_edicao_atual, bg="white")
            frame_botoes_edicao.pack(pady=20)
            
            tk.Button(frame_botoes_edicao, text="💾 Salvar Alterações", command=lambda: self.salvar_edicao(elemento),
                bg="#27ae60", fg="white", font=("Arial", 10, "bold"), padx=15, pady=8, relief="flat", cursor="hand2").pack(side=tk.LEFT, padx=5)
            tk.Button(frame_botoes_edicao, text="🗑 Descartar Alterações", command=self.descartar_edicao,
                bg="#e74c3c", fg="white", font=("Arial", 10, "bold"), padx=15, pady=8, relief="flat", cursor="hand2").pack(side=tk.LEFT, padx=5)
            tk.Button(frame_botoes_edicao, text="↩ Voltar à Seleção", command=self.voltar_selecao_cargas,
                bg="#95a5a6", fg="white", font=("Arial", 10, "bold"), padx=15, pady=8, relief="flat", cursor="hand2").pack(side=tk.LEFT, padx=5)
        
        tk.Button(frame_selecao, text="✏️ Editar Selecionado", command=abrir_edicao,
            bg="#f39c12", fg="white", font=("Arial", 10, "bold"), padx=15, pady=8, relief="flat", cursor="hand2").pack(pady=10)
        return frame
    
    def criar_frame_editar_apoios(self):
        frame, conteudo = self.criar_frame_operacao("Editar Apoios", "#f39c12")
        apoios = self.viga.obter_elementos_por_tipo(Apoio)
        
        if not apoios:
            tk.Label(conteudo, text="Nenhum apoio cadastrado.", bg="white", fg="#7f8c8d", font=("Arial", 10, "italic")).pack(pady=20)
            return frame
        
        frame_selecao = tk.Frame(conteudo, bg="white")
        frame_selecao.pack(fill=tk.BOTH, expand=True)
        tk.Label(frame_selecao, text="Selecione o apoio para editar:", bg="white", font=("Arial", 10, "bold")).pack(pady=5)
        tree, apoios_lista = self.criar_tabela_elementos(frame_selecao, apoios, "apoio")
        
        def abrir_edicao_apoio():
            selecao = tree.selection()
            if not selecao:
                messagebox.showwarning("Aviso", "Selecione um elemento para editar.")
                return
            item = tree.item(selecao[0])
            id_elemento = item['values'][0]
            messagebox.showinfo("Em desenvolvimento", f"Edição de apoio ID:{id_elemento} será implementada em breve.")
        
        tk.Button(frame_selecao, text="✏️ Editar Selecionado", command=abrir_edicao_apoio,
            bg="#f39c12", fg="white", font=("Arial", 10, "bold"), padx=15, pady=8, relief="flat", cursor="hand2").pack(pady=10)
        return frame
    
    def criar_frame_editar_comprimento(self):
        frame, conteudo = self.criar_frame_operacao("Editar Comprimento", "#f39c12")
        
        tk.Label(conteudo, text="Comprimento atual da viga:", bg="white", font=("Arial", 10, "bold")).pack(pady=(20, 5))
        tk.Label(conteudo, text=f"{self.viga.comprimento} m", bg="white", fg="#3498db", font=("Arial", 16, "bold")).pack(pady=10)
        tk.Label(conteudo, text="Novo comprimento (m):", bg="white", font=("Arial", 10)).pack(pady=(20, 5))
        entry_novo_comprimento = tk.Entry(conteudo, font=("Arial", 12), width=20)
        entry_novo_comprimento.pack(pady=10)
        entry_novo_comprimento.insert(0, str(self.viga.comprimento))
        
        def alterar_comprimento():
            try:
                novo = float(entry_novo_comprimento.get())
                if novo <= 0:
                    messagebox.showerror("Erro", "O comprimento deve ser maior que zero")
                    return
                if messagebox.askyesno("Confirmar", f"Alterar comprimento de {self.viga.comprimento}m para {novo}m?\n\nIsso pode afetar a posição dos elementos existentes."):
                    self.salvar_estado()
                    self.viga.elementos = [e for e in self.viga.elementos if not (hasattr(e, 'posicao_x') and e.posicao_x > novo)]
                    self.viga.comprimento = novo
                    self.desenhar_diagrama_corpo_livre()
                    self.label_info.config(text=f"Comprimento alterado para {novo} m")
                    self.mostrar_diagramas()
            except ValueError:
                messagebox.showerror("Erro", "Por favor, insira um valor numérico válido")
        
        tk.Button(conteudo, text="✓ Alterar Comprimento", command=alterar_comprimento,
            bg="#f39c12", fg="white", font=("Arial", 11, "bold"), padx=20, pady=10, relief="flat", cursor="hand2").pack(pady=20)
        return frame
    
    def criar_frame_remover_cargas(self):
        frame, conteudo = self.criar_frame_operacao("Remover Cargas", "#e74c3c")
        
        cargas = []
        cargas.extend(self.viga.obter_elementos_por_tipo(CargaConcentrada))
        cargas.extend(self.viga.obter_elementos_por_tipo(CargaDistribuida))
        
        if not cargas:
            tk.Label(conteudo, text="Nenhuma carga cadastrada.", bg="white", fg="#7f8c8d", font=("Arial", 10, "italic")).pack(pady=20)
            return frame
        
        tk.Label(conteudo, text="Selecione a carga para remover:", bg="white", font=("Arial", 10, "bold"), fg="#e74c3c").pack(pady=10)
        tree, cargas_lista = self.criar_tabela_elementos(conteudo, cargas, "carga")
        
        frame_botoes = tk.Frame(conteudo, bg="white")
        frame_botoes.pack(pady=15)
        
        def remover_selecionado():
            selecao = tree.selection()
            if not selecao:
                messagebox.showwarning("Aviso", "Selecione um elemento para remover.")
                return
            item = tree.item(selecao[0])
            id_elemento = item['values'][0]
            if messagebox.askyesno("Confirmar Remoção", f"Deseja realmente remover o elemento ID:{id_elemento}?\n\nEsta ação não pode ser desfeita."):
                self.salvar_estado()
                self.viga.remover_elemento(id_elemento)
                self.desenhar_diagrama_corpo_livre()
                self.label_info.config(text=f"Elemento ID:{id_elemento} removido com sucesso!")
                novo_frame = self.criar_frame_remover_cargas()
                self.frames_operacoes["Remover Carga"] = novo_frame
                if self.layout_modificado:
                    self.trocar_frame_operacao(novo_frame)
        
        tk.Button(frame_botoes, text="🗑 Remover Selecionado", command=remover_selecionado,
            bg="#e74c3c", fg="white", font=("Arial", 10, "bold"), padx=15, pady=8, relief="flat", cursor="hand2").pack(side=tk.LEFT, padx=5)
        return frame
    
    def criar_frame_remover_apoios(self):
        frame, conteudo = self.criar_frame_operacao("Remover Apoios", "#e74c3c")
        apoios = self.viga.obter_elementos_por_tipo(Apoio)
        
        if not apoios:
            tk.Label(conteudo, text="Nenhum apoio cadastrado.", bg="white", fg="#7f8c8d", font=("Arial", 10, "italic")).pack(pady=20)
            return frame
        
        tk.Label(conteudo, text="Selecione o apoio para remover:", bg="white", font=("Arial", 10, "bold"), fg="#e74c3c").pack(pady=10)
        tree, apoios_lista = self.criar_tabela_elementos(conteudo, apoios, "apoio")
        
        frame_botoes = tk.Frame(conteudo, bg="white")
        frame_botoes.pack(pady=15)
        
        def remover_selecionado():
            selecao = tree.selection()
            if not selecao:
                messagebox.showwarning("Aviso", "Selecione um elemento para remover.")
                return
            item = tree.item(selecao[0])
            id_elemento = item['values'][0]
            if messagebox.askyesno("Confirmar Remoção", f"Deseja realmente remover o apoio ID:{id_elemento}?\n\nEsta ação não pode ser desfeita."):
                self.salvar_estado()
                self.viga.remover_elemento(id_elemento)
                self.desenhar_diagrama_corpo_livre()
                self.label_info.config(text=f"Apoio ID:{id_elemento} removido com sucesso!")
                novo_frame = self.criar_frame_remover_apoios()
                self.frames_operacoes["Remover Apoio"] = novo_frame
                if self.layout_modificado:
                    self.trocar_frame_operacao(novo_frame)
        
        tk.Button(frame_botoes, text="🗑 Remover Selecionado", command=remover_selecionado,
            bg="#e74c3c", fg="white", font=("Arial", 10, "bold"), padx=15, pady=8, relief="flat", cursor="hand2").pack(side=tk.LEFT, padx=5)
        return frame
    
    def criar_frame_remover_momentos(self):
        frame, conteudo = self.criar_frame_operacao("Remover Momentos", "#e74c3c")
        momentos = self.viga.obter_elementos_por_tipo(Momento)
        
        if not momentos:
            tk.Label(conteudo, text="Nenhum momento cadastrado.", bg="white", fg="#7f8c8d", font=("Arial", 10, "italic")).pack(pady=20)
            return frame
        
        tk.Label(conteudo, text="Selecione o momento para remover:", bg="white", font=("Arial", 10, "bold"), fg="#e74c3c").pack(pady=10)
        tree, momentos_lista = self.criar_tabela_elementos(conteudo, momentos, "momento")
        
        frame_botoes = tk.Frame(conteudo, bg="white")
        frame_botoes.pack(pady=15)
        
        def remover_selecionado():
            selecao = tree.selection()
            if not selecao:
                messagebox.showwarning("Aviso", "Selecione um elemento para remover.")
                return
            item = tree.item(selecao[0])
            id_elemento = item['values'][0]
            if messagebox.askyesno("Confirmar Remoção", f"Deseja realmente remover o momento ID:{id_elemento}?\n\nEsta ação não pode ser desfeita."):
                self.salvar_estado()
                self.viga.remover_elemento(id_elemento)
                self.desenhar_diagrama_corpo_livre()
                self.label_info.config(text=f"Momento ID:{id_elemento} removido com sucesso!")
                novo_frame = self.criar_frame_remover_momentos()
                self.frames_operacoes["Remover Momento"] = novo_frame
                if self.layout_modificado:
                    self.trocar_frame_operacao(novo_frame)
        
        tk.Button(frame_botoes, text="🗑 Remover Selecionado", command=remover_selecionado,
            bg="#e74c3c", fg="white", font=("Arial", 10, "bold"), padx=15, pady=8, relief="flat", cursor="hand2").pack(side=tk.LEFT, padx=5)
        return frame
    
    def ao_adicionar_elemento(self, elemento):
        self.label_selecao.config(text=f"Adicionar: {elemento}")
        
        if elemento == "Carga Concentrada":
            novo_frame = self.criar_formulario_carga_concentrada()
        elif elemento == "Carga Distribuída":
            novo_frame = self.criar_formulario_carga_distribuida()
        elif elemento == "Momento":
            novo_frame = self.criar_formulario_momento()
        elif elemento == "Apoio":
            novo_frame = self.criar_formulario_apoio()
        else:
            return
        
        self.frames_operacoes[elemento] = novo_frame
        
        if self.layout_modificado:
            self.trocar_frame_operacao(novo_frame)
        else:
            self.iniciar_animacao_frame_operacao(novo_frame)
    
    def ao_editar_elemento(self, elemento):
        self.label_selecao.config(text=f"Editar: {elemento}")
        
        if not self.viga.criada:
            messagebox.showinfo("Aviso", "Crie a viga primeiro!")
            return
        
        if elemento == "Editar Carga":
            novo_frame = self.criar_frame_editar_cargas()
        elif elemento == "Editar Apoio":
            novo_frame = self.criar_frame_editar_apoios()
        elif elemento == "Editar Comprimento":
            novo_frame = self.criar_frame_editar_comprimento()
        else:
            return
        
        self.frames_operacoes[elemento] = novo_frame
        
        if self.layout_modificado:
            self.trocar_frame_operacao(novo_frame)
        else:
            self.iniciar_animacao_frame_operacao(novo_frame)
    
    def ao_remover_elemento(self, elemento):
        self.label_selecao.config(text=f"Remover: {elemento}")
        
        if not self.viga.criada:
            messagebox.showinfo("Aviso", "Crie a viga primeiro!")
            return
        
        if elemento == "Remover Carga":
            novo_frame = self.criar_frame_remover_cargas()
        elif elemento == "Remover Apoio":
            novo_frame = self.criar_frame_remover_apoios()
        elif elemento == "Remover Momento":
            novo_frame = self.criar_frame_remover_momentos()
        elif elemento == "Limpar Tudo":
            if messagebox.askyesno("Confirmar", "Tem certeza que deseja remover TODOS os elementos?\n\nEsta ação não pode ser desfeita!\nA viga será mantida."):
                self.salvar_estado()
                self.viga.limpar_tudo()
                self.viga.criada = True
                self.desenhar_diagrama_corpo_livre()
                self.label_info.config(text="Todos os elementos foram removidos")
                self.atualizar_frames_abertos()
            return
        else:
            return
        
        self.frames_operacoes[elemento] = novo_frame
        
        if self.layout_modificado:
            self.trocar_frame_operacao(novo_frame)
        else:
            self.iniciar_animacao_frame_operacao(novo_frame)
    
    def mostrar_diagramas(self):
        if self.layout_modificado:
            self.label_info.config(text="Mostrando diagramas...")
            self.restaurar_layout_original()
    
    def trocar_frame_operacao(self, novo_frame):
        if self.frame_atual and self.frame_atual.winfo_exists():
            self.frame_atual.place_forget()
        self.frame_atual = novo_frame
        if novo_frame and novo_frame.winfo_exists():
            novo_frame.place(x=10, y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
        self.root.update_idletasks()
    
    def iniciar_animacao_frame_operacao(self, frame_operacao):
        if self.animacao_em_andamento:
            return
        
        self.animacao_em_andamento = True
        self.frame_atual = frame_operacao
        
        if self.largura_frame == 0:
            self.atualizar_dimensoes()
        
        self.preparar_animacao()
        
        self.frame_esquerdo.place(x=10, y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
        self.frame_direito.place(x=self.largura_frame + 5, y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
        frame_operacao.place(x=-self.largura_frame - 10, y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
        
        self.root.update_idletasks()
        
        self.animacao_tempo_inicio = time.time()
        self.animacao_duracao = 0.8
        self.animacao_direcao = "direita"
        
        self.posicoes_iniciais = {'operacao': -self.largura_frame - 10, 'esquerdo': 10, 'direito': self.largura_frame + 5}
        self.posicoes_finais = {'operacao': 10, 'esquerdo': self.largura_frame + 5, 'direito': self.largura_total + 10}
        
        self.executar_frame_animacao(frame_operacao)
    
    def preparar_animacao(self):
        self.root.update_idletasks()
        try:
            self.canvas_fundo.tkraise()
        except:
            pass
        self.frame_esquerdo.grid_remove()
        self.frame_direito.grid_remove()
        if self.frame_atual and self.frame_atual.winfo_exists():
            self.frame_atual.place_forget()
        self.root.update_idletasks()
    
    def executar_frame_animacao(self, frame_operacao):
        if not self.animacao_em_andamento:
            return
        try:
            tempo_atual = time.time()
            tempo_decorrido = tempo_atual - self.animacao_tempo_inicio
            progresso_raw = min(tempo_decorrido / self.animacao_duracao, 1.0)
            progresso = self.easing_ease_in_out_cubic(progresso_raw)
            self.atualizar_posicoes_frames(progresso, frame_operacao)
            if progresso_raw < 1.0:
                delay = max(1, int(self.frame_interval))
                self.root.after(delay, lambda: self.executar_frame_animacao(frame_operacao))
            else:
                self.finalizar_animacao_operacao(frame_operacao)
        except Exception as e:
            print(f"Erro na animação: {e}")
            self.animacao_em_andamento = False
    
    def atualizar_posicoes_frames(self, progresso, frame_operacao):
        try:
            pos_operacao = self.interpolar(self.posicoes_iniciais['operacao'], self.posicoes_finais['operacao'], progresso)
            if frame_operacao and frame_operacao.winfo_exists():
                frame_operacao.place_configure(x=int(pos_operacao), y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
            
            pos_esquerdo = self.interpolar(self.posicoes_iniciais['esquerdo'], self.posicoes_finais['esquerdo'], progresso)
            if self.frame_esquerdo.winfo_exists():
                self.frame_esquerdo.place_configure(x=int(pos_esquerdo), y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
            
            pos_direito = self.interpolar(self.posicoes_iniciais['direito'], self.posicoes_finais['direito'], progresso)
            if self.frame_direito.winfo_exists():
                self.frame_direito.place_configure(x=int(pos_direito), y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
            
            self.root.update_idletasks()
        except Exception as e:
            print(f"Erro ao atualizar posições: {e}")
    
    def finalizar_animacao_operacao(self, frame_operacao):
        try:
            self.atualizar_dimensoes()
            if frame_operacao and frame_operacao.winfo_exists():
                frame_operacao.place_configure(x=10, y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
            self.frame_esquerdo.place_configure(x=self.largura_frame + 5, y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
            self.frame_direito.place_configure(x=self.largura_total + 10, y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
            self.root.update_idletasks()
            self.layout_modificado = True
            self.animacao_em_andamento = False
        except Exception as e:
            print(f"Erro ao finalizar animação: {e}")
            self.animacao_em_andamento = False
    
    def restaurar_layout_original(self):
        if self.animacao_em_andamento or not self.layout_modificado:
            return
        try:
            self.animacao_em_andamento = True
            self.atualizar_dimensoes()
            self.frame_direito.place(x=self.largura_total + 10, y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
            frame_operacao = self.frame_atual
            self.root.update_idletasks()
            self.animacao_tempo_inicio = time.time()
            self.animacao_duracao = 0.8
            self.animacao_direcao = "esquerda"
            self.posicoes_iniciais = {'operacao': 10, 'esquerdo': self.largura_frame + 5, 'direito': self.largura_total + 10}
            self.posicoes_finais = {'operacao': -self.largura_frame - 10, 'esquerdo': 10, 'direito': self.largura_frame + 5}
            self.executar_frame_animacao_restauracao(frame_operacao)
        except Exception as e:
            print(f"Erro ao restaurar layout: {e}")
            self.animacao_em_andamento = False
    
    def executar_frame_animacao_restauracao(self, frame_operacao):
        if not self.animacao_em_andamento:
            return
        try:
            tempo_atual = time.time()
            tempo_decorrido = tempo_atual - self.animacao_tempo_inicio
            progresso_raw = min(tempo_decorrido / self.animacao_duracao, 1.0)
            progresso = self.easing_ease_in_out_cubic(progresso_raw)
            
            if frame_operacao and frame_operacao.winfo_exists():
                pos_operacao = self.interpolar(self.posicoes_iniciais['operacao'], self.posicoes_finais['operacao'], progresso)
                frame_operacao.place_configure(x=int(pos_operacao), y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
            pos_esquerdo = self.interpolar(self.posicoes_iniciais['esquerdo'], self.posicoes_finais['esquerdo'], progresso)
            self.frame_esquerdo.place_configure(x=int(pos_esquerdo), y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
            pos_direito = self.interpolar(self.posicoes_iniciais['direito'], self.posicoes_finais['direito'], progresso)
            self.frame_direito.place_configure(x=int(pos_direito), y=self.pos_y_frame, width=self.largura_frame, height=self.altura_frame)
            self.root.update_idletasks()
            
            if progresso_raw < 1.0:
                delay = max(1, int(self.frame_interval))
                self.root.after(delay, lambda: self.executar_frame_animacao_restauracao(frame_operacao))
            else:
                self.finalizar_restauracao(frame_operacao)
        except Exception as e:
            print(f"Erro na restauração: {e}")
            self.animacao_em_andamento = False
    
    def finalizar_restauracao(self, frame_operacao):
        try:
            if frame_operacao and frame_operacao.winfo_exists():
                frame_operacao.place_forget()
            self.frame_esquerdo.place_forget()
            self.frame_direito.place_forget()
            self.root.update_idletasks()
            self.frame_esquerdo.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
            self.frame_direito.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
            self.root.update_idletasks()
            self.layout_modificado = False
            self.animacao_em_andamento = False
            self.frame_atual = None
            self.label_info.config(text="Diagramas restaurados com sucesso")
        except Exception as e:
            print(f"Erro ao finalizar restauração: {e}")
            self.animacao_em_andamento = False
    
    def ao_redimensionar(self, event):
        if event.widget == self.root and not self.animacao_em_andamento:
            if self.redimensionamento_timer:
                self.root.after_cancel(self.redimensionamento_timer)
            self.redimensionamento_timer = self.root.after(100, self.atualizar_dimensoes)
    
    def atualizar_dimensoes(self):
        try:
            self.root.update_idletasks()
            largura_total = self.container_principal.winfo_width()
            altura_total = self.container_principal.winfo_height()
            if largura_total > 100 and altura_total > 50:
                nova_largura_frame = (largura_total - 15) // 2
                nova_altura_frame = altura_total - 20
                if (abs(nova_largura_frame - self.largura_frame) > 5 or 
                    abs(nova_altura_frame - self.altura_frame) > 5 or self.largura_frame == 0):
                    self.largura_frame = nova_largura_frame
                    self.altura_frame = nova_altura_frame
                    self.pos_y_frame = 10
                    self.largura_total = largura_total
                    self.canvas_fundo.configure(width=largura_total, height=altura_total)
                    self.redesenhar_planos()
                    if self.layout_modificado and self.frame_atual and self.frame_atual.winfo_exists():
                        self.frame_atual.place_configure(width=self.largura_frame, height=self.altura_frame)
                        self.frame_esquerdo.place_configure(width=self.largura_frame, height=self.altura_frame)
        except Exception as e:
            print(f"Erro ao atualizar dimensões: {e}")
    
    def redesenhar_planos(self):
        try:
            if hasattr(self, 'fig_esquerdo'):
                self.fig_esquerdo.tight_layout()
                self.canvas_esquerdo.draw()
            if hasattr(self, 'fig_direito_sup'):
                self.fig_direito_sup.tight_layout()
                self.canvas_direito_sup.draw()
            if hasattr(self, 'fig_direito_inf'):
                self.fig_direito_inf.tight_layout()
                self.canvas_direito_inf.draw()
        except:
            pass
    
    def interpolar(self, inicio, fim, progresso):
        return inicio + (fim - inicio) * progresso
    
    def easing_ease_in_out_cubic(self, t):
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2

def main():
    root = tk.Tk()
    app = Aplicacao(root)
    root.mainloop()

if __name__ == "__main__":
    main()
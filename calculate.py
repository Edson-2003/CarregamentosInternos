import numpy as np

class VigaEngine:
    def __init__(self):
        self.comprimento = 10.0
        self.tipo_apoio = "Pino e Rolete"
        self.pos_apoio1 = 0.0
        self.pos_apoio2 = 10.0
        self.carregamentos = []
        self.reacoes = {}
        
        self.x_vals = np.linspace(0, self.comprimento, 1000)
        self.cortante = np.zeros_like(self.x_vals)
        self.momento = np.zeros_like(self.x_vals)

    def atualizar_geometria(self, L, tipo, p1, p2):
        self.comprimento = L
        self.tipo_apoio = tipo
        self.pos_apoio1 = p1
        self.pos_apoio2 = p2
        self.x_vals = np.linspace(0, self.comprimento, 1000)

    def adicionar_carga(self, tipo, val1, pos1, val2=0, pos2=0):
        self.carregamentos.append({
            'tipo': tipo, 'val1': val1, 'pos1': pos1, 'val2': val2, 'pos2': pos2
        })

    def remover_carga(self, index):
        if 0 <= index < len(self.carregamentos):
            self.carregamentos.pop(index)

    def calcular_reacoes(self):
        F_ext = 0
        M_ext_0 = 0

        for c in self.carregamentos:
            if c['tipo'] == 'Concentrada':
                F_ext += c['val1']
                M_ext_0 += c['val1'] * c['pos1']
            elif c['tipo'] == 'Momento Concentrado':
                M_ext_0 += c['val1'] 
            elif c['tipo'] == 'Distribuída Constante':
                comp_carga = c['pos2'] - c['pos1']
                força_eq = c['val1'] * comp_carga
                pos_eq = c['pos1'] + comp_carga / 2
                F_ext += força_eq
                M_ext_0 += força_eq * pos_eq
            elif c['tipo'] == 'Distribuída Linear':
                comp_carga = c['pos2'] - c['pos1']
                f_ret = c['val1'] * comp_carga
                pos_ret = c['pos1'] + comp_carga / 2
                f_tri = (c['val2'] - c['val1']) * comp_carga / 2
                pos_tri = c['pos1'] + (2/3 if c['val2'] > c['val1'] else 1/3) * comp_carga
                F_ext += f_ret + f_tri
                M_ext_0 += (f_ret * pos_ret) + (f_tri * pos_tri)

        self.reacoes.clear()

        if self.tipo_apoio == "Pino e Rolete":
            if self.pos_apoio1 == self.pos_apoio2:
                raise ValueError("Apoios não podem estar na mesma posição.")
            R2 = (-M_ext_0 - F_ext * self.pos_apoio1) / (self.pos_apoio2 - self.pos_apoio1)
            R1 = -F_ext - R2
            self.reacoes['R1_y'] = R1
            self.reacoes['R2_y'] = R2
            
        elif self.tipo_apoio == "Engaste":
            R_y = -F_ext
            M_eng = -M_ext_0 - (F_ext * self.pos_apoio1)
            self.reacoes['R_y'] = R_y
            self.reacoes['M_eng'] = M_eng

    def calcular_diagramas(self):
        self.calcular_reacoes()
        self.cortante = np.zeros_like(self.x_vals)
        self.momento = np.zeros_like(self.x_vals)

        for i, x in enumerate(self.x_vals):
            V = 0
            M = 0

            if self.tipo_apoio == "Pino e Rolete":
                if x > self.pos_apoio1 or np.isclose(x, self.pos_apoio1):
                    V += self.reacoes['R1_y']
                    M += self.reacoes['R1_y'] * (x - self.pos_apoio1)
                if x > self.pos_apoio2 or np.isclose(x, self.pos_apoio2):
                    V += self.reacoes['R2_y']
                    M += self.reacoes['R2_y'] * (x - self.pos_apoio2)
            elif self.tipo_apoio == "Engaste":
                if x > self.pos_apoio1 or np.isclose(x, self.pos_apoio1):
                    V += self.reacoes['R_y']
                    M += self.reacoes['R_y'] * (x - self.pos_apoio1)
                    M += self.reacoes['M_eng']

            for c in self.carregamentos:
                if c['tipo'] == 'Concentrada' and (x > c['pos1'] or np.isclose(x, c['pos1'])):
                    V += c['val1']
                    M += c['val1'] * (x - c['pos1'])
                elif c['tipo'] == 'Momento Concentrado' and (x > c['pos1'] or np.isclose(x, c['pos1'])):
                    M -= c['val1']
                elif c['tipo'] in ['Distribuída Constante', 'Distribuída Linear']:
                    x_start = c['pos1']
                    x_end = c['pos2']
                    if x > x_start:
                        x_efetivo = min(x, x_end)
                        dx = x_efetivo - x_start
                        if c['tipo'] == 'Distribuída Constante':
                            w_atual = c['val1']
                            f_eq = w_atual * dx
                            pos_eq = x_start + dx / 2
                        else:
                            w1 = c['val1']
                            w2 = c['val2']
                            taxa = (w2 - w1) / (x_end - x_start)
                            w_atual = w1 + taxa * dx
                            f_eq = (w1 + w_atual) / 2 * dx
                            if dx > 0:
                                d_cg = dx/3 * ((2*w_atual + w1)/(w_atual + w1))
                                pos_eq = x_start + d_cg
                            else:
                                pos_eq = x_start
                        V += f_eq
                        M += f_eq * (x - pos_eq)

            self.cortante[i] = V
            self.momento[i] = M

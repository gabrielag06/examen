"""
Simulador Monte Carlo de calendarización de trabajos (scheduling) con regla FIFO.
Examen Argumentativo Módulo 4-5 - Ma2004b Modelos de optimización.

Solo usa la biblioteca estándar de Python (tkinter, random, csv, statistics),
así el ejecutable sale ligero y portable.

Uso:
    python3 simulador.py  abre la interfaz gráfica
    python3 simulador.py --consola corre con parámetros por defecto, sin ventana
"""

import csv
import os
import random
import statistics
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path



# CLASES DEL MODELO

# son los factores de entrada que se pueden parametrizar desde la interfaz. 
@dataclass
class Parametros:
    """Factores de entrada (todos parametrizables desde la interfaz)."""
    min_trabajos: int = 20 #rangos de trabajo y máquina
    max_trabajos: int = 30
    min_maquinas: int = 3
    max_maquinas: int = 5
    cantidades: tuple = (10, 20, 30) # elementos posiblespor trabajo
    rates: tuple = (5, 10, 15)  # unidades por hora (rates) posibles
    n_simulaciones: int = 20 #num de simulaciones
    semilla: object = None  # semilla opcional None = aleatoria
    fecha_inicio: datetime = None # para fechaHoraInicio / fechaHoraFin


class Trabajo:
    """ Un trabajo: guarda su cantidad de elementos y una lista rates (u/h) 
    para cada máquina. Se asigna a una máquina al azar y se calcula su inicio y fin."""

    def __init__(self, id_trabajo, cantidad, rates_por_maquina):
        self.id = id_trabajo
        self.cantidad = cantidad
        self.rates = rates_por_maquina # lista, índice 0..m-1
        self.maquina = None   # id de máquina (1..m)
        self.orden = 0  # posición en la cola de su máquina
        self.inicio_h = 0.0
        self.fin_h = 0.0

    def duracion_en(self, indice_maquina):
        """Tiempo = cantidad de elementos / rate del trabajo en esa máquina."""
        return self.cantidad / self.rates[indice_maquina] # cantidad/rate de ese trabajo en esamáquina


class Maquina:
    """Una máquina con cola FIFO: primer trabajo que llega, primero que se atiende.
    guarda su id, índice y la lista de trabajos que atendió.también guarda el instante en que termina el último trabajo."""

    def __init__(self, id_maquina, indice):
        self.id = id_maquina
        self.indice = indice
        self.trabajos = []
        self.libre_en_h = 0.0 # tiempo en que termina el último trabajo

    def atender(self, trabajo): # asigna un trabajo a la máquina y calcula su inicio y fin
        trabajo.maquina = self.id
        trabajo.orden = len(self.trabajos) + 1 # posición en la cola
        trabajo.inicio_h = self.libre_en_h  # todos llegan en t = 0
        trabajo.fin_h = trabajo.inicio_h + trabajo.duracion_en(self.indice) # calcula el fin sumando la duración
        self.libre_en_h = trabajo.fin_h # actualiza el tiempo en que la máquina queda libre
        self.trabajos.append(trabajo)


class ResultadoSimulacion:
    """Resultado de una corrida (una combinación de factores). 
    recibe los trabajos y máquinas y calcula estadísticos."""

    def __init__(self, numero, trabajos, maquinas):
        self.numero = numero
        self.trabajos = trabajos
        self.maquinas = maquinas
        self.n_trabajos = len(trabajos)
        self.n_maquinas = len(maquinas)
        self.makespan = max(m.libre_en_h for m in maquinas) # el mayor tiempo en que una máquina termina su último trabajo
        self.total_elementos = sum(t.cantidad for t in trabajos) # total de elementos de todos los trabajos
        # rate promedio de los trabajos en la máquina que les tocó
        self.rate_promedio = statistics.mean(
            t.rates[t.maquina - 1] for t in trabajos)
        carga_total = sum(m.libre_en_h for m in maquinas)
        # utilización = tiempo ocupado total / (máquinas * makespan)
        self.utilizacion = carga_total / (self.n_maquinas * self.makespan) # carga total de todas las máquinas. 100% es perfecta utilización
        self.maquina_critica = max(maquinas, key=lambda m: m.libre_en_h).id # es la que termina al final y define el makespan


class Simulacion:
    """ simulación Monte Carlo completa. Todos los factores se generan a partir
    de números uniformes estándar U(0,1) transformados a sus rangos. recibe los parámetros y 
    un generador de números aleatorios (random.Random)."""

    def __init__(self, params, rng):
        self.p = params
        self.rng = rng

    #  Generador base: número aleatorio uniforme estándar U(0,1) 
    def _u(self):
        return self.rng.random() # u en [0, 1)

    def _entero(self, a, b):
        """da un entero entre a y b (extremos incluidos) y con la misma prob a cada uno.
        sirve para generar el número de trabajos, máquinas y la máquina a la que se asigna un trabajo."""
        return a + int(self._u() * (b - a + 1))

    def _elegir(self, valores):
        """escoge un valor de la lista; cada uno con probabilidad 1/k. 
        sirve para elegir la cantidad de elementos (10,20,30)y el rate de cada trabajo (5,10,15)."""
        return valores[int(self._u() * len(valores))]

    def ejecutar(self, numero): 
        """Ejecuta una simulación completa. genera trabajos y máquinas, los asigna y calcula estadísticos."""
        p = self.p
        n = self._entero(p.min_trabajos, p.max_trabajos) # trabajos: 20 a 30
        m = self._entero(p.min_maquinas, p.max_maquinas) # máquinas: 3 a 5
        trabajos = [
            Trabajo(i + 1,
                    self._elegir(p.cantidades),  # 10, 20 o 30
                    [self._elegir(p.rates) for _ in range(m)]) # 5, 10 o 15
            for i in range(n)
        ]
        maquinas = [Maquina(k + 1, k) for k in range(m)]
        # los trabajos llegan en orden de id, cada uno se asigna a una máquina al azar
        for t in trabajos:
            maquinas[self._entero(0, m - 1)].atender(t) # FIFO por máquina
        return ResultadoSimulacion(numero, trabajos, maquinas)


class Experimento:
    #Corre varias simulaciones, calcula estadísticos y exporta archivos

    def __init__(self, params):
        self.p = params
        self.rng = random.Random(params.semilla)
        self.resultados = []

    def ejecutar(self):
        sim = Simulacion(self.p, self.rng)
        self.resultados = [sim.ejecutar(i + 1) for i in range(self.p.n_simulaciones)]
        return self.resultados

    def estadisticos(self):
 # se calculan sobre los makespan de cada corrida: promedio, máximo, mínimo, rango y desviación estándar
        mk = [r.makespan for r in self.resultados]
        return {"promedio": statistics.mean(mk), "maximo": max(mk), "minimo": min(mk),
                "rango": max(mk) - min(mk),
                "desviacion": statistics.stdev(mk) if len(mk) > 1 else 0.0}

    def parametros_texto(self):
        # devuelve los factores de entrada con los que se corrió el experimento
        p = self.p
        inicio = (p.fecha_inicio.strftime("%Y-%m-%d %H:%M")
                  if p.fecha_inicio else "hora de la corrida")
        return [("Trabajos (uniforme entero)", f"{p.min_trabajos} a {p.max_trabajos}"),
                ("Maquinas (uniforme entero)", f"{p.min_maquinas} a {p.max_maquinas}"),
                ("Elementos por trabajo", ", ".join(map(str, p.cantidades))),
                ("Rates (u/h)", ", ".join(map(str, p.rates))),
                ("Numero de simulaciones", p.n_simulaciones),
                ("Semilla", p.semilla if p.semilla is not None else "aleatoria"),
                ("Fecha y hora de inicio", inicio),
                ("Regla de secuenciacion", "FIFO")]

    def exportar(self, carpeta):
        # exporta los archivos de secuenciación y resumen de resultados
        carpeta = Path(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        t0 = self.p.fecha_inicio or datetime.now().replace(second=0, microsecond=0)
        fmt = "%Y-%m-%d %H:%M:%S"

        # Secuenciación de todas las simulaciones
        ruta_sec = carpeta / "secuenciacion.csv"
        with open(ruta_sec, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Simulacion", "Maquina", "idTrabajo", "fechaHoraInicio",
                        "fechaHoraFin", "OrdenSecuenciacion", "IdProducto",
                        "Cantidad", "Rate_u_por_h", "Duracion_h"])
            for r in self.resultados:
                for m in r.maquinas:
                    for t in m.trabajos:
                        w.writerow([
                            r.numero, m.id, t.id,
                            (t0 + timedelta(hours=t.inicio_h)).strftime(fmt),
                            (t0 + timedelta(hours=t.fin_h)).strftime(fmt),
                            t.orden, f"P{t.id}",
                            t.cantidad, t.rates[m.indice],
                            round(t.fin_h - t.inicio_h, 4)])

        # Resumen por simulación (parámetros, makespan)
        ruta_res = carpeta / "resultados_simulaciones.csv"
        with open(ruta_res, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Simulacion", "NumTrabajos", "NumMaquinas",
                        "TotalElementos", "RatePromedioAsignado",
                        "Makespan_h", "Utilizacion", "MaquinaCritica"])
            for r in self.resultados:
                w.writerow([r.numero, r.n_trabajos, r.n_maquinas,
                            r.total_elementos, round(r.rate_promedio, 3),
                            round(r.makespan, 4), round(r.utilizacion, 4),
                            r.maquina_critica])
            e = self.estadisticos()
            w.writerow([])
            w.writerow(["Promedio makespan", round(e["promedio"], 4)])
            w.writerow(["Maximo makespan", round(e["maximo"], 4)])
            w.writerow(["Minimo makespan", round(e["minimo"], 4)])
            w.writerow(["Rango (max - min)", round(e["rango"], 4)])
            w.writerow(["Desviacion estandar", round(e["desviacion"], 4)])
            w.writerow([])
            w.writerow(["Parametros de entrada"])
            for etiqueta, valor in self.parametros_texto():
                w.writerow([etiqueta, valor])
        return ruta_sec, ruta_res



# carpeta para los archivos de salida 

def carpeta_base():
    """Carpeta junto al ejecutable (o junto al .py si se corre desde código)."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        if sys.platform == "darwin" and ".app/Contents/MacOS" in str(exe):
            return exe.parents[3]          # carpeta que contiene el .app
        return exe.parent
    return Path(__file__).resolve().parent


def abrir_carpeta(ruta):
    try:
        if sys.platform == "win32":
            os.startfile(str(ruta))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(ruta)])
        else:
            subprocess.Popen(["xdg-open", str(ruta)])
    except Exception:
        pass


def lista_enteros(texto):
    valores = tuple(int(x.strip()) for x in texto.split(",") if x.strip())
    if not valores or any(v <= 0 for v in valores):
        raise ValueError("Escribe enteros positivos separados por comas.")
    return valores


def texto_resumen(exp):
    e = exp.estadisticos()
    return (f"Simulaciones: {len(exp.resultados)}\n"
            f"Makespan promedio: {e['promedio']:.3f} h\n"
            f"Makespan máximo:   {e['maximo']:.3f} h\n"
            f"Makespan mínimo:   {e['minimo']:.3f} h\n"
            f"Rango (máx - mín): {e['rango']:.3f} h\n"
            f"Desv. estándar:    {e['desviacion']:.3f} h")



# INTERFAZ GRÁFICA

def lanzar_interfaz():
    import tkinter as tk
    from tkinter import filedialog, font as tkfont, messagebox, ttk

    #  paleta 

    FONDO, TARJETA, BORDE, BORDE_SUAVE = "#FBF9FF", "#FFFFFF", "#EAE5F6", "#F4F0FB"
    TINTA, GRIS, GRIS_CLARO = "#2F2B4F", "#6A6688", "#9C99B5"
    PRIMARIO, PRIMARIO_OSC, PRIMARIO_SUAVE = "#B9B6F2", "#A19DEA", "#EEEDFD"
    ACENTO = "#5A52C8"                        # lavanda fuerte: SOLO para letras
    VERDE, ROJO, AMBAR = "#8FD9BC", "#F5A9AF", "#F8D48E"
    VERDE_T, ROJO_T = "#2F8F6B", "#C0444F"    # verde y rojo fuertes: SOLO para letras
    ENC_A, ENC_B = "#E2DEFB", "#CFE8F7"       # encabezado: lavanda -> celeste
    TABLA_ENC, TABLA_ENC_HOVER = "#DDD9F8", "#CBC6F2"
    FILA_ALT, FILA_MEJOR, FILA_PEOR = "#FAF9FE", "#DDF5EA", "#FDE5E7"
    TEXTO_BLOQUE = "#2F2B4F"                  # letra oscura sobre los bloques del Gantt
    PALETA = ["#A5B4FC", "#99F6E4", "#FDE68A", "#FCA5A5", "#C4B5FD", "#86EFAC",
              "#F9A8D4", "#7DD3FC", "#FDBA74", "#BEF264", "#F0ABFC", "#67E8F9"]
    F = {}   # fuentes (se llenan al crear la ventana)

    def mezclar(c1, c2, t):
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))

    def rect_red(c, x0, y0, x1, y1, r=6, **kw):
        r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return c.create_polygon(pts, smooth=True, **kw)

    #  botón plano con efecto hover 
    class Boton(tk.Label):
        def __init__(self, padre, texto, comando, primario=False, fuente=None,
                     pady=8, bg_padre=TARJETA):
            self.primario = primario
            self.normal = PRIMARIO if primario else TARJETA
            self.encima = PRIMARIO_OSC if primario else PRIMARIO_SUAVE
            super().__init__(padre, text=texto, bg=self.normal,
                             fg=TINTA if primario else ACENTO,
                             font=fuente or F["texto_b"], cursor="hand2",
                             padx=14, pady=pady, highlightthickness=0 if primario else 1,
                             highlightbackground=BORDE)
            self.comando = comando
            self.bind("<Enter>", lambda _e: self.configure(bg=self.encima))
            self.bind("<Leave>", lambda _e: self.configure(bg=self.normal))
            self.bind("<ButtonRelease-1>", self._soltar)

        def _soltar(self, e):
            if 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
                self.comando()

    #  tabla tipo hoja de cálculo 
    class Tabla(tk.Frame):
        def __init__(self, padre, columnas, formato=None, etiquetar=None,
                     al_abrir=None, vacio="", alto=None, ordenable=True):
            super().__init__(padre, bg=TARJETA)
            self.columnas = columnas              # (título, ancho, ancla)
            self.formato = formato or {}          # índice , función de formato
            self.etiquetar = etiquetar            # fila, "mejor" / "peor" / None
            self.al_abrir = al_abrir
            self.ordenable = ordenable
            self.filas, self.visibles = [], []
            self.col_orden, self.desc = None, False
            ids = [f"c{i}" for i in range(len(columnas))]
            kw = {"height": alto} if alto else {}
            self.arbol = ttk.Treeview(self, columns=ids, show="headings",
                                      selectmode="browse", **kw)
            for i, (titulo, ancho, ancla) in enumerate(columnas):
                cmd = (lambda i=i: self._ordenar(i)) if ordenable else ""
                self.arbol.heading(f"c{i}", text=titulo, anchor=ancla, command=cmd)
                self.arbol.column(f"c{i}", width=ancho, minwidth=40, anchor=ancla)
            self.arbol.tag_configure("par", background=FILA_ALT)
            self.arbol.tag_configure("mejor", background=FILA_MEJOR, font=F["texto_b"])
            self.arbol.tag_configure("peor", background=FILA_PEOR)
            self.columnconfigure(0, weight=1)
            self.rowconfigure(0, weight=1)
            self.arbol.grid(row=0, column=0, sticky="nsew")
            if not alto:
                sb = ttk.Scrollbar(self, orient="vertical", command=self.arbol.yview)
                self.arbol.configure(yscrollcommand=sb.set)
                sb.grid(row=0, column=1, sticky="ns")
            self.aviso = tk.Label(self, text=vacio, bg=TARJETA, fg=GRIS_CLARO,
                                  font=F["texto"])
            self.aviso.place(relx=0.5, rely=0.5, anchor="center")
            if al_abrir:
                self.arbol.bind("<Double-1>", self._doble)

        def poner_filas(self, filas, reiniciar_orden=True):
            self.filas = list(filas)
            if reiniciar_orden:
                self.col_orden, self.desc = None, False
            self._pintar()

        def _ordenar(self, i):
            if self.col_orden == i:
                self.desc = not self.desc
            else:
                self.col_orden, self.desc = i, False
            self._pintar()

        def _pintar(self):
            for i, (titulo, _, _) in enumerate(self.columnas):
                flecha = ""
                if i == self.col_orden:
                    flecha = "  ▼" if self.desc else "  ▲"
                self.arbol.heading(f"c{i}", text=titulo + flecha)
            self.arbol.delete(*self.arbol.get_children())
            filas = self.filas
            if self.col_orden is not None:
                filas = sorted(filas, key=lambda f: f[self.col_orden], reverse=self.desc)
            self.visibles = filas
            if filas:
                self.aviso.place_forget()
            else:
                self.aviso.place(relx=0.5, rely=0.5, anchor="center")
            for k, fila in enumerate(filas):
                valores = [self.formato[j](v) if j in self.formato else v
                           for j, v in enumerate(fila)]
                tag = self.etiquetar(fila) if self.etiquetar else None
                tags = (tag,) if tag else (("par",) if k % 2 else ())
                self.arbol.insert("", "end", iid=str(k), values=valores, tags=tags)

        def _doble(self, evento):
            iid = self.arbol.identify_row(evento.y)
            if iid:
                self.al_abrir(self.visibles[int(iid)])

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self._fuentes()
            self.title("Simulador Monte Carlo · Calendarización FIFO")
            self.geometry("1360x820")
            self.minsize(1120, 700)
            self.configure(bg=FONDO)
            self.carpeta_salida = carpeta_base() / "resultados"
            self.vars = {}
            self.filas = [] # filas crudas de la pestaña Resumen
            self.resultados = []  # objetos ResultadoSimulacion
            self.sim_actual = None
            self.t0 = None
            self.barras, self.hover = [], None # gráfica de barras
            self.bloques, self.hover_b = [], None  # Gantt
            self.raton = (0, 0)
            self.mejor_mk = self.peor_mk = None
            self.pagina = "resumen"
            self._anim = {}
            self._estilos()
            self._crear_widgets()
            self.bind("<Return>", lambda _e: self._simular())
            self.bind("<Left>", lambda _e: self._tecla(-1))
            self.bind("<Right>", lambda _e: self._tecla(1))
            for n, clave in enumerate(("resumen", "sec", "res", "gantt"), start=1):
                for mod in ("Control", "Command"):
                    try:
                        self.bind(f"<{mod}-Key-{n}>", lambda _e, c=clave: self._mostrar(c))
                    except tk.TclError:
                        pass

        #  tipografía 
        def _fuentes(self):
            disponibles = set(tkfont.families(self))

            def elegir(candidatas, defecto):
                return next((n for n in candidatas if n in disponibles), defecto)

            sans = elegir(["Verdana","Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue",
                           "Avenir Next", "Ubuntu", "Noto Sans", "Helvetica", "Arial"],
                          "Helvetica")
            disp = elegir(["Gill Sans","Poppins", "Montserrat", "Segoe UI Semibold", "SF Pro Display",
                           "Avenir Next", "Helvetica Neue", "Ubuntu", "Noto Sans"], sans)
            F.update(texto=(sans, 11), texto_b=(sans, 11, "bold"), chico=(sans, 9),
                     mini=(sans, 8), tab=(disp, 11, "bold"), titulo=(disp, 25, "bold"),
                     h2=(disp, 13, "bold"), h3=(disp, 11, "bold"),
                     num=(disp, 24, "bold"), boton=(disp, 13, "bold"))
            self.option_add("*TCombobox*Listbox.font", F["texto"])

        # estilos ttk 
        def _estilos(self):
            s = ttk.Style(self)
            s.theme_use("clam")   # se ve igual en Mac y Windows
            s.configure(".", background=FONDO, foreground=TINTA, font=F["texto"])
            s.configure("TFrame", background=FONDO)
            s.configure("Campo.TEntry", fieldbackground=TARJETA, foreground=TINTA,
                        bordercolor=BORDE, lightcolor=BORDE, darkcolor=BORDE,
                        padding=(8, 5), insertcolor=TINTA)
            s.map("Campo.TEntry", bordercolor=[("focus", PRIMARIO)],
                  lightcolor=[("focus", PRIMARIO)], darkcolor=[("focus", PRIMARIO)])
            s.configure("TCombobox", fieldbackground=TARJETA, background=TARJETA,
                        foreground=TINTA, bordercolor=BORDE, lightcolor=BORDE,
                        darkcolor=BORDE, arrowcolor=ACENTO, padding=(8, 4))
            s.map("TCombobox", fieldbackground=[("readonly", TARJETA)],
                  selectbackground=[("readonly", TARJETA)],
                  selectforeground=[("readonly", TINTA)],
                  bordercolor=[("focus", PRIMARIO)])
            s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
            s.configure("Treeview", rowheight=28, background=TARJETA,
                        fieldbackground=TARJETA, foreground=TINTA, borderwidth=0,
                        font=F["texto"])
            s.map("Treeview", background=[("selected", PRIMARIO_SUAVE)],
                  foreground=[("selected", TINTA)])
            s.configure("Treeview.Heading", background=TABLA_ENC, foreground=TINTA,
                        font=(F["texto_b"][0], 10, "bold"), padding=(8, 9),
                        relief="flat", borderwidth=0)
            s.map("Treeview.Heading", background=[("active", TABLA_ENC_HOVER)])
            s.configure("Vertical.TScrollbar", background=BORDE, troughcolor=TARJETA,
                        bordercolor=TARJETA, arrowcolor=GRIS, relief="flat")
            s.map("Vertical.TScrollbar", background=[("active", GRIS_CLARO)])
            s.configure("Tarjeta.TCheckbutton", background=TARJETA, foreground=GRIS,
                        font=F["chico"])
            s.map("Tarjeta.TCheckbutton", background=[("active", TARJETA)],
                  indicatorcolor=[("selected", PRIMARIO)])

        # estructura general
        def _tarjeta(self, padre, **kw):
            return tk.Frame(padre, bg=TARJETA, highlightthickness=1,
                            highlightbackground=BORDE, **kw)

        def _crear_widgets(self):
            self._encabezado()

            # Barra de estado (se empaqueta antes para que quede abajo)
            pie = tk.Frame(self, bg=TARJETA, highlightthickness=1, highlightbackground=BORDE)
            pie.pack(fill="x", side="bottom")
            self.punto = tk.Label(pie, text="●", bg=TARJETA, fg=GRIS_CLARO, font=F["chico"])
            self.punto.pack(side="left", padx=(16, 6), pady=6)
            self.estado = tk.Label(pie, bg=TARJETA, fg=GRIS, font=F["chico"], anchor="w")
            self.estado.pack(side="left", fill="x", expand=True)
            tk.Label(pie, text="Ctrl/⌘ + 1-4: pestañas   ·   ← →: cambiar simulación",
                     bg=TARJETA, fg=GRIS_CLARO, font=F["chico"]).pack(side="right", padx=16)

            cuerpo = tk.Frame(self, bg=FONDO)
            cuerpo.pack(fill="both", expand=True, padx=18, pady=(14, 14))
            self._panel_parametros(cuerpo)

            der = tk.Frame(cuerpo, bg=FONDO)
            der.pack(side="left", fill="both", expand=True)
            self._barra_pestanas(der)
            self.paginas_frame = tk.Frame(der, bg=FONDO)
            self.paginas_frame.pack(fill="both", expand=True, pady=(12, 0))
            self.paginas_frame.columnconfigure(0, weight=1)
            self.paginas_frame.rowconfigure(0, weight=1)
            self.paginas = {}
            for clave, constructor in (("resumen", self._pag_resumen),
                                       ("sec", self._pag_secuenciacion),
                                       ("res", self._pag_resultados),
                                       ("gantt", self._pag_gantt)):
                pagina = tk.Frame(self.paginas_frame, bg=FONDO)
                pagina.grid(row=0, column=0, sticky="nsew")
                constructor(pagina)
                self.paginas[clave] = pagina
            self._mostrar("resumen")
            self._mensaje("Listo. Ajusta los parámetros y presiona SIMULAR.")

        def _encabezado(self):
            enc = tk.Canvas(self, height=74, highlightthickness=0, bg=ENC_A)
            enc.pack(fill="x")

            def dibujar(_e=None):
                enc.delete("all")
                w = max(enc.winfo_width(), 1)
                for x in range(0, w, 4):
                    enc.create_rectangle(x, 0, x + 4, 74, outline="",
                                         fill=mezclar(ENC_A, ENC_B, x / w))
                enc.create_text(24, 27, anchor="w", fill=TINTA, font=F["titulo"],
                                text="Simulador Monte Carlo · Calendarización FIFO")
                enc.create_text(25, 54, anchor="w", fill=GRIS, font=F["chico"],
                                text="Ma2004b · Modelos de optimización · Examen Módulo 4-5")
                chip = "Regla FIFO  ·  Medida: makespan"
                ancho = tkfont.Font(font=F["chico"]).measure(chip) + 28
                rect_red(enc, w - 24 - ancho, 22, w - 24, 52, r=15, fill="#FFFFFF",
                         outline=PRIMARIO)
                enc.create_text(w - 24 - ancho / 2, 37, fill=ACENTO, font=F["chico"],
                                text=chip)
            enc.bind("<Configure>", dibujar)

        # panel izquierdo: parámetros
        def _panel_parametros(self, padre):
            izq = tk.Frame(padre, bg=FONDO)
            izq.pack(side="left", fill="y", padx=(0, 18))
            cab = tk.Frame(izq, bg=FONDO)
            cab.pack(fill="x", pady=(0, 8))
            tk.Label(cab, text="Parámetros", bg=FONDO, fg=TINTA, font=F["h2"]).pack(side="left")
            reset = tk.Label(cab, text="Restablecer", bg=FONDO, fg=ACENTO,
                             font=F["chico"], cursor="hand2")
            reset.pack(side="right")
            reset.bind("<Button-1>", lambda _e: self._restablecer())
            reset.bind("<Enter>", lambda _e: reset.configure(fg=ACENTO))
            reset.bind("<Leave>", lambda _e: reset.configure(fg=ACENTO))

            self._grupo(izq, "Trabajos y máquinas", [
                ("Trabajos: mínimo", "min_t", None),
                ("Trabajos: máximo", "max_t", None),
                ("Máquinas: mínimo", "min_m", None),
                ("Máquinas: máximo", "max_m", None),
            ])
            self._grupo(izq, "Elementos y velocidades", [
                ("Elementos por trabajo", "cant", "Ej: 10,20,30"),
                ("Rates (u/h)", "rates", "Ej: 5,10,15"),
            ])
            self._grupo(izq, "Simulación", [
                ("Núm. de simulaciones", "nsim", None),
                ("Semilla", "semilla", "Opcional: misma semilla = mismos resultados"),
                ("Inicio", "fecha", "Formato: AAAA-MM-DD HH:MM"),
            ])
            Boton(izq, "▶   SIMULAR", self._simular, primario=True,
                  fuente=F["boton"], pady=12).pack(fill="x", pady=(2, 10))
            fila = tk.Frame(izq, bg=FONDO)
            fila.pack(fill="x")
            fila.columnconfigure((0, 1), weight=1, uniform="b")
            Boton(fila, "Abrir resultados", lambda: abrir_carpeta(self.carpeta_salida),
                  fuente=F["chico"]).grid(row=0, column=0, sticky="ew", padx=(0, 4))
            Boton(fila, "Cambiar carpeta", self._elegir_carpeta,
                  fuente=F["chico"]).grid(row=0, column=1, sticky="ew", padx=(4, 0))
            self._restablecer()

        def _grupo(self, padre, titulo, campos):
            g = self._tarjeta(padre)
            g.pack(fill="x", pady=(0, 10))
            cab = tk.Frame(g, bg=TARJETA)
            cab.pack(fill="x", padx=14, pady=(10, 2))
            tk.Frame(cab, bg=PRIMARIO, width=4, height=14).pack(side="left", padx=(0, 8))
            tk.Label(cab, text=titulo, bg=TARJETA, fg=TINTA, font=F["h3"]).pack(side="left")
            cuerpo = tk.Frame(g, bg=TARJETA)
            cuerpo.pack(fill="x", padx=14, pady=(0, 10))
            cuerpo.columnconfigure(0, weight=1)
            fila = 0
            for etiqueta, clave, pista in campos:
                tk.Label(cuerpo, text=etiqueta, bg=TARJETA, fg=TINTA,
                         font=F["texto"]).grid(row=fila, column=0, sticky="w", pady=(3, 0))
                var = tk.StringVar()
                ttk.Entry(cuerpo, textvariable=var, width=13, justify="right",
                          style="Campo.TEntry").grid(row=fila, column=1, sticky="e",
                                                     padx=(10, 0), pady=(3, 0))
                self.vars[clave] = var
                fila += 1
                if pista:
                    tk.Label(cuerpo, text=pista, bg=TARJETA, fg=GRIS_CLARO,
                             font=F["chico"]).grid(row=fila, column=0, columnspan=2,
                                                   sticky="w")
                    fila += 1

        def _restablecer(self):
            defectos = {"min_t": "20", "max_t": "30", "min_m": "3", "max_m": "5",
                        "cant": "10,20,30", "rates": "5,10,15", "nsim": "20",
                        "semilla": "", "fecha": datetime.now().strftime("%Y-%m-%d 08:00")}
            for clave, valor in defectos.items():
                self.vars[clave].set(valor)

        # barra de pestañas
        def _barra_pestanas(self, padre):
            barra = tk.Frame(padre, bg=FONDO)
            barra.pack(fill="x")
            self.pestanas = {}
            nombres = (("resumen", "Resumen"), ("sec", "Secuenciación"),
                       ("res", "Resultados"), ("gantt", "Diagrama de Gantt"))
            for n, (clave, texto) in enumerate(nombres, start=1):
                cont = tk.Frame(barra, bg=FONDO)
                cont.pack(side="left", padx=(0, 4))
                lbl = tk.Label(cont, text=f"{n}  {texto}", bg=FONDO, fg=GRIS, font=F["tab"],
                               padx=16, pady=8, cursor="hand2")
                lbl.pack()
                linea = tk.Frame(cont, bg=FONDO, height=3)
                linea.pack(fill="x")
                lbl.bind("<Button-1>", lambda _e, c=clave: self._mostrar(c))
                lbl.bind("<Enter>", lambda _e, c=clave: self._hover_pestana(c, True))
                lbl.bind("<Leave>", lambda _e, c=clave: self._hover_pestana(c, False))
                self.pestanas[clave] = (lbl, linea)
            tk.Frame(padre, bg=BORDE, height=1).pack(fill="x")

        def _hover_pestana(self, clave, dentro):
            if clave != self.pagina:
                self.pestanas[clave][0].configure(fg=ACENTO if dentro else GRIS)

        def _mostrar(self, clave):
            self.pagina = clave
            self.paginas[clave].tkraise()
            for c, (lbl, linea) in self.pestanas.items():
                activa = c == clave
                lbl.configure(fg=ACENTO if activa else GRIS)
                linea.configure(bg=ACENTO if activa else FONDO)
            if clave == "gantt":
                self.after(10, self._dibujar_gantt)

        # pestaña 1: resumen
        def _pag_resumen(self, pag):
            tarjetas = tk.Frame(pag, bg=FONDO)
            tarjetas.pack(fill="x")
            self.lbl_valor = {}
            definicion = (("prom", "Promedio", PRIMARIO), ("max", "Máximo", ROJO),
                          ("min", "Mínimo", VERDE), ("rango", "Rango (máx − mín)", AMBAR),
                          ("desv", "Desv. estándar", "#9ED8F5"))
            for i, (clave, titulo, color) in enumerate(definicion):
                tarjetas.columnconfigure(i, weight=1, uniform="tarj")
                t = self._tarjeta(tarjetas)
                t.grid(row=0, column=i, sticky="ew", padx=(0, 10 if i < 4 else 0))
                tk.Frame(t, bg=color, height=4).pack(fill="x")
                tk.Label(t, text=titulo, bg=TARJETA, fg=GRIS,
                         font=F["chico"]).pack(anchor="w", padx=14, pady=(10, 0))
                lbl = tk.Label(t, text="—", bg=TARJETA, fg=TINTA, font=F["num"])
                lbl.pack(anchor="w", padx=14)
                tk.Label(t, text="horas de makespan", bg=TARJETA, fg=GRIS_CLARO,
                         font=F["mini"]).pack(anchor="w", padx=14, pady=(0, 10))
                self.lbl_valor[clave] = lbl

            self.info_resumen = tk.Label(pag, text="Aún no hay resultados.", bg=FONDO,
                                         fg=GRIS, font=F["chico"], anchor="w")
            self.info_resumen.pack(fill="x", pady=(8, 8))

            graf = self._tarjeta(pag)
            graf.pack(fill="x")
            top = tk.Frame(graf, bg=TARJETA)
            top.pack(fill="x", padx=14, pady=(10, 0))
            tk.Label(top, text="Makespan por simulación (h)", bg=TARJETA, fg=TINTA,
                     font=F["h3"]).pack(side="left")
            self.var_ordenar = tk.BooleanVar(value=False)
            ttk.Checkbutton(top, text="Ordenar de menor a mayor",
                            style="Tarjeta.TCheckbutton", variable=self.var_ordenar,
                            command=self._dibujar_grafica).pack(side="right")
            self.canvas = tk.Canvas(graf, height=220, bg=TARJETA, highlightthickness=0)
            self.canvas.pack(fill="x", padx=8, pady=(0, 8))
            self.canvas.bind("<Configure>", lambda _e: self._dibujar_grafica())
            self.canvas.bind("<Motion>", self._al_mover)
            self.canvas.bind("<Leave>", self._al_salir)
            self.canvas.bind("<Button-1>", self._clic_barra)

            marco = self._tarjeta(pag)
            marco.pack(fill="both", expand=True, pady=(12, 0))
            top2 = tk.Frame(marco, bg=TARJETA)
            top2.pack(fill="x", padx=14, pady=(10, 8))
            tk.Label(top2, text="Resultados por simulación", bg=TARJETA, fg=TINTA,
                     font=F["h3"]).pack(side="left")
            tk.Label(top2, text="Verde = menor makespan · Rojo = mayor · clic en encabezado "
                                "para ordenar · doble clic abre su Gantt",
                     bg=TARJETA, fg=GRIS_CLARO, font=F["chico"]).pack(side="right")
            columnas = (("Sim", 60, "center"), ("# Trabajos", 95, "center"),
                        ("# Máquinas", 100, "center"), ("Total elem.", 100, "center"),
                        ("Rate prom.", 95, "center"), ("Makespan (h)", 115, "center"),
                        ("Utilización", 100, "center"), ("Máq. crítica", 105, "center"))
            self.tabla = Tabla(
                marco, columnas,
                formato={4: lambda v: f"{v:.2f}", 5: lambda v: f"{v:.3f}",
                         6: lambda v: f"{v:.1%}"},
                etiquetar=self._etiqueta_fila,
                al_abrir=lambda fila: self._abrir_gantt(fila[0]),
                vacio="Presiona SIMULAR para ver los resultados")
            self.tabla.pack(fill="both", expand=True)

        def _etiqueta_fila(self, fila):
            if fila[5] == self.mejor_mk:
                return "mejor"
            return "peor" if fila[5] == self.peor_mk else None

        def _animar(self, clave, valor, pasos=14):
            if clave in self._anim:
                self.after_cancel(self._anim[clave])
            lbl = self.lbl_valor[clave]

            def paso(i=1):
                e = 1 - (1 - i / pasos) ** 3
                lbl.configure(text=f"{valor * e:.2f}")
                if i < pasos:
                    self._anim[clave] = self.after(18, lambda: paso(i + 1))
            paso()

        #  gráfica de barras
        def _al_mover(self, evento):
            nuevo = next((i for x0, x1, i in self.barras if x0 <= evento.x <= x1), None)
            self.canvas.configure(cursor="hand2" if nuevo is not None else "")
            if nuevo != self.hover:
                self.hover = nuevo
                self._dibujar_grafica()

        def _al_salir(self, _evento):
            if self.hover is not None:
                self.hover = None
                self.canvas.configure(cursor="")
                self._dibujar_grafica()

        def _clic_barra(self, _evento):
            if self.hover is not None:
                self._abrir_gantt(self.hover)

        def _dibujar_grafica(self):
            c = self.canvas
            c.delete("all")
            self.barras = []
            w, h = c.winfo_width(), c.winfo_height()
            if w < 80 or h < 80:
                return
            if not self.filas:
                c.create_text(w / 2, h / 2, fill=GRIS_CLARO, font=F["texto"],
                              text="Presiona SIMULAR para ver el makespan de cada corrida")
                return

            datos = [(f["sim"], f["mk"]) for f in self.filas]     # (n.º de sim, makespan)
            if self.var_ordenar.get():
                datos.sort(key=lambda d: d[1])
            valores = [d[1] for d in datos]
            mejor, peor, prom = min(valores), max(valores), sum(valores) / len(valores)
            izq, der, arr, aba = 48, 16, 36, 28
            ancho = (w - izq - der) / len(datos)
            vmax = max(valores) * 1.12
            base, alto = h - aba, h - aba - arr

            # Leyenda
            medir = tkfont.Font(font=F["chico"]).measure
            lx = w - der
            for texto, color, es_linea in (("Promedio", AMBAR, True), ("Peor", ROJO, False),
                                           ("Mejor", VERDE, False),
                                           ("Makespan", PRIMARIO, False)):
                c.create_text(lx, 14, anchor="e", fill=GRIS, font=F["chico"], text=texto)
                lx -= medir(texto) + 8
                if es_linea:
                    c.create_line(lx - 16, 14, lx, 14, fill=color, dash=(3, 2), width=2)
                    lx -= 16 + 16
                else:
                    c.create_rectangle(lx - 10, 9, lx, 19, fill=color, outline="")
                    lx -= 10 + 16

            # Cuadrícula y ejes
            for k in range(5):
                y = base - alto * k / 4
                c.create_line(izq, y, w - der, y, fill=BORDE if k == 0 else BORDE_SUAVE)
                c.create_text(izq - 8, y, anchor="e", fill=GRIS_CLARO, font=F["mini"],
                              text=f"{vmax * k / 4:.0f}")

            # Barras
            for pos, (num, val) in enumerate(datos):
                x0, x1 = izq + pos * ancho + 3, izq + (pos + 1) * ancho - 3
                y = base - (val / vmax) * alto
                color = VERDE if val == mejor else (ROJO if val == peor else PRIMARIO)
                if num == self.hover:
                    color = mezclar(color, "#000000", 0.22)
                c.create_rectangle(x0, y, x1, base, fill=color, outline="")
                if len(datos) <= 30:
                    c.create_text((x0 + x1) / 2, base + 12, fill=GRIS, font=F["mini"],
                                  text=str(num))
                self.barras.append((x0, x1, num))

            # Promedio
            yp = base - (prom / vmax) * alto
            c.create_line(izq, yp, w - der, yp, fill=AMBAR, dash=(4, 3), width=2)

            # Valor exacto al pasar el cursor
            if self.hover is not None:
                val = next(v for n, v in datos if n == self.hover)
                c.create_text(izq + 8, 14, anchor="w", fill=ACENTO, font=F["texto_b"],
                              text=f"Sim {self.hover}: {val:.3f} h   ·   clic para ver su Gantt")

        # pestaña 2: secuenciación.csv 
        def _barra_archivo(self, marco, titulo, archivo):
            top = tk.Frame(marco, bg=TARJETA)
            top.pack(fill="x", padx=14, pady=(12, 8))
            tk.Label(top, text=titulo, bg=TARJETA, fg=TINTA, font=F["h2"]).pack(side="left")
            tk.Label(top, text=archivo, bg=PRIMARIO_SUAVE, fg=ACENTO,
                     font=F["chico"], padx=8, pady=2).pack(side="left", padx=10)
            Boton(top, "Abrir en Excel", lambda: self._abrir_archivo(archivo),
                  fuente=F["chico"], pady=5).pack(side="right")
            return top

        def _pag_secuenciacion(self, pag):
            marco = self._tarjeta(pag)
            marco.pack(fill="both", expand=True)
            self._barra_archivo(marco, "Secuenciación", "secuenciacion.csv")
            filtros = tk.Frame(marco, bg=TARJETA)
            filtros.pack(fill="x", padx=14, pady=(0, 10))
            tk.Label(filtros, text="Simulación", bg=TARJETA, fg=GRIS,
                     font=F["chico"]).pack(side="left")
            self.f_sim = tk.StringVar(value="Todas")
            self.combo_f_sim = ttk.Combobox(filtros, textvariable=self.f_sim, width=8,
                                            state="readonly", values=["Todas"])
            self.combo_f_sim.pack(side="left", padx=(6, 16))
            tk.Label(filtros, text="Máquina", bg=TARJETA, fg=GRIS,
                     font=F["chico"]).pack(side="left")
            self.f_maq = tk.StringVar(value="Todas")
            self.combo_f_maq = ttk.Combobox(filtros, textvariable=self.f_maq, width=8,
                                            state="readonly", values=["Todas"])
            self.combo_f_maq.pack(side="left", padx=6)
            self.cuenta_sec = tk.Label(filtros, bg=TARJETA, fg=GRIS_CLARO, font=F["chico"])
            self.cuenta_sec.pack(side="right")
            for combo in (self.combo_f_sim, self.combo_f_maq):
                combo.bind("<<ComboboxSelected>>", lambda _e: self._filtrar_sec())
            columnas = (("Simulacion", 90, "center"), ("Maquina", 80, "center"),
                        ("idTrabajo", 85, "center"), ("fechaHoraInicio", 150, "center"),
                        ("fechaHoraFin", 150, "center"), ("OrdenSecuenciacion", 140, "center"),
                        ("IdProducto", 90, "center"), ("Cantidad", 80, "center"),
                        ("Rate_u_por_h", 100, "center"), ("Duracion_h", 95, "center"))
            self.t_sec = Tabla(marco, columnas,
                               al_abrir=lambda fila: self._abrir_gantt(fila[0]),
                               vacio="Presiona SIMULAR para generar la secuenciación")
            self.t_sec.pack(fill="both", expand=True)
            self.sec_filas = []

        def _filtrar_sec(self):
            sim, maq = self.f_sim.get(), self.f_maq.get()
            filas = [f for f in self.sec_filas
                     if (sim == "Todas" or f[0] == int(sim))
                     and (maq == "Todas" or f[1] == int(maq))]
            self.t_sec.poner_filas(filas, reiniciar_orden=False)
            self.cuenta_sec.configure(text=f"{len(filas)} de {len(self.sec_filas)} filas")

        # pestaña 3: resultados_simulaciones.csv 
        def _pag_resultados(self, pag):
            marco = self._tarjeta(pag)
            marco.pack(fill="both", expand=True)
            self._barra_archivo(marco, "Resultados de las simulaciones",
                                "resultados_simulaciones.csv")
            columnas = (("Simulacion", 95, "center"), ("NumTrabajos", 105, "center"),
                        ("NumMaquinas", 110, "center"), ("TotalElementos", 120, "center"),
                        ("RatePromedioAsignado", 160, "center"), ("Makespan_h", 105, "center"),
                        ("Utilizacion", 100, "center"), ("MaquinaCritica", 120, "center"))
            self.t_res = Tabla(marco, columnas,
                               etiquetar=lambda f: ("mejor" if f[5] == self.mejor_mk else
                                                    ("peor" if f[5] == self.peor_mk else None)),
                               al_abrir=lambda fila: self._abrir_gantt(fila[0]),
                               vacio="Presiona SIMULAR para ver los resultados")
            self.t_res.pack(fill="both", expand=True)
            abajo = tk.Frame(marco, bg=TARJETA)
            abajo.pack(fill="x", padx=14, pady=(12, 10))
            abajo.columnconfigure((0, 1), weight=1, uniform="inf")
            izq = tk.Frame(abajo, bg=TARJETA)
            izq.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
            tk.Label(izq, text="Estadísticos del makespan", bg=TARJETA, fg=TINTA,
                     font=F["h3"]).pack(anchor="w", pady=(0, 6))
            self.t_stats = Tabla(izq, (("Estadístico", 190, "w"), ("Valor (h)", 110, "e")),
                                 formato={1: lambda v: f"{v:.4f}"}, alto=8,
                                 ordenable=False, vacio="")
            self.t_stats.pack(fill="x")
            self.t_stats.aviso.place_forget()
            der = tk.Frame(abajo, bg=TARJETA)
            der.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
            tk.Label(der, text="Factores de entrada", bg=TARJETA, fg=TINTA,
                     font=F["h3"]).pack(anchor="w", pady=(0, 6))
            self.t_factores = Tabla(der, (("Factor", 190, "w"), ("Valor", 230, "w")),
                                    alto=8, ordenable=False, vacio="")
            self.t_factores.pack(fill="x")
            self.t_factores.aviso.place_forget()

        #  pestaña 4: Gantt 
        def _pag_gantt(self, pag):
            marco = self._tarjeta(pag)
            marco.pack(fill="both", expand=True)
            top = tk.Frame(marco, bg=TARJETA)
            top.pack(fill="x", padx=14, pady=(12, 4))
            tk.Label(top, text="Diagrama de Gantt", bg=TARJETA, fg=TINTA,
                     font=F["h2"]).pack(side="left")
            self.sim_var = tk.StringVar(value="1")
            self.sim_var.trace_add("write", lambda *_a: self._cambiar_sim())
            Boton(top, "▶", lambda: self._tecla(1, forzar=True), fuente=F["texto_b"],
                  pady=3).pack(side="right")
            self.combo_gantt = ttk.Combobox(top, textvariable=self.sim_var, values=["1"],
                                            state="readonly", width=5)
            self.combo_gantt.pack(side="right", padx=6)
            Boton(top, "◀", lambda: self._tecla(-1, forzar=True), fuente=F["texto_b"],
                  pady=3).pack(side="right")
            tk.Label(top, text="Simulación", bg=TARJETA, fg=GRIS,
                     font=F["chico"]).pack(side="right", padx=(0, 8))
            self.gantt = tk.Canvas(marco, bg=TARJETA, highlightthickness=0)
            self.gantt.pack(fill="both", expand=True, padx=8, pady=(0, 8))
            self.gantt.bind("<Configure>", lambda _e: self._dibujar_gantt())
            self.gantt.bind("<Motion>", self._mover_gantt)
            self.gantt.bind("<Leave>", self._salir_gantt)

        def _mover_gantt(self, e):
            self.raton = (e.x, e.y)
            nuevo = next((i for i, b in enumerate(self.bloques)
                          if b[0] <= e.x <= b[2] and b[1] <= e.y <= b[3]), None)
            if nuevo != self.hover_b:
                self.hover_b = nuevo
                self._dibujar_gantt()
            else:
                self._tooltip()

        def _salir_gantt(self, _e):
            if self.hover_b is not None:
                self.hover_b = None
                self._dibujar_gantt()

        def _dibujar_gantt(self):
            c = self.gantt
            c.delete("all")
            self.bloques = []
            r = self.sim_actual
            w, h = c.winfo_width(), c.winfo_height()
            if w < 220 or h < 150:
                return
            if r is None:
                c.create_text(w / 2, h / 2, fill=GRIS_CLARO, font=F["texto"],
                              text="Presiona SIMULAR para ver la secuenciación de cada máquina")
                return
            izq, der, arr, aba = 74, 28, 52, 58
            m = r.n_maquinas
            fila = (h - arr - aba) / m
            alto = max(20, min(58, fila * 0.68))
            escala = (w - izq - der) / r.makespan
            paso = next((p for p in (1, 2, 5, 10, 20, 25, 50, 100)
                         if r.makespan / p <= 14), 200)

            c.create_text(izq - 50, 20, anchor="w", fill=TINTA, font=F["h2"],
                          text=f"Simulación {r.numero}")
            c.create_text(w - der, 20, anchor="e", fill=GRIS, font=F["chico"],
                          text=f"{r.n_trabajos} trabajos · {r.n_maquinas} máquinas · "
                               f"makespan {r.makespan:.2f} h · utilización {r.utilizacion:.1%}")

            # Bandas por máquina y cuadrícula de tiempo
            for k in range(m):
                y0 = arr + fila * k
                if k % 2 == 0:
                    c.create_rectangle(izq - 60, y0, w - der + 12, y0 + fila,
                                       fill=FILA_ALT, outline="")
            for t in range(0, int(r.makespan) + 1, paso):
                x = izq + t * escala
                c.create_line(x, arr, x, h - aba, fill=BORDE)
                c.create_text(x, h - aba + 14, fill=GRIS, font=F["mini"], text=str(t))
            c.create_text((izq + w - der) / 2, h - aba + 34, fill=GRIS, font=F["chico"],
                          text="Horas desde el inicio")

            xm = izq + r.makespan * escala
            for k, maq in enumerate(r.maquinas):
                yc = arr + fila * (k + 0.5)
                critica = maq.id == r.maquina_critica
                c.create_text(izq - 14, yc - (7 if critica else 0), anchor="e",
                              fill=ROJO_T if critica else TINTA, font=F["h3"],
                              text=f"M{maq.id}")
                if critica:
                    c.create_text(izq - 14, yc + 9, anchor="e", fill=ROJO_T,
                                  font=F["mini"], text="crítica")
                # Zona ociosa: desde que termina la máquina hasta el makespan
                xf = izq + maq.libre_en_h * escala
                if xm - xf > 2:
                    rect_red(c, xf + 2, yc - alto / 2, xm, yc + alto / 2, r=6,
                             fill="", outline=GRIS_CLARO, dash=(3, 3))
                    if xm - xf > 78:
                        c.create_text((xf + xm) / 2, yc, fill=GRIS_CLARO, font=F["mini"],
                                      text=f"libre {r.makespan - maq.libre_en_h:.1f} h")
                for t in maq.trabajos:
                    x0, x1 = izq + t.inicio_h * escala, izq + t.fin_h * escala
                    color = PALETA[(t.id - 1) % len(PALETA)]
                    idx = len(self.bloques)
                    activo = idx == self.hover_b
                    rect_red(c, x0 + 1, yc - alto / 2, x1 - 1, yc + alto / 2, r=6,
                             fill=color if not activo else mezclar(color, "#000000", 0.2),
                             outline=TINTA if activo else TARJETA, width=2 if activo else 1)
                    ancho = x1 - x0
                    if ancho > 56 and alto >= 36:
                        c.create_text((x0 + x1) / 2, yc - 7, fill=TEXTO_BLOQUE, font=F["texto_b"],
                                      text=str(t.id))
                        c.create_text((x0 + x1) / 2, yc + 9, fill=TEXTO_BLOQUE, font=F["mini"],
                                      text=f"{t.fin_h - t.inicio_h:.1f} h")
                    elif ancho > 16:
                        c.create_text((x0 + x1) / 2, yc, fill=TEXTO_BLOQUE, font=F["texto_b"],
                                      text=str(t.id))
                    self.bloques.append((x0, yc - alto / 2, x1, yc + alto / 2, t, maq))

            c.create_line(xm, arr - 8, xm, h - aba, fill=ROJO_T, dash=(4, 3), width=2)
            c.create_text(xm, arr - 16, fill=ROJO_T, font=F["chico"],
                          text=f"Makespan {r.makespan:.2f} h")
            c.create_text(izq - 50, h - 10, anchor="w", fill=GRIS_CLARO, font=F["mini"],
                          text="Cada bloque es un trabajo (su número) · ancho = cantidad ÷ rate · "
                               "línea punteada = zona sin trabajo")
            self._tooltip()

        def _tooltip(self):
            c = self.gantt
            c.delete("tip")
            if self.hover_b is None:
                return
            t, maq = self.bloques[self.hover_b][4], self.bloques[self.hover_b][5]
            lineas = [f"Trabajo {t.id}  ·  P{t.id}",
                      f"Máquina M{maq.id}  ·  orden {t.orden}",
                      f"{t.cantidad} u a {t.rates[maq.indice]} u/h",
                      f"Inicio {t.inicio_h:.2f} h  ·  Fin {t.fin_h:.2f} h",
                      f"Duración {t.fin_h - t.inicio_h:.2f} h"]
            ancho, alto = 210, 16 * len(lineas) + 18
            x = min(self.raton[0] + 16, c.winfo_width() - ancho - 6)
            y = min(self.raton[1] + 16, c.winfo_height() - alto - 6)
            rect_red(c, x, y, x + ancho, y + alto, r=8, fill=TINTA, outline="", tags="tip")
            for i, linea in enumerate(lineas):
                c.create_text(x + 12, y + 14 + 16 * i, anchor="w", tags="tip",
                              fill="white" if i else "#C7D2FE",
                              font=F["texto_b"] if i == 0 else F["chico"], text=linea)

        def _cambiar_sim(self):
            try:
                i = int(self.sim_var.get())
            except ValueError:
                return
            if not (1 <= i <= len(self.resultados)):
                return
            self.sim_actual = self.resultados[i - 1]
            self.hover_b = None
            self._dibujar_gantt()

        def _tecla(self, delta, forzar=False):
            if self.pagina != "gantt" or not self.resultados:
                return
            if not forzar:
                try:
                    if isinstance(self.focus_get(), (ttk.Entry, ttk.Combobox)):
                        return
                except KeyError:
                    pass
            try:
                i = int(self.sim_var.get()) + delta
            except ValueError:
                return
            self.sim_var.set(str(min(max(i, 1), len(self.resultados))))

        def _abrir_gantt(self, numero):
            self.sim_var.set(str(numero))
            self._mostrar("gantt")

        # acciones
        def _mensaje(self, texto, tipo="info"):
            self.punto.configure(fg={"ok": VERDE_T, "error": ROJO_T}.get(tipo, GRIS_CLARO))
            self.estado.configure(text=texto, fg=ROJO_T if tipo == "error" else GRIS)

        def _abrir_archivo(self, nombre):
            ruta = self.carpeta_salida / nombre
            if ruta.exists():
                abrir_carpeta(ruta)
            else:
                self._mensaje("Aún no existe el archivo: presiona SIMULAR primero.", "error")

        def _elegir_carpeta(self):
            c = filedialog.askdirectory(title="Carpeta de salida")
            if c:
                self.carpeta_salida = Path(c)
                self._mensaje(f"Carpeta de salida: {self.carpeta_salida}")

        def _leer_parametros(self):
            g = lambda k: self.vars[k].get().strip()
            p = Parametros(
                min_trabajos=int(g("min_t")), max_trabajos=int(g("max_t")),
                min_maquinas=int(g("min_m")), max_maquinas=int(g("max_m")),
                cantidades=lista_enteros(g("cant")), rates=lista_enteros(g("rates")),
                n_simulaciones=int(g("nsim")),
                semilla=int(g("semilla")) if g("semilla") else None,
                fecha_inicio=datetime.strptime(g("fecha"), "%Y-%m-%d %H:%M"),
            )
            if not (1 <= p.min_trabajos <= p.max_trabajos):
                raise ValueError("Revisa el rango de trabajos (mínimo <= máximo, >= 1).")
            if not (1 <= p.min_maquinas <= p.max_maquinas):
                raise ValueError("Revisa el rango de máquinas (mínimo <= máximo, >= 1).")
            if p.n_simulaciones < 1:
                raise ValueError("El número de simulaciones debe ser >= 1.")
            return p

        def _simular(self):
            try:
                p = self._leer_parametros()
            except ValueError as e:
                msg = str(e)
                if "invalid literal" in msg or "does not match format" in msg:
                    msg = "Hay un valor con formato incorrecto."
                self._mensaje(msg, "error")
                messagebox.showerror(
                    "Datos inválidos",
                    f"{msg}\n\nListas: números separados por comas (ej. 10,20,30).\n"
                    "Fecha: AAAA-MM-DD HH:MM (ej. 2026-10-20 08:00).")
                return
            exp = Experimento(p)
            exp.ejecutar()
            tipo = "ok"
            try:
                exp.exportar(self.carpeta_salida)
                aviso = f"Archivos guardados en {self.carpeta_salida}"
            except OSError as e:
                aviso, tipo = f"No se pudieron guardar los archivos: {e}", "error"

            est = exp.estadisticos()
            for clave, llave in (("prom", "promedio"), ("max", "maximo"), ("min", "minimo"),
                                 ("rango", "rango"), ("desv", "desviacion")):
                self._animar(clave, est[llave])

            self.resultados, self.t0 = exp.resultados, p.fecha_inicio
            self.filas = [dict(sim=r.numero, nt=r.n_trabajos, nm=r.n_maquinas,
                               elem=r.total_elementos, rate=r.rate_promedio,
                               mk=r.makespan, util=r.utilizacion,
                               crit=r.maquina_critica) for r in exp.resultados]
            self.mejor_mk = min(f["mk"] for f in self.filas)
            self.peor_mk = max(f["mk"] for f in self.filas)
            self.hover = None

            # Pestaña 1
            self.tabla.poner_filas([(f["sim"], f["nt"], f["nm"], f["elem"], f["rate"],
                                     f["mk"], f["util"], f["crit"]) for f in self.filas])
            mejor = min(exp.resultados, key=lambda r: r.makespan)
            peor = max(exp.resultados, key=lambda r: r.makespan)
            util = sum(r.utilizacion for r in exp.resultados) / len(exp.resultados)
            self.info_resumen.configure(
                text=f"Mejor: Sim {mejor.numero} ({mejor.makespan:.2f} h)   ·   "
                     f"Peor: Sim {peor.numero} ({peor.makespan:.2f} h)   ·   "
                     f"Utilización promedio: {util:.1%}   ·   "
                     f"{len(exp.resultados)} simulaciones")
            self._dibujar_grafica()

            # Pestaña 2: mismo contenido que secuenciacion.csv
            fmt = "%Y-%m-%d %H:%M:%S"
            self.sec_filas = [
                (r.numero, m.id, t.id,
                 (p.fecha_inicio + timedelta(hours=t.inicio_h)).strftime(fmt),
                 (p.fecha_inicio + timedelta(hours=t.fin_h)).strftime(fmt),
                 t.orden, f"P{t.id}", t.cantidad, t.rates[m.indice],
                 round(t.fin_h - t.inicio_h, 4))
                for r in exp.resultados for m in r.maquinas for t in m.trabajos]
            self.combo_f_sim.configure(values=["Todas"] + [str(r.numero) for r in exp.resultados])
            self.combo_f_maq.configure(
                values=["Todas"] + [str(k + 1) for k in range(max(r.n_maquinas
                                                                  for r in exp.resultados))])
            self.f_sim.set("Todas")
            self.f_maq.set("Todas")
            self._filtrar_sec()

            # Pestaña 3: mismo contenido que resultados_simulaciones.csv
            self.t_res.poner_filas([
                (r.numero, r.n_trabajos, r.n_maquinas, r.total_elementos,
                 round(r.rate_promedio, 3), round(r.makespan, 4),
                 round(r.utilizacion, 4), r.maquina_critica) for r in exp.resultados])
            self.t_stats.poner_filas([
                ("Promedio makespan", round(est["promedio"], 4)),
                ("Maximo makespan", round(est["maximo"], 4)),
                ("Minimo makespan", round(est["minimo"], 4)),
                ("Rango (max - min)", round(est["rango"], 4)),
                ("Desviacion estandar", round(est["desviacion"], 4))])
            self.t_factores.poner_filas(exp.parametros_texto())

            # Pestaña 4
            valores = [str(r.numero) for r in exp.resultados]
            self.combo_gantt.configure(values=valores)
            self.sim_var.set("1")
            self._cambiar_sim()
            self._mensaje(f"{len(exp.resultados)} simulaciones completadas · {aviso}", tipo)

    App().mainloop()



# 4. consola para pruebas rápidas sin ventana)

def modo_consola():
    p = Parametros(semilla=42,
                   fecha_inicio=datetime.now().replace(minute=0, second=0, microsecond=0))
    exp = Experimento(p)
    exp.ejecutar()
    print(f"{'Sim':>3} {'Trab':>5} {'Maq':>4} {'Elem':>6} {'Makespan(h)':>12} {'Util':>7}")
    for r in exp.resultados:
        print(f"{r.numero:>3} {r.n_trabajos:>5} {r.n_maquinas:>4} "
              f"{r.total_elementos:>6} {r.makespan:>12.3f} {r.utilizacion:>7.1%}")
    print(texto_resumen(exp))
    ruta_sec, ruta_res = exp.exportar(carpeta_base() / "resultados")
    print(f"\nArchivos: {ruta_sec}\n          {ruta_res}")


if __name__ == "__main__":
    if "--consola" in sys.argv:
        modo_consola()
    else:
        lanzar_interfaz()

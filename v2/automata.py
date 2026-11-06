"""AgentPy collection model, with individual-turn playback for the 3D viewer."""
from collections import deque
import agentpy as ap


class Robot(ap.Agent):
    def setup(self):
        self.indice = 0
        self.cargando = False
        self.entregados = 0
        self.bloqueos = 0
        self.vistas = set()
        self.cubos_conocidos = set()
        self.ruta_exploracion = []
        self.siguiente_punto = 0
        self.saliendo_deposito = 0
        self.esperas_seguidas = 0
        self.estacionamiento = None
        self.ruta_desvio = []
        self.destino_desvio = None

    def posicion(self):
        return tuple(self.model.grid.positions[self])

    @staticmethod
    def distancia(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def celdas_visibles(self):
        f, c = self.posicion()
        n = self.model.p.tamano
        radio = self.model.p.radio_vision
        for df in range(-radio, radio + 1):
            for dc in range(-(radio - abs(df)), radio - abs(df) + 1):
                celda = (f + df, c + dc)
                if 0 <= celda[0] < n and 0 <= celda[1] < n:
                    yield celda

    def percibir(self):
        # Solo ve cubos dentro de su radio de percepción.
        for celda in self.celdas_visibles():
            self.vistas.add(celda)
            if celda in self.model.cubos:
                self.cubos_conocidos.add(celda)
            else:
                self.cubos_conocidos.discard(celda)

    def desvio(self, destino):
        """Calcula un camino alternativo alrededor de los otros robots."""
        inicio = self.posicion()
        if destino in self.model.ocupadas:
            return []
        n = self.model.p.tamano
        cola = deque([inicio])
        anteriores = {inicio: None}
        while cola:
            actual = cola.popleft()
            if actual == destino:
                camino = []
                paso = actual
                while paso != inicio:
                    camino.append(paso)
                    paso = anteriores[paso]
                return camino[::-1]
            f, c = actual
            for vecino in ((f - 1, c), (f, c - 1), (f, c + 1), (f + 1, c)):
                if (0 <= vecino[0] < n and 0 <= vecino[1] < n
                        and vecino not in anteriores
                        and vecino not in self.model.ocupadas):
                    anteriores[vecino] = actual
                    cola.append(vecino)
        return []

    def mover_hacia(self, destino):
        """Si alguien ocupa el siguiente espacio, espera; luego puede rodearlo."""
        f, c = self.posicion()
        df, dc = destino
        if (f, c) == destino:
            self.esperas_seguidas = 0
            self.ruta_desvio = []
            self.destino_desvio = None
            return False

        if self.destino_desvio == destino and self.ruta_desvio:
            siguiente = self.ruta_desvio[0]
        else:
            self.ruta_desvio = []
            self.destino_desvio = None
            if f < df:
                siguiente = (f + 1, c)
            elif f > df:
                siguiente = (f - 1, c)
            elif c < dc:
                siguiente = (f, c + 1)
            else:
                siguiente = (f, c - 1)

        if siguiente in self.model.ocupadas:
            self.bloqueos += 1
            self.esperas_seguidas += 1
            if self.esperas_seguidas < 2:
                return False
            camino = self.desvio(destino)
            if camino:
                self.ruta_desvio = camino
                self.destino_desvio = destino
                siguiente = camino[0]
            else:
                # Si el destino mismo está ocupado, cede espacio al otro robot.
                # Siempre esperó al menos un turno antes de hacerlo.
                n = self.model.p.tamano
                opciones = ((f, c + 1), (f + 1, c), (f, c - 1), (f - 1, c))
                libres = [p for p in opciones if 0 <= p[0] < n
                          and 0 <= p[1] < n and p not in self.model.ocupadas
                          and p != self.model.deposito]
                if not libres:
                    return False
                siguiente = libres[0]
                self.ruta_desvio = []
                self.destino_desvio = None

        del self.model.ocupadas[(f, c)]
        self.model.grid.move_to(self, siguiente)
        self.model.ocupadas[siguiente] = self
        self.esperas_seguidas = 0
        if self.ruta_desvio:
            self.ruta_desvio.pop(0)
        return True

    def recoger(self):
        celda = self.posicion()
        if self.cargando or celda not in self.model.cubos:
            return False
        self.model.cubos.remove(celda)
        self.cubos_conocidos.discard(celda)
        self.cargando = True
        return True

    def proximo_punto_de_exploracion(self):
        # Ruta serpenteante precomputada, sin recorrer 10,000 celdas en cada paso.
        while self.siguiente_punto < len(self.ruta_exploracion):
            objetivo = self.ruta_exploracion[self.siguiente_punto]
            if self.posicion() != objetivo:
                return objetivo
            self.siguiente_punto += 1
        return None

    def siguiente_paso_deposito(self):
        """Entrada por (0, 1), salida por (1, 0) para disminuir bloqueos."""
        f, c = self.posicion()
        if (f, c) == (0, 1):
            return (0, 0)
        if c == 0:
            return (f, 1)
        if f > 0:
            return (0, c)
        return (0, 1)

    def actuar(self):
        self.percibir()
        pos = self.posicion()

        if self.cargando:
            if pos == self.model.deposito:
                self.cargando = False
                self.entregados += 1
                self.model.entregados += 1
                self.saliendo_deposito = 1
                return
            self.mover_hacia(self.siguiente_paso_deposito())
            self.percibir()
            if self.posicion() == self.model.deposito:
                self.cargando = False
                self.entregados += 1
                self.model.entregados += 1
                self.saliendo_deposito = 1
            return

        # El robot que acaba de entregar debe liberar el depósito y su salida.
        if self.saliendo_deposito:
            ruta_salida = [(1, 0), (2, 0), (2, 1)]
            destino = ruta_salida[self.saliendo_deposito - 1]
            if self.mover_hacia(destino):
                self.saliendo_deposito += 1
                if self.saliendo_deposito > len(ruta_salida):
                    self.saliendo_deposito = 0
            self.percibir()
            return

        if self.recoger():
            return

        # Un robot vacío cede el pasillo superior a un robot con cubo.
        # Solo necesita observar a otros robots a dos casillas de distancia.
        f, c = self.posicion()
        transportistas = [r for r in self.model.robots
                          if r is not self and r.cargando
                          and self.distancia((f, c), r.posicion()) <= 2]
        if f == 0 and c >= 1 and any(
                r.posicion()[0] == 0 and r.posicion()[1] >= c
                for r in transportistas):
            self.mover_hacia((1, c))
            self.percibir()
            return

        if self.cubos_conocidos:
            destino = min(self.cubos_conocidos,
                          key=lambda p: (self.distancia(pos, p), p))
        else:
            destino = self.proximo_punto_de_exploracion()

        if destino is None:
            destino = self.estacionamiento

        if destino is not None:
            # Tampoco se mete delante de un transportista que viene por fila 0.
            if f == 1 and destino[0] == 0 and any(
                    r.posicion()[0] == 0
                    and 0 <= r.posicion()[1] - c <= 2
                    for r in transportistas):
                return
            self.mover_hacia(destino)
            self.percibir()
            self.recoger()


class ModeloRecoleccion(ap.Model):
    def __init__(self, tamano=20, robots=7, cubos=20, radio_vision=2, seed=42, steps=40000):
        if any(not isinstance(v, int) for v in (tamano, robots, cubos, radio_vision, steps)):
            raise ValueError('Grid parameters must be integers')
        if steps < 1:
            raise ValueError('Step limit must be positive')
        super().__init__(dict(tamano=tamano, robots=robots, cubos=cubos,
                              radio_vision=radio_vision, seed=seed, steps=steps))
        self.turn = 0
        self.sim_setup()

    @property
    def complete(self):
        return not self.cubos and all(not r.cargando for r in self.robots)

    @property
    def finished(self):
        return not self.running or (self.turn == 0 and self.complete)

    def advance_agent(self):
        """Animate one AgentPy agent turn without precomputing future decisions.

        Equivalent to sim_step split across frames: increment t once per round,
        run agents in the supplied rotating order, then update/stop the model.
        """
        if self.finished:
            return None
        if self.turn == 0:
            self.t += 1
        robot = self.robots[(self.t + self.turn) % len(self.robots)]
        before = (robot.posicion(), robot.cargando)
        robot.actuar()
        self.turn += 1
        if self.turn == len(self.robots):
            self.turn = 0
            self.update()
            if self.complete or self.t >= self._steps:
                self.stop()
                self.end()
        return robot.indice, before, (robot.posicion(), robot.cargando)

    def step(self):
        """Standard AgentPy full-round hook, used by sim_step() and run()."""
        if self.turn:
            raise RuntimeError('Finish the current playback round before using sim_step/run')
        cantidad = len(self.robots)
        inicio = self.t % cantidad
        for desplazamiento in range(cantidad):
            self.robots[(inicio + desplazamiento) % cantidad].actuar()
        if self.complete:
            self.stop()

    def end(self):
        self.report('entregados', self.entregados)
        self.report('pasos', self.t)
        self.report('bloqueos', sum(r.bloqueos for r in self.robots))

    def setup(self):
        # AgentPy calls setup again when run() resumes an initialized model.
        if hasattr(self, 'grid'):
            return
        n = int(self.p.tamano)
        cantidad = int(self.p.robots)
        if n < 3 or not 1 <= cantidad <= n:
            raise ValueError("Usa tamaño >= 3 y entre 1 y 'tamano' robots.")
        if self.p.radio_vision < 0:
            raise ValueError("El radio de visión no puede ser negativo.")

        self.grid = ap.Grid(self, (n, n))
        self.deposito = (0, 0)
        self.entregados = 0
        self.ocupadas = {}

        self.robots = ap.AgentList(self, cantidad, Robot)
        filas_barrido = list(range(min(2, n - 1), n, 4))
        if n - 1 - filas_barrido[-1] > 2:
            filas_barrido.append(n - 1)

        inicios = []
        for i, robot in enumerate(self.robots):
            robot.indice = i
            inicio_col = i * n // cantidad
            fin_col = (i + 1) * n // cantidad - 1
            inicios.append((filas_barrido[0], inicio_col))
            robot.estacionamiento = (n - 1, inicio_col)
            # Ruta serpenteante por todas las columnas de cada franja.
            # Guardar cada casilla evita huecos si se interrumpe para llevar un cubo.
            robot.ruta_exploracion = [
                (fila, columna)
                for j, fila in enumerate(filas_barrido)
                for columna in (range(inicio_col, fin_col + 1) if j % 2 == 0
                                else range(fin_col, inicio_col - 1, -1))
            ]

        self.grid.add_agents(self.robots, positions=inicios)
        self.ocupadas = {r.posicion(): r for r in self.robots}
        if len(self.ocupadas) != cantidad:
            raise RuntimeError("Dos robots comenzaron en la misma casilla")

        libres = [
            (f, c) for f in range(n) for c in range(n)
            if (f, c) != self.deposito and (f, c) not in self.ocupadas
        ]
        if not 0 <= self.p.cubos <= len(libres):
            raise ValueError("No caben tantos cubos en las casillas libres.")
        self.cubos = set(self.random.sample(libres, self.p.cubos))
        for robot in self.robots:
            robot.percibir()


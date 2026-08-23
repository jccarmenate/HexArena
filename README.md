# HexArena

Hex de escritorio para Windows: contra la IA (con dificultades), jugador vs
jugador local, y jugador vs jugador en red (LAN / IP directa). Interfaz
HTML/SVG con tema oscuro dentro de una ventana nativa ([pywebview](https://pywebview.flowrl.com/)),
motor de reglas y la IA (MCTS + RAVE + heurística de distancia y puentes) en
Python puro.

## Ejecutar en desarrollo

```bash
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

Para iterar solo en la interfaz (sin levantar Python cada vez), abre
`ui/dev.html` en un navegador — trae un `pywebview_stub.js` que simula la API
con un tablero y una IA de juguete, solo para probar los flujos de pantalla.

## Generar el .exe portable

```bash
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pyinstaller hex_app.spec
```

El resultado queda en `dist/HexArena.exe`: un único archivo, sin instalador,
que corre desde cualquier carpeta o USB. La primera vez que Windows lo
ejecute puede mostrar una advertencia de SmartScreen (el ejecutable no está
firmado); hay que elegir "Más información" → "Ejecutar de todas formas".

## Pruebas

```bash
.venv\Scripts\python tests\test_engine.py      # reglas + IA: legalidad, conexión, puentes
.venv\Scripts\python tests\test_network.py     # host/cliente por TCP en localhost
.venv\Scripts\python tests\test_difficulty.py  # Difícil debe ganarle a Fácil (lento, ~10s)
```

## Estructura

```
main.py            entry point: crea la ventana pywebview
engine/board.py     HexBoard: reglas, adyacencia, conexión, puentes
engine/ai.py        HexAI: MCTS + RAVE, sesgo Dijkstra, niveles de dificultad
engine/network.py   host/cliente TCP para el modo en red
engine/api.py       puente entre pywebview y la UI (window.pywebview.api.*)
ui/                 index.html + style.css + app.js
```

## Modo en red — alcance

Un jugador aloja la partida (queda escuchando en su red local) y comparte su
IP y puerto; el otro se conecta directamente. Es LAN / IP directa, sin
matchmaking ni NAT traversal — para jugar por internet el anfitrión tendría
que configurar port-forwarding en su router por su cuenta.

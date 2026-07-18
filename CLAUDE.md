# CLAUDE.md — Jackal J100 trajectory control (ROS 2 Humble)

Workspace ROS 2 en el computador de a bordo del robot (`cpr-j100-0751` — **esta
máquina ES el robot físico**). Paquete propio: `src/jackal_trajectory_control`
(Python / rclpy). Objetivo: teleoperación manual con mando PlayStation +
trayectoria serpentina automática por odometría, activada con el botón X.
(Los datos térmicos que recolecta esta ruta los consume el proyecto ISAMI, que
vive en OTRO repositorio — no mezclar instrucciones.)

## Robot y sistema
- Clearpath Jackal J100, namespace `/j100_0751`, hostname `cpr-j100-0751`.
- Ubuntu 22.04, ROS 2 Humble, workspace `~/jackal_ws`.
- Entorno: `source /etc/clearpath/setup.bash` y `source ~/jackal_ws/install/setup.bash`.

## DDS — CRÍTICO
Los servicios Clearpath corren como usuario `administrator`; las sesiones de
`isami` NO reciben datos por la memoria compartida de Fast DDS (los segmentos
en `/dev/shm` son de otro usuario). El discovery sí funciona (los topics se
ven), pero `echo`/suscripciones quedan mudos. Arreglo: perfil UDP-only en
`~/jackal_ws/fastdds_udp_only.xml`, exportado en `~/.bashrc` como
`FASTRTPS_DEFAULT_PROFILES_FILE`. Toda terminal/launch de usuario necesita ese
export activo. No "arreglar" esto tocando la configuración de Clearpath.

## Reglas de seguridad (INNEGOCIABLES)
1. No modificar paquetes de sistema Clearpath ni nada bajo `/etc/clearpath/`.
2. No desactivar ni puentear el paro de emergencia.
3. No publicar comandos de velocidad durante análisis o diagnóstico.
4. Toda prueba de movimiento empieza con las ruedas levantadas (o en simulación
   en un equipo aparte — `clearpath_gz` NO está instalado en el robot).
5. Pedir autorización explícita del usuario antes de ejecutar cualquier cosa que
   pueda mover el robot físico.
6. El mando manual siempre debe poder sobreponerse: el controlador publica SOLO
   en `cmd_vel` (entrada "external" del twist_mux, prioridad mínima), así el
   joystick gana por diseño.
7. Código propio solo dentro de este workspace, en Python/rclpy.

## Topics (verificados en el robot)
| Topic | Tipo | Uso |
|---|---|---|
| `/j100_0751/cmd_vel` | Twist | salida del controlador (twist_mux "external", prioridad 1) |
| `/j100_0751/joy_teleop/joy` | Joy | botones del mando (publisher RELIABLE) |
| `/j100_0751/joy_teleop/cmd_vel` | Twist | teleop manual (prioridad 10) |
| `/j100_0751/rc_teleop/cmd_vel` | Twist | RC (prioridad 12) |
| `/j100_0751/platform/odom/filtered` | Odometry | odometría EKF usada por el controlador |
| `/j100_0751/platform/cmd_vel_unstamped` | Twist | salida del mux hacia el hardware |
| `/j100_0751/platform/emergency_stop` | — | lock del mux, prioridad 255 |

twist_mux (`/etc/clearpath/platform/config/twist_mux.yaml`): rc 12 > joy 10 >
marker 8 > external 1; timeouts 0.5 s; e-stop bloquea todo.

## Mando (índices medidos en j100_0751)
X=0 inicia · Círculo=1 cambia modo · Cuadrado=2 fija home · Triángulo=3 cancela
(mantener = regreso a home) · L1=9 / R1=10 override manual.
Máquina de estados: `WAITING_FOR_HOME → IDLE → RUNNING / RETURNING_HOME /
MANUAL_OVERRIDE`. Cuadrado exige odometría fresca (<1 s); X exige home fijado.
Las suscripciones a joy y odom usan QoS BEST_EFFORT (compatible con el
publisher RELIABLE del joy).

## Build y pruebas
```bash
source /opt/ros/humble/setup.bash
colcon build --packages-select jackal_trajectory_control   # desde ~/jackal_ws
source install/setup.bash
cd src/jackal_trajectory_control && python3 -m pytest test/ -q   # 8 tests, sin ROS
```
- `src/jackal_trajectory_control_backup/` está congelado con `COLCON_IGNORE`:
  no editarlo ni quitarle el ignore (evita el choque de nombres que rompía el build).
- Lanzamiento (prueba reducida, ruedas levantadas y con autorización):
```bash
ros2 launch jackal_trajectory_control joystick_trajectory.launch.py \
  columns:=2 rows:=2 spacing_x:=0.50 spacing_y:=0.50 \
  max_linear_speed:=0.10 max_angular_speed:=0.25 dwell_seconds:=1.0
```
- Parámetros por YAML (`config/joystick.yaml`) o argumentos de launch; no
  hardcodear valores en Python.

## Estado (2026-07-18)
Hecho:
- Paquete deduplicado (3 copias con el mismo nombre rompían `colcon build`);
  build OK; tests 8/8.
- Causa raíz del "no reacciona" resuelta y verificada: SHM entre usuarios
  (ver sección DDS). Con el perfil UDP: odom 50 Hz recibida, e-stop=false,
  nodo lanzado y suscripciones correctas (verificación sin publicar Twists).
- `launch_joy` ahora default `false`: la plataforma ya publica joy; un segundo
  joy duplica flancos de botón.
Pendiente:
- Prueba con mando real: Cuadrado → "Home set" (sin movimiento), X → RUNNING
  SOLO con ruedas levantadas y autorización explícita.
- Watchdog de joy: si el mando deja de publicar en RUNNING, cancelar la misión
  (hoy la misión sigue sin posibilidad de override por mando).
- Autoarranque del nodo (más adelante).

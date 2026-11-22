import sys
import zmq
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
from time import time

def main():
    # Setup ZMQ
    context = zmq.Context()
    poller = zmq.Poller()

    # Sub to Port 5555 (HS and Knee Angle)
    socket_hs = context.socket(zmq.SUB)
    socket_hs.setsockopt(zmq.LINGER, 0)
    socket_hs.setsockopt_string(zmq.SUBSCRIBE, "")
    socket_hs.setsockopt(zmq.CONFLATE, True)
    socket_hs.connect("tcp://localhost:5555")
    poller.register(socket_hs, zmq.POLLIN)

    # Variables
    timings_sec = [0.15, 0.50, 0.80] # default mapping for k1, k2, k3
    time_data = []
    knee_data = []
    t0_gaitcycle = time()

    app = QtWidgets.QApplication(sys.argv)
    
    # Configure graph theme
    pg.setConfigOptions(antialias=True)
    win = pg.GraphicsLayoutWidget(show=True, title="Real-Time Knee Angle & State Visualizer")
    win.resize(1000, 600)
    win.setBackground('#1E1E1E')

    plot = win.addPlot(title="Knee Angle within Gait Cycle (K1 / K2 / K3)")
    plot.setLabel('left', "Knee Angle", units="deg")
    plot.setLabel('bottom', "Time from Heel Strike", units="s")
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.setYRange(-20, 100)
    plot.setXRange(0, 1.5)

    curve = plot.plot(pen=pg.mkPen('#00BFFF', width=4))

    colors = ['#FF4C4C', '#32CD32', '#9370DB']
    labels = ['K1', 'K2', 'K3']
    lines = []
    texts = []

    for i in range(3):
        line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(colors[i], width=2, style=QtCore.Qt.PenStyle.DashLine))
        text = pg.TextItem(labels[i], color=colors[i], anchor=(0, 1))
        font = text.textItem.font()
        font.setPointSize(12)
        font.setBold(True)
        text.setFont(font)
        
        plot.addItem(line)
        plot.addItem(text)
        lines.append(line)
        texts.append(text)

    def update_lines():
        for i in range(3):
            lines[i].setPos(timings_sec[i])
            texts[i].setPos(timings_sec[i], 95 - (i * 5))

    update_lines()

    def update():
        nonlocal t0_gaitcycle, time_data, knee_data, timings_sec
        try:
            socks = dict(poller.poll(0))
            
            if socket_hs in socks:
                data = socket_hs.recv_pyobj()
                hs_flag = data.get("hs_flag", 0)
                knee_angle = data.get("knee_angle", 0.0)
                
                # Fetch dynamically learned K1, K2, K3 gait phase percentages
                k1_pct = data.get("k1_pct", 15)
                k2_pct = data.get("k2_pct", 50)
                k3_pct = data.get("k3_pct", 80)
                dur = data.get("duration", 1.1)
                
                # Compute actual absolute time positions for the bounds
                timings_sec[0] = (k1_pct / 100.0) * dur
                timings_sec[1] = (k2_pct / 100.0) * dur
                timings_sec[2] = (k3_pct / 100.0) * dur
                update_lines()
                
                curr_time = time()
                
                if hs_flag == 1:
                    t0_gaitcycle = curr_time
                    time_data = [] # Reset plot data completely
                    knee_data = []
                
                time_from_hs = curr_time - t0_gaitcycle
                
                # Failsafe clear if HS event drops
                if time_from_hs > 5.0:
                    time_data = []
                    knee_data = []
                    t0_gaitcycle = curr_time
                    time_from_hs = 0.0
                    
                time_data.append(time_from_hs)
                knee_data.append(knee_angle)
                
                curve.setData(time_data, knee_data)
                
        except Exception as e:
            pass

    timer = QtCore.QTimer()
    timer.timeout.connect(update)
    timer.start(20)

    try:
        app.exec()
    finally:
        socket_hs.close()

if __name__ == '__main__':
    main()

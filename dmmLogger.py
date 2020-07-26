# MIT License

# Copyright (c) [2018] [Josh Hansen]

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from PyQt5 import uic, QtWidgets, QtCore
import collections
import pyqtgraph as pg
import numpy as np
import sys
import visa
import ctypes
import time

MEAS_TYPE_DC_VOLTAGE = 0
MEAS_TYPE_DC_CURRENT = 1

RANGE_DC_CURRENT_200UA = 0
RANGE_DC_CURRENT_2MA = 1
RANGE_DC_CURRENT_20MA = 2
RANGE_DC_CURRENT_200MA = 3
RANGE_DC_CURRENT_2A = 4
RANGE_DC_CURRENT_10A = 5

RANGE_DC_VOLTAGE_200MV = 0
RANGE_DC_VOLTAGE_2V = 1
RANGE_DC_VOLTAGE_20V = 2
RANGE_DC_VOLTAGE_200V = 3
RANGE_DC_VOLTAGE_1000V = 4

AUTO_ZERO_SELECT_OFF = 0
AUTO_ZERO_SELECT_ON = 1
AUTO_ZERO_SELECT_ONCE = 2

BUFFER_SIZE = 1000

qt_app = QtWidgets.QApplication(sys.argv)
starttime = time.time()
millis = lambda: int(round((time.time()-starttime) * 1000))
#def millis():
#    return int(round(time.time() ))

class LoggingThread(QtCore.QThread):
    sig = QtCore.pyqtSignal(list, int)
    keep_running = True

    def __init__(self, instrument, measType, signal):
        super(LoggingThread, self).__init__()
        self.instrument = instrument
        self.measType = measType
        self.sig.connect(signal)

    def __del__(self):
        self.wait()

    def exit(self):
        self.keep_running = False

    def run(self):
        while self.keep_running:
                startTime = millis()
                #self.instrument.write(":RATE:CURRent:DC F")
                #self.instrument.query("MEASure:VOLTage:DC")
                #self.instrument.write(":RATE:CURRent:DC F")
                #measurement = self.instrument.read()
                measurement = self.instrument.query("READ?")
                measurement = measurement[11:]
                print(startTime)
                self.sig.emit(measurement.split(","), startTime)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
            super(MainWindow, self).__init__()
            uic.loadUi('dmmLogger.ui', self)

            self.selectedInst = None
            self.selectedInstText = 'None'
            self.selectedMeasTypeText = 'DC Voltage'
            self.selectedMeasTypeInt = MEAS_TYPE_DC_VOLTAGE
            self.selectedRangeTypeInt = RANGE_DC_VOLTAGE_200MV
            self.autoZeroSelectInt = AUTO_ZERO_SELECT_OFF
            self.selectedResText = 'None'
            self.avgTotal = 0
            self.pointCount = 1
            self.startTime = 0
            self.measUnitStr = "mV"
            self.measUnitMult = 1

            self.dataBufferY = collections.deque([0.0]*BUFFER_SIZE, BUFFER_SIZE)

            self.x = np.linspace(0, BUFFER_SIZE, BUFFER_SIZE)
            self.y = np.zeros(BUFFER_SIZE, dtype=np.float)

            self.plotList = []
            self.plotArray = np.array([])
            self.plt = self.plotGV
            self.plt.showGrid(x=True, y=True)
            self.plt.setClipToView = True

            pltPen = pg.mkPen(width=1.0, color=(255,0,0))
            self.curve = self.plt.plot(self.x, self.y, pen=pltPen)

            self.visa_rm = visa.ResourceManager('@py')
            self.startButton.clicked.connect(self.startButtonClicked)
            self.stopButton.clicked.connect(self.stopButtonClicked)
            self.scanButton.clicked.connect(self.scanButtonClicked)
            self.setStatusBar(self.statusbar)

            self.instSelectCB.activated.connect(self.instSelectActivated)
            self.measTypeCB.activated.connect(self.measTypeCBActivated)
            self.rangeCB.activated.connect(self.rangeCBActivated)
            self.autoZeroCB.activated.connect(self.autoZeroCBActivated)

            self.measTypeCB.addItem('DC Voltage')
            self.measTypeCB.addItem('DC Current')

            self.autoZeroCB.addItem('Off')
            self.autoZeroCB.addItem('On')
            self.autoZeroCB.addItem('Once')
            self.addVoltageRanges()

            self.show()

    def startButtonClicked(self):
        print('START')
        self.avgTotal = 0
        self.pointCount = 1
        self.selectedInst = self.visa_rm.open_resource(self.selectedInstText)

        self.selectedInst.write("CMDS RIGOL")
        print(self.selectedInst.query("*IDN?"))
        #self.selectedInst.write("TRIG:SOUR IMM")
        #print(self.selectedInst.query("TRIGger:SOURce?"))
        if self.selectedMeasTypeInt == MEAS_TYPE_DC_VOLTAGE:
            if self.selectedRangeTypeInt == RANGE_DC_VOLTAGE_200MV:
                self.measUnitStr = "mV"
                self.measUnitMult = 1000
            else:
                self.measUnitStr = "V"
                self.measUnitMult = 1
            print("Sending voltage command :MEAS:VOLT:DC " + str(self.selectedRangeTypeInt))
            self.selectedInst.write(":MEAS:VOLT:DC " + str(self.selectedRangeTypeInt))
            self.selectedInst.write(":RATE:VOLTage:DC F")
        elif self.selectedMeasTypeInt == MEAS_TYPE_DC_CURRENT:
            if self.selectedRangeTypeInt <= RANGE_DC_CURRENT_200MA:
                self.measUnitStr = "mA"
                self.measUnitMult = 1000
            else:
                self.measUnitStr = "A"
                self.measUnitMult = 1

            print('Send current command')
            self.selectedInst.write(":MEAS:CURR:DC " + str(self.selectedRangeTypeInt))
            self.selectedInst.write(":RATE:CURRent:DC F")
        #time.sleep(10)

        self.selectedInst.write("CMDS AGILENT")

        if self.autoZeroSelectInt == AUTO_ZERO_SELECT_OFF:
            self.selectedInst.write("ZERO:AUTO OFF")
        elif self.autoZeroSelectInt == AUTO_ZERO_SELECT_ON:
            self.selectedInst.write("ZERO:AUTO ON")
        elif self.autoZeroSelectInt == AUTO_ZERO_SELECT_ONCE:
            self.selectedInst.write("ZERO:AUTO ONCE")

        #self.selectedInst.write(":TRIG:DELAY 0")
        #self.selectedInst.write("TRIG:COUNT 1")
        #self.selectedInst.write("TRIG:SOUR IMM")
        self.selectedInst.write("SAMP:COUN 112")
        self.startTime = time.time()

        self.loggingThread = LoggingThread(self.selectedInst, self.selectedMeasTypeInt, self.addPlotPoint)
        self.loggingThread.start()

    def addCurrentRanges(self):
        self.rangeCB.clear()
        self.rangeCB.addItem('200uA')
        self.rangeCB.addItem('2mA')
        self.rangeCB.addItem('20mA')
        self.rangeCB.addItem('200mA')
        self.rangeCB.addItem('2A')
        self.rangeCB.addItem('10A')

    def addVoltageRanges(self):
        self.rangeCB.clear()
        self.rangeCB.addItem('200mV')
        self.rangeCB.addItem('2V')
        self.rangeCB.addItem('20V')
        self.rangeCB.addItem('200V')
        self.rangeCB.addItem('1000V')

    def stopButtonClicked(self):
        print('STOP')
        if self.loggingThread.isRunning():
            self.loggingThread.exit()

    def scanButtonClicked(self):
        print("SCAN")
        self.addInstruments(self.visa_rm.list_resources())
        self.selectedInstText = self.instSelectCB.itemText(0)

    def instSelectActivated(self, index):
        self.selectedInstText = self.instSelectCB.itemText(index)
        print(self.selectedInstText)

    def measTypeCBActivated(self, index):
        self.selectedMeasTypeText = self.measTypeCB.itemText(index)
        self.selectedMeasTypeInt = index
        if index == MEAS_TYPE_DC_VOLTAGE :
            self.addVoltageRanges()
        elif index == MEAS_TYPE_DC_CURRENT:
            self.addCurrentRanges()
        print(self.selectedMeasTypeText)

    def rangeCBActivated(self, index):
        self.selectedRangeTypeInt = index

    def autoZeroCBActivated(self, index):
        self.autoZeroSelectInt = index

    def addInstruments(self, instItems):
        self.instSelectCB.addItems(instItems)

    def addPlotPoint(self, points, startTime):

        for i in range(len(points)):
            pointData = float(points[i]) * self.measUnitMult
            self.avgTotal += pointData
            self.dataBufferY.append(pointData)

        self.pointCount += len(points)
        self.y[:] = self.dataBufferY
        self.curve.setData(self.x, self.y)
        qt_app.processEvents()
        samplesS = (1/((millis() - startTime)/len(points)))*1000

        currentTime = time.time() - self.startTime
        m, s = divmod(currentTime, 60)
        h, m = divmod(m, 60)

        self.timeLB.setText("%d:%02d:%02d" % (h, m, s))
        self.avgTotalLB.setText("%0.4f " % (self.avgTotal/self.pointCount) + self.measUnitStr)
        self.samplesLB.setText("%0.0f" % samplesS)

if __name__ == '__main__':

    mainWindow = MainWindow()
    sys.exit(qt_app.exec())
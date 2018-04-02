try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *


class BoundingBoxWidget(QWidget):

    def __init__(self, parent = None):
        QWidget.__init__(self, parent = parent)

        lineEditLabelsName = [ 'lat', 'lon']
        dropDownBoxLabelsname = [ 'sub']

        self.labelLineEdits = {}
        self.dropDownBoxs = {}

        self.checkBox = QCheckBox()
        self.checkBox.setMaximumWidth(20)
        #self.numberOfBoundingBoxs = QLineEdit()
        #self.numberOfBoundingBoxs.setMaximumWidth(50)
        self.pasteButton = QPushButton('Paste Geo')
        self.pasteButton.setMaximumWidth(90)

        topLayout = QHBoxLayout()
        topLayout.setAlignment(Qt.AlignLeft)
        boundingBoxInfoLayout = QGridLayout()
        boundingBoxInfoLayout.setContentsMargins(0, 0, 0, 0)
        vLayout = QVBoxLayout()
        vLayout.setContentsMargins(0, 0, 0, 0)

        topLayout.addWidget(self.checkBox)
        #topLayout.addWidget(self.numberOfBoundingBoxs)
        topLayout.addWidget(self.pasteButton)

        x = 0
        y = 1
        for itr in range(len(lineEditLabelsName)):
            boundingBoxInfoLayout.addWidget(QLabel(lineEditLabelsName[itr] + ': '),x/6, x % 6)
            self.labelLineEdits[lineEditLabelsName[itr]] = QLineEdit()
            boundingBoxInfoLayout.addWidget(self.labelLineEdits[lineEditLabelsName[itr]],x/6,y % 6)
            x += 2
            y += 2

        for itr in range(len(dropDownBoxLabelsname)):
            boundingBoxInfoLayout.addWidget(QLabel(dropDownBoxLabelsname[itr] + ': '),x/6,x % 6)
            self.dropDownBoxs[dropDownBoxLabelsname[itr]] = QComboBox()
            boundingBoxInfoLayout.addWidget(self.dropDownBoxs[dropDownBoxLabelsname[itr]],x/6 , y % 6)
            x += 2
            y += 2

        vLayout.addLayout(topLayout)
        vLayout.addLayout(boundingBoxInfoLayout)
        self.boundingBoxInfoLayoutContainer = QWidget()
        self.boundingBoxInfoLayoutContainer.setLayout(vLayout)
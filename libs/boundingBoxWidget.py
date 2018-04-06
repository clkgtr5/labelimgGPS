try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import os

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
        self.pasteButton.setMaximumWidth(80)
        self.pasteAllButton =  QPushButton('Paste All')
        self.pasteAllButton.setMaximumWidth(80)
        self.gotoGeo = QPushButton('Goto Geo')
        self.gotoGeo.setMaximumWidth(80)

        # topLayout = QHBoxLayout()
        # topLayout.setAlignment(Qt.AlignLeft|Qt.AlignCenter)
        boundingBoxInfoLayout = QGridLayout()
        boundingBoxInfoLayout.setAlignment(Qt.AlignLeft | Qt.AlignCenter)
        boundingBoxInfoLayout.setContentsMargins(0, 0, 0, 0)
        wholeLayout = QHBoxLayout()
        wholeLayout.setContentsMargins(0, 0, 0, 0)

        #all the componment add to grid layout first line.
        boundingBoxInfoLayout.addWidget(self.checkBox,0,0)
        #topLayout.addWidget(self.numberOfBoundingBoxs)
        boundingBoxInfoLayout.addWidget(self.pasteButton,0,1)
        boundingBoxInfoLayout.addWidget(self.pasteAllButton,0,2)
        x = 3
        y = 4
        for itr in range(len(lineEditLabelsName)):
            label = QLabel(lineEditLabelsName[itr] + ': ')
            label.setMaximumWidth(40)
            label.setMaximumHeight(30)
            boundingBoxInfoLayout.addWidget(label,x/10, x % 10)
            self.labelLineEdits[lineEditLabelsName[itr]] = QLineEdit()
            self.labelLineEdits[lineEditLabelsName[itr]].setMaximumWidth(100)
            boundingBoxInfoLayout.addWidget(self.labelLineEdits[lineEditLabelsName[itr]],x/10,y % 10)
            x += 2
            y += 2

        for itr in range(len(dropDownBoxLabelsname)):
            label = QLabel(dropDownBoxLabelsname[itr] + ': ')
            label.setMaximumWidth(40)
            label.setMaximumHeight(30)
            boundingBoxInfoLayout.addWidget(label,x/9,x % 9)
            self.dropDownBoxs[dropDownBoxLabelsname[itr]] = QComboBox()
            self.dropDownBoxs[dropDownBoxLabelsname[itr]].setMaximumWidth(80)
            boundingBoxInfoLayout.addWidget(self.dropDownBoxs[dropDownBoxLabelsname[itr]],x/9 , y % 9)
            x += 2
            y += 2

        self.thumbnail = QLabel()
        self.thumbnail.setFixedHeight(80)
        self.thumbnail.setFixedWidth(80)
        self.thumbnail.setScaledContents(True)
        #self.thumbnail.setPixmap(QPixmap(os.getcwd() + "/icons/close.png"))
        #print(os.getcwd() + "icons/color_line.png")
        #boundingBoxInfoLayout.addWidget( self.thumbnail, x / 11, x % 11)

        boundingBoxInfoLayout.addWidget(self.gotoGeo, x / 12, x % 12)
        boundingBoxInfoLayout.setAlignment(Qt.AlignTop |Qt.AlignLeft)
        #wholeLayout.addLayout(topLayout)
        wholeLayout.addLayout(boundingBoxInfoLayout)
        self.boundingBoxInfoLayoutContainer = QWidget()
        self.boundingBoxInfoLayoutContainer.setLayout(wholeLayout)
        self.boundingBoxInfoLayoutContainer.setAutoFillBackground(True)
        p = self.boundingBoxInfoLayoutContainer.palette()
        p.setColor(self.boundingBoxInfoLayoutContainer.backgroundRole(), Qt.white)
        self.boundingBoxInfoLayoutContainer.setPalette(p)
        self.boundingBoxInfoLayoutContainer.setMaximumHeight(50)
        #self.boundingBoxInfoLayoutContainer.setStyleSheet("background-color: white ")
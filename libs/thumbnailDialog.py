try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.lib import newIcon
import os

BB = QDialogButtonBox
class ThumbnailDialog(QDialog):
    def __init__(self, parent = None):
        super(ThumbnailDialog, self).__init__(parent)
        self.setBaseSize(300,350)
        self.fileName = QLabel(u'Save File Name:')
        self.fileName.setFixedHeight(20)
        self.fileName.setFixedWidth(200)
        self.fileName.setAlignment(Qt.AlignTop)
        self.imgName = QComboBox()

        self.imgThumbnail = QLabel()
        self.imgThumbnail.setFixedWidth(200)
        self.imgThumbnail.setFixedHeight(200)

        self.imgThumbnail.setScaledContents(True)
        self.imgThumbnail.setAlignment(Qt.AlignCenter)

        self.buttonBox = bb = BB(BB.Ok | BB.Cancel, Qt.Horizontal, self)
        bb.button(BB.Ok).setIcon(newIcon('done'))
        bb.button(BB.Cancel).setIcon(newIcon('undo'))

        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)

        self.imgData = None
        self.isSaved = False

        layout = QVBoxLayout()
        layout.addWidget(self.fileName)
        layout.addWidget(self.imgName)
        layout.addWidget(self.imgThumbnail)
        layout.addWidget(bb)
        self.setLayout(layout)

    def save(self):
        try:
            imgFileName = self.imgName.currentText()
            self.imgData.save(os.getcwd() + '/icons/thumbnails/{}.png'.format(imgFileName), 'PNG')
            print('save successed:',imgFileName)
            self.isSaved = True
            self.accept()
        except:
            print('save thumbnail failed')



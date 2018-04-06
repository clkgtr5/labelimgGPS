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
        self.setBaseSize(600,650)
        self.fileName = QLabel(u'Save File Name:')
        self.fileName.setFixedHeight(20)
        self.fileName.setFixedWidth(200)
        self.fileName.setAlignment(Qt.AlignTop)
        self.imgName = QComboBox()

        self.imgThumbnail = QLabel()
        self.imgThumbnail.setMinimumWidth(180)
        self.imgThumbnail.setMinimumHeight(180)
        self.imgThumbnail.setMaximumWidth(240)
        self.imgThumbnail.setMaximumHeight(240)

        self.imgThumbnail.setScaledContents(True)
        self.imgThumbnail.setAlignment(Qt.AlignCenter)

        self.buttonBox = bb = BB(BB.Ok | BB.Cancel, Qt.Horizontal, self)
        bb.button(BB.Ok).setIcon(newIcon('done'))
        bb.button(BB.Cancel).setIcon(newIcon('undo'))

        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)

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
            pixmap = self.imgThumbnail.pixmap()
            # saveFile = QFile()
            # saveFile.open(QIODevice.WriteOnly)
            image = pixmap.toImage()
            saveImage = QImage(image)
            saveImage.save(os.getcwd()+'/icons/thumbnails/{}.png'.format(imgFileName),'png')
            print('save successed:',imgFileName)
            self.isSaved = True
            self.accept()
        except:
            print('save thumbnail failed')
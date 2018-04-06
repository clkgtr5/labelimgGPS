#!/usr/bin/env python
# -*- coding: utf-8 -*-
import codecs
import os.path
import re
import sys
import subprocess
import json
import os

from functools import partial
from collections import defaultdict

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtCore import QUrl
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip
        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

# Add External libs
from PIL.ExifTags import TAGS, GPSTAGS
from PIL import Image
from PIL import ImageQt
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement
from lxml import etree
import resources

# Add internal libs
from libs.constants import *
from libs.lib import struct, newAction, newIcon, addActions, fmtShortcut, generateColorByText
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.labelDialog import LabelDialog
from libs.colorDialog import ColorDialog
from libs.labelFile import LabelFile, LabelFileError
from libs.toolBar import ToolBar
from libs.pascal_voc_io import PascalVocReader
from libs.pascal_voc_io import XML_EXT,ENCODE_METHOD
from libs.ustr import ustr
from libs.version import __version__
from libs.getExImgInfo import get_exif_data,_get_if_exist,_convert_to_degress,get_lat_lon
from libs.boundingBoxWidget import BoundingBoxWidget
from libs.thumbnailDialog import ThumbnailDialog
__appname__ = 'labelImg'

# Utility functions and classes.

def have_qstring():
    '''p3/qt5 get rid of QString wrapper as py3 has native unicode str type'''
    return not (sys.version_info.major >= 3 or QT_VERSION_STR.startswith('5.'))

def util_qt_strlistclass():
    return QStringList if have_qstring() else list


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


# PyQt5: TypeError: unhashable type: 'QListWidgetItem'
class HashableQListWidgetItem(QListWidgetItem):

    def __init__(self, *args):
        super(HashableQListWidgetItem, self).__init__(*args)

    def __hash__(self):
        return hash(id(self))


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, defaultFilename=None, defaultPrefdefClassFile=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)
        self.defaultLayout = None
        self.defaultURL = 'https://vtrans.github.io/signs-data-viewer/?lon=-72.683117&lat=44.296882&zoomLevel=18'
                          #"https://www.google.com/maps"
                          # "http://www.arcgis.com/home/webmap/viewer.html?url=http%3A%2F%2Fmaps.vtrans.vermont.gov" \
                          # "%2Farcgis%2Frest%2Fservices%2FAMP%2FSign_Symbols%2FFeatureServer&source=sd"
                          # "https://rawgit.com/VTrans/signs-data-viewer/master/index.html"
        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings

        # Save as Pascal voc xml
        self.defaultSaveDir = None
        self.usingPascalVocFormat = True
        # For loading all image under a directory
        self.mImgList = []
        self.dirname = None
        self.labelHist = []
        self.lastOpenDir = None

        # Whether we need to save or not.
        self.dirty = False

        self._noSelectionSlot = False
        self._beginner = True
        self.screencastViewer = "firefox"
        self.screencast = "https://youtu.be/p0nR2YsCY_U"

        # Load predefined classes to the list
        self.loadPredefinedClasses(defaultPrefdefClassFile)

        # Main widgets and related state.
        self.labelDialog = LabelDialog(parent=self, listItem=self.labelHist)
       
        self.itemsToShapes = {}
        self.shapesToItems = {}

        # map the img info items (boundingBoxWidget class) to shape.
        self.bndWidgetsToShapes = {}
        self.shapesToBndWidgets = {}
        self.pasteGeosToBndWidgets = {}
        self.pasteAllsToBndWidgets = {}
        self.QComboBoxSubsToBndWidgets = {}
        #self.checkBoxesToBndWidgets = {}
        self.gotoGeoToBndWidgets = {}

        self.bndNum = 0
        #refer cropped img
        self.cropped_img = None
        self.thumbnailDialog = None

        self.prevLabelText = ''
        # save xml object labels value
        self.objects = {}

        listLayout = QVBoxLayout()
        listLayout.setContentsMargins(0, 0, 0, 0)

        # Create a widget for using default label
        self.useDefaultLabelCheckbox = QCheckBox(u'Use default label')
        self.useDefaultLabelCheckbox.setChecked(True)
        self.defaultLabelTextLine = QLineEdit()
        self.defaultLabelTextLine.setText('SIGN')
        useDefaultLabelQHBoxLayout = QHBoxLayout()
        useDefaultLabelQHBoxLayout.addWidget(self.useDefaultLabelCheckbox)
        useDefaultLabelQHBoxLayout.addWidget(self.defaultLabelTextLine)
        useDefaultLabelContainer = QWidget()
        useDefaultLabelContainer.setLayout(useDefaultLabelQHBoxLayout)

        # Create a widget for edit and diffc button
              
        self.diffcButton = QCheckBox(u'difficult')
        self.diffcButton.setChecked(False)
        self.diffcButton.stateChanged.connect(self.btnstate)
        self.diffcButton.setVisible(False) #jchen add to save the space.
        self.editButton = QToolButton()
        self.editButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # Add some of widgets to listLayout
        listLayout.addWidget(self.editButton)
        listLayout.addWidget(self.diffcButton)
        listLayout.addWidget(useDefaultLabelContainer)

        # Create and add a widget for showing current label items
        self.labelList = QListWidget()
        labelListContainer = QWidget()
        labelListContainer.setLayout(listLayout)
        self.labelList.itemActivated.connect(self.labelSelectionChanged)
        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.labelList.itemDoubleClicked.connect(self.editLabel)
        # Connect to itemChanged to detect checkbox changes.
        self.labelList.itemChanged.connect(self.labelItemChanged)
        listLayout.addWidget(self.labelList)
        
        # Jchen27 = 03152018 add associate button
        # self.associateButton = QPushButton('associate', self)
        # self.associateButton.setToolTip('Get clipBoardInfo by stop')
        # self.associateButton.clicked.connect(self.associateButtonState)
        # self.clipBoardInfo = QLineEdit()
        # associateQHBoxLayout = QHBoxLayout()
        # associateQHBoxLayout.addWidget(self.associateButton)
        # associateQHBoxLayout.addWidget(self.clipBoardInfo)
        # associateContainer = QWidget()
        # associateContainer.setLayout(associateQHBoxLayout)
        # listLayout.addWidget(associateContainer)

        # self.clipBoardInfo.setText(QApplication.clipboard().text())

        self.dock = QDockWidget(u'Box Labels', self)
        self.dock.setObjectName(u'Labels')
        self.dock.setWidget(labelListContainer)

        # Tzutalin 20160906 : Add file list and dock to move faster
        self.fileListWidget = QListWidget()
        self.fileListWidget.itemDoubleClicked.connect(self.fileitemDoubleClicked)
        filelistLayout = QVBoxLayout()
        filelistLayout.setContentsMargins(0, 0, 0, 0)
        filelistLayout.addWidget(self.fileListWidget)
        fileListContainer = QWidget()
        fileListContainer.setLayout(filelistLayout)
        self.filedock = QDockWidget(u'File List', self)
        self.filedock.setObjectName(u'Files')
        self.filedock.setWidget(fileListContainer)

        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)
        
        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoomRequest)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }
        self.scrollArea = scroll
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        # Tzutalin 20160906 : Add file list and dock to move faster
        self.addDockWidget(Qt.RightDockWidgetArea, self.filedock)
        self.filedock.setFeatures(QDockWidget.DockWidgetFloatable)

        self.dockFeatures = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

        # Jchen =20180305: add a widget for webbrowser to load map
        # page viewer
        self.webViewer = QWebEngineView()
        self.webViewer.setMinimumHeight(100)
        self.webViewer.page()
        self.webViewer.load(QUrl(self.defaultURL))

        # navigation_bar
        self.navigation_bar = QToolBar('Navigation')
        self.navigation_bar.setIconSize(QSize(16, 16))

        #add buttons to navigation bar
        back_button = QAction(QIcon('icons/backward.png'), 'Back', self)
        next_button = QAction(QIcon('icons/forward.png'), 'Forward', self)
        home_button = QAction(QIcon('icons/home.png'), 'home', self)
        reload_button = QAction(QIcon('icons/reload.png'), 'reload', self)

        back_button.triggered.connect(self.webViewer.back)
        next_button.triggered.connect(self.webViewer.forward)
        home_button.triggered.connect(self.back_to_home)
        reload_button.triggered.connect(self.webViewer.reload)

        #add buttons to navigation_bar
        self.navigation_bar.addAction(back_button)
        self.navigation_bar.addAction(next_button)
        self.navigation_bar.addAction(home_button)
        self.navigation_bar.addAction(reload_button)

        #get enter for url
        self.urlbar = QLineEdit()
        self.urlbar.returnPressed.connect(self.navigate_to_url)

        self.navigation_bar.addSeparator()
        self.navigation_bar.addWidget(self.urlbar)

        # change the webbroswer url
        self.webViewer.urlChanged.connect(self.renew_urlbar)

        webBrowserLayout = QVBoxLayout()
        webBrowserLayout.setContentsMargins(0, 0, 0, 0)
        webBrowserLayout.addWidget(self.navigation_bar) #add navigation_bar
        webBrowserLayout.addWidget(self.webViewer)
        webBrowserContainer = QWidget()
        webBrowserContainer.setLayout(webBrowserLayout)

        # add scroll to webbrowser
        webScrollArea = QScrollArea()
        webScrollArea.setWidgetResizable(True)
        webScrollArea.setWidget(webBrowserContainer)

        # Jchen =20180305: add a webbrowser and dock to move faster
        self.webDock = QDockWidget(u'Traffic Sign Map', self)
        self.webDock.setObjectName(u'Browser')
        self.webDock.setWidget(webScrollArea)

        self.addDockWidget(Qt.RightDockWidgetArea, self.webDock)
        self.webDock.setFeatures(QDockWidget.DockWidgetFloatable)

        self.dockFeatures = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

        # Jchen = 20180311 add a dock to show the image infomation

        self.createThumbnail = QPushButton('create ThumbN', self)
        self.createThumbnail.setFixedWidth(120)
        self.createThumbnail.clicked.connect(self.createThumbnailClicked)

        self.thumbnail = QLabel()
        self.thumbnail.setMinimumWidth(100)
        self.thumbnail.setMinimumHeight(100)
        self.thumbnail.setScaledContents(True)
        # Connect to itemChanged to detect checkbox changes.
        self.imgInfodock = QDockWidget(u'image info', self)
        self.imgInfodock.setObjectName(u'img  infos')


        self.addDockWidget(Qt.RightDockWidgetArea, self.imgInfodock)
        self.imgInfodock.setFeatures(QDockWidget.DockWidgetFloatable)

        self.dockFeatures = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

        # Actions
        action = partial(newAction, self)
        quit = action('&Quit', self.close,
                      'Ctrl+Q', 'quit', u'Quit application')

        open = action('&Open', self.openFile,
                      'Ctrl+O', 'open', u'Open image or label file')

        opendir = action('&Open Dir', self.openDirDialog,
                         'Ctrl+u', 'open', u'Open Dir')

        changeSavedir = action('&Change Save Dir', self.changeSavedirDialog,
                               'Ctrl+r', 'open', u'Change default saved Annotation dir')

        openAnnotation = action('&Open Annotation', self.openAnnotationDialog,
                                'Ctrl+Shift+O', 'open', u'Open Annotation')

        openNextImg = action('&Next Image', self.openNextImg,
                             'd', 'next', u'Open Next')

        openPrevImg = action('&Prev Image', self.openPrevImg,
                             'a', 'prev', u'Open Prev')

        verify = action('&Verify Image', self.verifyImg,
                        'space', 'verify', u'Verify Image')

        save = action('&Save', self.saveFile,
                      'Ctrl+S', 'save', u'Save labels to file', enabled=False)

        saveAs = action('&Save As', self.saveFileAs,
                        'Ctrl+Shift+S', 'save-as', u'Save labels to a different file', enabled=False)

        close = action('&Close', self.closeFile, 'Ctrl+W', 'close', u'Close current file')

        resetAll = action('&ResetAll', self.resetAll, None, 'resetall', u'Reset all')

        color1 = action('Box Line Color', self.chooseColor1,
                        'Ctrl+L', 'color_line', u'Choose Box line color')

        createMode = action('Create\nRectBox', self.setCreateMode,
                            'w', 'new', u'Start drawing Boxs', enabled=False)
        editMode = action('&Edit\nRectBox', self.setEditMode,
                          'Ctrl+J', 'edit', u'Move and edit Boxs', enabled=False)

        create = action('Create\nRectBox', self.createShape,
                        'w', 'new', u'Draw a new Box', enabled=False)
        delete = action('Delete\nRectBox', self.deleteSelectedShape,
                        'Delete', 'delete', u'Delete', enabled=False)
        copy = action('&Duplicate\nRectBox', self.copySelectedShape,
                      'Ctrl+D', 'copy', u'Create a duplicate of the selected Box',
                      enabled=False)

        advancedMode = action('&Advanced Mode', self.toggleAdvancedMode,
                              'Ctrl+Shift+A', 'expert', u'Switch to advanced mode',
                              checkable=True)

        hideAll = action('&Hide\nRectBox', partial(self.togglePolygons, False),
                         'Ctrl+H', 'hide', u'Hide all Boxs',
                         enabled=False)
        showAll = action('&Show\nRectBox', partial(self.togglePolygons, True),
                         'Ctrl+A', 'hide', u'Show all Boxs',
                         enabled=False)

        help = action('&Tutorial', self.showTutorialDialog, None, 'help', u'Show demos')
        showInfo = action('&Information', self.showInfoDialog, None, 'help', u'Information')

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (fmtShortcut("Ctrl+[-+]"),
                                             fmtShortcut("Ctrl+Wheel")))
        self.zoomWidget.setEnabled(False)

        zoomIn = action('Zoom &In', partial(self.addZoom, 10),
                        'Ctrl++', 'zoom-in', u'Increase zoom level', enabled=False)
        zoomOut = action('&Zoom Out', partial(self.addZoom, -10),
                         'Ctrl+-', 'zoom-out', u'Decrease zoom level', enabled=False)
        zoomOrg = action('&Original size', partial(self.setZoom, 100),
                         'Ctrl+=', 'zoom', u'Zoom to original size', enabled=False)
        fitWindow = action('&Fit Window', self.setFitWindow,
                           'Ctrl+F', 'fit-window', u'Zoom follows window size',
                           checkable=True, enabled=False)
        fitWidth = action('Fit &Width', self.setFitWidth,
                          'Ctrl+Shift+F', 'fit-width', u'Zoom follows window width',
                          checkable=True, enabled=False)
        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut,
                       zoomOrg, fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action('&Edit Label', self.editLabel,
                      'Ctrl+E', 'edit', u'Modify the label of the selected Box',
                      enabled=False)
        self.editButton.setDefaultAction(edit)

        shapeLineColor = action('Shape &Line Color', self.chshapeLineColor,
                                icon='color_line', tip=u'Change the line color for this specific shape',
                                enabled=False)
        shapeFillColor = action('Shape &Fill Color', self.chshapeFillColor,
                                icon='color', tip=u'Change the fill color for this specific shape',
                                enabled=False)

        labels = self.dock.toggleViewAction()
        labels.setText('Show/Hide Label Panel')
        labels.setShortcut('Ctrl+Shift+L')

        # Lavel list context menu.
        labelMenu = QMenu()
        addActions(labelMenu, (edit, delete))
        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(
            self.popLabelListMenu)

        # Store actions for further handling.
        self.actions = struct(save=save, saveAs=saveAs, open=open, close=close, resetAll = resetAll,
                              lineColor=color1, create=create, delete=delete, edit=edit, copy=copy,
                              createMode=createMode, editMode=editMode, advancedMode=advancedMode,
                              shapeLineColor=shapeLineColor, shapeFillColor=shapeFillColor,
                              zoom=zoom, zoomIn=zoomIn, zoomOut=zoomOut, zoomOrg=zoomOrg,
                              fitWindow=fitWindow, fitWidth=fitWidth,
                              zoomActions=zoomActions,
                              fileMenuActions=(
                                  open, opendir, save, saveAs, close, resetAll, quit),
                              beginner=(), advanced=(),
                              editMenu=(edit, copy, delete,
                                        None, color1),
                              beginnerContext=(create, edit, copy, delete),
                              advancedContext=(createMode, editMode, edit, copy,
                                               delete, shapeLineColor, shapeFillColor),
                              onLoadActive=(
                                  close, create, createMode, editMode),
                              onShapesPresent=(saveAs, hideAll, showAll))

        self.menus = struct(
            file=self.menu('&File'),
            edit=self.menu('&Edit'),
            view=self.menu('&View'),
            help=self.menu('&Help'),
            recentFiles=QMenu('Open &Recent'),
            labelList=labelMenu)

        # Auto saving : Enable auto saving if pressing next
        self.autoSaving = QAction("Auto Saving", self)
        self.autoSaving.setCheckable(True)
        self.autoSaving.setChecked(settings.get(SETTING_AUTO_SAVE, False))
        # Sync single class mode from PR#106
        self.singleClassMode = QAction("Single Class Mode", self)
        self.singleClassMode.setShortcut("Ctrl+Shift+S")
        self.singleClassMode.setCheckable(True)
        self.singleClassMode.setChecked(settings.get(SETTING_SINGLE_CLASS, False))
        self.lastLabel = None

        self.saveLayout = QAction("Save layout when close", self)
        self.saveLayout.setCheckable(True)
        self.saveLayout.setChecked(False)

        addActions(self.menus.file,
                   (open, opendir, changeSavedir, openAnnotation, self.menus.recentFiles, save, saveAs, close, resetAll, quit))
        addActions(self.menus.help, (help, showInfo,self.saveLayout))
        addActions(self.menus.view, (
            self.autoSaving,
            self.singleClassMode,
            labels, advancedMode, None,
            hideAll, showAll, None,
            zoomIn, zoomOut, zoomOrg, None,
            fitWindow, fitWidth))

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        addActions(self.canvas.menus[1], (
            action('&Copy here', self.copyShape),
            action('&Move here', self.moveShape)))

        self.tools = self.toolbar('Tools')
        self.actions.beginner = (
            open, opendir, changeSavedir, openNextImg, openPrevImg, save, None, create, copy, delete, None, #after openPrevImg verify,
            zoomIn, zoom, zoomOut, fitWindow, fitWidth)

        self.actions.advanced = (
            open, opendir, changeSavedir, openNextImg, openPrevImg, save, None,
            createMode, editMode, None,
            hideAll, showAll)

        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.filePath = ustr(defaultFilename)
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        ## Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recentFileQStringList = settings.get(SETTING_RECENT_FILES)
                self.recentFiles = [ustr(i) for i in recentFileQStringList]
            else:
                self.recentFiles = recentFileQStringList = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(600, 500))
        position = settings.get(SETTING_WIN_POSE, QPoint(0, 0))
        self.resize(size)
        self.move(position)
        saveDir = ustr(settings.get(SETTING_SAVE_DIR, None))
        self.lastOpenDir = ustr(settings.get(SETTING_LAST_OPEN_DIR, None))
        if saveDir is not None and os.path.exists(saveDir):
            self.defaultSaveDir = saveDir
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.defaultSaveDir))
            self.statusBar().show()

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.lineColor = QColor(settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR))
        Shape.fill_color = self.fillColor = QColor(settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR))
        self.canvas.setDrawingColor(self.lineColor)
        # Add chris
        Shape.difficult = self.difficult

        def xbool(x):
            if isinstance(x, QVariant):
                return x.toBool()
            return bool(x)

        if xbool(settings.get(SETTING_ADVANCE_MODE, False)):
            self.actions.advancedMode.setChecked(True)
            self.toggleAdvancedMode()

        # Populate the File menu dynamically.
        self.updateFileMenu()

        # Since loading the file may take some time, make sure it runs in the background.
        if self.filePath and os.path.isdir(self.filePath):
            self.queueEvent(partial(self.importDirImages, self.filePath or ""))
        elif self.filePath:
            self.queueEvent(partial(self.loadFile, self.filePath or ""))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # Display cursor coordinates at the right of status bar
        self.labelCoordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.labelCoordinates)

        # Open Dir if deafult file
        if self.filePath and os.path.isdir(self.filePath):
            self.openDirDialog(dirpath=self.filePath)

        self.setFocusPolicy(Qt.StrongFocus)

    ##focus event.

    ## Support Functions ##
    # jchen = 20180403 create thumbnail

    def createThumbnailClicked(self):
        self.thumbnailDialog = ThumbnailDialog(self)

        TBD = self.thumbnailDialog
        with open('data/subclass.txt', 'r') as subclass:
            dropitems = subclass.readlines()
            for line in dropitems:
                line = line.strip()
                TBD.imgName.addItem(line)

        TBD.imgName.setEditable(True)
        allStrings = [TBD.imgName.itemText(i) for i in range(TBD.imgName.count())]
        autoComplete = QCompleter(allStrings)
        TBD.imgName.setCompleter(autoComplete)

        TBD.show()

        if (self.filePath):
            try:
                shape = self.canvas.selectedShape
                points = shape.points
                xmin = points[0].x()
                ymin = points[0].y()
                xmax = points[2].x()
                ymax = points[2].y()
            except:
                print('get croodinate failed')
            try:
                bndBoxWidget = self.shapesToBndWidgets[shape]
                TBD.imgName.setCurrentText(bndBoxWidget.dropDownBoxs['sub'].currentText())
            except:
                TBD.imgThumbnail.setText('No bounding \n box selected')
                print('get subclass failed')
            try:
                img = Image.open("{}".format(self.filePath))

                area = (xmin, ymin, xmax, ymax)
                cropped_img = img.crop(area)
                #cropped_img.save(os.getcwd() + '/icons/thumbnails/{}.png'.format(bndBoxWidget.dropDownBoxs['sub'].currentText()), 'PNG')
                TBD.imgData = cropped_img
            except:
                print('load image failed')
            try:
                cropped_img.resize((64,64), Image.ANTIALIAS)
                image1 = ImageQt.ImageQt(cropped_img)
                image2 = QImage(image1)
                pixmap = QPixmap.fromImage(image2)
                pixmap.scaled(64,64)
                TBD.imgThumbnail.setPixmap(pixmap)
            except:
                print('load img to label failed')

            # try:
            #     print(TBD.isSaved)
            #     if TBD.isSaved:
            #         subclassText = bndBoxWidget.dropDownBoxs['sub'].currentText()
            #         try:
            #             pixmap = QPixmap('icons/thumbnails/{}.png'.format(subclassText))
            #             pixmap.scaled(64, 64, Qt.KeepAspectRatio)
            #             bndBoxWidget.thumbnail.setPixmap(pixmap)
            #         except:
            #             bndBoxWidget.thumbnail.setText('No thumbnail')
            # except:
            #     print('change thumbnail failed')
    # jchen = 20180316 get clipboard info by focus on associatebutton
    def associateButtonState(self):
        self.clipBoardInfo.setText(QApplication.clipboard().text())
        return
    # navigate_to_url function

    def back_to_home(self):
        self.webViewer.load(QUrl(self.defaultURL))

    def navigate_to_url(self):
        q = QUrl(self.urlbar.text())
        if q.scheme() == '':
            q.setScheme('http')
        self.webViewer.setUrl(q)

    def renew_urlbar(self, q):
        #update url to new urlbar
        self.urlbar.setText(q.toString())
        self.urlbar.setCursorPosition(0)

    def noShapes(self):
        return not self.itemsToShapes

    def toggleAdvancedMode(self, value=True):
        self._beginner = not value
        self.canvas.setEditing(True)
        self.populateModeActions()
        self.editButton.setVisible(not value)
        if value:
            self.actions.createMode.setEnabled(True)
            self.actions.editMode.setEnabled(False)
            self.dock.setFeatures(self.dock.features() | self.dockFeatures)
        else:
            self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

    def populateModeActions(self):
        if self.beginner():
            tool, menu = self.actions.beginner, self.actions.beginnerContext
        else:
            tool, menu = self.actions.advanced, self.actions.advancedContext
        self.tools.clear()
        addActions(self.tools, tool)
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (self.actions.create,) if self.beginner()\
            else (self.actions.createMode, self.actions.editMode)
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def setBeginner(self):
        self.tools.clear()
        addActions(self.tools, self.actions.beginner)

    def setAdvanced(self):
        self.tools.clear()
        addActions(self.tools, self.actions.advanced)

    def setDirty(self):
        self.dirty = True
        self.actions.save.setEnabled(True)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.create.setEnabled(True)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.itemsToShapes.clear()
        self.shapesToItems.clear()
        self.labelList.clear()
        self.filePath = None
        self.imageData = None
        self.labelFile = None
        self.canvas.resetState()
        self.labelCoordinates.clear()

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filePath):
        if filePath in self.recentFiles:
            self.recentFiles.remove(filePath)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filePath)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    ## Callbacks ##
    def showTutorialDialog(self):
        return
        subprocess.Popen([self.screencastViewer, self.screencast])

    def showInfoDialog(self):
        msg = u'Name:{0} \nApp Version:{1} \n{2} '.format(__appname__, __version__, sys.version_info)
        QMessageBox.information(self, u'Information', msg)

    def createShape(self):
        assert self.beginner()
        self.canvas.setEditing(False)
        self.actions.create.setEnabled(False)
        #self.shapeSelectionChanged(True)
        # start here 0328

    def toggleDrawingSensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.
            #print('Cancel creation.')
            self.canvas.setEditing(True)
            self.canvas.restoreCursor()
            self.actions.create.setEnabled(True)

    def toggleDrawMode(self, edit=True):
        self.canvas.setEditing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def setCreateMode(self):
        assert self.advanced()
        self.toggleDrawMode(False)

    def setEditMode(self):
        assert self.advanced()
        self.toggleDrawMode(True)
        self.labelSelectionChanged()

    def updateFileMenu(self):
        currFilePath = self.filePath

        def exists(filename):
            return os.path.exists(filename)
        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f !=
                 currFilePath and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    def editLabel(self):
        if not self.canvas.editing():
            return
        item = self.currentItem()
        text = self.labelDialog.popUp(item.text())
        if text is not None:
            item.setText(text)
            item.setBackground(generateColorByText(text))
            self.setDirty()

    # Tzutalin 20160906 : Add file list and dock to move faster
    def fileitemDoubleClicked(self, item=None):
        currIndex = self.mImgList.index(ustr(item.text()))
        if currIndex < len(self.mImgList):
            filename = self.mImgList[currIndex]
            if filename:
                self.loadFile(filename)

    # Add chris
    def btnstate(self, item= None):
        """ Function to handle difficult examples
        Update on each object """
        if not self.canvas.editing():
            return

        item = self.currentItem()
        if not item: # If not selected Item, take the first one
            item = self.labelList.item(self.labelList.count()-1)

        difficult = self.diffcButton.isChecked()

        try:
            shape = self.itemsToShapes[item]
        except:
            pass
        # Checked and Update
        try:
            if difficult != shape.difficult:
                shape.difficult = difficult
                self.setDirty()
            else:  # User probably changed item visibility
                self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)
        except:
            pass

    # React to canvas signals.
    def shapeSelectionChanged(self, selected=False):
        if self._noSelectionSlot:
            self._noSelectionSlot = False
        else:
            shape = self.canvas.selectedShape
            if shape:
                self.shapesToItems[shape].setSelected(True)
            else:
                self.labelList.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.edit.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)


    def addLabel(self, shape):
        item = HashableQListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setBackground(generateColorByText(shape.label))
        self.itemsToShapes[item] = shape
        self.shapesToItems[shape] = item
        self.labelList.addItem(item)
        try:
            pass
            #print(self.filePath)
            #print(self.canvas.selectedShape)
        except:
            print('file path is none')
        #jcehn = 20180401 add imginfo
        self.addImgInfo(shape)
        self.shapesToBndWidgets[shape].boundingBoxInfoLayoutContainer.setVisible(True)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)

    def remLabel(self, shape):
        if shape is None:
            # print('rm empty label')
            return
        item = self.shapesToItems[shape]
        self.labelList.takeItem(self.labelList.row(item))
        self.remImgInfo(shape)
        del self.shapesToItems[shape]
        del self.itemsToShapes[item]

    def loadLabels(self, shapes):
        s = []
        for label, points, line_color, fill_color, difficult in shapes:
            shape = Shape(label=label)
            for x, y in points:
                shape.addPoint(QPointF(x, y))
            shape.difficult = difficult
            shape.close()
            s.append(shape)

            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generateColorByText(label)

            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generateColorByText(label)

            self.addLabel(shape)

        self.canvas.loadShapes(s)

    def saveLabels(self, annotationFilePath):
        annotationFilePath = ustr(annotationFilePath)
        if self.labelFile is None:
            self.labelFile = LabelFile()
            self.labelFile.verified = self.canvas.verified

        def format_shape(s):
            return dict(label=s.label,
                        line_color=s.line_color.getRgb(),
                        fill_color=s.fill_color.getRgb(),
                        points=[(p.x(), p.y()) for p in s.points],
                       # add chris
                        difficult = s.difficult)

        shapes = [format_shape(shape) for shape in self.canvas.shapes]

        obejcts = []
        for shape in self.canvas.shapes:
            try:
                obejcts.append(self.objects[shape])
            except Exception as e:
                pritn('Exception in convert objects in savePascal:', str(e))
        # Can add differrent annotation formats here
        try:
            if self.usingPascalVocFormat is True:
                print ('Img: ' + self.filePath + ' -> Its xml: ' + annotationFilePath)
                self.labelFile.savePascalVocFormat(annotationFilePath, shapes, self.filePath, self.imageData,
                                                   self.lineColor.getRgb(), self.fillColor.getRgb(),objects = obejcts, geoInfo = self.geoInfo)
                # delete xml file when there is no bounding box in the image
                try:
                    if self.noShapes():
                        os.remove(annotationFilePath)
                except:
                    print('no xml file to delete')
            else:
                self.labelFile.save(annotationFilePath, shapes, self.filePath, self.imageData,
                                    self.lineColor.getRgb(), self.fillColor.getRgb())
            return True
        except LabelFileError as e:
            self.errorMessage(u'Error saving label data', u'<b>%s</b>' % e)
            return False

    def copySelectedShape(self):
        self.addLabel(self.canvas.copySelectedShape())
        # fix copy and delete
        self.shapeSelectionChanged(True)

    def labelSelectionChanged(self):
        item = self.currentItem()
        if item and self.canvas.editing():
            self._noSelectionSlot = True
            self.canvas.selectShape(self.itemsToShapes[item])
            shape = self.itemsToShapes[item]
            #change checkbox status
            self.changeCheckBoxStatus(shape)
            self.loadThumbnail(shape)
            # Add Chris
            self.diffcButton.setChecked(shape.difficult)

    def changeCheckBoxStatus(self,shape):
        try:
            for s in self.shapesToBndWidgets:
                self.shapesToBndWidgets[s].checkBox.setCheckable(False)
                self.shapesToBndWidgets[s].checkBox.setChecked(False)
                p = self.shapesToBndWidgets[s].boundingBoxInfoLayoutContainer.palette()
                p.setColor(self.shapesToBndWidgets[s].boundingBoxInfoLayoutContainer.backgroundRole(), Qt.white)
                self.shapesToBndWidgets[s].boundingBoxInfoLayoutContainer.setPalette(p)

            self.shapesToBndWidgets[shape].checkBox.setCheckable(True)
            self.shapesToBndWidgets[shape].checkBox.setChecked(True)
            p = self.shapesToBndWidgets[shape].boundingBoxInfoLayoutContainer.palette()
            p.setColor(self.shapesToBndWidgets[shape].boundingBoxInfoLayoutContainer.backgroundRole(), Qt.darkGray)
            self.shapesToBndWidgets[shape].boundingBoxInfoLayoutContainer.setPalette(p)

        except Exception as e:
            print('Exception is :', str(e))
            print('selected the boundingbox failed')

    def labelItemChanged(self, item):
        shape = self.itemsToShapes[item]
        label = item.text()
        if label != shape.label:
            shape.label = item.text()
            shape.line_color = generateColorByText(shape.label)
            self.setDirty()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    # Callback functions:
    def newShape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        if not self.useDefaultLabelCheckbox.isChecked() or not self.defaultLabelTextLine.text():
            if len(self.labelHist) > 0:
                self.labelDialog = LabelDialog(
                    parent=self, listItem=self.labelHist)

            # Sync single class mode from PR#106
            if self.singleClassMode.isChecked() and self.lastLabel:
                text = self.lastLabel
            else:
                text = self.labelDialog.popUp(text=self.prevLabelText)
                self.lastLabel = text
        else:
            text = self.defaultLabelTextLine.text()

        # Add Chris
        self.diffcButton.setChecked(False)
        if text is not None:
            self.prevLabelText = text
            generate_color = generateColorByText(text)
            shape = self.canvas.setLastLabel(text, generate_color, generate_color)
            self.addLabel(shape)
            if self.beginner():  # Switch to edit mode.
                self.canvas.setEditing(True)
                self.actions.create.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.setDirty()

            if text not in self.labelHist:
                self.labelHist.append(text)
        else:
            # self.canvas.undoLastLine()
            self.canvas.resetAllLines()

    def scrollRequest(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)

    def zoomRequest(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scrollBars[Qt.Horizontal]
        v_bar = self.scrollBars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scrollArea.width()
        h = self.scrollArea.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta / (8 * 15)
        scale = 10
        self.addZoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.itemsToShapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def loadFile(self, filePath=None,updateWebbrowser = True):
        """Load the specified file, or the last opened file if None."""

        self.resetState()
        self.canvas.setEnabled(False)
        if filePath is None:
            filePath = self.settings.get(SETTING_FILENAME)

        # Make sure that filePath is a regular python string, rather than QString
        filePath = str(filePath)

        unicodeFilePath = ustr(filePath)

        # Tzutalin 20160906 : Add file list and dock to move faster
        # Highlight the file item
        if unicodeFilePath and self.fileListWidget.count() > 0:
            index = self.mImgList.index(unicodeFilePath)
            fileWidgetItem = self.fileListWidget.item(index)
            fileWidgetItem.setSelected(True)

        if unicodeFilePath and os.path.exists(unicodeFilePath):
            if LabelFile.isLabelFile(unicodeFilePath):
                try:
                    self.labelFile = LabelFile(unicodeFilePath)
                except LabelFileError as e:
                    self.errorMessage(u'Error opening file',
                                      (u"<p><b>%s</b></p>"
                                       u"<p>Make sure <i>%s</i> is a valid label file.")
                                      % (e, unicodeFilePath))
                    self.status("Error reading %s" % unicodeFilePath)
                    return False
                self.imageData = self.labelFile.imageData
                self.lineColor = QColor(*self.labelFile.lineColor)
                self.fillColor = QColor(*self.labelFile.fillColor)
            else:
                #print("not in labelfile")
                # Load image:
                # read data first and store for saving into label file.
                self.imageData = read(unicodeFilePath, None)
                self.labelFile = None

            # Jchen 20180315 Load image geoInfo

            try:
                self.geoInfo = get_lat_lon(get_exif_data(Image.open(unicodeFilePath)))  #self.geoInfo  = (lat,lon) or (lat,lon, alt)
                if updateWebbrowser:
                    #googleQueryUrl = 'https://www.google.com/maps/search/?api=1&query='
                    vtranMapUrl = 'https://vtrans.github.io/signs-data-viewer/?lon=-72.683117&lat=44.296882&zoomLevel=18'
                    imgUrl = 'https://vtrans.github.io/signs-data-viewer/?lon={:.6f}&lat={:.6f}&zoomLevel=18'.format(self.geoInfo[1],self.geoInfo[0])
                    self.webViewer.load(QUrl(imgUrl))
                    self.urlbar.setText(imgUrl)
                #print(imgUrl)
            except:
                print('loading img geoInfo failed.')


            image = QImage.fromData(self.imageData)
            if image.isNull():
                self.errorMessage(u'Error opening file',
                                  u"<p>Make sure <i>%s</i> is a valid image file." % unicodeFilePath)
                self.status("Error reading %s" % unicodeFilePath)
                return False
            self.status("Loaded %s" % os.path.basename(unicodeFilePath))
            self.image = image
            self.filePath = unicodeFilePath
            self.canvas.loadPixmap(QPixmap.fromImage(image))
            if self.labelFile:
                self.loadLabels(self.labelFile.shapes)
            self.setClean()
            self.canvas.setEnabled(True)
            self.adjustScale(initial=True)
            self.paintCanvas()
            self.addRecentFile(self.filePath)
            self.toggleActions(True)

            # Label xml file and show bound box according to its filename
            if self.usingPascalVocFormat is True:
                if self.defaultSaveDir is not None:
                    basename = os.path.basename(
                        os.path.splitext(self.filePath)[0]) + XML_EXT
                    xmlPath = os.path.join(self.defaultSaveDir, basename)
                    self.loadPascalXMLByFilename(xmlPath)
                else:
                    xmlPath = os.path.splitext(filePath)[0] + XML_EXT
                    if os.path.isfile(xmlPath):
                        self.loadPascalXMLByFilename(xmlPath)

                #Jchen = 20180316 add image info dock for bound box info
                xmlPath = os.path.splitext(filePath)[0] + XML_EXT
                shapes = self.canvas.shapes

                try:
                    signinfos = self.parseXML(xmlPath)
                    #print('signinfos:',len(signinfos),'shapes:',len(shapes))
                    for count in range(len(shapes)):
                        self.objects[shapes[count]] = signinfos[count]
                except:
                    print('load xml file to objects failed')
                    #print(self.objects[shapes[count]])

                self.loadImgInfo(shapes)

            self.setWindowTitle(__appname__ + ' ' + filePath)

            # Default : select last item if there is at least one item
            if self.labelList.count():
                self.labelList.setCurrentItem(self.labelList.item(self.labelList.count()-1))
                self.labelList.item(self.labelList.count()-1).setSelected(True)

            self.canvas.setFocus(True)

            return True
        return False

    # jchen  = 20180401 add imginfo btnbox funxtions
    def addImgInfo(self,shape):
        bndWidget = BoundingBoxWidget()
        self.shapesToBndWidgets[shape] = bndWidget
        self.bndWidgetsToShapes[bndWidget] = shape
        try:
            #print('find object')
            object = self.objects[shape]
        except:
            self.objects[shape] = {}

        self.imgInfoLayout.addWidget(bndWidget.boundingBoxInfoLayoutContainer)

        #bndWidget.setObjectName("BoundingBoxWidget_{}".format(count))
        try:
            with open('data/subclass.txt', 'r') as subclass:
                dropitems = subclass.readlines()
                for line in dropitems:
                    line = line.strip()
                    bndWidget.dropDownBoxs['sub'].addItem(line)

            pasteGeoButton = bndWidget.pasteButton
            pasteGeoButton.setObjectName('pasteGeo_'+str(self.bndNum))
            pasteGeoButton.clicked.connect(self.pasteGeo)

            self.pasteGeosToBndWidgets[pasteGeoButton.objectName()] = bndWidget

            pasteAllbutton = bndWidget.pasteAllButton
            pasteAllbutton.setObjectName('pasteAll_' + str(self.bndNum))
            pasteAllbutton.clicked.connect(self.pasteAll)

            self.pasteAllsToBndWidgets[pasteAllbutton.objectName()] = bndWidget

            QComboBoxSub = bndWidget.dropDownBoxs['sub']
            QComboBoxSub.setObjectName('QComboBoxSub_' + str(self.bndNum))
            try:
                QComboBoxSub.setCurrentText(self.objects[shape]['subclass'])
            except:
                pass
            self.QComboBoxSubsToBndWidgets[QComboBoxSub.objectName()] = bndWidget

            # create a completer with the strings in the column as model
            QComboBoxSub.setEditable(True)
            allStrings = [QComboBoxSub.itemText(i) for i in range(QComboBoxSub.count())]
            autoComplete = QCompleter(allStrings)
            QComboBoxSub.setCompleter(autoComplete)

            #add event function
            QComboBoxSub.currentTextChanged.connect(self.QComboBoxSubChanged)

            #show the thumbnail
            thumbnail = self.thumbnail
            try:
                pixmap = QPixmap('icons/thumbnails/{}.png'.format(self.objects[shape]['subclass']))
                pixmap.scaled(64,64, Qt.KeepAspectRatio)
                thumbnail.setPixmap(pixmap)
            except:
                thumbnail.setText('No thumbnail')
            self.createThumbnail.setVisible(True)
            self.thumbnail.setVisible(True)

            #add the checkbox checkfunntion
            # checkBox = bndWidget.checkBox
            # checkBox.setObjectName('checkBox_' + str(self.bndNum))
            # self.checkBoxesToBndWidgets[checkBox.objectName()] = bndWidget
            #
            # checkBox.stateChanged.connect(self.checkBoxStateChanged)

            #add the goto geo function

            self.bndNum += 1
        except Exception as e:
            print('Exception in addImgInfo:', str(e))
            print('load class failed')

        # partial(self.lineEditChanged, count)
        # Using image geoinfo as bounding box geoinfo.
        try:
            latText = self.objects[shape]['latitude']
            longText =  self.objects[shape]['longitude']
            bndWidget.labelLineEdits['lat'].setText('{:.7f}'.format(float(latText)))
            bndWidget.labelLineEdits['lon'].setText('{:.7f}'.format(float(longText)))
        except Exception as e:
            print('exception in loading geo info:',str(e))
            bndWidget.labelLineEdits['lat'].setText('{:.7f}'.format(self.geoInfo[0]))
            bndWidget.labelLineEdits['lon'].setText('{:.7f}'.format(self.geoInfo[1]))
        except:
            print('No Geoinfo')
        #bndWidget.numberOfBoundingBoxs.setText(str(count + 1))

    def remImgInfo(self,shape):
        if shape is None:
            return
        bndBoxWidget = self.shapesToBndWidgets[shape]
        bndBoxWidget.boundingBoxInfoLayoutContainer.setVisible(False)
        self.imgInfoLayout.removeWidget(bndBoxWidget.boundingBoxInfoLayoutContainer)
        del self.objects[shape]
        del self.shapesToBndWidgets[shape]
        del self.bndWidgetsToShapes[bndBoxWidget]

    # jchen = 20180329 add
    def loadImgInfo(self, shapes):
        # add the imageinfomation to imginfodock
        self.imgInfoLayout = QVBoxLayout()
        self.imgInfoLayout.setContentsMargins(0, 0, 0, 0)
        self.imgInfoLayout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.hLayout = QVBoxLayout()
        self.hLayout.setAlignment(Qt.AlignTop)
        self.hLayout.addWidget(self.createThumbnail)
        self.hLayout.addWidget(self.thumbnail)
        self.thumbnail.setVisible(False)
        self.createThumbnail.setVisible(False)
        self.wholeImgInfoLayout = QHBoxLayout()
        self.wholeImgInfoLayout.addLayout(self.imgInfoLayout)
        self.wholeImgInfoLayout.addLayout(self.hLayout)
        self.wholeImgInfoLayout.setAlignment(Qt.AlignTop)
        imgInfoListContainer = QWidget()
        imgInfoListContainer.setLayout(self.wholeImgInfoLayout)

        # jchen 0328 add Scroll function
        imgInfoScroll = QScrollArea()
        imgInfoScroll.setWidget(imgInfoListContainer)
        imgInfoScroll.setWidgetResizable(True)
        self.imgInfoScrollBars = {
            Qt.Vertical: imgInfoScroll.verticalScrollBar()
        }
        self.imgInfoScrollArea = imgInfoScroll
        self.imgInfodock.setWidget(self.imgInfoScrollArea)
        # self.imgInfo.clear()
        #self.imgXmlInfos = []

        # add the boundingBoxWidget children
        self.bndNum = 0 # count is len()
        for shape in shapes:
            self.addImgInfo(shape)


    def pasteGeo(self):
        clipboardText = QApplication.clipboard().text()
        pasteGeoName = self.sender().objectName()
        try:
            bndBoxWidget = self.pasteGeosToBndWidgets[pasteGeoName]
            shape = self.bndWidgetsToShapes[bndBoxWidget]
        except:
            return
        try:
            clipboardText = json.loads(clipboardText)
            self.objects[shape]['latitude'] = clipboardText['latitude']
            self.objects[shape]['longitude'] = clipboardText['longitude']
           #print('imgXmlInfos name:', self.imgXmlInfos[bndCount].objectName())
            bndBoxWidget.labelLineEdits['lat'].setText('{:.7f}'.format(clipboardText['latitude']))
            bndBoxWidget.labelLineEdits['lon'].setText('{:.7f}'.format(clipboardText['longitude']))
            self.setDirty()
        except Exception as e:
            print('Exception in pasteGeo:',str(e),'\n',clipboardText)
            pass

    def pasteAll(self):
        clipboardText = QApplication.clipboard().text()
        pasteAllName = self.sender().objectName()
        try:
            bndBoxWidget = self.pasteAllsToBndWidgets[pasteAllName]
            shape = self.bndWidgetsToShapes[bndBoxWidget]
            #print(shape)
        except:
            return
        try:
            clipboardText = json.loads(clipboardText)
            self.objects[shape]['latitude'] = clipboardText['latitude']
            self.objects[shape]['longitude'] = clipboardText['longitude']
            # print('imgXmlInfos name:', self.imgXmlInfos[bndCount].objectName())
            bndBoxWidget.labelLineEdits['lat'].setText('{:.7f}'.format(clipboardText['latitude']))
            bndBoxWidget.labelLineEdits['lon'].setText('{:.7f}'.format(clipboardText['longitude']))
            self.objects[shape]['subclass'] = clipboardText['MUTCDCode']
            self.objects[shape]['SignMainGeneralOID'] = clipboardText['SignMainGeneralOID']
            self.objects[shape]['ID'] = clipboardText['ID']
            self.objects[shape]['LaneDirection'] = clipboardText['LaneDirection']
            self.objects[shape]['Marker'] = clipboardText['Marker']
            self.objects[shape]['City'] = clipboardText['City']
            self.objects[shape]['County'] = clipboardText['County']
            self.objects[shape]['District'] = clipboardText['District']
            self.objects[shape]['STREETNAME'] = clipboardText['STREETNAME']
            self.objects[shape]['MUTCDCode'] = clipboardText['MUTCDCode']
            self.objects[shape]['Retired'] = clipboardText['Retired']
            self.objects[shape]['Replaced'] = clipboardText['Replaced']
            self.objects[shape]['SignAge'] = clipboardText['SignAge']
            self.objects[shape]['TWN_TID'] = clipboardText['TWN_TID']
            self.objects[shape]['TWN_MI'] = clipboardText['TWN_MI']
            self.objects[shape]['QCFLAG'] = clipboardText['QCFLAG']
            self.objects[shape]['MIN_TWN_FMI'] = clipboardText['MIN_TWN_FMI']
            self.objects[shape]['MAX_TWN_TMI'] = clipboardText['MAX_TWN_TMI']
            self.objects[shape]['SR_SID'] = clipboardText['SR_SID']
            self.objects[shape]['OFFSET'] = clipboardText['OFFSET']
            self.objects[shape]['PublishDate'] = clipboardText['PublishDate']
            #print(self.objects[shape])
            self.setDirty()
        except Exception as e:
            print('Exception in pasteAll:', str(e), '\n', clipboardText)
            pass
        try:
            bndBoxWidget.dropDownBoxs['sub'].setCurrentText(self.objects[shape]['subclass'])
        except:
            print('subclass show failed')


    #jchen = 20180402 new
    def QComboBoxSubChanged(self):
        QComboBoxSubName = self.sender().objectName()
        #print('in QComboBoxSubChanged')
        try:
            bndBoxWidget = self.QComboBoxSubsToBndWidgets[QComboBoxSubName]
            shape = self.bndWidgetsToShapes[bndBoxWidget]
        except:
            return
        try:
            subclassText = bndBoxWidget.dropDownBoxs['sub'].currentText()
            self.objects[shape]['subclass'] = subclassText
            #only the seleted bounding box can show the thumbnail
            if shape == self.canvas.selectedShape:
                self.loadThumbnail(shape)
                self.setDirty()
        except Exception as e:
            print('Exception in QComboBoxSubChanged:',str(e))

    def loadThumbnail(self,shape):
        try:
            pixmap = QPixmap('icons/thumbnails/{}.png'.format(self.objects[shape]['subclass']))
            pixmap.scaled(64, 64, Qt.KeepAspectRatio)
            self.thumbnail.setPixmap(pixmap)
        except:
            self.thumbnail.setText('No thumbnail')

    #checkbox state change function
    # def checkBoxStateChanged(self):
    #     checkBox = self.sender()
    #     checkBoxName = checkBox.objectName()
    #     print(checkBoxName)
    #     try:
    #         bndBoxWidget = self.checkBoxesToBndWidgets[checkBoxName]
    #         shape = self.bndWidgetsToShapes[bndBoxWidget]
    #     except:
    #         return
    #
    #     if checkBox.isChecked():
    #         print(checkBox.isChecked())
    #         #self.labelSelectionChanged()



    def parseXML(self, filepath):
        assert filepath.endswith(XML_EXT), "Unsupport file format"
        parser = etree.XMLParser(encoding=ENCODE_METHOD)
        xmltree = ElementTree.parse(filepath, parser=parser).getroot()

        signInfos = []
        for object_iter in xmltree.findall('object'):
            signInfo = {}
            try:
                location = object_iter.find("location")
                latitude = location.find('latitude').text
                signInfo['latitude'] = latitude
                longitude = location.find('longitude').text
                signInfo['longitude'] = longitude
                altitude = location.find('altitude').text
                signInfo['altitude'] = altitude
            except Exception as e:
                print('Exception in parseXml:',str(e))

            try:
                superclass = object_iter.find('superclass').text
                signInfo['superclass'] = superclass
            except:
                print('Exception in parseXml superclass')
            try:
                subclass = object_iter.find('subclass').text
                signInfo['subclass'] = subclass
            except:
                print('Exception in parseXml subclass')
            try:
                SignMainGeneralOID = object_iter.find('SignMainGeneralOID').text
                signInfo['SignMainGeneralOID'] = SignMainGeneralOID
            except:
                print('Exception in parseXml SignMainGeneralOID')
            try:
                ID = object_iter.find('ID').text
                signInfo['ID'] = ID
            except:
                print('Exception in parseXml ID')
            try:
                LaneDirection = object_iter.find('LaneDirection').text
                signInfo['LaneDirection'] = LaneDirection
            except:
                print('Exception in parseXml LaneDirection')
            try:
                Marker = object_iter.find('Marker').text
                signInfo['Marker'] = Marker
            except:
                print('Exception in parseXml Marker')
            try:
                City = object_iter.find('City').text
                signInfo['City'] = City
            except:
                print('Exception in parseXml City')
            try:
                County = object_iter.find('County').text
                signInfo['County'] = County
            except:
                print('Exception in parseXml County')
            try:
                District = object_iter.find('District').text
                signInfo['District'] = District
            except:
                print('Exception in parseXml District')
            try:
                STREETNAME = object_iter.find('STREETNAME').text
                signInfo['STREETNAME'] = STREETNAME
            except:
                print('Exception in parseXml STREETNAME')
            try:
                MUTCDCode = object_iter.find('MUTCDCode').text
                signInfo['MUTCDCode'] = MUTCDCode
            except:
                print('Exception in parseXml MUTCDCode')
            try:
                Retired = object_iter.find('Retired').text
                signInfo['Retired'] = Retired
            except:
                print('Exception in parseXml Retired')
            try:
                Replaced = object_iter.find('Replaced').text
                signInfo['Replaced'] = Replaced
            except:
                print('Exception in parseXml Replaced')
            try:
                SignAge = object_iter.find('SignAge').text
                signInfo['SignAge'] = SignAge
            except:
                print('Exception in parseXml SignAge')
            try:
                TWN_TID = object_iter.find('TWN_TID').text
                signInfo['TWN_TID'] = TWN_TID
            except:
                print('Exception in parseXml TWN_TID')
            try:
                TWN_MI = object_iter.find('TWN_MI').text
                signInfo['TWN_MI'] = TWN_MI
            except:
                print('Exception in parseXml TWN_MI')
            try:
                QCFLAG = object_iter.find('QCFLAG').text
                signInfo['QCFLAG'] = QCFLAG
            except:
                print('Exception in parseXml QCFLAG')
            try:
                MIN_TWN_FMI = object_iter.find('MIN_TWN_FMI').text
                signInfo['MIN_TWN_FMI'] = MIN_TWN_FMI
            except:
                print('Exception in parseXml MIN_TWN_FMI')
            try:
                MAX_TWN_TMI = object_iter.find('MAX_TWN_TMI').text
                signInfo['MAX_TWN_TMI'] = MAX_TWN_TMI
            except:
                print('Exception in parseXml MAX_TWN_TMI')
            try:
                SR_SID = object_iter.find('SR_SID').text
                signInfo['SR_SID'] = SR_SID
            except:
                print('Exception in parseXml SR_SID')
            try:
                OFFSET = object_iter.find('OFFSET').text
                signInfo['OFFSET'] = OFFSET
            except:
                print('Exception in parseXml OFFSET')
            try:
                PublishDate = object_iter.find('PublishDate').text
                signInfo['PublishDate'] = PublishDate
            except:
                print('Exception in parseXml PublishDate')
            signInfos.append(signInfo)
        return signInfos

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        settings = self.settings
        # If it loads images from dir, don't load it at the begining
        if self.dirname is None:
            settings[SETTING_FILENAME] = self.filePath if self.filePath else ''
        else:
            settings[SETTING_FILENAME] = ''

        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_LINE_COLOR] = self.lineColor
        settings[SETTING_FILL_COLOR] = self.fillColor
        settings[SETTING_RECENT_FILES] = self.recentFiles
        settings[SETTING_ADVANCE_MODE] = not self._beginner
        settings[SETTING_DOCK_GEOMETRY] = self.dock.saveGeometry()
        if self.defaultSaveDir and os.path.exists(self.defaultSaveDir):
            settings[SETTING_SAVE_DIR] = ustr(self.defaultSaveDir)
        else:
            settings[SETTING_SAVE_DIR] = ""

        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            settings[SETTING_LAST_OPEN_DIR] = self.lastOpenDir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ""

        settings[SETTING_AUTO_SAVE] = self.autoSaving.isChecked()
        settings[SETTING_SINGLE_CLASS] = self.singleClassMode.isChecked()
        #save setting
        print(self.saveLayout.isChecked())
        if self.saveLayout.isChecked():
            settings.save()
    ## User Dialogs ##

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = ['.jpeg', '.jpg', '.png', '.bmp']
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.join(root, file)
                    path = ustr(os.path.abspath(relativePath))
                    images.append(path)
        images.sort(key=lambda x: x.lower())
        return images

    def changeSavedirDialog(self, _value=False):
        if self.defaultSaveDir is not None:
            path = ustr(self.defaultSaveDir)
        else:
            path = '.'

        dirpath = ustr(QFileDialog.getExistingDirectory(self,
                                                       '%s - Save annotations to the directory' % __appname__, path,  QFileDialog.ShowDirsOnly
                                                       | QFileDialog.DontResolveSymlinks))

        if dirpath is not None and len(dirpath) > 1:
            self.defaultSaveDir = dirpath

        self.statusBar().showMessage('%s . Annotation will be saved to %s' %
                                     ('Change saved folder', self.defaultSaveDir))
        self.statusBar().show()

    def openAnnotationDialog(self, _value=False):
        if self.filePath is None:
            self.statusBar().showMessage('Please select image first')
            self.statusBar().show()
            return

        path = os.path.dirname(ustr(self.filePath))\
            if self.filePath else '.'
        if self.usingPascalVocFormat:
            filters = "Open Annotation XML file (%s)" % ' '.join(['*.xml'])
            filename = ustr(QFileDialog.getOpenFileName(self,'%s - Choose a xml file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]
            self.loadPascalXMLByFilename(filename)

    def openDirDialog(self, _value=False, dirpath=None):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else '.'
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = os.path.dirname(self.filePath) if self.filePath else '.'

        targetDirPath = ustr(QFileDialog.getExistingDirectory(self,
                                                     '%s - Open Directory' % __appname__, defaultOpenDirPath,
                                                     QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        self.importDirImages(targetDirPath)

    def importDirImages(self, dirpath):
        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.dirname = dirpath
        self.filePath = None
        self.fileListWidget.clear()
        self.mImgList = self.scanAllImages(dirpath)
        self.openNextImg()
        for imgPath in self.mImgList:
            item = QListWidgetItem(imgPath)
            self.fileListWidget.addItem(item)

    def verifyImg(self, _value=False):
        # Proceding next image without dialog if having any label
         if self.filePath is not None:
            try:
                self.labelFile.toggleVerify()
            except AttributeError:
                # If the labelling file does not exist yet, create if and
                # re-save it with the verified attribute.
                self.saveFile()
                self.labelFile.toggleVerify()

            self.canvas.verified = self.labelFile.verified
            self.paintCanvas()
            self.saveFile()
         print("out verify img")

    def openPrevImg(self, _value=False):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
            else:
                self.changeSavedirDialog()
                return

        if not self.mayContinue():
            return

        if len(self.mImgList) <= 0:
            return

        if self.filePath is None:
            return

        currIndex = self.mImgList.index(self.filePath)
        if currIndex - 1 >= 0:
            filename = self.mImgList[currIndex - 1]
            if filename:
                self.loadFile(filename)

    def openNextImg(self, _value=False):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
            else:
                self.changeSavedirDialog()
                return

        if not self.mayContinue():
            return

        if len(self.mImgList) <= 0:
            return

        filename = None
        if self.filePath is None:
            filename = self.mImgList[0]
        else:
            currIndex = self.mImgList.index(self.filePath)
            if currIndex + 1 < len(self.mImgList):
                filename = self.mImgList[currIndex + 1]

        if filename:
            self.loadFile(filename)

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = os.path.dirname(ustr(self.filePath)) if self.filePath else '.'
        formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        filters = "Image & Label files (%s)" % ' '.join(formats + ['*%s' % LabelFile.suffix])
        filename = QFileDialog.getOpenFileName(self, '%s - Choose Image or Label file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.loadFile(filename)


    def saveFile(self, _value=False):
        if self.defaultSaveDir is not None and len(ustr(self.defaultSaveDir)):
            if self.filePath:
                imgFileName = os.path.basename(self.filePath)
                savedFileName = os.path.splitext(imgFileName)[0] + XML_EXT
                savedPath = os.path.join(ustr(self.defaultSaveDir), savedFileName)
                self._saveFile(savedPath)
        else:
            imgFileDir = os.path.dirname(self.filePath)
            imgFileName = os.path.basename(self.filePath)
            savedFileName = os.path.splitext(imgFileName)[0] + XML_EXT
            savedPath = os.path.join(imgFileDir, savedFileName)
            self._saveFile(savedPath)
            # jchen27 = 03272018 comment the first time save dir check
            # self._saveFile(savedPath if self.labelFile
            #               else self.saveFileDialog())

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._saveFile(self.saveFileDialog())

    def saveFileDialog(self):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % LabelFile.suffix
        openDialogPath = self.currentPath()
        dlg = QFileDialog(self, caption, openDialogPath, filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filenameWithoutExtension = os.path.splitext(self.filePath)[0]
        dlg.selectFile(filenameWithoutExtension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            return dlg.selectedFiles()[0]
        print('choose cancel?')
        return ''

    def _saveFile(self, annotationFilePath):
        if annotationFilePath and self.saveLabels(annotationFilePath):
            self.setClean()
            self.statusBar().showMessage('Saved to  %s' % annotationFilePath)
            self.statusBar().show()

    def closeFile(self, _value=False):
        #print('in close file')
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def resetAll(self):
        self.settings.reset()
        self.close()
        proc = QProcess()
        proc.startDetached(os.path.abspath(__file__))

    def mayContinue(self):
        return not (self.dirty and not self.discardChangesDialog())

    def discardChangesDialog(self):
        yes, no = QMessageBox.Yes, QMessageBox.No
        msg = u'You have unsaved changes, proceed anyway?'
        return yes == QMessageBox.warning(self, u'Attention', msg, yes | no)

    def errorMessage(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(self.filePath) if self.filePath else '.'

    def chooseColor1(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.lineColor = color
            Shape.line_color = color
            self.canvas.setDrawingColor(color)
            self.canvas.update()
            self.setDirty()

    def deleteSelectedShape(self):
        self.remLabel(self.canvas.deleteSelected())
        self.setDirty()
        if self.noShapes():
            self.thumbnail.setVisible(False)
            self.createThumbnail.setVisible(False)
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)

    def chshapeLineColor(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selectedShape.line_color = color
            self.canvas.update()
            self.setDirty()

    def chshapeFillColor(self):
        color = self.colorDialog.getColor(self.fillColor, u'Choose fill color',
                                          default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selectedShape.fill_color = color
            self.canvas.update()
            self.setDirty()

    def copyShape(self):
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape)
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def loadPredefinedClasses(self, predefClassesFile):
        if os.path.exists(predefClassesFile) is True:
            with codecs.open(predefClassesFile, 'r', 'utf8') as f:
                for line in f:
                    line = line.strip()
                    if self.labelHist is None:
                        self.labelHist = [line]
                    else:
                        self.labelHist.append(line)

    def loadPascalXMLByFilename(self, xmlPath):
        if self.filePath is None:
            return
        if os.path.isfile(xmlPath) is False:
            return

        tVocParseReader = PascalVocReader(xmlPath)
        shapes = tVocParseReader.getShapes()
        self.loadLabels(shapes)
        self.canvas.verified = tVocParseReader.verified


def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default


def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("app"))
    # Tzutalin 201705+: Accept extra agruments to change predefined class file
    # Usage : labelImg.py image predefClassFile
    win = MainWindow(argv[1] if len(argv) >= 2 else None,
                     argv[2] if len(argv) >= 3 else os.path.join(
                         os.path.dirname(sys.argv[0]),
                         'data', 'predefined_classes.txt'))
    win.show()
    return app, win


def main(argv=[]):
    '''construct main app and run it'''
    app, _win = get_main_app(argv)
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main(sys.argv))

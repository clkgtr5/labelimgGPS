import sys
from PyQt5.QtWidgets import QComboBox, QApplication, QCompleter
from PyQt5.QtGui import QSortFilterProxyModel, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt

class ExtendedCombo( QComboBox ):
    def __init__( self,  parent = None):
        super( ExtendedCombo, self ).__init__( parent )

        self.setFocusPolicy( Qt.StrongFocus )
        self.setEditable( True )
        self.completer = QCompleter( self )

        # always show all completions
        self.completer.setCompletionMode( QCompleter.UnfilteredPopupCompletion )
        self.pFilterModel = QSortFilterProxyModel( self )
        self.pFilterModel.setFilterCaseSensitivity( Qt.CaseInsensitive )



        self.completer.setPopup( self.view() )


        self.setCompleter( self.completer )


        self.lineEdit().textEdited[unicode].connect( self.pFilterModel.setFilterFixedString )
        self.completer.activated.connect(self.setTextIfCompleterIsClicked)

    def setModel( self, model ):
        super(ExtendedCombo, self).setModel( model )
        self.pFilterModel.setSourceModel( model )
        self.completer.setModel(self.pFilterModel)

    def setModelColumn( self, column ):
        self.completer.setCompletionColumn( column )
        self.pFilterModel.setFilterKeyColumn( column )
        super(ExtendedCombo, self).setModelColumn( column )


    def view( self ):
        return self.completer.popup()

    def index( self ):
        return self.currentIndex()

    def setTextIfCompleterIsClicked(self, text):
      if text:
        index = self.findText(text)
        self.setCurrentIndex(index)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    model = QStandardItemModel()

    for i,word in enumerate( ['hola', 'adios', 'hello', 'good bye'] ):
        item = QStandardItem(word)
        model.setItem(i, 0, item)



    combo = ExtendedCombo()
    combo.setModel(model)
    combo.setModelColumn(0)

    combo.show()

    sys.exit(app.exec_())